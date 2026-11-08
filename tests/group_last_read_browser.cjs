// James, 6 Nov 2026: "when I open a group chat, it seems to scroll all the way to the bottom. It shouldn't do that.
// It should show me where my last read message is and start the reading there."
// Opening a group with more unread than fits lands on the "N new messages" divider (first unread), not the bottom,
// and stays there while photos load in, a new message or a late backfill arrives, the phone's visual viewport
// resizes, or the desktop window crosses the split width. Telegram, Signal, WhatsApp and LINE groups, phone and
// desktop, inside a real Wizard shell host on two real skins (Nebula and Signal). Synthetic data only.
// Stage: AGENT_STAGE_DIR=<dir> python3 tests/group_last_read_stage.py <port> &
// Run:   AGENT_STAGE_DIR=<dir> SHELL_DIR=<wizard-ux web dir> node tests/group_last_read_browser.cjs <outdir>
// Every group's newest message shares one timestamp on purpose: reading one chat must not stop the next from reading.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR, shell = process.env.SHELL_DIR;
assert(dir && shell, 'AGENT_STAGE_DIR and SHELL_DIR are required');
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
const out = path.resolve(process.argv[2] || path.join(dir, 'evidence')); fs.mkdirSync(out, {recursive: true});
const src = fs.readFileSync(path.join(shell, 'core/skins.js'), 'utf8');
const table = src.slice(src.indexOf('  const SKINS = ['), src.indexOf('  // Each skin'));
const palettes = vm.runInNewContext('const T=o=>o;' + table + ';SKINS').filter(s => ['nebula', 'signal'].includes(s.id)).map(s => ({id: s.id, t: s.t}));
assert.equal(palettes.length, 2, 'real Nebula and Signal skins');
const host = skin => `<!doctype html><html data-skin="${skin}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/wizard-os-home/core/skins.css"><script>window.WizCore={apps:()=>({APPS:[{url:'/'}]})};window.setFixtureSkin=id=>{const s=JSON.parse(atob('${Buffer.from(JSON.stringify(palettes)).toString('base64')}')).find(s=>s.id===id);for(const[k,v]of Object.entries(s.t))document.documentElement.style.setProperty('--'+k,v);document.documentElement.dataset.skin=id;window.WizAppearance?.sync()};setFixtureSkin('${skin}')</script><script src="/wizard-os-home/core/appearance-host.js" defer></script><style>html,body{margin:0;height:100%;background:var(--bg)}iframe{width:100%;height:100%;border:0;display:block}</style></head><body><iframe src="/" title="Messenger"></iframe></body></html>`;
const TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png', '.woff2': 'font/woff2'};
const ok = body => ({status: 200, contentType: 'application/json', body: JSON.stringify({ok: true, result: body})});
// A tall photo, delivered 1.5 s late so it lands after the chat has parked on the divider.
const PHOTO = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="640"><rect width="400" height="640" fill="#6a8caf"/><circle cx="200" cy="260" r="90" fill="#f4d35e"/></svg>';

async function setup(browser, skin, viewport) {
  const phone = viewport.width < 640;
  const ctx = await browser.newContext({viewport, deviceScaleFactor: 1, ...(phone ? {isMobile: true, hasTouch: true} : {})});
  await ctx.addCookies([{name: 'wizard_messenger_session', value: st.cookie, url: st.origin}]);
  const t = {reads: [], unreads: [], inject: [], media: 0, phone};
  await ctx.route(u => new URL(u).pathname === '/__host', r => r.fulfill({status: 200, contentType: 'text/html', body: host(skin)}));
  await ctx.route('**/wizard-os-home/**', r => {
    const f = path.join(shell, new URL(r.request().url()).pathname.replace(/^\/wizard-os-home\//, ''));
    if (!fs.existsSync(f) || !fs.statSync(f).isFile()) return r.fulfill({status: 404, body: ''});
    return r.fulfill({status: 200, contentType: TYPES[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f)});
  });
  await ctx.route(/\/api\/unified\/people\/[^/]+\/(read|unread)$/, r => {
    if (r.request().method() !== 'POST') return r.continue();
    const u = new URL(r.request().url()), id = decodeURIComponent(u.pathname.split('/').slice(-2)[0]);
    (u.pathname.endsWith('/unread') ? t.unreads : t.reads).push({id, at: Date.now()});
    return r.fulfill(ok({ok: true}));
  });
  await ctx.route(/\/api\/unified\/updates/, async r => {
    if (!t.inject.length) await new Promise(res => setTimeout(res, 700));
    return r.fulfill(ok(t.inject.shift() || {seq: 0}));
  });
  await ctx.route(/\/api\/unified\/media\//, async r => { t.media++; await new Promise(res => setTimeout(res, 1500)); return r.fulfill({status: 200, contentType: 'image/svg+xml', body: PHOTO}); });
  const page = await ctx.newPage(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(st.origin + '/__host');
  const f = page.frameLocator('iframe');
  await f.locator('.u-person').first().waitFor({timeout: 30000});
  return Object.assign(t, {ctx, page, f, errors, frame: () => page.frames().find(x => x !== page.mainFrame())});
}
async function open(t, label, settle = 2600) {
  const row = t.f.locator('.u-person', {hasText: label}).first();
  if (t.phone) await row.tap(); else await row.click();
  await t.f.locator('.u-thread-body .u-row').first().waitFor();
  await t.page.waitForTimeout(settle);
}
async function leave(t) {
  if (t.phone) await t.f.locator('.u-back').first().click();
  else { await t.page.keyboard.press('Escape'); await t.f.locator('#unified-inbox[data-detail=none]').waitFor({timeout: 5000}); }
  await t.page.waitForTimeout(500);
}
const look = t => t.frame().evaluate(() => {
  const sc = document.querySelector('.u-timeline'), ds = sc.querySelectorAll('.u-unread-divider'), d = ds[0];
  const r = {count: ds.length, bottom: sc.scrollHeight - sc.scrollTop - sc.clientHeight < 80, height: sc.clientHeight, scrollTop: Math.round(sc.scrollTop), scrollHeight: sc.scrollHeight,
    photos: sc.querySelectorAll('img.in').length};
  if (!d) return r;
  let after = 0; for (let e = d.nextElementSibling; e; e = e.nextElementSibling) if (e.classList.contains('u-row') && !e.classList.contains('outgoing')) after++;
  const box = d.getBoundingClientRect(), top = sc.getBoundingClientRect().top;
  return {...r, label: d.textContent, after, offset: Math.round(box.top - top), visible: box.top >= top && box.bottom <= top + sc.clientHeight};
});
const steps = [];
const parked = (v, what) => {
  steps.push([what, Date.now()]);
  assert.equal(v.count, 1, what + ': one divider ' + JSON.stringify(v));
  assert.ok(v.visible, what + ': divider on screen ' + JSON.stringify(v));
  assert.equal(v.bottom, false, what + ': not scrolled to the bottom ' + JSON.stringify(v));
};
const readsFor = (t, id) => t.reads.filter(r => r.id === id).length;
async function thread(t, id) { return t.frame().evaluate(async id => (await (await fetch('api/unified/people/' + id + '?limit=60')).json()).result, id); }

async function full(browser, viewport) {
  const tag = viewport.width < 640 ? 'phone' : 'desktop', t = await setup(browser, 'nebula', viewport), results = [];
  for (const key of (process.env.LAST_READ_GROUPS || 'climbing,signal,ferry,tokyo,big').split(',')) {
    const g = {...st.groups[key]}, what = `${tag} ${g.network} ${g.label}`;
    // The chat id the inbox lists (a Signal group's person can be re-keyed by the store), never the staging guess.
    g.id = await t.frame().evaluate(async label => { const r = (await (await fetch('api/unified/groups')).json()).result; return (r.groups || r.people || []).find(p => p.display_name === label)?.id; }, g.label);
    assert.ok(g.id, what + ': listed');
    await open(t, g.label, key === 'big' ? 4500 : 2600);
    let v = await look(t);
    parked(v, what + ' opened');
    assert.equal(v.label, g.unread + ' new messages', what); assert.equal(v.after, g.unread, what + ': divider before the first unread');
    assert.ok(v.offset < v.height * 0.35, what + ': divider near the top, got ' + v.offset + '/' + v.height);
    assert.equal(readsFor(t, g.id), 0, what + ': not marked read while parked');
    if (['climbing', 'signal', 'tokyo'].includes(key)) assert.ok(t.media > 0, what + ': photos requested');
    const start = v.offset;
    await t.page.waitForTimeout(1800); v = await look(t); parked(v, what + ' after photos loaded in');
    // A new message arrives while parked.
    const th = await thread(t, g.id), last = th.messages[th.messages.length - 1];
    t.inject.push({seq: 1e9 + results.length * 10 + 1, people: [{...th.person, unread: g.unread + 1}], messages: {[g.id]: [{...last, id: last.id + '-new', timestamp: Date.now(), original: 'Just arrived', text: 'Just arrived', translated: null, media: null, msgtype: 'm.text'}]}});
    await t.page.waitForTimeout(2200); v = await look(t); parked(v, what + ' after a new message');
    // A late backfill lands above the divider (older than the read mark).
    const older = th.messages.filter(m => !m.outgoing)[2] || th.messages[0];
    t.inject.push({seq: 1e9 + results.length * 10 + 2, people: [{...th.person, unread: g.unread + 1}], messages: {[g.id]: [0, 1, 2].map(i => ({...older, id: older.id + '-late' + i, timestamp: older.timestamp + 1 + i, original: 'Backfilled ' + i, text: 'Backfilled ' + i, translated: null, media: null, msgtype: 'm.text'}))}});
    await t.page.waitForTimeout(2200); v = await look(t); parked(v, what + ' after a late backfill');
    if (t.phone) {
      await t.page.setViewportSize({width: viewport.width, height: viewport.height - 300}); await t.page.waitForTimeout(500);
      await t.page.setViewportSize(viewport); await t.page.waitForTimeout(700);
      v = await look(t); parked(v, what + ' after the visual viewport resized');
    } else {
      await t.page.setViewportSize({width: 600, height: viewport.height}); await t.page.waitForTimeout(700);
      await t.page.setViewportSize(viewport); await t.page.waitForTimeout(900);
      v = await look(t); parked(v, what + ' after the window crossed the split width');
    }
    // The server resets the feed (store rebuilt): the open chat reloads and parks on the divider again.
    t.inject.push({reset: true, seq: 1});
    await t.page.waitForTimeout(key === 'big' ? 5000 : 3000); v = await look(t); parked(v, what + ' after the feed reset');
    assert.equal(v.label, g.unread + ' new messages', what + ' after the feed reset');
    assert.equal(readsFor(t, g.id), 0, what + ': still unread ' + JSON.stringify({steps: steps.slice(-6), reads: t.reads.slice(-3)}));
    if (key === 'climbing') await t.page.screenshot({path: path.join(out, `group-last-read-${tag}-nebula-${key}.png`)});
    await leave(t);
    await open(t, g.label); v = await look(t); parked(v, what + ' reopened while still unread');
    // The owner reads down to the newest (photos may still be growing the timeline): then, and only then, it is read.
    for (let i = 0; i < 8 && !readsFor(t, g.id); i++) { await t.frame().evaluate(() => { const sc = document.querySelector('.u-timeline'); sc.scrollTop = sc.scrollHeight; }); await t.page.waitForTimeout(500); }
    if (readsFor(t, g.id) !== 1) console.error('diagnostic', what, await t.page.screenshot({path: path.join(out, 'diag-' + key + '-' + tag + '.png')}).then(() => ''), JSON.stringify({steps, heads: await t.frame().evaluate(() => [...document.querySelectorAll('.u-who-text, .u-timeline')].map(e => e.className + ':' + (e.className.includes('u-who') ? e.textContent : e.isConnected + '/' + e.offsetParent?.className))),gid: g.id, readWho: await Promise.all(t.reads.map(r => t.frame().evaluate(async id => (await (await fetch('api/unified/people/' + id + '?limit=1')).json()).result?.person?.display_name, r.id))), reads: t.reads, view: await look(t), hidden: await t.frame().evaluate(() => document.hidden)}));
    assert.equal(readsFor(t, g.id), 1, what + ': read once the owner reaches the bottom');
    results.push({group: g.label, network: g.network, tag, startOffset: start, height: v.height});
    await leave(t);
  }
  assert.deepEqual(t.errors, [], tag + ' page errors');
  await t.ctx.close();
  return results;
}
async function skinShot(browser, viewport) {
  const tag = viewport.width < 640 ? 'phone' : 'desktop', t = await setup(browser, 'signal', viewport), g = st.groups.tokyo;
  await open(t, g.label); const v = await look(t); parked(v, tag + ' signal skin ' + g.label);
  await t.page.screenshot({path: path.join(out, `group-last-read-${tag}-signal-tokyo.png`)});
  await t.ctx.close(); return {tag, skin: 'signal', group: g.label, offset: v.offset};
}
module.exports = {setup, open, look};
if (require.main === module) (async () => {
  const browser = await chromium.launch({args: ['--no-sandbox']});
  try {
    const report = [];
    for (const viewport of [{width: 390, height: 844}, {width: 1280, height: 800}].filter(v => !process.env.ONLY || process.env.ONLY === (v.width < 640 ? 'phone' : 'desktop'))) report.push(...await full(browser, viewport), await skinShot(browser, viewport));
    fs.writeFileSync(path.join(out, 'group-last-read-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 1)); console.log('group last read: ok');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
