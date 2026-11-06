// Forum-only, synthetic fixture. Never contacts the owner installation.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {origin,createFixture}=require('./helpers/group_features_fixture.cjs');
assert(process.cwd().startsWith('/srv/work/'));
const out=path.resolve(process.argv[2]),shell=process.env.SHELL_DIR,staticDir=path.resolve(__dirname,'../static');fs.mkdirSync(out,{recursive:true});
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png'};
(async()=>{const browser=await chromium.launch({headless:true,args:['--no-sandbox']});const results=[];
try{for(const mode of ['standalone','desktop','phone'])for(const skin of ['nebula','signal']){
const ctx=await browser.newContext({viewport:mode==='phone'?{width:390,height:844}:{width:1440,height:900},isMobile:mode==='phone',hasTouch:mode==='phone',serviceWorkers:'block'});
const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
const fixture=createFixture('line');
fixture.person.members=[];fixture.person.display_name='Synthetic LINE group';fixture.person.identities[0].network='line';
const dm=JSON.parse(JSON.stringify(fixture.person));dm.id='synthetic-dm';dm.kind='person';dm.display_name='Synthetic LINE friend';dm.identities[0].kind='person';dm.identities[0].id='line-dm';
fixture.routes['/api/unified/people']={people:[dm],seq:1};
let releaseUpdate;let seq=1;
await ctx.addInitScript(()=>{if(window===parent){localStorage.setItem('wos.coached','true');localStorage.setItem('wos.welcome.v1','done');}});
await ctx.route('**/*',async route=>{const req=route.request(),u=new URL(req.url()),p=u.pathname;if(u.origin!==origin)return route.abort();
const send=json=>route.fulfill({json});
if(p==='/wizard/hermes/api/model/options')return send({provider:'synthetic',providers:[{slug:'synthetic',authenticated:true,auth_type:'fixture'}]});
if(p.includes('/api/')){
if(p.includes('/unified/updates')){await new Promise(r=>releaseUpdate=r);return send({ok:true,result:{seq:++seq,people:[fixture.person,dm],messages:{},typing:{},removed:[]}});}
if(p.includes('/unified/people/synthetic-dm')){if(req.method()==='POST')return send({ok:true,result:{ok:true}});return send({ok:true,result:{person:dm,messages:[{...fixture.msg,id:'matrix:$line-null-sender',person_id:dm.id,sender:null,reactions:[]},{...fixture.msg,id:'matrix:$line-sticker',person_id:dm.id,msgtype:'m.sticker',original:'',media:null,reactions:[]},{...fixture.msg,id:'matrix:$line-edited',person_id:dm.id,edited:true,reply_to:'matrix:$line-null-sender',reactions:[{key:'👍',count:1}]}],typing:[],has_more:false,next_cursor:null}});}
const a=fixture.reply(u.href,req.method(),req.postData()?req.postDataJSON():undefined);return send(a??{ok:true,result:{providers:[]}});
}
if(p==='/wizard/hermes/api/model/options')return send({provider:'synthetic',providers:[{slug:'synthetic',authenticated:true,auth_type:'fixture'}]});
if(p==='/wizard/v1/apps')return send({apps:[{id:'messenger',url:'/app/',name:'Messenger'}]});
if(p==='/wizard/v1/bootstrap')return send({bootstrap:1,endpoints:{apps:'/wizard/v1/apps'},settings:{agent:{name:'Synthetic Wizard'}},capabilities:{}});
if(p.endsWith('/ui-preferences'))return send({migrations:{'launcher-seed-v1':true}});
if(p.startsWith('/wizard/')||p.includes('/store-data/'))return send({data:[],has_more:false,apps:[],wam:[],shell:[],complete:true,unavailable:[],first_run:false});
if(p.endsWith('/ux-version.txt'))return route.fulfill({body:'synthetic',contentType:'text/plain'});
if(p==='/app/'||p==='/')return route.fulfill({path:path.join(staticDir,'index.html'),contentType:'text/html'});
let file=p.startsWith('/wizard-os-home/')?path.join(shell,p.slice('/wizard-os-home/'.length)||'index.html'):path.join(staticDir,p.replace(/^\/app\//,''));
if(p.endsWith('/data.js')||p.endsWith('/summaries.js'))return route.fulfill({body:'',contentType:'text/javascript'});
if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file,contentType:types[path.extname(file)]||'application/octet-stream'});
return route.fulfill({status:404,body:''});});
try{
let f=page;
if(mode==='standalone')await page.goto(origin+'/app/');else{await page.goto(origin+'/wizard-os-home/?shell='+ (mode==='phone'?'phone':'desktop'));await page.waitForFunction(()=> (window.__wos||window.__wux)&&window.WizCore);await page.evaluate(()=>WizCore.appsLoaded());await page.evaluate(mode=>(mode==='phone'?__wos:__wux).openApp(WizCore.apps(mode==='phone'?'mobile':'desktop').APP.messenger),mode);await page.waitForFunction(()=>[...document.querySelectorAll('iframe')].some(f=>f.src.endsWith('/app/')));f=page.frameLocator('iframe[src$="/app/"]');await page.evaluate(s=>{WosSkin.set(s);WizAppearance.sync();},skin);}
await f.locator('.u-person').first().waitFor();
const row=f.locator('.u-person[data-pid="synthetic-dm"]');const b=await row.boundingBox();await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();
// Exact production repaint path, synchronously between press and release.
await f.locator('html').evaluate(()=>window.MessengerUnified.setNativeRows([]));
await page.mouse.up();
await f.locator('.u-composer textarea').waitFor({timeout:3000});
const draft=f.locator('.u-composer textarea');await draft.click();await page.keyboard.type('Synthetic click works');assert.equal(await draft.inputValue(),'Synthetic click works');assert.equal(await draft.evaluate(e=>e===document.activeElement),true);
if(mode!=='phone'){
const group=f.locator('.u-person[data-pid="synthetic-group"]');if(await group.isVisible()){await group.click();await draft.waitFor();await draft.fill('@');await f.locator('.u-person[data-pid="synthetic-dm"]').click();await draft.waitFor();await draft.fill('Synthetic second chat');}}
await page.screenshot({path:path.join(out,mode+'-'+skin+'.png')});assert.deepEqual(errors,[]);results.push({mode,skin,pass:true,clickDuringBackfill:true,composerFocused:true});
}catch(e){await page.screenshot({path:path.join(out,mode+'-'+skin+'-failure.png')});fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({mode,skin,error:e.stack,errors,url:page.url(),diagnostic:await page.evaluate(()=>({wos:!!window.__wos,core:!!window.WizCore,log:window.__welcomeLog,body:document.body.innerText.slice(0,1000)}))},null,2));throw e;}finally{await ctx.close();}
}
fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({pass:true,syntheticOnly:true,results},null,2));console.log(JSON.stringify(results));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
