import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const src = readFileSync(new URL('../static/unified.js', import.meta.url), 'utf8');
const start = src.indexOf('  function replaceListRows(');
assert.ok(start > 0);
const helper = src.slice(start, src.indexOf('\n  const isLow', start));
const ctx = {}; vm.runInNewContext(helper + '\nthis.replace = replaceListRows;', ctx);
test('list refresh restores the previous scroll synchronously after replacing rows', () => {
  let top = 400; const events = [], rows = {};
  const list = {get scrollTop() { events.push('read'); return top; }, set scrollTop(v) { events.push('restore'); top = v; },
    replaceChildren(got) { assert.equal(got, rows); events.push('replace'); top = 0; }};
  ctx.replace(list, rows);
  assert.equal(top, 400);
  assert.deepEqual(events, ['read', 'replace', 'restore']);
});
test('empty/shorter filtered list uses native clamping, not a deferred stale scroll write', () => {
  let top = 400; let max = 1000;
  const list = {get scrollTop() { return top; }, set scrollTop(v) { top = Math.min(max, Math.max(0, v)); },
    replaceChildren() { max = 0; top = 0; }};
  ctx.replace(list, {}); assert.equal(top, 0);
  assert.doesNotMatch(helper, /requestAnimationFrame|setTimeout|Promise/);
  assert.match(src.slice(src.indexOf('  function drawList('), start), /replaceListRows\(list, frag\)/);
});

// Exercise the actual production feed parser with serialized synthetic API state, not shared object references.
const mergeSource = src.slice(src.indexOf('  function mergeList('), src.indexOf('  function mergeMessages('));
const applySource = src.slice(src.indexOf('  function apply('), src.indexOf('  async function feed('));
const keySource = src.match(/  const listKey = [^\n]+/)[0];
test('seq-only redraw cannot insert a server-only row; feed people payload merges the serialized row', () => {
  const serverPeople = [{id:'p0', identities:[{kind:'person', network:'whatsapp'}], last:{timestamp:100}}];
  const store = {seq:5, lists:{people:JSON.parse(JSON.stringify(serverPeople)), groups:[]}, threads:{}, typing:{}};
  let draws = 0;
  const feed = {store, s:{person:null, tab:'inbox'}, split:{on:true}, drawList:() => draws++,
    noteUnread:() => {}, persist:() => {}, unreadById:{}, mutedById:{}, lowById:{}, mediumById:{}, kindById:{}};
  vm.runInNewContext(keySource + '\n' + mergeSource + applySource + '\nthis.applyFeed=apply;', feed);
  const extra = {id:'p-extra', identities:[{kind:'person', network:'telegram'}], last:{timestamp:1}};
  serverPeople.push(extra);
  feed.applyFeed(JSON.parse(JSON.stringify({seq:7})));
  assert.equal(store.lists.people.length, 1, 'server array mutation and seq-only redraw never insert');
  assert.equal(draws, 1, 'redraw alone would satisfy the old mutation wait');
  feed.applyFeed(JSON.parse(JSON.stringify({seq:8, people:[extra]})));
  assert.equal(store.lists.people.length, 2);
  assert.equal(store.lists.people.at(-1).id, 'p-extra', 'production listKey and oldest-last sort accept feed person');
});
test('height probe delivers the row through the API and waits for exact attached row without scrolling it', () => {
  const fixture = readFileSync(new URL('./list_scroll_browser.cjs', import.meta.url), 'utf8');
  assert.match(fixture, /seqOnlyControl \? \{seq:7\} : \{seq:7, people:\[extra\]\}/);
  assert.doesNotMatch(fixture, /people\.push\(extra\)/);
  assert.match(fixture, /waitForFunction\(\(\) => document\.querySelector\('\.u-list \[data-pid="p-extra"\]'\)\?\.isConnected/);
  assert.match(fixture, /feed adds one rendered row/);
  assert.match(fixture, /feed insertion genuinely changes list height/);
  assert.match(fixture, /Math\.abs\(row\.top - start\) >= 2/);
});
