'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {browserContext,makeDocument}=require('./helpers/unified_browser_context.cjs');
const source=fs.readFileSync('static/unified.js','utf8');
const inventory=require('./fixtures/unified_browser_inventory.json');
const flush=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};
function fixture(options={}) {
  const document=makeDocument();
  for(const [id,tag] of [['messenger','main'],['inbox-tabs','nav'],['unified-inbox','section']]){
    const el=document.createElement(tag);el.id=id;document.body.append(el);
  }
  const f=browserContext({document,...options});
  vm.runInNewContext(source,f.context,{filename:'static/unified.js'});
  return {...f,document};
}
test('unified VM browser dependency inventory is explicit (no permissive globals)',()=>{
  for(const [owner,groups] of Object.entries(inventory.members)){
    const found=[...new Set([...source.matchAll(new RegExp('\\b'+owner.replaceAll('.','\\.')+'\\.([A-Za-z_$][\\w$]*)','g'))].map(m=>m[1]))].sort();
    assert.deepEqual(found,Object.values(groups).flat().sort(),owner+' inventory drift; trace startup before updating');
  }
  const f=fixture();
  for(const name of inventory.globals.provided)assert.notEqual(typeof f.context[name],'undefined',name);
  for(const name of inventory.globals.absentOptional)assert.equal(typeof f.context[name],'undefined',name);
  assert.equal(f.context.window,f.context);assert.equal(f.context.self,f.context);
  f.dispose();
});
test('shipping bootstrap consumes only valid chat fragments, preserving path/query/history state',()=>{
  for(const hash of ['#chat=abc_-9','#chat='+('a'.repeat(64)),'#chat=','#chat='+('a'.repeat(65)),'#chat=a!b','#chat=x&y','#Chat=x','#advanced']){
    const document=makeDocument();
    const f=browserContext({document,url:'https://synthetic.invalid/apps/messenger/?a=1&b=%2F'+hash});
    const state={fixture:true};f.context.history.state=state;
    let hashEvents=0,popEvents=0;
    f.context.addEventListener('hashchange',()=>hashEvents++);f.context.addEventListener('popstate',()=>popEvents++);
    vm.runInNewContext(source,f.context,{filename:'static/unified.js'});
    const valid=/^#chat=([A-Za-z0-9_-]{1,64})$/.test(hash);
    assert.equal(f.context.location.hash,valid?'':hash);
    assert.equal(f.context.location.pathname,'/apps/messenger/');assert.equal(f.context.location.search,'?a=1&b=%2F');
    assert.equal(f.historyCalls.length,valid?1:0);assert.deepEqual(f.context.history.state,state);
    assert.equal(hashEvents,0);assert.equal(popEvents,0);
    f.dispose();
  }
});
test('same-origin history, storage, fragment moves, selectors, events and timers have real state',()=>{
  const document=makeDocument(), f=browserContext({document});
  assert.throws(()=>f.context.history.replaceState(null,'','https://other.invalid/'),{name:'SecurityError'});
  const state={x:1};f.context.history.replaceState(state,'','?x=2#h');state.x=2;assert.equal(f.context.history.state.x,1);
  assert.equal(f.context.location.hash,'#h');assert.equal(f.context.location.search,'?x=2');
  const storage=f.context.sessionStorage;storage.setItem('k',123);assert.equal(storage.getItem('k'),'123');assert.equal(storage.length,1);storage.removeItem('k');assert.equal(storage.getItem('k'),null);
  const frag=document.createDocumentFragment(), child=document.createElement('button');child.classList.add('test');frag.append(child);document.body.append(frag);
  assert.equal(frag.children.length,0);assert.equal(child.parent,document.body);assert.equal(child.isConnected,true);assert.equal(document.querySelector('button.test'),child);
  assert.throws(()=>document.querySelector(':unsupported'),/Unsupported fixture selector/);child.remove();assert.equal(child.isConnected,false);
  let fired=0;const fn=()=>fired++;f.context.addEventListener('hashchange',fn);f.navigateHash('#chat=x');assert.equal(fired,1);f.context.removeEventListener('hashchange',fn);f.navigateHash('#chat=y');assert.equal(fired,1);
  const timer=f.context.setTimeout(()=>{throw new Error('callback sentinel');},10);assert.throws(()=>f.runTimer(timer),/callback sentinel/);assert.equal(f.timers.size,0);
  const interval=f.context.setInterval(()=>fired++,20);f.runTimer(interval);assert.equal(fired,2);f.context.clearInterval(interval);assert.equal(f.timers.size,0);f.dispose();
});
test('shipping mount/auth/signout and pagehide execute at phone and desktop widths',async()=>{
  for(const width of [390,1200]){
    const f=fixture({overrides:{innerWidth:width}}),calls=[],unexpected=[];
    const api=async(path)=>{
      calls.push(path);
      const responses={'api/unified/people':{people:[],seq:0},'api/unified/groups':{groups:[],seq:0},
        'api/unified/connectors':{providers:[]},'api/unified/telegram/status':{},'api/drafts':{drafts:[]},'api/unified/directory':{people:[],groups:[]}};
      if(!(path in responses)){unexpected.push(path);throw new Error('Unexpected contract API '+path);}
      return responses[path];
    };
    f.context.MessengerUnified.mount({api});f.context.MessengerUnified.authenticated();await flush();
    f.context.dispatchEvent({type:'resize'});await flush();
    for(const [id,timer] of [...f.timers])if(timer.kind==='animation')f.runTimer(id);
    assert.equal(f.document.documentElement.getAttribute('data-split')!==null,width>=900);
    assert.ok(f.document.querySelector('.u-list'));assert.match(f.document.body.textContent,/No chats yet/);
    f.context.dispatchEvent({type:'pagehide'});assert.equal(JSON.parse(f.context.sessionStorage.getItem('messenger.resume')).tab,'people');
    assert.ok([...f.timers.values()].some(t=>t.kind==='interval'&&t.ms===20000));
    f.context.MessengerUnified.signout();assert.equal(f.document.getElementById('unified-inbox').textContent,'');
    assert.deepEqual(unexpected,[]);assert.deepEqual(f.violations,[]);
    f.dispose();
  }
});
