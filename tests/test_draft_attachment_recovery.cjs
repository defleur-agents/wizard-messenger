// Executes the production serverDraft controller against an isolated strict-revision synthetic endpoint.
// No Messenger server, credentials, provider, private draft, or message store is used.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(process.env.STATIC_JS || path.join(__dirname, '../static/unified.js'), 'utf8');
const controller = source.slice(source.indexOf('  function serverDraft('), source.indexOf('  function composer('));
const tick = () => new Promise(r => setImmediate(r));
const defer = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; };
const copy = v => structuredClone(v);
async function fixture(saved = []) {
  let row = saved === null ? null : {id: 'synthetic-draft', person_id: 'alice', identity_id: 'signal-alice', revision: 1, text: 'Keep this caption', state: 'draft', attachments: saved};
  let next = 0, writes = 0, failPut = new Set(), failGet = new Set(), holdPut = null, holdGet = null, failDelete = false;
  const counts = {puts: 0, deletes: 0, sends: 0}, errors = [];
  const view = {id: 'alice', attach: null}, ui = {draft: {value: '', focus() {}}, channel: {value: 'signal-alice', options: [{value: 'signal-alice'}]}, grow() {}, paintBar() {}, paintVia() {}};
  const bad = (code) => Object.assign(new Error(code), {code});
  async function api(url, options = {}) {
    const body = options.body || {}, method = options.method || 'GET';
    if (url.endsWith('/attachments/' + (url.split('/').pop())) && url.includes('/attachments/') && method === 'DELETE') {
      if (failDelete) throw bad('storage_failed');
      if (body.revision !== row.revision) throw bad('draft_changed');
      row.attachments = row.attachments.filter(a => a.id !== url.split('/').pop()); row.revision++; counts.deletes++;
    } else if (method === 'POST' && url === 'api/drafts') {
      if (row) throw bad('draft_exists');
      row = {...body, id: 'synthetic-draft', revision: 1, state: 'draft', attachments: []};
    } else if (method === 'POST') {
      if (body.revision !== row.revision) throw bad('draft_changed');
      row = {...row, text: body.text, revision: row.revision + 1};
    } else if (method === 'DELETE') {
      if (body.revision !== row.revision) throw bad('draft_changed');
      row = null;
    }
    return {draft: copy(row)};
  }
  async function draftRaw(url, method, blob, q) {
    counts.puts++;
    if (holdPut) { const gate = holdPut; holdPut = null; await gate.promise; }
    if (failPut.has(q.name)) throw bad('storage_failed');
    if (q.revision !== row.revision) throw bad('draft_changed');
    row.attachments.push({id: 'file-' + (++next), name: q.name, mime: blob.type, bytes: blob.size}); row.revision++;
    return {draft: copy(row)};
  }
  const context = vm.createContext({view, ui, Blob, File: class extends Blob { constructor(b, name, o) { super(b, o); this.name = name; } },
    URL: {createObjectURL: () => 'blob:synthetic', revokeObjectURL() {}},
    uid: () => String(++next), api, draftRaw, csrf: () => 'synthetic', error: e => errors.push(e.message),
    fetch: async url => { const id = url.split('/').pop(); if (holdGet) { const gate = holdGet; holdGet = null; await gate.promise; }
      return {ok: !failGet.has(id), blob: async () => new Blob(['synthetic'], {type: 'image/png'})}; },
    preparePhoto: async f => ({blob: f, albumBlob: f, url: 'blob:synthetic', w: 1, h: 1}),
    draftWrites: writes, draftWrote() { context.draftWrites++; }, refreshDraftIndex() {},
    fetchDrafts: async () => row ? [copy(row)] : [], closedDrafts: new Set(), agentName: () => 'Owner',
    SD_SAVE_MS: 500000, SD_POLL_MS: 500000, setTimeout: (fn, ms) => ms === 0 ? setTimeout(fn, 0) : 0,
    clearTimeout, setInterval: () => 0, clearInterval() {}, document: {hidden: false},
    node: (tag, cls, text) => ({tag, cls, text, append() {}}), button: () => ({}),
  });
  vm.runInContext(controller + '\nthis.sd = serverDraft("alice", ui);', context);
  view.sd = context.sd;
  await new Promise(r => setTimeout(r, 10));
  const item = name => ({key: name, name, bytes: 3, file: true, blob: new Blob(['abc'], {type: 'application/pdf'})});
  return {sd: context.sd, ui, view, item, counts, errors, row: () => copy(row), failPut, failGet,
    holdPut() { return holdPut = defer(); }, holdGet() { return holdGet = defer(); },
    failDelete(v) { failDelete = v; }, remoteAttachments(a) { row.attachments = a; row.revision++; },
    replaceView() { view.id = 'bob'; view.sd = {}; view.attach = [item('bob-only')]; },
    async select(...items) { view.attach = [...(view.attach || []), ...items]; await context.sd.attach(items); },
    async remove(it) { view.attach = (view.attach || []).filter(a => a !== it); await context.sd.detach(it); },
  };
}

test('two overlapping selections use successive revisions, not a sticky false error', async () => {
  const f = await fixture(), first = f.item('one.pdf'), second = f.item('two.pdf'), gate = f.holdPut();
  const a = f.select(first); await tick(); const b = f.select(second); await tick(); gate.resolve();
  await Promise.all([a, b]);
  assert.equal(f.row().attachments.length, 2); assert.equal(f.sd.uploadError, false); assert.deepEqual(f.errors, []);
});
test('overlapping selections in an empty composer create only one draft', async () => {
  const f = await fixture(null), gate = f.holdPut(), a = f.select(f.item('one.pdf')); await tick();
  const b = f.select(f.item('two.pdf')); gate.resolve(); await Promise.all([a, b]);
  assert.equal(f.row().attachments.length, 2); assert.equal(f.sd.uploadError, false); assert.equal(f.sd.conflict, null);
});
test('autosave waits for attachment revision, preserving caption and both files', async () => {
  const f = await fixture(), gate = f.holdPut(), a = f.select(f.item('one.pdf')); await tick();
  f.ui.draft.value = 'New caption'; const save = f.sd.save(); await tick(); gate.resolve(); await Promise.all([a, save]);
  assert.equal(f.row().text, 'New caption'); assert.equal(f.row().attachments.length, 1); assert.equal(f.sd.conflict, null);
});
test('transient PUT failure retries from retained bytes and clears its own error', async () => {
  const f = await fixture(), it = f.item('one.pdf'); f.failPut.add(it.name); await f.select(it);
  assert.equal(f.sd.uploadError, true); assert.equal(f.view.attach[0], it);
  assert.equal(f.sd.note().text, 'An attachment could not be saved or opened. Remove it or reload the draft before sending.');
  f.failPut.clear(); await f.sd.retry();
  assert.equal(f.sd.uploadError, false); assert.equal(f.row().attachments.length, 1); assert.equal(f.ui.draft.value, 'Keep this caption');
});
test('removing one failed upload cannot clear another failed upload', async () => {
  const f = await fixture(), one = f.item('one.pdf'), two = f.item('two.pdf'); f.failPut.add(one.name); f.failPut.add(two.name);
  await f.select(one, two); await f.remove(one); assert.equal(f.sd.uploadError, true); assert.equal(f.view.attach[0], two);
  await f.sd.retry(); assert.equal(f.sd.uploadError, true); assert.equal(f.row().attachments.length, 0); assert.equal(f.counts.sends, 0);
});
test('remove while PUT is pending removes the saved item without orphaning it', async () => {
  const f = await fixture(), it = f.item('one.pdf'), gate = f.holdPut(), put = f.select(it); await tick();
  const removal = f.remove(it); gate.resolve(); await Promise.all([put, removal]);
  assert.equal(f.row().attachments.length, 0); assert.equal(f.view.attach?.length || 0, 0); assert.equal(f.sd.uploadError, false);
});
test('failed GET stays selectable/removable, never disappears silently', async () => {
  const f = await fixture(); f.failGet.add('broken'); f.remoteAttachments([{id: 'broken', name: 'broken.png', mime: 'image/png', bytes: 9}]);
  await f.sd.check(true); assert.equal(f.sd.loadError, true); assert.equal(f.view.attach[0].sid, 'broken');
  await f.remove(f.view.attach[0]); assert.equal(f.sd.loadError, false); assert.equal(f.row().attachments.length, 0);
});
test('retry opens a failed download without losing text or the healthy attachment', async () => {
  const f = await fixture(), healthy = f.item('healthy.pdf'); await f.select(healthy); f.failGet.add('broken');
  f.remoteAttachments([...f.row().attachments, {id: 'broken', name: 'broken.png', mime: 'image/png', bytes: 9}]);
  await f.sd.check(true); assert.equal(f.sd.loadError, true); f.failGet.clear(); await f.sd.retry();
  assert.equal(f.sd.loadError, false); assert.equal(f.view.attach.length, 2); assert.ok(f.view.attach.includes(healthy));
  assert.equal(f.ui.draft.value, 'Keep this caption');
});
test('failed DELETE restores the chip and blocks until removal succeeds', async () => {
  const f = await fixture(), it = f.item('one.pdf'); await f.select(it); f.failDelete(true); await f.remove(it);
  assert.equal(f.sd.loadError, true); assert.equal(f.view.attach[0], it); assert.equal(f.row().attachments.length, 1);
  f.failDelete(false); await f.sd.retry(); assert.equal(f.sd.loadError, false); assert.equal(f.row().attachments.length, 0);
});
test('late download cannot cross into another conversation', async () => {
  const f = await fixture(), gate = f.holdGet(); f.remoteAttachments([{id: 'slow', name: 'slow.png', mime: 'image/png', bytes: 9}]);
  const load = f.sd.check(true); await tick(); f.replaceView(); gate.resolve(); await load;
  assert.deepEqual(f.view.attach.map(a => a.name), ['bob-only']);
});
test('send barrier waits for pending upload and uses its final revision exactly once', async () => {
  const f = await fixture(), gate = f.holdPut(), upload = f.select(f.item('one.pdf')); await tick();
  f.sd.closeForSend(); gate.resolve(); await upload; await f.sd.afterSend();
  assert.equal(f.row(), null); assert.equal(f.counts.puts, 1); assert.equal(f.sd.loadError, false); assert.equal(f.sd.uploadError, false);
});
