'use strict';
// New canonical frame/SDK acceptance, NOT a re-run of accepted source/fake-host scenes.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium,devices}=require(process.env.PLAYWRIGHT_MODULE),{PNG}=require('pngjs');
const L=require(path.join(process.env.MESSENGER_STATIC_DIR,'app.js'));
const OUT=path.resolve(process.argv[2]),ORIGIN=process.argv[3];fs.mkdirSync(OUT,{recursive:true});
const R={pass:false,scope:'actual installed shell archive + actual image-extracted static + real shared SDK; synthetic HTTP data only',runs:[],staticHashes:{},sdkHashes:{},prohibited:[]};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const names=['Ana Souza','Ben Okafor','Chloe Martin','Dev Patel','Elena Rossi','Farid Haddad','Grace Lee','Hiro Sato','Ines Duarte','Jonas Berg','Kira Novak','Liam Walsh','Maya Cohen','Nico Ferraro','Olga Petrova','Pablo Ruiz','Quinn Adler','Rosa Lima','Sam Turner','Tara Singh','Umar Khan','Vera Lind','Wes Carter','Xia Wang','Yusuf Demir','Zoe Hart','Arjun Rao','Bea Klein','Caio Prado','Dana Wolfe'];
const frames=frame=>frame.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
const difference=(a,b)=>{a=PNG.sync.read(a);b=PNG.sync.read(b);assert.equal(a.width,b.width);assert.equal(a.height,b.height);let n=0;for(let i=0;i<a.data.length;i+=4)if(!a.data.subarray(i,i+4).equals(b.data.subarray(i,i+4)))n++;return n;};
async function opacity(page,frame,label){
 const panel=frame.locator('#u-overlay .u-sheet, #u-overlay .u-menu').first();await panel.waitFor();
 const box=await panel.boundingBox();assert(box&&box.width>100&&box.height>100);
 await frame.evaluate(async()=>{await document.fonts.ready;await Promise.all(document.querySelector('#u-overlay').getAnimations({subtree:true}).map(a=>a.finished.catch(()=>{})));});
 const clip={x:Math.ceil(box.x)+20,y:Math.ceil(box.y)+45,width:Math.floor(box.width)-40,height:Math.min(100,Math.floor(box.height)-80)};
 await frame.evaluate(()=>{const e=document.createElement('div');e.id='qa-canary';Object.assign(e.style,{position:'fixed',inset:'0',zIndex:'999',background:'magenta',color:'lime',fontSize:'32px',pointerEvents:'none'});e.textContent='LOUD SYNTHETIC TEXT '.repeat(200);document.body.append(e);const o=document.querySelector('#u-overlay');o.dataset.qaZ=o.style.zIndex;o.style.zIndex='1000';});
 await frames(frame);const a=await page.screenshot({clip});await frame.locator('#qa-canary').evaluate(e=>e.style.visibility='hidden');await frames(frame);const b=await page.screenshot({clip});
 assert.equal(difference(a,b),0,'floating text panel lets background through '+label);
 const css=await panel.evaluate(e=>{const s=e.getAttribute('style');e.style.setProperty('background','transparent','important');e.style.setProperty('background-image','none','important');return s;});
 await frame.locator('#qa-canary').evaluate(e=>e.style.visibility='visible');await frames(frame);const c=await page.screenshot({clip});await frame.locator('#qa-canary').evaluate(e=>e.style.visibility='hidden');await frames(frame);const d=await page.screenshot({clip});
 assert(difference(c,d)>0,'opacity negative control did not discriminate');await panel.evaluate((e,s)=>s===null?e.removeAttribute('style'):e.setAttribute('style',s),css);
 await frame.evaluate(()=>{document.querySelector('#qa-canary').remove();const o=document.querySelector('#u-overlay');o.style.zIndex=o.dataset.qaZ;delete o.dataset.qaZ;});
 fs.writeFileSync(path.join(OUT,label+'-opaque.png'),b);return {pass:true,negativeControl:true};
}
function fixture(){
 const now=Date.now(),minute=60000,nets=['whatsapp','telegram','signal','instagram','line'];
 const people=names.map((n,i)=>({id:'p'+i,display_name:n,identities:[{id:'p'+i+'-i',network:nets[i%5],kind:'person',label:n}],labels:[],unread:0,muted:false,low_priority:false,last:{text:'Synthetic message '+i,timestamp:i===20?now:now-(i+1)*9*minute,outgoing:false},language:'',peer_read_ts:0}));
 const threads={};for(const p of people)threads[p.id]=Array.from({length:8},(_,k)=>({id:p.id+'-m'+k,sender:p.display_name,outgoing:false,original:'Synthetic text '+k,translated:'',timestamp:now-(40-k)*minute,identity_id:p.identities[0].id,network:p.identities[0].network,reactions:[],msgtype:'m.text'}));
 people.push({id:'p-status',display_name:'WhatsApp Status Broadcast',identities:[{id:'p-status-i',network:'whatsapp',kind:'person',label:'WhatsApp Status Broadcast'}],labels:[],unread:0,last:{text:'',unavailable:'status',timestamp:now-1000*minute,outgoing:false}});
 threads['p-status']=[{id:'status-native',sender:'Synthetic Status Sender',outgoing:false,original:'',timestamp:now-1000*minute,identity_id:'p-status-i',network:'whatsapp',reactions:[],msgtype:'m.notice',unavailable:'status'}];
 threads.p0=[{...threads.p0[0],id:'ordinary-wait',original:'',network:'whatsapp',unavailable:'waiting',msgtype:'m.notice'}];
 const drafts=[],updates=[];let draftSeq=0;const ownKey='11'.repeat(32),peer='22'.repeat(32),own={account_id:ownKey,npub:L.encodePublic(ownKey),display_name:'Synthetic Owner'},dm={group_id:'ab'.repeat(32),members:[{member_id:peer,display_name:'Synthetic Private Alice'},{member_id:ownKey}]};
 const priv=[{message_id:'e'.repeat(64),group_id:dm.group_id,author:peer,direction:'received',text:'Synthetic encrypted chat fixture',created_at:now/1000}];
 async function route(route){
  const req=route.request(),u=new URL(req.url());let p=u.pathname.replace(/^\/messenger\//,'');if(!p.startsWith('api/'))return route.continue();
  const ok=result=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,result})});const body=()=>JSON.parse(req.postData()||'{}');
  if(p==='api/view/session')return ok({authenticated:true,csrf_token:'synthetic-only'});
  if(p==='api/status')return ok({state:'ready',account_configured:true});
  if(p==='api/identity')return ok({identity:own});
  if(p==='api/contacts')return ok({contacts:[]});if(p==='api/invites')return ok({invites:[]});if(p==='api/dms')return ok({dms:[dm]});
  if(p.startsWith('api/dms/')&&p.endsWith('/messages'))return ok({messages:priv,next_cursor:null});
  if(p==='api/unified/people')return ok({people,seq:5});if(p==='api/unified/groups')return ok({groups:[],seq:5});
  if(p==='api/unified/directory')return ok({people:people.map(({id,display_name,identities})=>({id,display_name,identities})),groups:[]});
  const thread=/^api\/unified\/people\/([^/]+)$/.exec(p);
  if(thread){const person=people.find(x=>x.id===decodeURIComponent(thread[1]));if(req.method()==='POST'){Object.assign(person,body());return ok(person);}return ok({person,messages:threads[person.id],has_more:false,next_cursor:null,seq:5,typing:[]});}
  if(p.endsWith('/read'))return ok({});
  if(p==='api/drafts'&&req.method()==='GET')return ok({drafts});
  if(p==='api/drafts'&&req.method()==='POST'){const b=body(),d={id:'d'+(++draftSeq),person_id:b.person_id,identity_id:b.identity_id,text:b.text||'',revision:1,state:'draft',attachments:[],created_by:{id:'owner',name:'You'},updated:Date.now()};drafts.push(d);return ok({draft:d});}
  const dr=/^api\/drafts\/([^/]+)$/.exec(p);if(dr){const d=drafts.find(x=>x.id===dr[1]);if(req.method()==='DELETE'){drafts.splice(drafts.indexOf(d),1);return ok({});}if(req.method()==='POST'){Object.assign(d,body(),{revision:d.revision+1,updated:Date.now()});return ok({draft:d});}return ok({draft:d});}
  if(p==='api/unified/updates'){await new Promise(r=>setTimeout(r,150));return ok(updates.shift()||{seq:5});}
  if(['api/unified/status','api/unified/accounts','api/unified/providers','api/connectors','api/connectors/status','api/providers','api/agents','api/agent-keys','api/translation/status','api/remote/status'].includes(p))return ok({accounts:[],providers:[],agents:[],enabled:false});
  // No writes to any real backend, no unknown API/stream forwarding.
  if(req.method()!=='GET'){R.prohibited.push(req.method()+' '+p);return route.fulfill({status:403,body:'fixture refuses unknown write'});}
  return ok({});
 }
 return {route,people,threads,drafts,updates};
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const [shell,entry,options] of [['desktop','desktop.html?open=messenger',{viewport:{width:1280,height:900}}],['phone','index.html?shell=phone&open=messenger',{...devices['Pixel 7']}]]){
   const ctx=await browser.newContext(options),page=await ctx.newPage(),data=fixture(),errors=[],bodies=[];const row={shell,skins:[],errors,screenshots:[]};R.runs.push(row);
   try{
    await ctx.route('**/*',route=>{const u=new URL(route.request().url());if(u.protocol==='data:'||u.protocol==='blob:')return route.continue();if(u.origin!==ORIGIN){R.prohibited.push(u.origin+u.pathname);return route.abort();}if(u.pathname.startsWith('/messenger/api/'))return data.route(route);return route.continue();});
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',r=>{const u=new URL(r.url());if(r.status()!==200)return;if(u.pathname.startsWith('/messenger/')&&!u.pathname.includes('/api/')||/\/core\/(app-client|app-services|appearance-host|skins|share-sheet)\.(js|css)$/.test(u.pathname))bodies.push(r.body().then(b=>{const rel=u.pathname;if(rel.startsWith('/messenger/'))R.staticHashes[rel.slice(11)||'index.html']=sha(b);else R.sdkHashes[rel.replace('/wizard-os-home/','')]=sha(b);}).catch(()=>{}));});
    await page.addInitScript(({shell})=>{localStorage.setItem('wos.skin','nebula');localStorage.setItem('wux.shell',shell);localStorage.setItem('wos.coached','true');localStorage.setItem('wos.tour','done');localStorage.setItem('wos.tour.done','1');},{shell});
    await page.goto(ORIGIN+'/wizard-os-home/'+entry,{waitUntil:'load'});
    const handle=await page.waitForSelector('iframe[src*="/messenger/"]',{timeout:30000}),frame=await handle.contentFrame();
    await frame.locator('.u-list .u-person',{hasText:'Kira Novak'}).waitFor();
    assert(await page.evaluate(()=>WizAppServices.inspect().some(x=>x.appId==='messenger'&&x.ready)),'no canonical SDK attachment');
    const ready=await frame.evaluate(()=>WizardApp.ready({name:'Messenger'}));assert.equal(ready.hosted,true);assert.equal(ready.appId,'messenger');
    await page.waitForFunction(()=>WizAppearance.inspect().some(x=>x.acked));
    const identity=await frame.evaluate(()=>window.__qaFrameIdentity=crypto.randomUUID());
    for(const skin of ['nebula','grove']){
     if(skin!=='nebula')await page.evaluate(s=>WosSkin.set(s),skin);
     await frame.waitForFunction(s=>document.documentElement.dataset.skin===s,skin,{timeout:15000});
     assert.equal(await frame.evaluate(()=>window.__qaFrameIdentity),identity,'skin remounted frame');
     row.skins.push({id:skin,scheme:await frame.evaluate(()=>document.documentElement.dataset.colorScheme)});
     const statusRow=frame.locator('.u-list .u-person[data-pid="p-status"]');
     assert.match(await statusRow.innerText(),/Status update/);
     await statusRow.click();await frame.locator('.u-row[data-id="status-native"] .u-unavailable').waitFor();
     assert.match(await frame.locator('.u-row[data-id="status-native"] .u-unavailable').innerText(),/Status update\s*\(view it in WhatsApp on your phone\)/);
     await page.evaluate(()=>WizAppServices.back(document.querySelector('iframe[src*="/messenger/"]')));
     await frame.locator('.u-list .u-person[data-pid="p0"]').click();
     await frame.locator('.u-row[data-id="ordinary-wait"] .u-unavailable').waitFor();
     assert.match(await frame.locator('.u-row[data-id="ordinary-wait"] .u-unavailable').innerText(),/Waiting for this message\s*\(WhatsApp is still sending it\)/);
     await page.evaluate(()=>WizAppServices.back(document.querySelector('iframe[src*="/messenger/"]')));
     row['statusBroadcast-'+skin]={statusWording:true,ordinaryChatStillWaits:true};
     // A real shell Share opens the app's Send to… picker through the shared SDK, with recent-first ordering.
     await page.waitForFunction(()=>WosShareSheet._state().receivers.messenger?.targets?.length>0);
     const targets=await page.evaluate(()=>WosShareSheet._state().receivers.messenger.targets);assert.equal(targets[0].id,'p20','recent share targets must not be A-Z');
     await page.evaluate(()=>{WosShareSheet.show({kind:'text',text:'Synthetic shared composer '+Date.now(),title:'Synthetic share'},()=>Promise.resolve('unsupported'));});
     await page.locator('[data-shs-app="messenger"].shs-app').click();
     await frame.locator('.u-directory-row').first().waitFor();assert.match(await frame.locator('.u-directory-row').first().innerText(),/Umar Khan/);
     row['opacity-'+skin]=await opacity(page,frame,shell+'-'+skin);
     // Outside closes, and the next opening reuses the same real SDK/frame.
     await frame.locator('#u-overlay').click({position:{x:3,y:3}});await frame.locator('#u-overlay').waitFor({state:'detached'});
     await page.evaluate(()=>{WosShareSheet.show({kind:'text',text:'Synthetic retained shared text',title:'Synthetic share'},()=>Promise.resolve('unsupported'));});
     await page.locator('[data-shs-app="messenger"].shs-app').click();await frame.locator('.u-directory-row').first().click();
     await frame.waitForFunction(()=>document.querySelector('textarea[aria-label="Message"]')?.value.includes('Synthetic retained shared text'));
     assert.equal(data.drafts.some(d=>d.text.includes('Synthetic retained shared text'))||await frame.locator('textarea[aria-label="Message"]').inputValue()==='Synthetic retained shared text',true);
     const back=()=>page.evaluate(()=>WizAppServices.back(document.querySelector('iframe[src*="/messenger/"]')));
     assert.equal(await back(),'handled');await frame.locator('.u-list').waitFor();
     const list=frame.locator('.u-list');await list.evaluate(e=>e.scrollTop=400);await frames(frame);const start=await list.evaluate(e=>e.scrollTop);assert(start>300);
     const reads=data.people.length,extra={...data.people[0],id:'extra-'+skin,display_name:'Zed Synthetic '+skin,last:{text:'Synthetic feed insertion',timestamp:1,outgoing:false}};
     data.updates.push({seq:skin==='nebula'?6:7,people:[extra]});
     await frame.locator('.u-list [data-pid="'+extra.id+'"]').waitFor();await frames(frame);assert(Math.abs(await list.evaluate(e=>e.scrollTop)-start)<2,'canonical feed scroll moved');
     await frame.locator('.u-list .u-person',{hasText:'Kira Novak'}).click();await frame.locator('.u-who-text strong',{hasText:'Kira Novak'}).waitFor();
     const save=page.waitForResponse(r=>r.url().includes('/api/drafts')&&r.request().method()==='POST');await frame.locator('textarea[aria-label="Message"]').fill('Synthetic canonical '+shell+' '+skin);await save;
     assert(data.drafts.some(d=>d.person_id==='p10'&&d.text==='Synthetic canonical '+shell+' '+skin));
     if(await frame.evaluate(()=>innerWidth)>=640){assert(Math.abs(await list.evaluate(e=>e.scrollTop)-start)<2);await frame.locator('.u-list .u-person',{hasText:'Maya Cohen'}).click();assert(Math.abs(await list.evaluate(e=>e.scrollTop)-start)<2);}
     assert.equal(await back(),'handled');await list.waitFor();assert(Math.abs(await list.evaluate(e=>e.scrollTop)-start)<2,'canonical Back scroll moved');
     await back();assert.equal(await frame.evaluate(()=>window.__qaFrameIdentity),identity,'root Back exited app');
     const shot=shell+'-'+skin+'-canonical.png';await page.screenshot({path:path.join(OUT,shot)});row.screenshots.push({file:shot,sha256:sha(fs.readFileSync(path.join(OUT,shot)))});
     assert(await frame.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'canonical horizontal clipping');
    }
    // Same-frame synchronous reaction to a real click, while directory response is deliberately withheld.
    let release;const held=new Promise(r=>release=r);
    await ctx.route('**/api/unified/directory',async r=>{await held;return data.route(r);});
    await frame.getByRole('button',{name:'New chat',exact:true}).click();
    assert(await frame.locator('#u-overlay, .u-newmsg').count()>0,'no immediate local response while backend held');release();
    await ctx.unroute('**/api/unified/directory');
    await page.emulateMedia({colorScheme:'dark'});await page.goto(ORIGIN+'/messenger/');await page.locator('.u-person').first().waitFor();
    assert.equal((await page.evaluate(()=>WizardApp.ready())).hosted,false);
    const bg=await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor);assert.notEqual(bg,'rgba(0, 0, 0, 0)');row.standaloneBackground=bg;
    const stand=shell+'-standalone.png';await page.screenshot({path:path.join(OUT,stand)});row.screenshots.push({file:stand,sha256:sha(fs.readFileSync(path.join(OUT,stand)))});
    await Promise.all(bodies);assert.deepEqual(errors,[]);
   }finally{await ctx.close();}
  }
  // Exact delivered assets, not a broad screenshot-count assertion.
  for(const [n,v] of Object.entries(R.staticHashes)){const root=process.env.MESSENGER_PUBLIC_PIN_DIR&&['index.html','app.js','app.css'].includes(n)?process.env.MESSENGER_PUBLIC_PIN_DIR:process.env.MESSENGER_STATIC_DIR;const p=path.join(root,n);assert.equal(sha(fs.readFileSync(p)),v,n);}
  R.publicPinnedClientKept=!!process.env.MESSENGER_PUBLIC_PIN_DIR;
  for(const [n,v] of Object.entries(R.sdkHashes)){assert.equal(sha(fs.readFileSync(path.join(process.env.WIZARD_WEB_DIR,n))),v,n);}
  for(const n of ['index.html','app.js','unified.js','unified.css'])assert(R.staticHashes[n],'missing packaged asset delivery '+n);
  for(const n of ['core/app-client.js','core/app-services.js','core/appearance-host.js','core/share-sheet.js'])assert(R.sdkHashes[n],'missing canonical SDK delivery '+n);
  assert.deepEqual(R.prohibited,[]);R.pass=true;
 }finally{await browser.close();fs.writeFileSync(path.join(OUT,'receipt.json'),JSON.stringify(R,null,2)+'\n');}
})().catch(e=>{console.error(e);process.exitCode=1;});
