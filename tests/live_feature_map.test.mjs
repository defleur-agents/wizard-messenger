import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const src = fs.readFileSync(new URL('../static/unified.js', import.meta.url), 'utf8');
const between = (a, b) => src.slice(src.indexOf(a), src.indexOf(b, src.indexOf(a)));

test('All / Unread and Direct / Groups / Merged still have executable filter choices', () => {
  const code = between("  const SEGMENTS =", "  const kept =");
  const ctx = {};
  vm.runInNewContext(code + ';this.segments = SEGMENTS;this.types = TYPES;', ctx);
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.segments)), [['all','All'],['unread','Unread'],['medium','Medium'],['low','Low']]);
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.types)), [['all','All chats'],['direct','Direct'],['groups','Groups'],['merged','Merged']]);
  assert.ok(src.includes("TYPES.filter(t => t[0] !== 'merged' || f.merged).map(([v, t]) => radio(t, f.type === v, pick('type', v)))"));
  assert.ok(src.includes('for (const [value, text] of SEGMENTS)'));
});

test('Move to Inbox / Move to Low priority survive via Normal / Low priority, with immediate change and failure rollback', async () => {
  const rows = [{id:'fixture',low_priority:false,medium_priority:false}];
  let reject; const request = new Promise((_, no) => { reject = no; });
  const toasts = [], calls = [];
  const ctx = {store:{lists:{people:rows,groups:[]}}, priorityOf:p=>p.low_priority?'low':p.medium_priority?'medium':'normal',
    drawList(){},syncBadge(){},toast:m=>toasts.push(m),persist(){},call:(url,body)=>{calls.push({url,body});return request;}};
  vm.runInNewContext(between('  async function setPriority(', '  async function setMuted(') + ';this.change = setPriority;', ctx);
  const p = rows[0], pending = ctx.change(p,'low');
  assert.equal(p.low_priority,true,'change must paint before the backend completes');
  assert.equal(calls[0].url,'people/fixture'); assert.equal(calls[0].body.low_priority,true);
  reject(new Error('Could not change priority')); await pending;
  assert.equal(p.low_priority,false,'failed priority move rolls back');
  assert.equal(toasts.at(-1),'Could not change priority');
  ctx.call = async () => ({});
  const expectedLow = 'Moved to Low priority', expectedNormal = 'Moved to Inbox';
  await ctx.change(p,'low'); assert.equal(toasts.at(-1), expectedLow);
  await ctx.change(p,'normal'); assert.equal(toasts.at(-1), expectedNormal);
  assert.equal(p.low_priority,false); assert.equal(p.medium_priority,false);
  assert.ok(src.includes("const PRIORITIES = [['normal', 'Normal'], ['medium', 'Medium'], ['low', 'Low']]"));
  assert.ok(src.includes('run: () => setPriority(p, v)'));
});
