// "N new messages" divider (Miguel, 6 Nov 2026: opening a chat with unread messages didn't show where to start
// reading). WhatsApp/Telegram/Beeper behaviour: the read position is taken when the chat opens, one divider sits
// right before the first unread incoming message, the chat opens parked on it, and the chat is marked read only once
// the owner has scrolled to the bottom. The divider stays until he leaves the chat.
// Stage: tests/unread_divider_stage.py (synthetic chats, real ViewServer + store). Every read/unread POST is answered
// here and recorded, so the stage stays unread for each run; the feed is answered here too so a test can inject a
// new message.
// AGENT_STAGE_DIR=<dir> python3 tests/unread_divider_stage.py <port> &  then  node tests/unread_divider_browser.cjs [outdir]
// SHOTS=<dir> also writes the parked Lena chat on Dark / Light / Landscapes Dark / Landscapes Light, phone + desktop.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR || '/home/oscar/.hermes/cache/scratch/unread-stage';
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
const out = path.resolve(process.argv[2] || process.env.EVIDENCE_DIR || dir); fs.mkdirSync(out, {recursive: true});
const SHOTS = process.env.SHOTS; if (SHOTS) fs.mkdirSync(SHOTS, {recursive: true});
const WEB = process.env.WIZARD_WEB_DIR;
const P = {
  dark: {scheme: 'dark', bg: '#000000', ink: '#f7f7f7', ink2: '#c4c4c4', ink3: '#8a8a8a', line2: 'rgba(255,255,255,.26)', accent: '#ffffff', on: '#000000', glass: '#000000'},
  light: {scheme: 'light', bg: '#ffffff', ink: '#000000', ink2: '#2e2e2e', ink3: '#6b6b6b', line2: 'rgba(0,0,0,.32)', accent: '#000000', on: '#ffffff', glass: '#ffffff'},
  landscapes: {scheme: 'dark', bg: '#0B0A10', ink: '#ffffff', ink2: 'rgba(255,255,255,.80)', ink3: 'rgba(255,255,255,.58)', line2: 'rgba(255,255,255,.28)', accent: '#7A5CFF', on: '#ffffff', glass: 'linear-gradient(160deg,#1d2a44,#4a3150 50%,#0b0a10)'},
  'landscapes-light': {scheme: 'light', bg: '#EEF1F4', ink: '#111216', ink2: 'rgba(17,18,22,.76)', ink3: 'rgba(17,18,22,.54)', line2: 'rgba(0,0,0,.26)', accent: '#5B3FE6', on: '#ffffff', glass: 'linear-gradient(160deg,#cfd8e3,#eef1f4 55%,#e6dccf)'},
};
const tokens = p => ({canvas: 'transparent', base: p.bg, surface: `color-mix(in srgb, ${p.ink} 6%, transparent)`, 'surface-raised': `color-mix(in srgb, ${p.ink} 10%, transparent)`,
  text: p.ink, 'text-secondary': p.ink2, 'text-muted': p.ink3, border: p.line2, accent: p.accent, 'accent-soft': `color-mix(in srgb, ${p.accent} 16%, transparent)`, 'on-accent': p.on});
const TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png'};
const ok = body => ({status: 200, contentType: 'application/json', body: JSON.stringify({ok: true, result: body})});

async function setup(browser, p, viewport) {
  const phone = viewport.width < 640;
  const ctx = await browser.newContext({viewport, deviceScaleFactor: 2, colorScheme: p.scheme, ...(phone ? {isMobile: true, hasTouch: true} : {})});
  await ctx.addCookies([{name: 'wizard_messenger_session', value: st.cookie, url: st.origin}]);
  await ctx.route('**/wizard-os-home/**', r => {
    const u = new URL(r.request().url());
    if (!WEB) return r.continue({url: 'http://127.0.0.1:8796' + u.pathname});
    const f = path.join(WEB, u.pathname.replace(/^\/wizard-os-home\//, ''));
    if (!fs.existsSync(f)) return r.fulfill({status: 404, body: ''});
    return r.fulfill({status: 200, contentType: TYPES[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f)});
  });
  const t = {reads: [], unreads: [], inject: []};
  await ctx.route(/\/api\/unified\/people\/[^/]+\/(read|unread)$/, r => {
    if (r.request().method() !== 'POST') return r.continue();
    const u = new URL(r.request().url()), id = decodeURIComponent(u.pathname.split('/').slice(-2)[0]);
    (u.pathname.endsWith('/unread') ? t.unreads : t.reads).push({id, body: r.request().postDataJSON(), at: Date.now()});
    return r.fulfill(ok({ok: true}));
  });
  // The feed: answered here (quiet, once a second) so nothing on the stage changes and a test can push a message.
  await ctx.route(/\/api\/unified\/updates/, async r => {
    if (!t.inject.length) await new Promise(res => setTimeout(res, 800));
    return r.fulfill(ok(t.inject.shift() || {seq: 0}));
  });
  await ctx.addInitScript(([scheme, tk, glass]) => {
    const mark = () => {
      const r = document.documentElement; if (!r) return false;
      r.dataset.wzHosted = ''; r.dataset.colorScheme = scheme; r.style.colorScheme = scheme;
      for (const [k, v] of Object.entries(tk)) r.style.setProperty('--wz-' + k, v);
      r.style.background = glass; return true;
    };
    if (!mark()) new MutationObserver((_, o) => { if (mark()) o.disconnect(); }).observe(document, {childList: true});
  }, [p.scheme, tokens(p), p.glass]);
  const page = await ctx.newPage(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(st.origin + '/');
  await page.locator('.u-person').first().waitFor({timeout: 20000});
  return Object.assign(t, {ctx, page, errors, phone});
}
async function open(t, name, settle = 1200) {
  const row = t.page.locator('.u-person', {hasText: name}).first();
  if (t.phone) await row.tap(); else await row.click();
  await t.page.locator('.u-thread-body .u-row').first().waitFor();
  await t.page.waitForTimeout(settle);
}
async function leave(t) {
  if (t.phone) await t.page.locator('.u-back').first().click();
  else { await t.page.keyboard.press('Escape'); await t.page.locator('#unified-inbox[data-detail=none]').waitFor({timeout: 5000}); }
  await t.page.waitForTimeout(500);
}
// Divider state: label, incoming rows after it, its offset from the top of the timeline, and whether we are at the bottom.
const look = page => page.evaluate(() => {
  const sc = document.querySelector('.u-timeline'), ds = sc.querySelectorAll('.u-unread-divider'), d = ds[0];
  const r = {count: ds.length, bottom: sc.scrollHeight - sc.scrollTop - sc.clientHeight < 80, height: sc.clientHeight};
  if (!d) return r;
  let after = 0, first = null;
  for (let e = d.nextElementSibling; e; e = e.nextElementSibling) if (e.classList.contains('u-row') && !e.classList.contains('outgoing')) { after++; first ??= e.querySelector('.bubble-text, .u-text, p')?.textContent || e.textContent; }
  const box = d.getBoundingClientRect(), top = sc.getBoundingClientRect().top;
  const span = d.querySelector('span'), cs = getComputedStyle(span);
  return {...r, label: d.textContent, after, first, offset: box.top - top, visible: box.top >= top && box.bottom <= top + sc.clientHeight,
    fontSize: cs.fontSize, color: cs.color, overflow: sc.scrollWidth > sc.clientWidth + 1};
});
const toBottom = async page => { await page.evaluate(() => { const sc = document.querySelector('.u-timeline'); sc.scrollTop = sc.scrollHeight; }); await page.waitForTimeout(900); };
const readsFor = (t, id) => t.reads.filter(r => r.id === id);
const rowUnread = (t, name) => t.page.evaluate(n => { const r = [...document.querySelectorAll('.u-person')].find(e => e.textContent.includes(n)); return r ? r.classList.contains('unread') : null; }, name);

async function scenario(browser, viewport) {
  const tag = viewport.width < 640 ? 'phone' : 'desktop', t = await setup(browser, P.dark, viewport), {page} = t, results = [];
  const check = (name, fn) => results.push(name) && fn;
  // 1. Lena: 25 unread, taller than the window. Parks at the divider, no read until the bottom.
  await open(t, 'Lena');
  let v = await look(page);
  assert.equal(v.count, 1, tag + ' Lena: one divider'); assert.equal(v.label, '25 new messages'); assert.equal(v.after, 25, tag + ' Lena: 25 incoming rows after the divider');
  assert.ok(v.visible && v.offset >= 0 && v.offset < v.height * 0.25, tag + ' Lena: divider parked near the top, got offset ' + v.offset + ' of ' + v.height);
  assert.equal(v.bottom, false, tag + ' Lena: not scrolled to the bottom');
  assert.equal(v.fontSize, '12px'); assert.equal(v.overflow, false);
  await page.waitForTimeout(1200);
  assert.equal(readsFor(t, st.lena).length, 0, tag + ' Lena: no read call while parked at the divider');
  check('Lena parks at "25 new messages", no read while parked');
  await toBottom(page);
  assert.equal(readsFor(t, st.lena).length, 1, tag + ' Lena: read fires once at the bottom');
  v = await look(page); assert.equal(v.count, 1, tag + ' Lena: divider stays after reading'); assert.equal(v.label, '25 new messages');
  if (!t.phone) assert.equal(await rowUnread(t, 'Lena'), false, tag + ' Lena: list row no longer unread');
  check('read fires at the bottom, divider stays, row clears');
  // A new message while at the bottom: no second divider, the old one does not move, read follows the new one.
  const thread = await page.evaluate(async id => (await (await fetch('api/unified/people/' + id + '?limit=1')).json()).result, st.lena);
  const last = thread.messages[thread.messages.length - 1];
  const fresh = {...last, id: last.id + '-new', timestamp: Date.now(), original: 'One more thing', text: 'One more thing', translated: null};
  t.inject.push({seq: 1e9, people: [{...thread.person, unread: 1}], messages: {[st.lena]: [fresh]}});
  await page.waitForTimeout(2200);
  v = await look(page);
  assert.equal(v.count, 1, tag + ' new message: still one divider'); assert.equal(v.after, 26, tag + ' new message: divider did not move'); assert.equal(v.label, '25 new messages');
  assert.equal(readsFor(t, st.lena).length, 2, tag + ' new message at the bottom: read follows');
  check('new message at the bottom: no new divider, read follows');
  await leave(t);
  if (t.phone) assert.equal(await rowUnread(t, 'Lena'), false, tag + ' Lena: list row no longer unread after Back');
  await open(t, 'Lena'); v = await look(page);
  assert.equal(v.count, 0, tag + ' Lena reopened: no divider'); assert.equal(v.bottom, true, tag + ' Lena reopened: at the bottom');
  check('reopened read chat: no divider, at the bottom');
  await leave(t);
  // 2. Cora: already read, no divider.
  await open(t, 'Cora'); v = await look(page);
  assert.equal(v.count, 0, tag + ' Cora: no divider'); assert.equal(v.bottom, true);
  await page.waitForTimeout(600); assert.equal(readsFor(t, st.cora).length, 0, tag + ' Cora: nothing to read');
  check('read chat: no divider'); await leave(t);
  // 3. Bram: 2 unread that fit on screen: divider, bottom as before, read at once.
  await open(t, 'Bram'); v = await look(page);
  assert.equal(v.label, '2 new messages'); assert.equal(v.after, 2); assert.equal(v.bottom, true, tag + ' Bram: fits, shows the bottom');
  assert.equal(readsFor(t, st.bram).length, 1, tag + ' Bram: read at once');
  check('2 unread that fit: divider, bottom, read at once'); await leave(t);
  // 4. Dan: 150 unread, older than the first page: older pages load until the first unread.
  await open(t, 'Dan', 3000); v = await look(page);
  assert.equal(v.label, '150 new messages'); assert.equal(v.after, 150, tag + ' Dan: first unread reached through older pages');
  assert.ok(v.visible && v.offset < v.height * 0.25, tag + ' Dan: divider parked near the top'); assert.equal(readsFor(t, st.dan).length, 0);
  check('150 unread beyond the first page: older pages load, parks'); await leave(t);
  // 5. Group, 6. merged WhatsApp+Telegram (the server count, not the newest read mark), 7. Wizard chat.
  for (const [name, id, n] of [['Family', st.family, 18], ['Mia', st.mia, 12], ['Noor', st.noor, 20]]) {
    await open(t, name); v = await look(page);
    assert.equal(v.count, 1, tag + ' ' + name + ': one divider'); assert.equal(v.label, n + ' new messages'); assert.equal(v.after, n, tag + ' ' + name + ': rows after divider');
    if (!v.bottom) { assert.equal(readsFor(t, id).length, 0, tag + ' ' + name + ': no read while parked'); await toBottom(page); }
    assert.equal(readsFor(t, id).length, 1, tag + ' ' + name + ': read once at the bottom');
    check(name + ': ' + n + ' new messages, read at the bottom'); await leave(t);
  }
  // 8. Mark as unread (thread ⋯) on Cora: reopening shows the divider before the last incoming message.
  await open(t, 'Cora');
  await page.getByRole('button', {name: 'Chat options'}).first().click();
  await page.getByRole('menuitem', {name: 'Mark as unread'}).click();
  await page.waitForTimeout(800);
  assert.equal(t.unreads.filter(r => r.id === st.cora).length, 1, tag + ' Cora: unread POST');
  if (await page.locator('.u-timeline').count()) await leave(t);
  await open(t, 'Cora'); v = await look(page);
  assert.equal(v.label, '1 new message', tag + ' Cora after Mark as unread'); assert.equal(v.after, 1);
  check('Mark as unread → "1 new message" before the last message');
  assert.deepEqual(t.errors, [], tag + ' page errors');
  await t.ctx.close();
  return {tag, results};
}

async function shots(browser) {
  for (const [skin, p] of Object.entries(P)) for (const viewport of [{width: 390, height: 844}, {width: 1280, height: 800}]) {
    const t = await setup(browser, p, viewport), tag = viewport.width < 640 ? 'phone' : 'desktop';
    await open(t, 'Lena'); await t.page.mouse.move(1, 1);
    const v = await look(t.page); assert.equal(v.label, '25 new messages', skin + ' ' + tag);
    await t.page.screenshot({path: path.join(SHOTS, `unread-divider-${skin}-${tag}.png`)});
    await t.ctx.close();
  }
}

(async () => {
  const browser = await chromium.launch();
  try {
    const report = [];
    report.push(await scenario(browser, {width: 390, height: 844}));
    report.push(await scenario(browser, {width: 1280, height: 800}));
    if (SHOTS) await shots(browser);
    fs.writeFileSync(path.join(out, 'unread-divider-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 1)); console.log('unread divider: ok');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
