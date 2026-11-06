const assert=require('node:assert/strict'),{gunzipSync}=require('node:zlib');
// Serialized by Playwright: keep this function self-contained and lossless.
async function decodeScreenshot({base64,roi}) {
  const i=await createImageBitmap(await(await fetch('data:image/png;base64,'+base64)).blob());
  const c=document.createElement('canvas');c.width=i.width;c.height=i.height;
  const x=c.getContext('2d');x.drawImage(i,0,0);
  const raw=x.getImageData(0,0,i.width,i.height).data;
  const compressed=new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
  let binary='';
  for(let n=0;n<compressed.length;n+=32768)binary+=String.fromCharCode(...compressed.subarray(n,n+32768));
  const crop=document.createElement('canvas');crop.width=roi.width;crop.height=roi.height;
  crop.getContext('2d').drawImage(c,roi.x,roi.y,roi.width,roi.height,0,0,roi.width,roi.height);
  i.close();
  return {w:c.width,h:c.height,compressedRGBA:btoa(binary),png:crop.toDataURL().split(',')[1]};
}
function restorePixels({w,h,compressedRGBA}) {
  assert(Number.isSafeInteger(w)&&w>0&&Number.isSafeInteger(h)&&h>0&&Number.isSafeInteger(w*h*4),'unknown capture geometry');
  const p=gunzipSync(Buffer.from(compressedRGBA,'base64'),{maxOutputLength:w*h*4});
  assert.equal(p.length,w*h*4,'unknown pixel data');
  return {w,h,p};
}
module.exports={decodeScreenshot,restorePixels};
