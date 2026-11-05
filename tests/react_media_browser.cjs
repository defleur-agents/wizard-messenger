// Reactions on media (Miguel, 5 Nov 2026: "I received a GIF but I wasn't able to react to it").
// Since 16.16 GIFs, stickers and uncaptioned photos are drawn without bubble chrome, so the whole message is media;
// right-click (desktop) and a long-press (phone) on it must open the message menu with the reaction strip, exactly
// like a text bubble, while a tap still opens the viewer (photos), plays a held GIF, or does nothing (stickers).
// Same staged server as incoming_media_browser (tests/incoming_media_stage.py, synthetic chats, mx mocked).
// Checks on Dark / Light / Landscapes light at 390 (touch) and 1280 (mouse):
//  - an incoming reaction on a GIF renders as a chip under the bubble-less media;
//  - right-click / long-press on a GIF, a sticker and an uncaptioned photo opens .u-menu with .u-quick (no native menu,
//    no viewer, no selection mode); picking an emoji POSTs messages/<id>/react and a mine chip renders under the media;
//  - a long-press on a text bubble still starts selection (unchanged), a tap on the photo still opens the viewer.
// AGENT_STAGE_DIR=<dir> python3 tests/incoming_media_stage.py <port> &  then  node tests/react_media_browser.cjs [outdir]
// SHOTS=<dir> also writes menu-on-GIF screenshots for Landscapes light.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR || '/home/oscar/.hermes/cache/scratch/incoming-stage';
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
const out = path.resolve(process.argv[2] || process.env.EVIDENCE_DIR || dir); fs.mkdirSync(out, {recursive: true});
const SHOTS = process.env.SHOTS; if (SHOTS) fs.mkdirSync(SHOTS, {recursive: true});
const WEB = process.env.WIZARD_WEB_DIR;
const P = {
  dark: {scheme: 'dark', bg: '#000000', ink: '#f7f7f7', ink2: '#c4c4c4', ink3: '#8a8a8a', line2: 'rgba(255,255,255,.26)', accent: '#ffffff', on: '#000000', glass: '#141414'},
  light: {scheme: 'light', bg: '#ffffff', ink: '#000000', ink2: '#2e2e2e', ink3: '#6b6b6b', line2: 'rgba(0,0,0,.32)', accent: '#000000', on: '#ffffff', glass: '#f0f0f0'},
  'landscapes-light': {scheme: 'light', bg: '#EEF1F4', ink: '#111216', ink2: 'rgba(17,18,22,.76)', ink3: 'rgba(17,18,22,.54)', line2: 'rgba(0,0,0,.26)', accent: '#5B3FE6', on: '#ffffff', glass: 'linear-gradient(160deg,#cfd8e3,#eef1f4 55%,#e6dccf)'},
};
const tokens = p => ({canvas: 'transparent', base: p.bg, surface: `color-mix(in srgb, ${p.ink} 6%, transparent)`, 'surface-raised': `color-mix(in srgb, ${p.ink} 10%, transparent)`,
  text: p.ink, 'text-secondary': p.ink2, 'text-muted': p.ink3, border: p.line2, accent: p.accent, 'accent-soft': `color-mix(in srgb, ${p.accent} 16%, transparent)`, 'on-accent': p.on});
const TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png'};

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
  await ctx.addInitScript(([scheme, t, glass]) => {
    const mark = () => {
      const r = document.documentElement; if (!r) return false;
      r.dataset.wzHosted = ''; r.dataset.colorScheme = scheme; r.style.colorScheme = scheme;
      for (const [k, v] of Object.entries(t)) r.style.setProperty('--wz-' + k, v);
      r.style.background = glass; return true;
    };
    if (!mark()) new MutationObserver((_, o) => { if (mark()) o.disconnect(); }).observe(document, {childList: true});
    // Record whether the native context menu would have shown (a listener on window runs after the bubble's).
    window.__native = 0; addEventListener('contextmenu', e => { if (!e.defaultPrevented) window.__native++; });
  }, [p.scheme, tokens(p), p.glass]);
  const page = await ctx.newPage(), errors = [], reacts = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => { if (/\/react$/.test(new URL(r.url()).pathname) && r.request().method() === 'POST') reacts.push({url: decodeURIComponent(r.url()), status: r.status()}); });
  await page.goto(st.origin + '/');
  await page.locator('.u-person').first().waitFor({timeout: 20000});
  const cdp = phone ? await ctx.newCDPSession(page) : null;
  return {ctx, page, errors, reacts, phone, cdp};
}
const open = async (page, phone, name) => {
  const row = page.locator('.u-person', {hasText: name}).first();
  if (phone) await row.tap(); else await row.click();
  await page.locator('.u-thread-body .u-row').first().waitFor();
  await page.waitForTimeout(900);
};
// WizardApp.media is frozen; standalone, its view() opens the photo with window.open, so count those calls.
const stubViewer = page => page.evaluate(() => { window.__viewed = 0; window.open = () => { window.__viewed++; return null; }; });
const centre = async loc => { await loc.evaluate(e => e.scrollIntoView({block: 'center'})); await loc.page().waitForTimeout(250); const b = await loc.boundingBox(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; };
// A real finger hold: CDP touch events produce touch + pointer events and the hold's own contextmenu on release.
async function hold(cdp, page, at, ms = 700) {
  await cdp.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [{x: at.x, y: at.y}]});
  await page.waitForTimeout(ms);
  await cdp.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  await page.waitForTimeout(250);
}
async function openMenuOn(t, loc) {
  const {page, phone, cdp} = t, at = await centre(loc);
  if (phone) await hold(cdp, page, at); else { await page.mouse.click(at.x, at.y, {button: 'right'}); await page.waitForTimeout(200); }
}
async function reactOn(t, id, tag) {
  const {page} = t, row = page.locator(`.u-row[data-id="${id}"]`);
  await stubViewer(page); const native0 = await page.evaluate(() => window.__native);
  await openMenuOn(t, row.locator('.u-media'));
  const quick = page.locator('.u-menu .u-quick');
  await quick.waitFor({timeout: 3000}).catch(() => {});
  assert.equal(await quick.count(), 1, `${tag} ${id}: menu with reactions opens on the media`);
  assert.ok(await quick.locator('.u-qr-btn').count() >= 6, `${tag} ${id}: reaction strip has emoji`);
  assert.ok(await page.locator('.u-menu .u-act', {hasText: 'Reply'}).count() === 1, `${tag} ${id}: Reply in the media menu`);
  assert.ok(await page.locator('.u-menu .u-act', {hasText: 'Select'}).count() >= 1, `${tag} ${id}: Select in the media menu`);
  assert.equal(await page.evaluate(() => window.__viewed), 0, `${tag} ${id}: hold/right-click opens no viewer`);
  assert.equal(await page.evaluate(() => window.__native), native0, `${tag} ${id}: native context menu suppressed`);
  assert.equal(await page.locator('.u-selection:not([hidden])').count(), 0, `${tag} ${id}: not selection mode`);
  // Let the menu settle after the release (a phone's lifted finger must not close it).
  await page.waitForTimeout(300);
  assert.equal(await page.locator('.u-menu .u-quick').count(), 1, `${tag} ${id}: menu stays open after release`);
  const pick = quick.locator('.u-qr-btn:not(.mine):not(.more)').first(), key = (await pick.innerText()).trim();
  const n0 = t.reacts.length;
  if (t.phone) await pick.tap(); else await pick.click();
  for (let i = 0; i < 40 && t.reacts.length === n0; i++) await page.waitForTimeout(100);
  assert.equal(t.reacts.length, n0 + 1, `${tag} ${id}: one react POST`);
  assert.ok(t.reacts.at(-1).url.includes(`/messages/${id}/react`) && t.reacts.at(-1).status === 200, `${tag} ${id}: POST messages/<id>/react 200`);
  const chip = row.locator('.u-reactions .u-react.mine');
  await chip.waitFor({timeout: 3000});
  assert.ok((await chip.innerText()).startsWith(key), `${tag} ${id}: own ${key} chip renders`);
  await chipPlacement(page, id, tag);
  return key;
}
// The chip strip sits just under the bubble-less media, inside the row, never far below or on top of it.
async function chipPlacement(page, id, tag) {
  const g = await page.evaluate(id => {
    const row = document.querySelector(`.u-row[data-id="${CSS.escape(id)}"]`), m = row.querySelector('.u-media').getBoundingClientRect();
    const s = row.querySelector('.u-reactions').getBoundingClientRect(), r = row.getBoundingClientRect();
    return {mb: m.bottom, ml: m.left, mr: m.right, st: s.top, sb: s.bottom, sl: s.left, sr: s.right, rl: r.left, rr: r.right, h: s.height};
  }, id);
  assert.ok(g.h > 10, `${tag} ${id}: chip strip visible`);
  assert.ok(g.st >= g.mb - 14 && g.st <= g.mb + 8, `${tag} ${id}: chips tucked under the media (${Math.round(g.st - g.mb)}px)`);
  assert.ok(g.sl >= g.rl - 1 && g.sr <= g.rr + 1, `${tag} ${id}: chips inside the row`);
  assert.ok(g.sl < g.mr && g.sr > g.ml, `${tag} ${id}: chips under the media, not beside it`);
}

(async () => {
  const browser = await chromium.launch();
  for (const [skin, p] of Object.entries(P)) for (const viewport of [{width: 390, height: 844}, {width: 1280, height: 860}]) {
    const tag = skin + '-' + viewport.width;
    const t = await setup(browser, p, viewport), {ctx, page, errors, phone} = t;
    await open(page, phone, 'Family');
    // Incoming reaction on the bubble-less GIF shows as a chip under it.
    const heart = page.locator('.u-row[data-id="$gif"] .u-reactions .u-react', {hasText: '❤️'});
    assert.equal(await heart.count(), 1, tag + ' incoming ❤️ on the GIF renders');
    await page.locator('.u-row[data-id="$gif"] .u-media').evaluate(e => e.scrollIntoView({block: 'center'}));
    await chipPlacement(page, '$gif', tag + ' incoming');
    // Screenshot the menu on the GIF (Landscapes light), then close it without reacting.
    if (SHOTS && skin === 'landscapes-light') {
      await openMenuOn(t, page.locator('.u-row[data-id="$gif"] .u-media'));
      await page.locator('.u-menu .u-quick').waitFor();
      await page.mouse.move(2, 2); await page.waitForTimeout(250);
      await page.screenshot({path: path.join(SHOTS, `menu-on-gif-landscapes-light-${viewport.width}.png`)});
      await page.keyboard.press('Escape'); await page.waitForTimeout(250);
      assert.equal(await page.locator('.u-menu').count(), 0);
    }
    await reactOn(t, '$gif', tag);
    await reactOn(t, '$photo', tag);
    // Tap on the photo still opens the viewer (no menu).
    await stubViewer(page);
    const photo = page.locator('.u-row[data-id="$photo"] .u-media'); await centre(photo);
    if (phone) await photo.tap(); else await photo.click();
    await page.waitForTimeout(300);
    assert.equal(await page.evaluate(() => window.__viewed), 1, tag + ' tap on the photo opens the viewer');
    assert.equal(await page.locator('.u-menu').count(), 0, tag + ' tap on the photo opens no menu');
    // Text bubble hold is unchanged on a phone: it starts selection (right-click on desktop opens the menu).
    const text = page.locator('.u-row[data-id="$f5"] .u-text');
    if (phone) {
      await hold(t.cdp, page, await centre(text));
      assert.equal(await page.locator('.u-selection:not([hidden])').count(), 1, tag + ' text hold still selects');
      assert.equal(await page.locator('.u-menu').count(), 0, tag + ' text hold opens no menu');
      await page.locator('.u-selection button', {hasText: 'Cancel'}).tap(); await page.waitForTimeout(200);
    } else {
      const at = await centre(text); await page.mouse.click(at.x, at.y, {button: 'right'}); await page.waitForTimeout(200);
      assert.equal(await page.locator('.u-menu .u-quick').count(), 1, tag + ' text right-click menu');
      await page.keyboard.press('Escape'); await page.waitForTimeout(200);
    }
    if (SHOTS && skin === 'landscapes-light') { await page.locator('.u-row[data-id="$gif"] .u-media').evaluate(e => e.scrollIntoView({block: 'center'})); await page.mouse.move(2, 2); await page.waitForTimeout(250); await page.screenshot({path: path.join(SHOTS, `reacted-gif-photo-landscapes-light-${viewport.width}.png`)}); }
    // Sticker (Telegram, chrome-less).
    if (phone) { await page.locator('.u-back').first().tap(); await page.locator('.u-person').first().waitFor(); }
    await open(page, phone, 'Wizard devs');
    await reactOn(t, '$sticker', tag);
    await stubViewer(page);
    const stk = page.locator('.u-row[data-id="$sticker"] .u-media'); await centre(stk);
    if (phone) await stk.tap(); else await stk.click();
    await page.waitForTimeout(300);
    assert.equal(await page.evaluate(() => window.__viewed), 0, tag + ' tap on a sticker opens no viewer');
    if (await page.locator('.u-menu').count()) { await page.keyboard.press('Escape'); await page.waitForTimeout(200); }
    await page.mouse.move(2, 2);
    await page.screenshot({path: path.join(out, `react-media-${tag}-sticker.png`)});
    assert.ok(await page.evaluate(() => { const b = document.querySelector('.u-thread-body'); return b && b.scrollWidth <= b.clientWidth + 1; }), tag + ' no sideways overflow');
    assert.deepEqual(errors, [], tag + ' page errors');
    await ctx.close();
    console.log('ok', tag);
  }
  await browser.close();
  console.log('PASS react_media_browser: right-click / long-press on GIF, sticker and uncaptioned photo opens the reaction menu, react POST + chip, incoming chip under media, tap = viewer, text hold unchanged; 3 skins x 390/1280');
})().catch(e => { console.error('FAIL', e); process.exit(1); });
