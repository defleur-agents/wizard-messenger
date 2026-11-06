// SYNTHETIC DOM only: behavior, not screenshot/layout/provider evidence.
const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const {mentionQuery,parseMentions,insertMention,mentionKey,reactorGroups}=require('../static/unified.js');
const {makeDocument,browserContext,Element}=require('./helpers/unified_browser_context.cjs');
const members=[{id:'@telegram_1:synthetic.invalid',name:'Alice Example',label:'Alice Example',identity_id:'synthetic'},
{id:'@telegram_2:synthetic.invalid',name:'Bob Example',label:'Bob Example',identity_id:'synthetic'}];
test('mention query excludes emails and supports caret in the middle',()=>{
  assert.equal(mentionQuery('mail@example.org'),null);
  assert.deepEqual(mentionQuery('Hi @Al rest',6),{start:3,end:6,query:'al'});
  assert.equal(mentionQuery('Hi @Al\nrest'),null);
});
test('selected mention replaces only the query and preserves trailing text',()=>{
  const text='Hi @Al later', q=mentionQuery(text,6), next=insertMention(text,q,members[0]);
  assert.equal(next.text,'Hi @Alice Example  later'); assert.equal(next.text.slice(0,next.caret),'Hi @Alice Example ');
});
test('parsing supplies UTF-16 spans, boundaries and longest label first',()=>{
  const text='😀 @Alice Example! mail@Bob Example';
  assert.deepEqual(parseMentions(text,members),[{id:members[0].id,name:members[0].name,start:3,end:17}]);
  assert.deepEqual(parseMentions('@Alice ExampleExtra',members),[]);
});
test('arrow keys wrap and Enter/Tab select; Escape closes without sending',()=>{
  assert.equal(mentionKey('ArrowUp',0,2).index,1);
  assert.equal(mentionKey('ArrowDown',1,2).index,0);
  assert(mentionKey('Enter',1,2).select); assert(mentionKey('Tab',0,2).select);
  assert(mentionKey('Escape',0,2).close); assert(!mentionKey('x',0,2).handled);
});
test('reactor groups deduplicate identities and retain missing count',()=>{
  const u={id:'synthetic-a',name:'Synthetic Alice'};
  const result=reactorGroups([{key:'👍',count:3,reactors:[u,u]}]);
  assert.equal(result[0].reactors.length,1); assert.equal(result[0].missing,2);
});
function fixture(touch=false) {
  const document=makeDocument(), root=document.createElement('main'); root.id='messenger'; document.body.append(root);
  const app=browserContext({document,overrides:{matchMedia:()=>({matches:touch,addEventListener(){}}), ResizeObserver:class{observe(){}},navigator:{vibrate(){}},getComputedStyle:()=>({})}});
  // Only add concrete browser methods this controller exercises; never synthesize unknown properties.
  Element.prototype.prepend=function(...nodes){const prior=[...this.children];this.replaceChildren(...nodes,...prior);};
  Element.prototype.scrollIntoView=function(){};
  Element.prototype.setSelectionRange=function(start,end){this.selectionStart=start;this.selectionEnd=end;};
  Element.prototype.closest=function(selector){let el=this;while(el){if(el.classList.contains(selector.slice(1)))return el;el=el.parent;}return null;};
  const source=fs.readFileSync(require.resolve('../static/unified.js'),'utf8').replace('  window.MessengerUnified = {','  window.__groupQA = {mentionComposer,reactionChip,reactorList,richText,back,view,s,bubble};\n  window.MessengerUnified = {');
  vm.runInNewContext(source,app.context);
  return {...app,document,root,qa:app.context.__groupQA};
}
function click(el, extra={}) { el.onclick({pointerType:'mouse',preventDefault(){},stopPropagation(){},...extra}); }
test('renderer keyboard chooses highlighted member, mirror paints name, outside and Back close picker',()=>{
  const f=fixture(), {document:d,root,qa}=f;
  const form=d.createElement('form'),field=d.createElement('div'),draft=d.createElement('textarea'); field.append(draft);form.append(field);root.append(form);
  let ui; ui=qa.mentionComposer(form,field,draft,()=>members,()=>ui.update());
  draft.value='@';draft.selectionStart=1;ui.update();
  const picker=root.querySelector('.u-mention-picker');assert(!picker.hidden);
  const key=key=>draft.dispatchEvent({type:'keydown',key,preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){}});
  key('ArrowDown');key('Tab');assert.equal(draft.value,'@Bob Example ');assert(picker.hidden);
  assert.equal(field.querySelector('mark').textContent,'@Bob Example');
  draft.value='@';draft.selectionStart=1;ui.update();assert.equal(qa.back(),true);assert(picker.hidden);
  ui.update();d.dispatchEvent({type:'pointerdown',target:root});assert(picker.hidden);
  f.dispose();
});
test('desktop hover tooltip names actual reactors; right-click opens emoji tabs and Back keeps app',()=>{
  const f=fixture(), {qa,root}=f, r={key:'👍',count:2,reactors:[{id:'a',name:'Synthetic Alice'}]};let toggles=0;
  const chip=qa.reactionChip(r,[r],{pid:null,toggle:()=>toggles++});root.append(chip);
  chip.dispatchEvent({type:'pointerenter',pointerType:'mouse'});const tip=chip.querySelector('.u-reactor-tooltip');assert(!tip.hidden);assert.match(tip.textContent,/Synthetic Alice/);assert.match(tip.textContent,/unavailable/);
  chip.dispatchEvent({type:'contextmenu',preventDefault(){}});assert.equal(root.querySelectorAll('.u-reactor-tabs button').length,2);
  assert.equal(toggles,0);assert.equal(qa.back(),true);assert.equal(root.querySelector('.u-overlay'),null);assert(root.isConnected);
  f.dispose();
});
test('phone tap and 450ms touch long-press open reactor sheet, never toggle; outside closes',()=>{
  const f=fixture(true), {qa,root}=f, r={key:'❤️',count:1,reactors:[{id:'b',name:'Synthetic Bob'}]};let toggles=0;
  const chip=qa.reactionChip(r,[r],{pid:null,toggle:()=>toggles++});root.append(chip);
  click(chip,{pointerType:'touch'});assert(root.querySelector('.u-reactor-list'));qa.back();
  chip.dispatchEvent({type:'pointerdown',button:0,pointerType:'touch',clientX:10,clientY:10,stopPropagation(){}});
  assert(chip.classList.contains('pressed'));
  const timer=[...f.timers].find(([,v])=>v.ms===450);assert(timer);f.runTimer(timer[0]);
  const layer=root.querySelector('.u-overlay');assert(layer);assert.match(layer.textContent,/Synthetic Bob/);
  click(layer,{target:layer});assert.equal(root.querySelector('.u-overlay'),null);assert.equal(toggles,0);
  f.dispose();
});
test('incoming mention link is rendered as data, never executable HTML',()=>{
  const f=fixture(); const text='Hi @Alice Example';
  const el=f.qa.richText('u-text',text,parseMentions(text,members));
  assert.equal(el.querySelector('a').textContent,'@Alice Example');assert.match(el.querySelector('a').href,/https:\/\/matrix.to/);
  f.dispose();
});
