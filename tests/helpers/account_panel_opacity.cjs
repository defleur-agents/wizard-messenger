const assert=require('node:assert/strict'),fs=require('node:fs');
const {interiorRegion,comparePixels,requireEqual}=require('./panel_pixel_oracle.cjs');
// Browser fixture only: no production CSS or capture-difference-derived masks.
module.exports=async function opacity(target,page,prefix,geometry){
  const panel=target.locator('.u-sheet');
  await target.evaluate(async()=>{await document.fonts.ready;for(const a of document.querySelector('.u-sheet').getAnimations({subtree:true}))if(a.effect.getTiming().iterations!==Infinity)await a.finished;});
  const original=await panel.getAttribute('style');
  await panel.evaluate(e=>{e.style.position='relative';e.style.zIndex='1';e.style.willChange='transform';});
  const computed=await panel.evaluate(e=>{const c=getComputedStyle(e),r=e.getBoundingClientRect();return {background:c.backgroundColor,image:c.backgroundImage,opacity:c.opacity,rect:{x:r.x,y:r.y,width:r.width,height:r.height},radii:[c.borderTopLeftRadius,c.borderTopRightRadius,c.borderBottomRightRadius,c.borderBottomLeftRadius],paddingLeft:parseFloat(c.paddingLeft),borderLeft:parseFloat(c.borderLeftWidth),deviceScaleFactor:devicePixelRatio,animations:e.getAnimations({subtree:true}).map(a=>({playState:a.playState,currentTime:a.currentTime}))};});
  const roi=interiorRegion(computed);
  const exclusions=await panel.evaluate((e,roi)=>{const r=e.getBoundingClientRect(),box={left:r.left+roi.x,top:r.top+roi.y,right:r.left+roi.x+roi.width,bottom:r.top+roi.y+roi.height};const overlaps=b=>b.width>0&&b.height>0&&b.left<box.right&&b.right>box.left&&b.top<box.bottom&&b.bottom>box.top;const conflicts=[];for(const child of e.querySelectorAll('*'))if([...child.getClientRects()].some(overlaps))conflicts.push(child.tagName+'.'+child.className);const walk=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);while(walk.nextNode()){if(!walk.currentNode.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(walk.currentNode);if([...range.getClientRects()].some(overlaps))conflicts.push('text');}return {box,conflicts};},roi);
  fs.writeFileSync(prefix+'-computed.json',JSON.stringify({computed,geometry,roi,exclusions,reason:'fixed 8x32 background-only left-padding strip bounded by measured corner radii; rounded bounding-box corners are outside panel paint'},null,2));
  assert.deepEqual(exclusions.conflicts,[],'ROI must exclude all descendants/text/controls/images');
  assert.deepEqual(computed.animations,[],'unknown active animation');
  const decode=async(buffer,name)=>page.evaluate(async({base64,roi})=>{const i=await createImageBitmap(await(await fetch('data:image/png;base64,'+base64)).blob()),c=document.createElement('canvas');c.width=i.width;c.height=i.height;const x=c.getContext('2d');x.drawImage(i,0,0);const p=Array.from(x.getImageData(0,0,i.width,i.height).data),crop=document.createElement('canvas');crop.width=roi.width;crop.height=roi.height;crop.getContext('2d').drawImage(c,roi.x,roi.y,roi.width,roi.height,0,0,roi.width,roi.height);return {w:i.width,h:i.height,p,png:crop.toDataURL().split(',')[1]};},{base64:buffer.toString('base64'),roi}).then(d=>{fs.writeFileSync(prefix+'-'+name+'-roi.png',Buffer.from(d.png,'base64'));delete d.png;return d;});
  const shot=async name=>decode(await panel.screenshot({path:prefix+'-'+name+'.png',animations:'disabled',caret:'hide'}),name);
  const loud=async()=>{await panel.evaluate(e=>{const x=document.createElement('div');x.id='loud-behind';x.style='position:absolute;inset:0;color:red;background:repeating-linear-gradient(0deg,#f0f 0 6px,#0f0 6px 12px);font:60px serif;z-index:0;pointer-events:auto';x.textContent='LOUD BACKGROUND '.repeat(100);e.before(x);});const order=await panel.evaluate((e,roi)=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect(),probe=document.querySelector('#loud-behind');return {interior:document.elementsFromPoint(r.x+roi.x+4,r.y+roi.y+4).map(x=>x===e?'panel':x===probe?'probe':x.tagName),exposed:document.elementFromPoint(p.x+1,p.y+1)===probe};},roi);const probe=await decode(await target.locator('#loud-behind').screenshot({path:prefix+'-probe.png',animations:'disabled',caret:'hide'}),'probe');order.exposedPixel=probe.p.slice(0,4);fs.writeFileSync(prefix+'-probe.json',JSON.stringify(order,null,2));assert(order.interior.indexOf('panel')>=0&&order.interior.indexOf('probe')>order.interior.indexOf('panel')&&order.exposed,'probe directly below panel with exposed paint');assert(['255,0,255,255','0,255,0,255'].includes(order.exposedPixel.join(',')),'exposed probe pixel must be painted loud color');};
  const differenceImage=async(a,b,name)=>{const p=[];for(let y=roi.y;y<roi.y+roi.height;y++)for(let x=roi.x;x<roi.x+roi.width;x++){const n=(y*a.w+x)*4;p.push(Math.abs(a.p[n]-b.p[n]),Math.abs(a.p[n+1]-b.p[n+1]),Math.abs(a.p[n+2]-b.p[n+2]),255);}const png=await page.evaluate(({p,width,height})=>{const c=document.createElement('canvas');c.width=width;c.height=height;c.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(p),width,height),0,0);return c.toDataURL().split(',')[1];},{p,width:roi.width,height:roi.height});fs.writeFileSync(prefix+'-'+name+'-roi-difference.png',Buffer.from(png,'base64'));};
  const remove=()=>target.locator('#loud-behind').evaluate(e=>e.remove());
  try{
    const before=await shot('before'),unchanged=await shot('unchanged');
    await page.screenshot({path:prefix+'-full-before.png',animations:'disabled',caret:'hide'});
    await loud();const over=await shot('over'),overControl=await shot('over-control');
    await page.screenshot({path:prefix+'-full.png',animations:'disabled',caret:'hide'});
    await remove();const restored=await shot('restored');
    const differences={unchanged:comparePixels(before,unchanged,roi),overControl:comparePixels(over,overControl,roi),restored:comparePixels(before,restored,roi),opacity:comparePixels(before,over,roi)};
    await differenceImage(before,over,'opacity');
    fs.writeFileSync(prefix+'-diff.json',JSON.stringify({computed,geometry,roi,differences},null,2));
    for(const [a,b]of[[before,unchanged],[over,overControl],[before,restored],[before,over]])requireEqual(a,b,roi);
    assert.equal(Number(computed.opacity),1,'text panel opacity 1');
    await panel.evaluate(e=>e.style.setProperty('background','transparent','important'));
    const negativeBefore=await shot('negative-before'),negativeControl=await shot('negative-control');await loud();const negativeOver=await shot('negative-over'),negativeOverControl=await shot('negative-over-control');await remove();const negativeRestored=await shot('negative-restored');
    const negative=comparePixels(negativeBefore,negativeOver,roi);
    await differenceImage(negativeBefore,negativeOver,'negative');
    fs.writeFileSync(prefix+'-negative.json',JSON.stringify({roi,negative,controls:[comparePixels(negativeBefore,negativeControl,roi),comparePixels(negativeOver,negativeOverControl,roi),comparePixels(negativeBefore,negativeRestored,roi)]},null,2));
    for(const [a,b]of[[negativeBefore,negativeControl],[negativeOver,negativeOverControl],[negativeBefore,negativeRestored]])requireEqual(a,b,roi);
    assert.throws(()=>requireEqual(negativeBefore,negativeOver,roi),/panel interior changed/,'actual transparency must fail SAME ROI oracle');
  }finally{
    await target.locator('#loud-behind').evaluateAll(es=>es.forEach(e=>e.remove()));
    await panel.evaluate((e,original)=>original===null?e.removeAttribute('style'):e.setAttribute('style',original),original);
  }
};
