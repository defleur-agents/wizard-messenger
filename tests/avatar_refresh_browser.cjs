// Forum only. Real hosted client + source view; ALL accounts/messages/identities are SYNTHETIC.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
if(!process.cwd().startsWith('/srv/work/')) throw Error('Forum /srv/work only');
const out=path.resolve(process.argv[2]),shell=process.env.SHELL_DIR,staticDir=path.resolve(process.env.STATIC_DIR||path.join(__dirname,'../static'));fs.mkdirSync(out,{recursive:true});
// Reuse LINE's hosted Appearance fixture, not hand-built colour tokens.
assert(fs.existsSync(path.join(shell,'core/skins.js')), 'Pinned real skin source required');
// Same palette extraction/real appearance host as the passing LINE fixture.
const vm=require('node:vm'),src=fs.readFileSync(path.join(shell,'core/skins.js'),'utf8');
const table=src.slice(src.indexOf('  const SKINS = ['),src.indexOf('  // Each skin'));
const palettes=vm.runInNewContext('const T=o=>o;'+table+';SKINS').filter(s=>['nebula','signal'].includes(s.id)).map(s=>({id:s.id,t:s.t}));
assert.equal(palettes.length,2);
const host=`<!doctype html><html data-skin="nebula"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/wizard-os-home/core/skins.css"><script>window.WizCore={apps:()=>({APPS:[{url:'/app/'}]})};window.setFixtureSkin=id=>{const s=JSON.parse(atob('${Buffer.from(JSON.stringify(palettes)).toString('base64')}')).find(s=>s.id===id);for(const[k,v]of Object.entries(s.t))document.documentElement.style.setProperty('--'+k,v);document.documentElement.dataset.skin=id;window.WizAppearance?.sync()};setFixtureSkin('nebula')</script><script src="/wizard-os-home/core/appearance-host.js" defer></script><style>html,body{margin:0;height:100%;background:var(--bg)}.win,iframe{width:100%;height:100%;border:0}</style></head><body><div class="st-embed win"><iframe src="/app/" title="Synthetic group"></iframe></div></body></html>`;
const {origin,createFixture}=require('./helpers/group_features_fixture.cjs');
const types={'.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.html':'text/html'};
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE}),results=[];
 try {for(const profile of [{name:'desktop',viewport:{width:1280,height:860}},{name:'phone',viewport:{width:390,height:844},isMobile:true,hasTouch:true}]){
  const ctx=await browser.newContext({...profile,deviceScaleFactor:1,reducedMotion:'reduce'}),page=await ctx.newPage(),fixture=createFixture(),errors=[],unmatched=[];
  const photo={...fixture.person,id:'photo-synthetic',display_name:'Photo Example',kind:'person',avatar:'fixture-v1',unread:0,identities:fixture.person.identities.map(i=>({...i,kind:'person'}))};
  const noPhoto={...photo,id:'initials-synthetic',display_name:'Initials Example',avatar:null};fixture.person.avatar='group-fixture-v1';
  fixture.routes['/api/unified/people']={people:[photo,noPhoto],seq:1};fixture.routes['/api/unified/groups']={groups:[fixture.person],seq:1};fixture.routes['/api/unified/connectors']={providers:[]};
  for(const p of [photo,noPhoto]){fixture.routes['/api/unified/people/'+p.id]={person:p,messages:[],has_more:false};fixture.routes['/api/unified/people/'+p.id+'/read']={ok:true};}
  const png=Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#205872"/><circle cx="32" cy="23" r="12" fill="#e5c49b"/><path d="M10 64v-8a22 22 0 0 1 44 0v8" fill="#ed925b"/></svg>');
  let requests=0;
  page.on('pageerror',e=>errors.push(e.stack||e.message));
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url()),p=u.pathname;
   if(u.origin!==origin){unmatched.push(u.origin);return route.abort();}
   if(p==='/')return route.fulfill({body:host,contentType:'text/html'});
   if(p.startsWith('/wizard-os-home/')){const file=path.join(shell,p.slice('/wizard-os-home/'.length));return route.fulfill({path:file,contentType:types[path.extname(file)]||'text/plain'});}
   if(p==='/app/')return route.fulfill({path:path.join(staticDir,'index.html'),contentType:'text/html'});
   if(p.endsWith('/avatar')){requests++;await new Promise(r=>setTimeout(r,100));return route.fulfill({body:png,contentType:'image/svg+xml'});}
   if(!p.includes('/api/')){const name=p.startsWith('/app/')?p.slice(5):p.slice(1),file=path.join(staticDir,!fs.existsSync(path.join(staticDir,name))&&['favicon.svg','icon-192.png'].includes(name)?'../'+name:name);if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file,contentType:types[path.extname(file)]||'application/octet-stream'});unmatched.push(p);return route.fulfill({status:404,body:''});}
   if(p.endsWith('/api/unified/updates'))return; // Held synthetic change feed; driver repaints via the real filter and Back/open handlers.
   const answer=fixture.reply(req.url(),req.method(),req.postData()?req.postDataJSON():undefined);
   if(answer===null){unmatched.push(req.method()+' '+p);return route.fulfill({status:501,json:{ok:false,error:{code:'fixture_route_missing'}}});}
   return route.fulfill({json:answer});
  });
  try {
   await page.goto(origin+'/');const f=page.frameLocator('iframe');await f.locator('.u-person[data-pid="photo-synthetic"] img').waitFor();
   await f.locator('.u-person[data-pid="photo-synthetic"] img').evaluate(img=>img.decode());
   await f.locator('.u-person[data-pid="synthetic-group"] img').evaluate(img=>img.decode());
   await f.locator('body').evaluate(()=>{
    window.__avatarFrames={violations:[],frames:0,known:new Map(),nodes:new Map(),replaced:0};
    function sample(){const s=window.__avatarFrames;s.frames++;
     for(const el of document.querySelectorAll('.u-person .u-avatar,.u-thread-head .u-avatar')){
      const rect=el.getBoundingClientRect();if(!rect.width||!rect.height)continue;
      const pid=el.closest('.u-person')?.dataset.pid,key=pid||'header',img=el.querySelector('img'),url=img?.dataset.src;
      if(pid==='initials-synthetic'){if(img||el.textContent!=='IE')s.violations.push({key,reason:'no-photo fallback changed'});continue;}
      if(!img)continue;
      const ready=!img.hidden&&img.complete&&img.naturalWidth>0;
      if(s.known.get(key)===url&&!ready)s.violations.push({key,reason:'initials frame after photo loaded',frame:s.frames});
      if(s.nodes.has(key)&&s.known.get(key)===url&&s.nodes.get(key)!==img)s.replaced++;
      if(ready){s.known.set(key,url);s.nodes.set(key,img);}
     }
     requestAnimationFrame(sample);
    }sample();
   });
   for(const skin of ['nebula','signal']){
    await page.evaluate(s=>setFixtureSkin(s),skin);
    for(let i=0;i<10;i++){await f.locator('.u-chip[data-filter="all"]').click();await page.waitForTimeout(130);}
    assert.equal(await f.locator('.u-person[data-pid="initials-synthetic"] .u-avatar img').count(),0);
    await page.screenshot({path:path.join(out,`${profile.name}-${skin}-list.png`)});
    await f.locator('.u-person[data-pid="photo-synthetic"]').click();
    await f.locator('.u-thread-head img').waitFor();await f.locator('.u-thread-head img').evaluate(img=>img.decode());await page.waitForTimeout(30);
    for(let i=0;i<10;i++){
     if(profile.name==='desktop')await f.locator('.u-close').click();else await f.locator('.u-back').click();
     await f.locator('.u-person[data-pid="photo-synthetic"]').click();await page.waitForTimeout(130);
    }
    await page.screenshot({path:path.join(out,`${profile.name}-${skin}-thread.png`)});
    if(profile.name==='desktop')await f.locator('.u-close').click();else await f.locator('.u-back').click();
   }
   const sampled=await f.locator('body').evaluate(()=>{const s=window.__avatarFrames;return {frames:s.frames,violations:s.violations.slice(0,100),violationCount:s.violations.length,replaced:s.replaced};});
   results.push({profile:profile.name,requests,listRefreshes:20,threadRefreshes:20,...sampled,errors,unmatched});
  }catch(e){await page.screenshot({path:path.join(out,profile.name+'-failure.png')});throw e;}finally{await ctx.close();}
 }
 const pass=results.every(r=>!r.violationCount&&!r.replaced&&!r.errors.length&&!r.unmatched.length);
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({pass,syntheticOnly:true,realSharedAppearance:true,installedAppProven:false,results},null,2));console.log(JSON.stringify({pass,results},null,2));assert(pass,'avatar refresh regressed; see result.json');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
