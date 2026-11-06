// James, 6 Nov 2026: "when I open a group chat, it seems to scroll all the way to the bottom. It shouldn't do that.
// It should show me where my last read message is and start the reading there."
// Browser-free guards for the pieces that broke it; the full proof is tests/group_last_read_browser.cjs (forum).
const {test} = require('node:test'), assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
const src = fs.readFileSync(require('node:path').join(__dirname, '../static/unified.js'), 'utf8');
const fn = name => { const a = src.indexOf('  function ' + name + '('); assert(a > 0, name); const b = src.indexOf('\n  }\n', a); return src.slice(a, b + 4); };

test('the desktop split change remembers the reading place before the layout changes', () => {
  const body = fn('relayout');
  const place = body.indexOf('readingPlace()'), flip = body.indexOf("toggleAttribute('data-split'");
  assert(place > 0 && flip > place, 'measure in the old layout, then flip');
  assert.match(body, /reopenThread\(place\)/);
});

test('rebuilding the open chat holds the place instead of following to the bottom', () => {
  const body = fn('reopenThread');
  assert.match(body, /paintThread\(!place, !!place\)/);
  assert.match(body, /putPlace\(place\)/);
  assert.match(fn('paintThread'), /const follow = !hold && \(toBottom \|\| nearBottom\(\)\)/);
});

test('a feed reset re-parks a chat that was being read, and reloads the desktop list beside it', () => {
  assert.match(src, /const reading = !!again && !!view\.scroll\?\.isConnected && !nearBottom\(\);/);
  assert.match(src, /reading \? \{\.\.\.again, settled: false, parked: false\}/);
  assert.match(src, /if \(s\.person\) \{ openPerson\(s\.person\); if \(split\.on\) renderList\(\); \}/);
});

test('reading one chat never stops another chat with the same newest timestamp from being marked read', () => {
  const calls = [];
  const env = {calls, document: {hidden: false}, split: {on: false}, s: {tab: 'groups'}, unreadById: {}, syncBadge() {}, drawList() {},
    listKey: () => 'groups', nearBottom: () => true, call: (p, b) => { calls.push(p); return Promise.resolve(); }};
  const at = 1793980000000;
  const thread = id => ({person: {id, last_read_ts: at - 9e5}, messages: [{id: id + '-1', timestamp: at, outgoing: false}]});
  env.store = {threads: {a: thread('a'), b: thread('b')}, lists: {groups: [{id: 'a', unread: 3, last_read_ts: at - 9e5}, {id: 'b', unread: 4, last_read_ts: at - 9e5}]}};
  env.view = {id: 'a', scroll: {}, unread: {settled: true}};
  vm.runInNewContext(fn('markRead') + '; markRead(); view.id = "b"; markRead(); markRead();', env);
  assert.deepEqual(calls, ['people/a/read', 'people/b/read']);
});
