// Pure transport regression; Canvas is stubbed, not claimed as native browser proof.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {createHash}=require('node:crypto'),{inflateSync,gzipSync}=require('node:zlib'),vm=require('node:vm');
const {decodeScreenshot,restorePixels}=require('./helpers/panel_pixel_transport.cjs');
const {comparePixels,requireEqual}=require('./helpers/panel_pixel_oracle.cjs');
// Actual retained PNG: heavy_5902e8de289244c2983823406da01b16 / 4d4880b4aa50 /
// evidence/account-layout/phone-enlarged-nebula-opacity-before.png.
const png=fs.readFileSync(require.resolve('./fixtures/retained_account_opacity_before.png'));
assert.equal(createHash('sha256').update(png).digest('hex'),'8e4dd50ad70050952e26dfafa9982c6b0512297d04e6b08660eb62eb2e321666');
function retainedPNG() {
  assert.equal(png.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  const w=png.readUInt32BE(16),h=png.readUInt32BE(20),idat=[];
  assert.deepEqual([...png.subarray(24,29)],[8,2,0,0,0],'this fixture is noninterlaced RGB8');
  for(let n=8;n<png.length;){const len=png.readUInt32BE(n),type=png.toString('ascii',n+4,n+8);if(type==='IDAT')idat.push(png.subarray(n+8,n+8+len));n+=len+12;}
  const data=inflateSync(Buffer.concat(idat)),stride=w*3,rgb=Buffer.alloc(stride*h),p=Buffer.alloc(w*h*4);
  assert.equal(data.length,(stride+1)*h);
  const paeth=(a,b,c)=>{const q=a+b-c,da=Math.abs(q-a),db=Math.abs(q-b),dc=Math.abs(q-c);return da<=db&&da<=dc?a:db<=dc?b:c;};
  for(let y=0;y<h;y++){
    const filter=data[y*(stride+1)];assert(filter<=4);
    for(let x=0;x<stride;x++){
      const n=y*stride+x,a=x>=3?rgb[n-3]:0,b=y?rgb[n-stride]:0,c=y&&x>=3?rgb[n-stride-3]:0;
      rgb[n]=(data[y*(stride+1)+x+1]+[0,a,b,Math.floor((a+b)/2),paeth(a,b,c)][filter])&255;
    }
  }
  for(let n=0;n<w*h;n++){rgb.copy(p,n*4,n*3,n*3+3);p[n*4+3]=255;}
  return {w,h,p};
}
const image=retainedPNG(),roi={x:2,y:14,width:8,height:32};
async function transfer(p=image.p) {
  let closed=false,draws=[],reads=[];
  const sandbox={Blob,Response,CompressionStream,Uint8Array,btoa,
    fetch:async url=>{assert.equal(url,'data:image/png;base64,'+png.toString('base64'));return {blob:async()=>new Blob([png])};},
    createImageBitmap:async blob=>{assert.deepEqual(Buffer.from(await blob.arrayBuffer()),png);return {width:image.w,height:image.h,close(){closed=true;}};},
    document:{createElement:tag=>{assert.equal(tag,'canvas');return {width:0,height:0,getContext:()=>({drawImage(...args){draws.push(args);},getImageData(...args){reads.push(args);return {data:new Uint8ClampedArray(p)};}}),toDataURL:()=> 'data:image/png;base64,cm9pLXN0dWI='};}}};
  // Execute exactly the self-contained function Playwright serializes.
  const decode=vm.runInNewContext('('+decodeScreenshot.toString()+')',sandbox);
  const wire=JSON.parse(JSON.stringify(await decode({base64:png.toString('base64'),roi})));
  assert(closed);assert.deepEqual(reads,[[0,0,image.w,image.h]]);
  assert.deepEqual(draws[1].slice(1),[roi.x,roi.y,roi.width,roi.height,0,0,roi.width,roi.height]);
  assert.equal(wire.png,'cm9pLXN0dWI=','crop data is forwarded separately, not used as raw pixels');
  assert.equal(wire.p,undefined,'full raw array must never cross the protocol');
  return {wire,result:restorePixels(wire)};
}
test('actual retained PNG full RGBA survives serialized native gzip transport byte for byte',async()=>{
  const {wire,result}=await transfer();
  assert.deepEqual(result,image);assert(Buffer.isBuffer(result.p));
  assert.equal(requireEqual(image,result,roi).changedPixels,0);
  const rawJSONBytes=Buffer.byteLength(JSON.stringify([...image.p])),wireBytes=Buffer.byteLength(JSON.stringify(wire));
  assert(wireBytes<rawJSONBytes/50,'transport must remove the full-RGBA JSON bottleneck');
  console.log(JSON.stringify({retainedPNGBytes:png.length,rgbaBytes:image.p.length,rawJSONBytes,wireBytes}));
});
test('one interior channel mutation survives compression and still fails the exact oracle',async()=>{
  const p=Buffer.from(image.p);p[(roi.y*image.w+roi.x)*4]^=1;
  const {result}=await transfer(p);assert.deepEqual(result.p,p);
  assert.equal(comparePixels(image,result,roi).changedPixels,1);
  assert.throws(()=>requireEqual(image,result,roi),/panel interior changed/);
});
test('corrupt, missing, short, oversized and invalid-geometry pixel payloads fail closed',()=>{
  const payload=p=>({w:image.w,h:image.h,compressedRGBA:gzipSync(p).toString('base64')});
  for(const p of [image.p.subarray(1),Buffer.concat([image.p,Buffer.from([0])])])assert.throws(()=>restorePixels(payload(p)));
  assert.throws(()=>restorePixels({...payload(image.p),compressedRGBA:'not-gzip'}));
  assert.throws(()=>restorePixels({w:image.w,h:image.h}));
  assert.throws(()=>restorePixels({...payload(image.p),w:0}),/geometry/);
  assert.throws(()=>restorePixels({...payload(image.p),h:NaN}),/geometry/);
});
