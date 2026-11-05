// Fixed background-only padding ROI; never infer exclusions from changed pixels.
const assert = require('node:assert/strict');
function interiorRegion(c) {
  const length = (s, total) => { assert.match(s, /^\d+(?:\.\d+)?(?:px|%)$/); return parseFloat(s)*(s.endsWith('%')?total/100:1); };
  const radii = c.radii.map(s => { const a=s.split(/\s+/); return [length(a[0],c.rect.width),length(a[1]||a[0],c.rect.height)]; });
  // A side-padding strip below BOTH top corners and above BOTH bottom corners.
  const roi={x:Math.ceil(c.borderLeft)+2,y:Math.ceil(Math.max(radii[0][1],radii[1][1]))+2,width:8,height:32};
  assert(roi.x+roi.width <= c.paddingLeft-1, 'no background-only side padding ROI');
  assert(roi.y+roi.height < c.rect.height-Math.max(radii[2][1],radii[3][1])-2, 'no nonempty corner-free ROI');
  assert.equal(c.deviceScaleFactor,1,'ROI is in screenshot pixels');
  return roi;
}
function comparePixels(a,b,roi) {
  assert(a.w===b.w&&a.h===b.h,'capture geometry changed');
  assert(a.p.length===a.w*a.h*4&&b.p.length===b.w*b.h*4,'unknown pixel data');
  assert(roi.width>0&&roi.height>0&&[roi.x,roi.y,roi.width,roi.height].every(Number.isInteger),'invalid ROI');
  assert(roi.x>=0&&roi.y>=0&&roi.x+roi.width<=a.w&&roi.y+roi.height<=a.h,'ROI outside image');
  let changedPixels=0,wholeChangedPixels=0,maxChannelDelta=0;
  for(let y=0;y<a.h;y++)for(let x=0;x<a.w;x++){
    const n=(y*a.w+x)*4;let changed=false;
    for(let k=0;k<4;k++){const d=Math.abs(a.p[n+k]-b.p[n+k]);changed ||= d!==0;if(x>=roi.x&&x<roi.x+roi.width&&y>=roi.y&&y<roi.y+roi.height)maxChannelDelta=Math.max(maxChannelDelta,d);}
    if(changed){wholeChangedPixels++;if(x>=roi.x&&x<roi.x+roi.width&&y>=roi.y&&y<roi.y+roi.height)changedPixels++;}
  }
  return {changedPixels,wholeChangedPixels,maxChannelDelta,sameGeometry:true,width:a.w,height:a.h,roi};
}
function requireEqual(a,b,roi) {const d=comparePixels(a,b,roi);assert.equal(d.changedPixels,0,'panel interior changed: '+JSON.stringify(d));return d;}
module.exports={interiorRegion,comparePixels,requireEqual};
