/* James: mic must show its take immediately and never hide a running recorder.
 * James (31 Oct 2026, Samsung SM-S938B): a start that never answers must hand the composer back, not sit on
 * "Stopping…" forever with the mic disabled.
 * Exact production composer, isolated synthetic dependencies; no contacts/network.
 * MESSENGER_SOURCE=<old unified.js> proves the hung-start cases fail before the fix. */
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const source=fs.readFileSync(process.env.MESSENGER_SOURCE||path.join(__dirname,'../static/unified.js'),'utf8');
const composer=source.slice(source.indexOf('  function composer(id, p) {'),source.indexOf('  // WebM (Matroska)'));
const fixture=`
window.view={}; const s={drafts:{},person:'synthetic'},localAudio=new Map();
const voiceTapSession=Math.random().toString(36),voiceKept=new Map(),voiceQueued=new Set();let voiceRecoveryWork=null;
const node=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e};
const iconButton=(icon,label,fn,cls)=>{const e=node('button',cls,label);e.type='button';e.setAttribute('aria-label',label);e.onclick=fn;return e;};
const button=(text,fn,cls)=>{const e=node('button',cls,text);e.type='button';e.onclick=fn;return e;};
const netLabel=n=>n,netBadge=()=>node('span'),bridged=n=>['telegram','whatsapp','signal'].includes(n),actionMenu=()=>{},serverDraft=()=>null,uid=()=>Math.random().toString(36).slice(2),preparePhoto=async f=>({blob:f}),editMsg=()=>{},reviewSend=()=>{};
const cap=x=>x,reviewedOf=()=>false,hold=()=>{},error=e=>{document.querySelector('#hidden-error').textContent=e.message;},toast=()=>{},fmtDur=ms=>'0:'+Math.floor(ms/1000),queueSend=(id,msg)=>{window.sent={id,take:msg.voice.take};WizardApp.capture.ack(msg.voice.take);},saveDrafts=()=>{},nameOf=()=>'',snippet=()=>'',call=async()=>({});
${composer}
window.rebuild=()=>{document.querySelector('#root').replaceChildren(composer('synthetic',{identities:[{id:'tg-fixture',network:'telegram',label:'Synthetic'}]}));}; rebuild();`;
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM});try{
const p=await browser.newPage({viewport:{width:390,height:844}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
// Plain-audio (PCM WAV) capture on a browser without AudioEncoder, like the Mac app. capturedMs is what the shared
// recorder really saved; the clock keeps running regardless.
async function setup(capturedMs, wallMs){
 await p.setContent('<div id="root"></div><p id="hidden-error" hidden></p>');
 await p.evaluate(([capturedMs,wallMs])=>{delete window.AudioEncoder;const real=window.MediaRecorder?.isTypeSupported?.bind(MediaRecorder);MediaRecorder.isTypeSupported=m=>!/webm/.test(m)&&!!real?.(m);window.calls={start:0,ack:0,opts:null};window.sent=null;window.active=null;const t0=Date.now()-wallMs;
  const wav=ms=>new Blob([new Uint8Array(44+ms*32)],{type:'audio/wav'});
  window.session={id:'take-1',onLevel:()=>()=>{},onWarn:()=>()=>{},getInfo:()=>({startedAt:t0,durationMs:capturedMs}),cancel:async()=>{active=null;},
   stop:async()=>{active=null;return{id:'take-1',mime:'audio/wav',durationMs:capturedMs,meta:{purpose:'messenger-voice',person:'synthetic'},blob:wav(capturedMs)};}};
  window.WizardApp={update:{hold:()=>({release(){}})},capture:{capabilities:()=>({pcm:true}),current:()=>active?{id:active,appId:'messenger',active:true,recording:true,phase:'recording',meta:{}}:null,
   attach:async()=>null,ack:async()=>{calls.ack++;},pending:async()=>[],settle:async()=>[],start:async opts=>{calls.start++;calls.opts=opts;active='take-1';return session;}}};
 },[capturedMs,wallMs]);await p.evaluate(fixture);
}
// 1. A clipped take (7 s of a 2-minute recording) is not sent; it is kept with an honest notice.
await setup(7000,120000);await p.getByRole('button',{name:'Record voice message'}).click();
await p.getByRole('button',{name:'Send voice message'}).waitFor();
assert.equal(await p.evaluate(()=>calls.opts.pcm),true,'Mac-like browser records plain audio');
await p.locator('.u-voice-notice').waitFor({timeout:3000});
assert.match(await p.locator('.u-voice-notice').innerText(),/stopped reaching Wizard/,'stall shown while recording');
await p.getByRole('button',{name:'Send voice message'}).click();
await p.locator('.u-unsent-voice').waitFor();
assert.equal(await p.evaluate(()=>window.sent),null,'clipped take not sent');
assert.equal(await p.evaluate(()=>calls.ack),0,'clipped take kept in custody');
assert.match(await p.locator('.u-voice-notice').innerText(),/Only 0:0?7 of your (2:0\d|0:12\d) recording reached Wizard, so it was not sent/);
await p.locator('.u-voice-keep-send').click();
assert.equal(await p.evaluate(()=>window.sent?.take),'take-1','owner can still send it');
console.log('PASS clipped take kept, notice honest, Send still possible');
// 2. A complete take is sent as usual, with no notice.
await setup(5000,5000);await p.getByRole('button',{name:'Record voice message'}).click();
await p.getByRole('button',{name:'Send voice message'}).waitFor();await p.waitForTimeout(1300);
assert.equal(await p.locator('.u-voice-notice').isVisible(),false,'no stall notice for a healthy take');
await p.getByRole('button',{name:'Send voice message'}).click();
await p.waitForFunction(()=>window.sent);
console.log('PASS complete take sent');
// 3. A browser that records WebM (the Mac app) uses its own recorder, not the plain-audio path that stops when hidden.
await setup(5000,5000);await p.evaluate(()=>{MediaRecorder.isTypeSupported=m=>/webm/.test(m);});
await p.getByRole('button',{name:'Record voice message'}).click();await p.getByRole('button',{name:'Send voice message'}).waitFor();
assert.equal(await p.evaluate(()=>calls.opts.pcm),undefined,'WebM-capable browser does not use plain audio');
console.log('PASS WebM browser keeps its own recorder');
assert.deepEqual(errors,[]);console.log('ALL PASS voice_capture_guard_browser');
}finally{await browser.close();}})().catch(e=>{console.error('FAIL',e.message);process.exit(1);});
