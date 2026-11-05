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
