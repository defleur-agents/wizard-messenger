// Actual retained Chromium RGBA, not invented expected screenshots. No browser/dependencies.
const {test}=require('node:test'),assert=require('node:assert/strict'),zlib=require('node:zlib');
const {interiorRegion,comparePixels,requireEqual}=require('./helpers/panel_pixel_oracle.cjs');
const recorded=require('./fixtures/recorded_account_corner_pixels.json');
const decode=d=>({w:d.w,h:d.h,p:zlib.inflateSync(Buffer.from(d.rgba_zlib_base64,'base64'))});
const a=decode(recorded.before),b=decode(recorded.over),roi=interiorRegion(recorded.provenance);
test('real recorded rounded corners reject old whole-box oracle but have zero interior differences',()=>{
  assert.deepEqual(roi,{x:2,y:14,width:8,height:32});
  assert.equal(comparePixels(a,b,{x:0,y:0,width:a.w,height:a.h}).changedPixels,170);
  assert.throws(()=>requireEqual(a,b,{x:0,y:0,width:a.w,height:a.h}),/panel interior changed/);
  assert.equal(requireEqual(a,b,roi).changedPixels,0);
  for(let y=0;y<a.h;y++)for(let x=0;x<a.w;x++){
    const n=(y*a.w+x)*4;
    if(!a.p.subarray(n,n+4).equals(b.p.subarray(n,n+4)))assert((x<12||x>=a.w-12)&&(y<12||y>=a.h-12),'recorded change not in rounded corner');
  }
});
test('even one unknown interior channel change fails stability and opacity equality',()=>{
  const changed={...a,p:Buffer.from(a.p)};changed.p[(roi.y*a.w+roi.x)*4]^=1;
  assert.equal(comparePixels(a,changed,roi).changedPixels,1);
  assert.throws(()=>requireEqual(a,changed,roi),/panel interior changed/);
});
test('empty, missing, unstable geometry and insufficient padding fail closed',()=>{
  assert.throws(()=>comparePixels(a,{...b,w:b.w-1},roi),/geometry/);
  assert.throws(()=>comparePixels(a,{...b,p:[]},roi),/unknown/);
  assert.throws(()=>comparePixels(a,b,{...roi,width:0}),/invalid/);
  assert.throws(()=>interiorRegion({...recorded.provenance,paddingLeft:4}),/padding/);
});
