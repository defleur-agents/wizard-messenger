// Forum only. Real hosted client + source view; ALL accounts/messages/identities are SYNTHETIC.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
if(!process.cwd().startsWith('/srv/work/')) throw Error('Forum /srv/work only');
const out=path.resolve(process.argv[2]),shell=process.env.SHELL_DIR,staticDir=path.resolve(__dirname,'../static');fs.mkdirSync(out,{recursive:true});
// Reuse LINE's hosted Appearance fixture, not hand-built colour tokens.
assert(fs.existsSync(path.join(shell,'core/skins.js')), 'Pinned real skin source required');
const host=`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/wizard-os-home/core/skins.css"><script src="/wizard-os-home/core/skins.js"></script><script>window.WizCore={apps:()=>({APPS:[{url:'/app/'}]})};window.setFixtureSkin=id=>{window.WosSkin.set(id);window.WizAppearance?.sync()};setFixtureSkin('nebula')</script><script src="/wizard-os-home/core/appearance-host.js" defer></script><style>html,body{margin:0;height:100%;background:var(--bg)}.win,iframe{width:100%;height:100%;border:0}</style></head><body><div class="st-embed win"><iframe src="/app/" title="Synthetic group"></iframe></div></body></html>`;
const alice={id:'@telegram_101:messenger.internal',name:'Alice Example',label:'Alice Example',identity_id:'synthetic-id'},bob={id:'@telegram_102:messenger.internal',name:'Bob Example',label:'Bob Example',identity_id:'synthetic-id'};
const types={'.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.html':'text/html'};
(async()=>{const browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});const results=[];
try { for(const profile of [{name:'desktop',viewport:{width:1280,height:860}},{name:'phone',viewport:{width:390,height:844},isMobile:true,hasTouch:true}]) {
 const ctx=await browser.newContext({...profile,deviceScaleFactor:1,reducedMotion:'reduce'}),page=await ctx.newPage(),errors=[],forbidden=[];page.on('pageerror',e=>errors.push(e.message));
 let sent=[]; const now=Date.now(),reactions=[{key:'👍',count:2,mine:false,identities_complete:true,reactors:[alice,bob]},{key:'❤️',count:1,mine:false,identities_complete:true,reactors:[bob]}];
 const msg={id:'matrix:$synthetic',person_id:'synthetic-group',network:'telegram',identity_id:'synthetic-id',direction:'in',outgoing:false,timestamp:now-10000,kind:'text',original:'Welcome @Owner Example',mentions:[{id:'@owner:messenger.internal',name:'Owner Example',start:8,end:22}],mentioned:true,sender:'Alice Example',reactions,deleted:false,media:[]};
 const person={id:'synthetic-group',kind:'group',display_name:'Synthetic test group',unread:1,unread_mentions:1,language:'en',translation_enabled:false,identities:[{id:'synthetic-id',network:'telegram',address:'!synthetic',label:'Synthetic test group',kind:'group'}],preferred_identity:'synthetic-id',members:[alice,bob],last:msg};
 await page.route('**/*',async route=>{const req=route.request(),u=new URL(req.url()),p=u.pathname;
  if(u.origin!=='http://fixture.test'){forbidden.push(u.origin);return route.abort();}
  const json=data=>route.fulfill({json:data});
  if(p==='/')return route.fulfill({body:host,contentType:'text/html'});
  if(p.startsWith('/wizard-os-home/')){const file=path.join(shell,p.slice('/wizard-os-home/'.length));return fs.existsSync(file)?route.fulfill({path:file,contentType:types[path.extname(file)]||'text/plain'}):route.fulfill({status:404,body:''});}
  if(p==='/app/')return route.fulfill({path:path.join(staticDir,'index.html'),contentType:'text/html'});
  if(!p.includes('/api/')){const file=path.join(staticDir,p.replace(/^\/app\//,''));return fs.existsSync(file)?route.fulfill({path:file,contentType:types[path.extname(file)]||'application/octet-stream'}):route.fulfill({status:404,body:''});}
  if(p.endsWith('/api/view/session'))return json({view:true,csrf:'synthetic',capabilities:{view_session:true,passkeys:false}});
  if(p.endsWith('/api/status'))return json({state:'ready',account_id:'c'.repeat(64),display_name:'Synthetic Owner',groups:[],configured:true});
  if(p.endsWith('/api/unified/status'))return json({ok:true,seq:1,networks:[{network:'telegram',label:'Telegram',state:'connected',logins:[]}],telegram:{state:'connected'},agent:{access:false},translation:{ready:false},push:{enabled:false}});
  if(p.endsWith('/api/drafts'))return json(req.method()==='GET'?{drafts:[]}:{draft:null,cleared:true});
  if(p.endsWith('/api/unified/updates'))return new Promise(resolve=>setTimeout(()=>resolve(json({seq:1,messages:[],people:[],typing:[],removed:[]})),20000));
  if(p.endsWith('/api/unified/people'))return json({people:[person],seq:1});
  if(p.endsWith('/api/unified/groups'))return json({groups:[person],seq:1});
  if(p.endsWith('/api/unified/people/synthetic-group')&&req.method()==='GET'){assert(!u.searchParams.has('cursor'));assert(['60',null].includes(u.searchParams.get('limit')));return json({person,messages:[msg,...sent],typing:[],has_more:false,next_cursor:null});}
  if(p.endsWith('/api/unified/people/synthetic-group/send')){const b=req.postDataJSON();const m={...msg,id:'matrix:$sent'+sent.length,direction:'out',outgoing:true,timestamp:Date.now(),original:b.text,mentioned:false,mentions:require('../static/unified.js').parseMentions(b.text,[alice,bob]),reactions:[],client_id:b.client_id};sent.push(m);return json({message:m,seq:2});}
  if(p.endsWith('/api/unified/people/synthetic-group/read')||p.endsWith('/api/unified/people/synthetic-group/typing'))return json({ok:true});
  if(p.endsWith('/api/unified/directory'))return json({people:[],groups:[person]});
  if(p.includes('/login')||p.includes('/enable')||p.includes('/unlock')){forbidden.push(p);return route.abort();}
  if(p.endsWith('/api/unified/listen'))return json({events:[]});
  return json({});
 });
 await page.goto('http://fixture.test/');const f=page.frameLocator('iframe');await f.locator('.u-person').first().waitFor();await f.locator('.u-person').first().click();await f.locator('.u-composer textarea').waitFor();
 const docMarker=await f.locator('html').evaluate(el=>el.dataset.qaDocument=String(Math.random()));let previousAccent;
 for(const skin of ['nebula','signal']) {
  await page.evaluate(skin=>setFixtureSkin(skin),skin);
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('iframe').contentDocument.documentElement).getPropertyValue('--wz-accent').trim()!=='');
  if(previousAccent)await page.waitForFunction(old=>getComputedStyle(document.querySelector('iframe').contentDocument.documentElement).getPropertyValue('--wz-accent').trim()!==old,previousAccent);
  previousAccent=await f.locator('html').evaluate(el=>getComputedStyle(el).getPropertyValue('--wz-accent').trim());assert(previousAccent);
  const draft=f.locator('.u-composer textarea');await draft.fill('@');await f.locator('.u-mention-picker:not([hidden])').waitFor();
  await page.screenshot({path:path.join(out,`${profile.name}-${skin}-mention-picker.png`)});
  const panel=await f.locator('.u-mention-picker').evaluate(el=>getComputedStyle(el).backgroundColor);assert.match(panel,/^rgb\(/,'opaque picker floor');
  await draft.press('ArrowDown');await draft.press('Tab');assert.equal(await draft.inputValue(),'@Bob Example ');assert.equal(await f.locator('.u-mention-mirror mark').textContent(),'@Bob Example');
  await f.locator('.u-send').click();await f.locator('.u-message.outgoing .u-mention').last().waitFor();await page.screenshot({path:path.join(out,`${profile.name}-${skin}-sent-mention.png`)});
  assert.equal(await f.locator('html').getAttribute('data-qa-document'),docMarker,'live skin never reloads document');
  assert(await f.locator('.u-mentioned').count(),'incoming owner mention highlight');
  const chip=f.locator('.u-react').first();
  if(profile.hasTouch)await chip.focus();else await chip.hover();
  await chip.locator('.u-reactor-tooltip:not([hidden])').waitFor();assert.match(await chip.locator('.u-reactor-tooltip').textContent(),/Alice Example.*Bob Example/s);
  await page.screenshot({path:path.join(out,`${profile.name}-${skin}-reactor-tooltip${profile.hasTouch?'-keyboard-focus':''}.png`)});
  if(profile.hasTouch){const box=await chip.boundingBox(),cdp=await ctx.newCDPSession(page),points=[{x:box.x+box.width/2,y:box.y+box.height/2}];await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:points});await page.waitForTimeout(520);await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await cdp.detach();}
  else await chip.click({button:'right'});
  await f.locator('.u-reactor-list').waitFor();await page.waitForTimeout(100);assert(await f.locator('.u-reactor-list').isVisible(),'long-press release keeps sheet open');
  await f.getByRole('tab',{name:'All',exact:true}).click();assert.equal(await f.locator('.u-reactor-row').filter({hasText:'Alice Example'}).count(),1);
  await f.getByRole('tab',{name:'❤️ 1',exact:true}).click();assert.equal(await f.locator('.u-reactor-list .u-reactor-row').count(),1);await f.getByRole('tab',{name:'All',exact:true}).click();
  await page.screenshot({path:path.join(out,`${profile.name}-${skin}-reactor-sheet.png`)});
  await f.locator('.u-overlay').click({position:{x:8,y:8}});await f.locator('.u-overlay').waitFor({state:'detached'});assert(await f.locator('.u-timeline').isVisible());
  await chip.click(profile.hasTouch?{}:{button:'right'});await f.locator('.u-reactor-list').waitFor();await page.goBack();await f.locator('.u-overlay').waitFor({state:'detached'});assert(await f.locator('.u-timeline').isVisible(),'Back closes sheet, not app');
  results.push({profile:profile.name,skin,picker:true,sentMention:true,ownerHighlight:true,tooltip:profile.hasTouch?'keyboard focus (phone has no hover)':'hover',reactorSheet:true,liveSkin:true,opaquePanel:panel});
 }
 assert.deepEqual(errors,[]);assert.deepEqual(forbidden,[]);assert(await f.locator('html').evaluate(el=>el.scrollWidth<=innerWidth));await ctx.close();
 }
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({pass:true,syntheticOnly:true,realSharedAppearance:true,providerMessagingProven:false,results},null,2));
} finally {await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
