// Incoming media display (Miguel, 4 Nov 2026: "I can't see GIFs/photos people send", "something's wrong with the tags").
// Disposable ViewServer + real unified store fed through the real ingest path (tests/incoming_media_stage.py).
// Checks, on Dark / Light / Landscapes light at 390 and 1280:
//  - a WhatsApp GIF (m.video + fi.mau.gif) autoplays muted + looped inline, with a GIF tag and no ▶ / duration,
//    pauses while off screen and plays once scrolled into view; with reduced motion it holds still until tapped;
//  - a Telegram animated sticker plays chrome-less (no bubble, no viewer on tap);
//  - a static image/gif is served as the GIF itself (not a still thumbnail);
//  - @mentions show the best known name as a chip (owner's own mention highlighted), never " (WA)";
//  - expired WhatsApp media shows a quiet placeholder, never the bridge's "Failed to bridge…" sentence,
//    in the bubble and the chat-list preview; a decrypt-retry edit shows its photo;
//  - **bold** / `code` render as formatting, not literal asterisks.
// AGENT_STAGE_DIR=<dir> python3 tests/incoming_media_stage.py <port> &  then  node tests/incoming_media_browser.cjs [outdir]
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR || '/home/oscar/.hermes/cache/scratch/incoming-stage';
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
const out = path.resolve(process.argv[2] || process.env.EVIDENCE_DIR || dir); fs.mkdirSync(out, {recursive: true});
const WEB = process.env.WIZARD_WEB_DIR;  // optional shell checkout serving /wizard-os-home/ (else the box's :8796)
const P = {
  dark: {scheme: 'dark', bg: '#000000', ink: '#f7f7f7', ink2: '#c4c4c4', ink3: '#8a8a8a', line2: 'rgba(255,255,255,.26)', accent: '#ffffff', on: '#000000', glass: '#141414'},
  light: {scheme: 'light', bg: '#ffffff', ink: '#000000', ink2: '#2e2e2e', ink3: '#6b6b6b', line2: 'rgba(0,0,0,.32)', accent: '#000000', on: '#ffffff', glass: '#f0f0f0'},
  'landscapes-light': {scheme: 'light', bg: '#EEF1F4', ink: '#111216', ink2: 'rgba(17,18,22,.76)', ink3: 'rgba(17,18,22,.54)', line2: 'rgba(0,0,0,.26)', accent: '#5B3FE6', on: '#ffffff', glass: 'linear-gradient(160deg,#cfd8e3,#eef1f4 55%,#e6dccf)'},
};
const tokens = p => ({canvas: 'transparent', base: p.bg, surface: `color-mix(in srgb, ${p.ink} 6%, transparent)`, 'surface-raised': `color-mix(in srgb, ${p.ink} 10%, transparent)`,
  text: p.ink, 'text-secondary': p.ink2, 'text-muted': p.ink3, border: p.line2, accent: p.accent, 'accent-soft': `color-mix(in srgb, ${p.accent} 16%, transparent)`, 'on-accent': p.on});
const TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png'};

async function setup(browser, p, viewport, extra = {}) {
  const phone = viewport.width < 640;
  const ctx = await browser.newContext({viewport, deviceScaleFactor: 2, colorScheme: p.scheme, ...(phone ? {isMobile: true, hasTouch: true} : {}), ...extra});
  await ctx.addCookies([{name: 'wizard_messenger_session', value: st.cookie, url: st.origin}]);
  await ctx.route('**/wizard-os-home/**', r => {
    const u = new URL(r.request().url());
    if (!WEB) return r.continue({url: 'http://127.0.0.1:8796' + u.pathname});
    const f = path.join(WEB, u.pathname.replace(/^\/wizard-os-home\//, ''));
    if (!fs.existsSync(f)) return r.fulfill({status: 404, body: ''});
    return r.fulfill({status: 200, contentType: TYPES[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f)});
  });
  await ctx.addInitScript(([scheme, t, glass]) => {
    localStorage.setItem('messenger.previews', '1');
    const mark = () => {
      const r = document.documentElement; if (!r) return false;
      r.dataset.wzHosted = ''; r.dataset.colorScheme = scheme; r.style.colorScheme = scheme;
      for (const [k, v] of Object.entries(t)) r.style.setProperty('--wz-' + k, v);
      r.style.background = glass; return true;
    };
    if (!mark()) new MutationObserver((_, o) => { if (mark()) o.disconnect(); }).observe(document, {childList: true});
  }, [p.scheme, tokens(p), p.glass]);
  const page = await ctx.newPage(), errors = [], media = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => { if (r.url().includes('/api/unified/media/')) media.push({url: r.url(), status: r.status(), type: r.headers()['content-type']}); });
  await page.goto(st.origin + '/');
  await page.locator('.u-person').first().waitFor({timeout: 20000});
  return {ctx, page, errors, media, phone};
}
const open = async (page, phone, name) => {
  const row = page.locator('.u-person', {hasText: name}).first();
  if (phone) await row.tap(); else await row.click();
  await page.locator('.u-thread-body .u-row').first().waitFor();
  await page.waitForTimeout(900);
};
const playing = loc => loc.evaluate(async v => { const a = v.currentTime; await new Promise(r => setTimeout(r, 600)); return !v.paused && v.currentTime !== a; });

(async () => {
  const browser = await chromium.launch();
  for (const [skin, p] of Object.entries(P)) for (const viewport of [{width: 390, height: 844}, {width: 1280, height: 860}]) {
    const tag = skin + '-' + viewport.width;
    const {ctx, page, errors, media, phone} = await setup(browser, p, viewport);
    // Chat list: the expired voice note is a placeholder, never the bridge's sentence.
    const fam = page.locator('.u-person', {hasText: 'Family'}).first();
    assert.match(await fam.innerText(), /🎤 Voice message not available/, tag + ' list preview placeholder');
    assert.doesNotMatch(await page.locator('body').innerText(), /Failed to bridge|\(WA\)/, tag + ' no bridge text in the list');
    await open(page, phone, 'Family');
    const body = page.locator('.u-thread-body');
    const text = await body.innerText();
    assert.doesNotMatch(text, /Failed to bridge|Decrypting message|\(WA\)/, tag + ' thread shows no bridge sentences');
    // Expired photo: muted placeholder plus caption.
    const gone = page.locator('.u-row[data-id="$expired"] .u-unavailable');
    assert.match(await gone.innerText(), /📷 Photo not available\s*\(expired on WhatsApp\)/);
    assert.equal(await page.locator('.u-row[data-id="$expired"] .u-text').innerText(), 'our trip to the lake');
    assert.match(await page.locator('.u-row[data-id="$expired2"] .u-unavailable').innerText(), /Voice message not available/);
    assert.match(await page.locator('.u-row[data-id="$lost"] .u-unavailable').innerText(), /Message couldn't be decrypted\s*\(on WhatsApp\)/);
    // Decrypt-retry edit became a real photo.
    const sunset = page.locator('.u-row[data-id="$wait"] .u-media img');
    await sunset.waitFor(); await page.waitForFunction(id => { const i = document.querySelector(`.u-row[data-id="${id}"] .u-media img`); return i && i.naturalWidth > 0; }, '$wait');
    assert.equal(await page.locator('.u-row[data-id="$wait"] .u-edited').count(), 0, 'bridge delivery is not an edit');
    // Mention chips: best known name, owner highlighted.
    const chips = page.locator('.u-row[data-id="$mention"] .u-mention');
    assert.deepEqual(await chips.allInnerTexts(), ['@Bram', '@Miguel Ortiz']);
    assert.equal(await page.locator('.u-row[data-id="$mention"] .u-mention.me').innerText(), '@Miguel Ortiz');
    const chipBg = await page.locator('.u-row[data-id="$mention"] .u-mention.me').evaluate(e => getComputedStyle(e).backgroundColor);
    assert.notEqual(chipBg, 'rgba(0, 0, 0, 0)', tag + ' own mention is highlighted');
    // Static GIF image: served as the GIF itself.
    const still = page.locator('.u-row[data-id="$static"] .u-media.gif');
    await still.locator('img').waitFor();
    await page.waitForFunction(() => { const i = document.querySelector('.u-row[data-id="$static"] .u-media img'); return i && i.naturalWidth > 0; });
    assert.equal(await still.locator('.u-gif-tag').innerText(), 'GIF');
    assert.ok(media.some(m => m.url.includes(encodeURIComponent('$static')) && /image\/gif/.test(m.type || '')), tag + ' static GIF thumb is image/gif');
    await page.mouse.move(2, 2);
    await page.screenshot({path: path.join(out, `incoming-${tag}-thread.png`)});
    // GIF: off screen at open (the thread opens at the bottom), so paused; plays once scrolled into view.
    const gifBox = page.locator('.u-row[data-id="$gif"] .u-media.gif'), gif = gifBox.locator('video');
    const attrs = await gif.evaluate(v => ({loop: v.loop, muted: v.muted, inline: v.playsInline, preload: v.preload, autoplay: v.autoplay}));
    assert.deepEqual(attrs, {loop: true, muted: true, inline: true, preload: 'auto', autoplay: true});
    assert.equal(await gifBox.locator('.u-play, .u-vdur').count(), 0, 'no play button or duration on a GIF');
    assert.equal(await gifBox.locator('.u-gif-tag').innerText(), 'GIF');
    assert.equal(await gifBox.evaluate(b => { const r = b.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; }), false, 'GIF starts off screen');
    assert.equal(await gif.evaluate(v => v.paused), true, tag + ' off-screen GIF is paused');
    await gifBox.evaluate(b => b.scrollIntoView({block: 'center'}));
    await page.waitForTimeout(500);
    assert.ok(await playing(gif), tag + ' GIF plays when visible');
    await page.mouse.move(2, 2);
    await page.screenshot({path: path.join(out, `incoming-${tag}-gif.png`)});
    // Animated sticker (Telegram): chrome-less, plays, and a tap opens no viewer.
    if (phone) { await page.locator('.u-back').first().tap(); await page.locator('.u-person').first().waitFor(); }
    await open(page, phone, 'Wizard devs');
    const stk = page.locator('.u-row[data-id="$sticker"]');
    assert.equal(await stk.locator('.u-message.sticker-only .u-media.sticker video').count(), 1);
    assert.equal(await stk.locator('.u-message').evaluate(e => getComputedStyle(e).backgroundColor), 'rgba(0, 0, 0, 0)', 'sticker has no bubble');
    assert.ok(await playing(stk.locator('video')), tag + ' animated sticker plays');
    await page.evaluate(() => { window.__viewed = 0; if (window.WizardApp?.media) window.WizardApp.media.view = () => { window.__viewed++; }; });
    if (phone) await stk.locator('.u-media').tap(); else await stk.locator('.u-media').click();
    await page.waitForTimeout(300);
    assert.equal(await page.evaluate(() => window.__viewed), 0, 'tapping a sticker opens no viewer');
    // (On a phone a tap on any bubble opens its action menu; close it with Escape, which keeps the chat open.)
    if (await page.locator('.u-menu').count()) { await page.keyboard.press('Escape'); await page.waitForTimeout(250); }
    assert.equal(await page.locator('.u-menu').count(), 0);
    // Markdown from Telegram/Slack and a Telegram username mention.
    const md = page.locator('.u-row[data-id="$md"] .u-text');
    assert.equal(await md.locator('strong').innerText(), 'Install Wizard OS');
    assert.equal(await md.locator('code').innerText(), 'wam doctor');
    assert.equal(await md.locator('.u-mention').innerText(), '@zoe_dev');
    assert.doesNotMatch(await md.innerText(), /\*\*|`/);
    await page.mouse.move(2, 2);
    await page.screenshot({path: path.join(out, `incoming-${tag}-sticker.png`)});
    // Nothing overflows sideways.
    assert.ok(await page.evaluate(() => { const b = document.querySelector('.u-thread-body'); return b && b.scrollWidth <= b.clientWidth + 1; }), tag + ' no sideways overflow');
    assert.deepEqual(errors, [], tag + ' page errors');
    await ctx.close();
    console.log('ok', tag);
  }
  // Reduced motion: GIFs hold still with a ▶ until tapped.
  {
    const {ctx, page, errors, phone} = await setup(browser, P.dark, {width: 390, height: 844}, {reducedMotion: 'reduce'});
    await open(page, phone, 'Family');
    const box = page.locator('.u-row[data-id="$gif"] .u-media.gif');
    await box.evaluate(b => b.scrollIntoView({block: 'center'})); await page.waitForTimeout(500);
    assert.equal(await box.locator('.u-play').count(), 1);
    assert.equal(await box.locator('video').evaluate(v => v.paused), true, 'reduced motion: GIF does not autoplay');
    await page.evaluate(() => { window.__viewed = 0; if (window.WizardApp?.media) window.WizardApp.media.view = () => { window.__viewed++; }; });
    await box.tap(); await page.waitForTimeout(400);
    assert.ok(await playing(box.locator('video')), 'reduced motion: tap plays the GIF');
    assert.equal(await page.evaluate(() => window.__viewed), 0, 'first tap plays, it does not open the viewer');
    assert.deepEqual(errors, []);
    await ctx.close();
    console.log('ok reduced-motion');
  }
  await browser.close();
  console.log('PASS incoming_media_browser: GIF autoplay/offscreen pause/reduced motion, animated sticker, static GIF, mention chips, expired + undecryptable placeholders, markdown; 3 skins x 390/1280');
})().catch(e => { console.error('FAIL', e); process.exit(1); });
