// Synthetic DOM/API regressions; never logs account credentials or provider traffic.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor(tag) {
    this.tag=tag; this.children=[]; this.attrs={}; this.value=''; this.style={}; this.dataset={}; this.className='';
    const classes=()=>this.className.split(/\s+/).filter(Boolean);
    this.classList={contains:c=>classes().includes(c),add:(...cs)=>{this.className=[...new Set([...classes(),...cs])].join(' ');},remove:(...cs)=>{this.className=classes().filter(c=>!cs.includes(c)).join(' ');},toggle:(c,force)=>{const on=force===undefined?!classes().includes(c):!!force;this.classList[on?'add':'remove'](c);return on;}};
  }
  append(...nodes) { for (const n of nodes) { n.parent=this; this.children.push(n); } }
  replaceChildren(...nodes) { for (const n of this.children) n.parent=null; this.children=[]; this.append(...nodes); }
  contains(n) { return this===n || this.children.some(c => c.contains(n)); }
  remove() { if (this.parent) this.parent.children=this.parent.children.filter(n => n!==this); this.parent=null; }
  setAttribute(k,v) { this.attrs[k]=v; }
  getContext() { return {fillRect(){}}; }
  querySelector(selector) {
    const match=n=>selector.startsWith('.') ? n.classList.contains(selector.slice(1)) : n.tag===selector;
    for (const child of this.children) { if (match(child)) return child; const found=child.querySelector(selector); if (found) return found; }
    return null;
  }
}
const window = {setTimeout: (f, ms) => setTimeout(f, ms === 60000 ? ms : 0), clearTimeout, qrcode: () => ({addData(){},make(){},getModuleCount:()=>1,isDark:()=>true})};
vm.runInNewContext(fs.readFileSync('static/connectors.js','utf8'), {window,document:{createElement:t=>new Element(t)}});
const all = root => [root,...root.children.flatMap(all)];
const text = root => all(root).map(n=>n.textContent||'').join('\n');
const button = (root,label) => all(root).find(n=>n.tag==='button'&&n.textContent===label);
const tick = () => new Promise(r=>setTimeout(r,0));
const deferred = () => { let resolve,reject; const promise=new Promise((r,j)=>{resolve=r;reject=j;}); return {promise,resolve,reject}; };
const step = (overrides={}) => ({login_id:'process',step_id:'credentials',txn_id:'bls_first',type:'user_input',user_input:{fields:[{id:'email',type:'email'},{id:'password',type:'password'}]},...overrides});
const submit = root => all(root).find(n=>n.tag==='form').onsubmit({preventDefault(){}});
async function delayedStartClose() {
  const root=new Element('main'), start=deferred(), calls=[];
  const ui=window.MessengerConnectors(root,async (p,m,b)=>{calls.push({p,b}); if(p.endsWith('/start')) return start.promise; return {};});
  const running=ui.start('line','email'); await tick(); await ui.close();
  start.resolve(step()); await running;
  assert.equal(root.children.length,0,'late start must not reopen closed sheet');
  assert.equal(calls.filter(c=>c.p.endsWith('/cancel')).length,1,'orphan start cancelled');
  assert.equal(calls.find(c=>c.p.endsWith('/cancel')).b.login_id,'process');
}
async function competingStartsAndCloseDuringCancel() {
  const root=new Element('main'), calls=[]; let cancel=deferred();
  const ui=window.MessengerConnectors(root,async(p,m,b)=>{ calls.push({p,b}); if(p.endsWith('/start')) return step(); if(p.endsWith('/cancel')) return cancel.promise; return {providers:[]}; });
  await ui.start('line','email');
  const first=ui.start('line','email'); const second=ui.start('slack','email');
  await tick(); cancel.resolve({}); await Promise.all([first,second]);
  assert.equal(calls.filter(c=>c.p.endsWith('/start')).length,2,'superseded start never sent');
  assert.ok(calls.filter(c=>c.p.endsWith('/start')).at(-1).p.includes('/slack/'));
  cancel=deferred(); const cancelling=button(root,'Cancel').onclick(); await tick(); await ui.close();
  cancel.resolve({}); await cancelling;
  assert.equal(root.children.length,0,'late Cancel callback cannot call show after close');
}
async function waitErrorsAreNotExpiry() {
  const root=new Element('main'), calls=[];
  const ui=window.MessengerConnectors(root,async(p)=>{calls.push(p); if(p.endsWith('/start')) return step({type:'display_and_wait',display_and_wait:{type:'nothing'}}); if(p.endsWith('/step')) throw new Error('Private bridge connection interrupted'); return {};});
  await ui.start('line','qr');
  assert.match(text(root),/Private bridge connection interrupted/);
  assert.doesNotMatch(text(root),/That code expired/);
  assert.ok(button(root,'Start again'));
  assert.equal(calls.filter(p=>p.endsWith('/start')).length,1,'restart requires owner click');
  await ui.close();
}
async function pendingPollsDoNotReplaySecrets() {
  const root=new Element('main'), calls=[]; let polls=0;
  const ui=window.MessengerConnectors(root,async(p,m,b)=>{
    calls.push({p,b: b&&JSON.parse(JSON.stringify(b))});
    if(p.endsWith('/start')) return step();
    if(p.endsWith('/step')) return ++polls===1 ? {type:'pending'} : step({step_id:'workspace',txn_id:'bls_second',instructions:'Choose a workspace',user_input:{fields:[{id:'workspace',type:'select',options:['Workspace A','Workspace B'],default_value:'Workspace B'},{id:'optional',type:'username',optional:true}]}});
    return {};
  });
  await ui.start('slack','email');
  for(const n of all(root).filter(n=>n.tag==='input')) n.value='synthetic-private-input';
  const submitting=submit(root); await submit(root); await submitting;
  const steps=calls.filter(c=>c.p.endsWith('/step'));
  assert.equal(steps.length,2,'double submit ignored; one poll follows one submission');
  assert.equal(steps[0].b.fields.password,'synthetic-private-input');
  assert.deepEqual(steps[1].b.fields,{},'poll carries no credentials');
  assert.equal(steps[1].b.txn_id,'bls_first');
  assert.equal(all(root).find(n=>n.tag==='select').value,'Workspace B');
  assert.equal(all(root).find(n=>n.name==='optional').required,false);
  await ui.close();
}
async function lineQRPinAndCloseErrorFence() {
  const root=new Element('main'), pin=deferred(), calls=[];
  const ui=window.MessengerConnectors(root,async(p,m,b)=>{
    calls.push({p,b});
    if(p.endsWith('/start')) return step({type:'display_and_wait',step_id:'qr',display_and_wait:{type:'qr',data:'synthetic-qr'}});
    if(p.endsWith('/step')&&b.step_id==='qr') return step({type:'display_and_wait',step_id:'pin',txn_id:'bls_pin',display_and_wait:{type:'code',data:'123456'}});
    if(p.endsWith('/step')) return pin.promise;
    return {};
  });
  const running=ui.start('line','qr'); await tick(); await tick();
  assert.match(text(root),/123456/,'PIN replaces QR while awaiting phone');
  assert.equal(calls.filter(c=>c.p.endsWith('/step')).at(-1).b.txn_id,'bls_pin');
  await ui.close(); pin.reject(new Error('late synthetic failure')); await running;
  assert.equal(root.children.length,0,'closed view never displays late wait errors');
}
async function challengeIsHumanActionNotBlankFailure() {
  const root=new Element('main'), calls=[];
  const ui=window.MessengerConnectors(root,async(p)=>{calls.push(p); return p.endsWith('/start') ? step({type:'challenge',challenge:'cookies'}) : {};});
  await ui.start('instagram','android');
  assert.match(text(root),/cannot safely complete/); assert.match(text(root),/official app or website/);
  assert.equal(calls.filter(p=>p.endsWith('/step')).length,0,'never bypass browser challenge');
  await ui.close();
}
async function telegramApplicationSetup() {
  const root=new Element('main'), calls=[]; let fail=false;
  const ui=window.MessengerConnectors(root,async(p,m,b)=>{
    calls.push({p,m,b:b&&JSON.parse(JSON.stringify(b))});
    if(p==='/api/view/telegram/application') { if(fail) throw new Error('synthetic-secret-hash'); return {configured:true}; }
    return {providers:[{network:'telegram',label:'Telegram',supported:true,state:'not_configured',flows:[]}]};
  });
  // Dormant Telegram lives under Add until explicitly selected; setup is never automatic.
  const openTelegram = async () => {
    await all(root).find(n=>n.tag==='button' && n.dataset.network==='telegram').onclick();
    await button(root,'Set up Telegram').onclick();
  };
  await ui.show(); await openTelegram();
  assert.equal(all(root).find(n=>n.tag==='a').href,'https://my.telegram.org/apps');
  const id=all(root).find(n=>n.name==='api_id'), hash=all(root).find(n=>n.name==='api_hash');
  assert.equal(hash.type,'password'); id.value='12345'; hash.value='synthetic-secret-hash';
  await submit(root); assert.equal(hash.value,'');
  const saved=calls.find(c=>c.p==='/api/view/telegram/application');
  assert.deepEqual(saved.b,{api_id:'12345',api_hash:'synthetic-secret-hash'});
  assert.match(text(root),/warming up/); assert.ok(button(root,'Refresh accounts'));
  assert.equal(calls.filter(c=>c.p.endsWith('/start')).length,0,'saving application keys never starts account login');
  await button(root,'Refresh accounts').onclick(); await openTelegram();
  fail=true; all(root).find(n=>n.name==='api_hash').value='synthetic-secret-hash';
  await submit(root); assert.match(text(root),/Check the API ID and hash/); assert.doesNotMatch(text(root),/synthetic-secret-hash/);
  await ui.close();
}
async function lineFirstRunSetup() {
  const root=new Element('main'), calls=[], enabled=deferred(); let statusReads=0;
  const provider={network:'line',label:'LINE',supported:true,state:'not_configured',flows:[]};
  const flows=[{id:'dev.highest.matrix.line.qr_login'},{id:'dev.highest.matrix.line.email_login'}];
  const ui=window.MessengerConnectors(root,async(p,m,b)=>{
    calls.push({p,m,b});
    if(p.endsWith('/enable')) return enabled.promise;
    if(p.endsWith('/status')) return ++statusReads===1 ? {state:'unavailable',flows:[]} : {state:'disconnected',flows};
    return {providers:[provider]};
  });
  await ui.show();
  await all(root).find(n=>n.tag==='button'&&n.dataset.network==='line').onclick();
  assert.match(text(root),/Needs one-time setup/);
  assert.ok(button(root,'Set up LINE'),'regression: the exact dead state has an action');
  assert.equal(calls.filter(c=>c.p.endsWith('/enable')).length,0,'picking LINE cannot change installation state');
  const setup=button(root,'Set up LINE').onclick();
  assert.match(text(root),/Starting the private LINE connection/,'click paints before backend');
  enabled.resolve({enabled:true,network:'line'}); await setup;
  assert.equal(calls.filter(c=>c.p.endsWith('/enable')).length,1);
  assert.equal(statusReads,2); assert.ok(button(root,'Show QR code')); assert.ok(button(root,'Sign in with email & password'));
  assert.equal(calls.filter(c=>c.p.endsWith('/start')).length,0,'readiness never signs in');
  assert.ok(button(root,'Back to accounts')); await ui.close();
}
async function lineSetupFailureAndClose() {
  for(const mode of ['missing','offline','no-flows','close','timeout']) {
    const root=new Element('main'), slow=deferred(), calls=[];
    const provider={network:'line',label:'LINE',supported:true,state:'not_configured',flows:[]};
    const ui=window.MessengerConnectors(root,async(p)=>{
      calls.push(p);
      if(p.endsWith('/enable')&&mode==='missing') throw Object.assign(new Error('private provisioning token MUST NOT appear'),{code:'connector_not_configured'});
      if(p.endsWith('/status')) return mode==='close'||mode==='timeout' ? slow.promise : {state:mode==='no-flows'?'disconnected':'unavailable',flows:[]};
      return {providers:[provider]};
    });
    await ui.show(); await all(root).find(n=>n.tag==='button'&&n.dataset.network==='line').onclick();
    const previousTimer=window.setTimeout; let expire;
    if(mode==='timeout') window.setTimeout=(f,ms)=>ms===60000?(expire=f,0):previousTimer(f,ms);
    const setup=button(root,'Set up LINE').onclick(); await tick();
    if(mode==='close') { await ui.close(); slow.resolve({state:'disconnected',flows:[{id:'dev.highest.matrix.line.email_login'}]}); }
    if(mode==='timeout') { expire(); }
    await setup; window.setTimeout=previousTimer;
    if(mode==='close') assert.equal(root.children.length,0,'late setup cannot reopen a closed sheet');
    else {
      assert.ok(button(root,'Retry LINE setup'),mode+' offers explicit recovery');
      assert.ok(button(root,'Back to accounts'));
      assert.doesNotMatch(text(root),/MUST NOT appear|Sign in with email & password/);
      if(mode==='missing'||mode==='no-flows') assert.match(text(root),/installation.*incomplete/);
      else assert.match(text(root),/did not become ready/);
      if(mode==='timeout') { slow.resolve({state:'disconnected',flows:[{id:'dev.highest.matrix.line.email_login'}]}); await tick(); assert.ok(button(root,'Retry LINE setup'),'late readiness cannot overwrite timeout'); }
    }
    assert.equal(calls.filter(p=>p.endsWith('/start')).length,0); await ui.close();
  }
}
(async()=>{
  const tests=[delayedStartClose,competingStartsAndCloseDuringCancel,waitErrorsAreNotExpiry,pendingPollsDoNotReplaySecrets,lineQRPinAndCloseErrorFence,challengeIsHumanActionNotBlankFailure,telegramApplicationSetup,lineFirstRunSetup,lineSetupFailureAndClose];
  for(const test of tests) await test();
  console.log(`connector login runtime: ${tests.length} synthetic UI regressions passed`);
})().catch(e=>{console.error(e);process.exitCode=1;});
