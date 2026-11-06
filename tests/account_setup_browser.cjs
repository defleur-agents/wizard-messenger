// James, 5 Nov: warm Slack/Instagram belong in Add, never giant setup cards in Settings.
// Synthetic framebuffer ONLY. This harness never opens any provider or a real login page.
// SHELL_DIR is a pinned wizard-ux/web snapshot; shared host/client and palettes are real.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const staticDir = path.resolve(__dirname, '../static'), shellDir = process.env.SHELL_DIR;
const lineOnly = process.env.LINE_SETUP_ONLY === '1';
const instagramOnly = process.env.INSTAGRAM_SETUP_ONLY === '1';
const fixtureSkins = lineOnly || instagramOnly ? ['nebula', 'signal'] : ['nebula', 'sepia'];
let lineHost;
if(lineOnly || instagramOnly) {
  // Reuse the current shared Appearance host contract from draft_attachment_recovery_browser.
  const vm=require('node:vm'),src=fs.readFileSync(path.join(shellDir,'core/skins.js'),'utf8');
  const table=src.slice(src.indexOf('  const SKINS = ['),src.indexOf('  // Each skin'));
  const palettes=vm.runInNewContext('const T=o=>o;'+table+';SKINS').filter(s=>fixtureSkins.includes(s.id)).map(s=>({id:s.id,t:s.t}));
  assert.equal(palettes.length,2);
  lineHost=`<!doctype html><html data-skin="nebula"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/wizard-os-home/core/skins.css"><script>window.WizCore={apps:()=>({APPS:[{url:'/app/'}]})};window.setFixtureSkin=id=>{const s=JSON.parse(atob('${Buffer.from(JSON.stringify(palettes)).toString('base64')}')).find(s=>s.id===id);for(const[k,v]of Object.entries(s.t))document.documentElement.style.setProperty('--'+k,v);document.documentElement.dataset.skin=id;window.WizAppearance?.sync()};setFixtureSkin('nebula')</script><script src="/wizard-os-home/core/appearance-host.js" defer></script><style>html,body{margin:0;height:100%;background:var(--bg)}nav{height:36px;display:flex}nav button{flex:1}iframe{border:0;display:block;width:100%;height:calc(100vh - 36px)}</style></head><body><nav><button onclick="setFixtureSkin('nebula')">Nebula</button><button onclick="setFixtureSkin('signal')">Signal</button></nav><div class="st-embed win"><iframe src="/app/" title="Synthetic account setup"></iframe></div></body></html>`;
}
const out = path.resolve(process.argv[2] || 'account-setup-evidence'); fs.mkdirSync(out, {recursive:true});
const L = require('../static/app.js');
const types = {'.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.html':'text/html'};
const host = `<!doctype html><html data-shell="proxy"><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/wizard-os-home/core/skins.css"><link rel="stylesheet" data-skin-pkg href="/wizard-os-home/skins/sepia/skin.css"><script>window.WizCore={apps:()=>({APPS:[{url:'/app/'}]})};</script><script src="/wizard-os-home/core/skins.js"></script><script src="/wizard-os-home/core/appearance-host.js"></script><style>html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);font:14px system-ui}nav{height:32px}.win{position:absolute;inset:32px 0 0;background:var(--sk-win)}iframe{width:100%;height:100%;border:0}button{cursor:pointer}</style></head><body><nav>Hosted synthetic proxy <button onclick="WosSkin.set('nebula')">Nebula</button><button onclick="WosSkin.set('sepia')">Sepia</button></nav><section class="win"><iframe src="/app/"></iframe></section></body></html>`;
(async()=>{
  assert(shellDir, 'SHELL_DIR required: real pinned shell source, not invented palette tokens');
  const browser = await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
  const maker = await browser.newPage();
  const frame = await maker.evaluate(()=>{const c=document.createElement('canvas');c.width=1280;c.height=1000;const x=c.getContext('2d');x.fillStyle='#e8edf4';x.fillRect(0,0,1280,1000);x.strokeStyle='#93a3ba';for(let i=0;i<1280;i+=80){x.beginPath();x.moveTo(i,0);x.lineTo(i,1000);x.stroke();}for(let i=0;i<1000;i+=80){x.beginPath();x.moveTo(0,i);x.lineTo(1280,i);x.stroke();}x.fillStyle='#182738';x.font='bold 48px sans-serif';x.fillText('SYNTHETIC PAGE — no account',35,110);for(const [a,b,t]of[[0,0,'TL'],[1160,0,'TR'],[0,900,'BL'],[1160,900,'BR']]){x.fillStyle='#197c59';x.fillRect(a,b,120,100);x.fillStyle='white';x.fillText(t,a+18,b+65);}return c.toDataURL('image/png').split(',')[1];}); await maker.close();
  const summary=[];
  for(const profile of [{name:'phone-enlarged',viewport:{width:360,height:640},isMobile:true,hasTouch:true},{name:'desktop-constrained',viewport:{width:860,height:620}},{name:'desktop-wide',viewport:{width:1280,height:860}}]){
    const ctx=await browser.newContext({...profile,deviceScaleFactor:1,reducedMotion:'reduce'});
    const page=await ctx.newPage(), errors=[], inputs=[], cancelled=[], starts=[], forbidden=[];
    page.on('pageerror',e=>errors.push(e.message));
    const prov=(network,label,state,flows=[])=>({network,label,state,flows,supported:true,logins:state==='connected'?[{id:'fixture',name:'Fixture account'}]:[]});
    const providers=[prov('telegram','Telegram','connected'),prov('slack','Slack','disconnected',[{id:'cookies',name:'Browser'}]),prov('instagram','Instagram DMs','disconnected',[{id:'android',name:'Native'}]),prov('twitter','X','not_configured')];
    if(instagramOnly) providers.find(p=>p.network==='instagram').flows=['instagram','android','instagram-password'].map(id=>({id}));
    let releaseEnable, statusReads=0, enableCount=0, loginPhase=0;
    const loginCalls=[];
    const loginStep=(type,step_id,params={})=>({login_id:'synthetic-instagram',txn_id:'bls_'+step_id,type,step_id:'fi.mau.meta.instagram.'+step_id,...params});
    if(lineOnly) providers.push(prov('line','LINE','not_configured'));
    let seq=0, id=0, releaseFrameCapture=null, holdFrames=false;
    let frameCaptureGate=Promise.resolve();
    await page.route('**/*',async route=>{
      const req=route.request(),u=new URL(req.url());
      if(u.origin!=='https://messenger.test'){forbidden.push(u.origin);return route.abort();}
      const p=u.pathname, api=p.replace(/^\/app\//,'/');
      const ok=result=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,result})});
      if(p==='/host')return route.fulfill({contentType:'text/html',body:lineOnly||instagramOnly?lineHost:host});
      if(p.startsWith('/wizard-os-home/')){const file=path.join(shellDir,p.slice(16));return fs.existsSync(file)&&fs.statSync(file).isFile()?route.fulfill({contentType:types[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)}):route.fulfill({status:404,body:''});}
      if(api==='/api/view/session')return ok({authenticated:true,csrf_token:'synthetic'});
      if(api==='/api/status')return ok({state:'ready',account_configured:true});
      const key='11'.repeat(32);
      if(api==='/api/identity')return ok({identity:{account_id:key,npub:L.encodePublic(key),display_name:'Fixture owner'}});
      if(['/api/contacts','/api/invites','/api/dms'].includes(api))return ok({contacts:[],invites:[],dms:[]});
      if(api==='/api/unified/people')return ok({people:[{id:'a',display_name:'Synthetic chat',identities:[{id:'i',network:'telegram',kind:'person'}],labels:[],unread:0,last:{text:'Fixture',timestamp:Date.now(),outgoing:false}}],seq:5});
      if(api==='/api/unified/groups')return ok({groups:[],seq:5});
      if(api==='/api/unified/connectors')return ok({providers});
      if(lineOnly && api==='/api/unified/connectors/line/enable') { enableCount++; await new Promise(resolve=>releaseEnable=resolve); return ok({enabled:true,network:'line'}); }
      if(lineOnly && api==='/api/unified/connectors/line/status') {
        const p=providers.find(p=>p.network==='line');
        Object.assign(p,++statusReads===1 ? {state:'unavailable',flows:[]} : {state:'disconnected',flows:[{id:'dev.highest.matrix.line.qr_login'},{id:'dev.highest.matrix.line.email_login'}]}); return ok(p);
      }
      if(lineOnly && /\/line\/(start|step|disconnect)$/.test(api)) { forbidden.push(api); return route.abort(); }
      if(instagramOnly && api==='/api/unified/connectors/instagram/start') {
        const b=JSON.parse(req.postData()); loginCalls.push({action:'start',flow:b.flow}); loginPhase=0;
        if(b.flow==='instagram') return ok(loginStep('cookies','cookies',{cookies:{url:'https://www.instagram.com/',fields:['sessionid','csrftoken','ds_user_id'].map(id=>({id,required:true,sources:[{type:'cookie',name:id}]}))}}));
        return ok(loginStep('user_input','credentials',{user_input:{fields:[{id:'username',name:'Username',type:'username'},{id:'password',name:'Password',type:'password'}]}}));
      }
      if(instagramOnly && api==='/api/unified/connectors/instagram/step') {
        const b=JSON.parse(req.postData()); loginCalls.push({action:'step',type:b.type,fields:Object.keys(b.fields||{})});
        if(b.fields?.username==='synthetic-rejected') return route.fulfill({status:409,json:{ok:false,error:{code:'login_failed',message:'Instagram sign-in: The password you entered is incorrect. Try browser sign-in if this keeps happening.'}}});
        if(b.type==='cookies') {assert.deepEqual(Object.keys(b.fields).sort(),['csrftoken','ds_user_id','sessionid']);return ok({type:'complete'});}
        if(++loginPhase===1) return ok(loginStep('user_input','totp',{instructions:'Enter the code from your authenticator app.',user_input:{fields:[{id:'code',name:'Verification code',type:'2fa_code'}]}}));
        if(loginPhase===2) return ok(loginStep('display_and_wait','afad_wait',{instructions:'Approve this request in the Instagram app.',display_and_wait:{type:'nothing'}}));
        return ok({type:'complete'});
      }
      if(api==='/api/unified/connectors/browser/start'){starts.push(JSON.parse(req.postData()));return ok({id:'synthetic-'+(++id)});}
      if(/\/browser\/[^/]+\/frame$/.test(api)){await new Promise(r=>setTimeout(r,120));if(holdFrames)await frameCaptureGate;return ok({seq:++seq,frame,state:'signing_in',host:'synthetic.invalid'});}
      if(/\/browser\/[^/]+\/input$/.test(api)){inputs.push(JSON.parse(req.postData()));return ok({});}
      if(/\/browser\/[^/]+\/cancel$/.test(api)){cancelled.push(api);return ok({});}
      if(api.startsWith('/api/unified/updates')){await new Promise(r=>setTimeout(r,1500));return ok({seq:5});}
      if(api.startsWith('/api/'))return ok({});
      const file=path.join(staticDir,p.replace(/^\/app\//,'')||'index.html');
      if(!file.startsWith(staticDir)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
      return route.fulfill({contentType:types[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});
    });
    await page.goto('https://messenger.test/host');
    const f=page.frames().find(f=>f.url().endsWith('/app/')); assert(f);
    await f.locator('.u-person').first().waitFor({timeout:15000});
    await f.waitForFunction(()=>document.documentElement.dataset.skin==='nebula');
    if(profile.isMobile)await f.addStyleTag({content:'html {font-size:20px} body{font-size:18px}'});
    await f.locator('.u-settings-btn').click();
    await f.getByRole('button',{name:'Add an account',exact:true}).waitFor();
    assert.equal(await f.locator('.c-plus .c-tile-name').innerText(),'Add','original Your accounts → Add tile preserved');
    assert.equal(await f.locator('.c-card').count(),0,'Settings contains NO automatic disconnected setup cards');
    assert.equal(await f.locator('.c-viewer').count(),0);
    await f.locator('.c-plus').click();
    assert.deepEqual(await f.locator('.c-add').evaluateAll(es=>es.map(e=>e.dataset.network).sort()),lineOnly?['instagram','line','slack','twitter']:['instagram','slack','twitter']);
    if(instagramOnly) {
      await f.locator('.c-add[data-network=instagram]').click();
      const doc=await f.evaluate(()=>window.__instagramDocument=crypto.randomUUID());
      const captures=async state=>{
        for(const skin of fixtureSkins) {
          await page.getByRole('button',{name:skin==='nebula'?'Nebula':'Signal',exact:true}).click();
          await f.waitForFunction(s=>document.documentElement.dataset.skin===s,skin); await page.waitForTimeout(350);
          assert.equal(await f.evaluate(()=>window.__instagramDocument),doc);
          assert.equal(await f.locator('.u-sheet').evaluate(e=>e.scrollWidth>e.clientWidth+1),false);
          await page.screenshot({path:path.join(out,`${profile.name}-${skin}-instagram-${state}.png`)});
        }
      };
      assert.equal(await f.locator('.c-card button').first().innerText(),'Sign in with browser (recommended)');
      await captures('options');
      await f.getByRole('button',{name:'Sign in with browser (recommended) for Instagram DMs',exact:true}).click();
      await f.locator('.c-paste').waitFor(); await captures('browser');
      const paste="curl 'https://www.instagram.com/direct/inbox/' -H 'cookie: sessionid=synthetic-session; csrftoken=synthetic-csrf; ds_user_id=1234; other=discarded'";
      await f.locator('.c-paste').fill(paste); await captures('browser-draft');
      assert.equal(await f.locator('.c-paste').inputValue(),paste,'skin changes preserve unsent cookie draft');
      await f.getByRole('button',{name:'Connect',exact:true}).click();
      await f.getByText('Instagram connected',{exact:true}).waitFor();
      await f.getByRole('button',{name:'Done',exact:true}).click();
      await f.locator('.c-plus').click(); await f.locator('.c-add[data-network=instagram]').click();
      await f.getByRole('button',{name:'Username and password for Instagram DMs',exact:true}).click();
      await f.locator('input[name=username]').fill('synthetic-owner'); await f.locator('input[name=password]').fill('synthetic-password');
      await f.getByRole('button',{name:'Continue',exact:true}).click();
      await f.locator('input[name=code]').waitFor(); assert.equal(await f.locator('input[name=code]').getAttribute('type'),'password');
      await captures('verification-code');
      await f.locator('input[name=code]').fill('123456'); await f.getByRole('button',{name:'Continue',exact:true}).click();
      await f.getByRole('button',{name:'I approved it — continue',exact:true}).waitFor(); await captures('approval');
      await f.getByRole('button',{name:'I approved it — continue',exact:true}).click();
      await f.getByText('Instagram connected',{exact:true}).waitFor();
      await f.getByRole('button',{name:'Done',exact:true}).click();
      await f.locator('.c-plus').click(); await f.locator('.c-add[data-network=instagram]').click();
      await f.getByRole('button',{name:'Username and password for Instagram DMs',exact:true}).click();
      await f.locator('input[name=username]').fill('synthetic-rejected'); await f.locator('input[name=password]').fill('synthetic-password');
      await f.getByRole('button',{name:'Continue',exact:true}).click();
      await f.getByText(/The password you entered is incorrect/).waitFor();
      await f.getByRole('button',{name:'Use browser sign-in',exact:true}).waitFor(); await captures('rejection');
      assert.equal(starts.length,0,'Instagram never opens a remote browser'); assert.deepEqual(errors,[]); assert.deepEqual(forbidden,[]);
      summary.push({profile:profile.name,status:'PASS',coverage:'synthetic hosted Instagram browser cookies + credentials/code/approval only; no real login',loginCalls});
      await ctx.close(); continue;
    }
    if(lineOnly) {
      await f.locator('.c-add[data-network=line]').click();
      assert.equal(await f.locator('.c-card .c-pill').innerText(),'Needs one-time setup');
      assert(await f.getByRole('button',{name:'Set up LINE',exact:true}).isVisible());
      assert.equal(enableCount,0,'opening LINE must be owner-controlled, never enable itself');
      const documentId=await f.evaluate(()=>window.__lineDocument=crypto.randomUUID()),paints=[];
      const captures=async state=>{
        for(const skin of fixtureSkins) {
          await page.getByRole('button',{name:skin==='nebula'?'Nebula':'Signal',exact:true}).click();
          await f.waitForFunction(s=>document.documentElement.dataset.skin===s,skin); await page.waitForTimeout(350);
          assert.equal(await f.evaluate(()=>window.__lineDocument),documentId);
          assert.equal(await f.locator('.u-sheet').evaluate(e=>e.scrollWidth>e.clientWidth+1),false);
          const paint=await f.locator('.u-sheet').evaluate(e=>({bg:getComputedStyle(e).backgroundColor,ink:getComputedStyle(e).color}));paints.push({state,skin,...paint});
          await page.screenshot({path:path.join(out,`${profile.name}-${skin}-line-${state}.png`)});
        }
      };
      await captures('actionable');
      await f.getByRole('button',{name:'Set up LINE',exact:true}).click();
      await f.getByText('Starting the private LINE connection… This can take up to a minute.',{exact:true}).waitFor();
      assert.equal(statusReads,0,'pending is painted while enable I/O is held');
      assert.equal(await f.getByRole('button',{name:'Set up LINE',exact:true}).count(),0,'double setup is impossible');
      assert.equal(enableCount,1); releaseEnable();
      await f.getByRole('button',{name:/Sign in with email & password for LINE/}).waitFor();
      assert(await f.getByRole('button',{name:/QR code.*for LINE/}).isVisible());
      assert.equal(statusReads,2); await captures('ready');
      assert.notEqual(paints[0].bg,paints[1].bg);
      assert.equal(starts.length,0); assert.deepEqual(forbidden,[]); assert.deepEqual(errors,[]);
      await f.getByRole('button',{name:'Back to accounts',exact:true}).click();
      await f.locator('.c-add[data-network=line]').waitFor();
      assert.deepEqual(errors,[]);
      await page.goto('https://messenger.test/app/');
      await page.locator('.u-person').first().waitFor(); await page.locator('.u-settings-btn').click();
      await page.locator('.c-plus').click(); await page.locator('.c-add[data-network=line]').click();
      assert.equal(await page.locator('html').evaluate(e=>e.classList.contains('wz-hosted')),false);
      await page.screenshot({path:path.join(out,`${profile.name}-line-standalone-dark.png`)});
      summary.push({profile:profile.name,status:'PASS',coverage:'synthetic hosted LINE setup only; no provider sign-in',paints,enableCount,statusReads});
      await ctx.close(); continue;
    }
    assert.equal(starts.length,0,'rendering settings/add cannot start a browser');
    await f.locator('.c-add[data-network=instagram]').click();
    assert.equal(await f.locator('.c-card').count(),1,'only selected Instagram opens');
    await f.locator('.c-back').click();
    await f.locator('.c-add[data-network=slack]').waitFor();
    await f.locator('.c-add[data-network=slack]').click();
    await f.locator('.c-card .primary').click();
    await f.locator('.c-live-img').waitFor();
    await f.waitForFunction(()=>document.querySelector('.c-live-img')?.naturalWidth===1280);
    const doc=await f.evaluate(()=>window.__fixtureDocument=(window.__fixtureDocument||crypto.randomUUID()));
    const paints=[];
    for(const skin of ['nebula','sepia']){
      await page.getByRole('button',{name:skin==='nebula'?'Nebula':'Sepia',exact:true}).click();
      await f.waitForFunction(s=>document.documentElement.dataset.skin===s,skin);
      await page.waitForTimeout(350);
      const paint=await f.locator('.u-sheet').evaluate(e=>({bg:getComputedStyle(e).backgroundColor,ink:getComputedStyle(e).color,skin:document.documentElement.dataset.skin})); paints.push(paint);
      assert.equal(await f.evaluate(()=>window.__fixtureDocument),doc,'skin change preserves document and flow');
      assert.equal(starts.length,1,'skin switch must not create a second browser');
      const geometry=await f.evaluate(()=>{const shell=document.querySelector('.c-live'),img=document.querySelector('.c-live-img'),panel=document.querySelector('.u-sheet');const b=img.getBoundingClientRect(),r=shell.getBoundingClientRect();return {fit:b.width<=shell.clientWidth+1&&b.height<=shell.clientHeight+1,inside:r.bottom<=innerHeight+1,overflow:panel.scrollWidth>panel.clientWidth+1,stageHeight:r.height};});
      assert(geometry.fit&&geometry.inside&&!geometry.overflow&&geometry.stageHeight>=80,JSON.stringify(geometry));
      for(const sel of ['.c-live-tools','.c-live-keys','.c-waiting']){const b=await f.locator(sel).boundingBox();assert(b&&b.y>=32&&b.y+b.height<=profile.viewport.height+1,sel+' reachable without zoom');}
      // Hold synthetic frame replacement only while comparing paint; the real product poller stays unchanged.
      holdFrames=true;frameCaptureGate=new Promise(resolve=>releaseFrameCapture=resolve);
      await page.waitForTimeout(150);
      await require('./helpers/account_panel_opacity.cjs')(f,page,path.join(out,`${profile.name}-${skin}-opacity`),geometry);
      holdFrames=false;releaseFrameCapture();releaseFrameCapture=null;
      await page.screenshot({path:path.join(out,`${profile.name}-${skin}-fit.png`)});
    }
    assert.notEqual(paints[0].bg,paints[1].bg,'actual dark/light paint differs');
    const img=f.locator('.c-live-img'),b=await img.boundingBox();
    await page.mouse.click(b.x+b.width*.75,b.y+b.height*.6);
    await page.waitForTimeout(80);let tap=inputs.filter(x=>x.type==='tap').at(-1);assert(Math.abs(tap.x-.75)<.015&&Math.abs(tap.y-.6)<.015,'fit tap maps to image not letterbox');
    await f.getByRole('button',{name:'Full size',exact:true}).click();
    await f.locator('.c-live').evaluate(e=>{e.scrollLeft=450;e.scrollTop=250;});
    const stage=await f.locator('.c-live').boundingBox(), image=await img.boundingBox();
    const x=stage.x+45,y=stage.y+45;await page.mouse.click(x,y);await page.waitForTimeout(80);
    tap=inputs.filter(i=>i.type==='tap').at(-1);assert(Math.abs(tap.x-(x-image.x)/image.width)<.015&&Math.abs(tap.y-(y-image.y)/image.height)<.015,'full-size panned mapping');
    await page.screenshot({path:path.join(out,`${profile.name}-full-size.png`)});
    await f.getByRole('button',{name:'Fit window',exact:true}).click();
    await f.getByRole('button',{name:'↓ Page',exact:true}).click();await f.getByRole('button',{name:'‹ Page back',exact:true}).click();
    await page.waitForTimeout(80);assert(inputs.some(x=>x.type==='scroll'&&x.dy===360));assert(inputs.some(x=>x.type==='back'));
    // Shell Back unwinds one layer, cancels exact disposable session, and leaves account selection reachable.
    await f.evaluate(()=>window.MessengerUnified.back());
    await f.locator('.c-card[data-network=slack]').waitFor();assert.equal(await f.locator('.c-viewer').count(),0);
    await page.waitForTimeout(80);assert.equal(cancelled.length,1);assert.equal(new Set(cancelled).size,1);
    await f.evaluate(()=>window.MessengerUnified.back());await f.locator('.c-add[data-network=slack]').waitFor();
    // Outside click collapses Add, then dismisses Settings: never exits the app.
    await f.locator('.u-overlay').evaluate(e=>e.dispatchEvent(new MouseEvent('click',{bubbles:true})));
    assert.equal(await f.locator('.c-add-panel').isVisible(),false);
    await f.locator('.u-overlay').evaluate(e=>e.dispatchEvent(new MouseEvent('click',{bubbles:true})));
    assert.equal(await f.locator('.u-overlay').count(),0);assert(await f.locator('.u-person').first().isVisible());
    if(profile.name==='phone-enlarged'){
      await page.goto('https://messenger.test/app/');
      await page.locator('.u-person').first().waitFor(); await page.locator('.u-settings-btn').click();
      await page.locator('.c-plus').click(); await page.locator('.c-add[data-network=slack]').click(); await page.locator('.c-card .primary').click();
      await page.waitForFunction(()=>document.querySelector('.c-live-img')?.naturalWidth===1280);
      assert.equal(await page.locator('html').getAttribute('data-skin'),null,'standalone does not pretend to be hosted');
      const dark=await page.locator('.u-sheet').evaluate(e=>({bg:getComputedStyle(e).backgroundColor,ink:getComputedStyle(e).color}));
      assert.notEqual(dark.bg,'rgba(0, 0, 0, 0)'); assert.notEqual(dark.bg,dark.ink);
      holdFrames=true;frameCaptureGate=new Promise(resolve=>releaseFrameCapture=resolve);
      await page.waitForTimeout(150);
      await require('./helpers/account_panel_opacity.cjs')(page,page,path.join(out,'phone-standalone-opacity'),{standalone:true});
      holdFrames=false;releaseFrameCapture();releaseFrameCapture=null;
      await page.screenshot({path:path.join(out,'phone-standalone-dark.png')});
      await page.getByRole('button',{name:'Cancel sign-in',exact:true}).click(); await page.waitForTimeout(80);
      assert.equal(cancelled.length,2,'standalone uses and cleans up the same disposable route');
    }
    assert.deepEqual(forbidden,[],'no provider navigation');assert.deepEqual(errors,[]);
    summary.push({profile:profile.name,paints,starts:starts.length,cancelled:cancelled.length,inputs:inputs.length,status:'PASS'});
    await ctx.close();
  }
  fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify({coverage:'synthetic hosted proxy, real shared appearance host/client; no live auth or physical device',summary},null,2));
  await browser.close();console.log(JSON.stringify(summary));
})().catch(e=>{console.error(e);process.exit(1)});
