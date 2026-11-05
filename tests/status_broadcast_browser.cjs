// WhatsApp Status posts (Miguel, 5 Nov 2026: a status landed as "WhatsApp is still sending it").
// The bridge almost never receives status posts, so in the WhatsApp Status Broadcast chat (portal status@broadcast)
// the decrypt-failure placeholder reads "🟢 Status update (view it in WhatsApp on your phone)", in the bubble and the
// chat-list preview; an ordinary chat's fresh decrypt failure still reads "Waiting for this message (WhatsApp is still
// sending it)". Disposable stage: tests/incoming_media_stage.py (no homeserver, no real account).
// AGENT_STAGE_DIR=<dir> python3 tests/incoming_media_stage.py <port> &  then  node tests/status_broadcast_browser.cjs [outdir]
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR || '/home/oscar/.hermes/cache/scratch/incoming-stage';
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
const out = path.resolve(process.argv[2] || process.env.EVIDENCE_DIR || dir); fs.mkdirSync(out, {recursive: true});
const WEB = process.env.WIZARD_WEB_DIR;
const TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png'};
const SKINS = {
  dark: {scheme: 'dark', bg: '#000000', ink: '#f7f7f7', ink2: '#c4c4c4', ink3: '#8a8a8a', line2: 'rgba(255,255,255,.26)', accent: '#ffffff', on: '#000000'},
  light: {scheme: 'light', bg: '#ffffff', ink: '#000000', ink2: '#2e2e2e', ink3: '#6b6b6b', line2: 'rgba(0,0,0,.32)', accent: '#000000', on: '#ffffff'},
};
const tokens = p => ({canvas: 'transparent', base: p.bg, surface: `color-mix(in srgb, ${p.ink} 6%, transparent)`, 'surface-raised': `color-mix(in srgb, ${p.ink} 10%, transparent)`,
  text: p.ink, 'text-secondary': p.ink2, 'text-muted': p.ink3, border: p.line2, accent: p.accent, 'accent-soft': `color-mix(in srgb, ${p.accent} 16%, transparent)`, 'on-accent': p.on});

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
  await ctx.addInitScript(([scheme, t, bg]) => {
    localStorage.setItem('messenger.previews', '1');
    const mark = () => {
      const r = document.documentElement; if (!r) return false;
      r.dataset.wzHosted = ''; r.dataset.colorScheme = scheme; r.style.colorScheme = scheme;
      for (const [k, v] of Object.entries(t)) r.style.setProperty('--wz-' + k, v);
      r.style.background = bg; return true;
    };
    if (!mark()) new MutationObserver((_, o) => { if (mark()) o.disconnect(); }).observe(document, {childList: true});
  }, [p.scheme, tokens(p), p.bg]);
  const page = await ctx.newPage(), errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(st.origin + '/');
  await page.locator('.u-person').first().waitFor({timeout: 20000});
  return {ctx, page, errors, phone};
}
async function open(page, phone, name) {
  const row = page.locator('.u-person', {hasText: name}).first();
  if (phone) await row.tap(); else await row.click();
  await page.locator('.u-thread-body .u-row').first().waitFor();
  await page.waitForTimeout(700);
}
async function back(page, phone) {
  if (phone) await page.locator('.u-back').first().click(); else await page.keyboard.press('Escape');
  await page.waitForTimeout(500);
}

(async () => {
  const browser = await chromium.launch();
  for (const [skin, p] of Object.entries(SKINS)) for (const viewport of [{width: 390, height: 844}, {width: 1280, height: 860}]) {
    const tag = skin + '-' + viewport.width;
    const {ctx, page, errors, phone} = await setup(browser, p, viewport);
    const statusRow = page.locator('.u-person', {hasText: 'WhatsApp Status Broadcast'}).first();
    assert.match(await statusRow.innerText(), /🟢 Status update/, tag + ' status list preview');
    assert.doesNotMatch(await statusRow.innerText(), /Waiting for this message|couldn't be decrypted/, tag + ' status preview not waiting');
    assert.match(await page.locator('.u-person').filter({hasText: 'Waiting for this message'}).first().innerText(), /Ana/, tag + ' ordinary chat still waits');
    await open(page, phone, 'WhatsApp Status Broadcast');
    const gone = page.locator('.u-row[data-id="$status"] .u-unavailable');
    assert.match(await gone.innerText(), /^🟢 Status update\s*\(view it in WhatsApp on your phone\)$/, tag + ' status bubble');
    const thread = await page.locator('.u-thread-body').innerText();
    assert.doesNotMatch(thread, /still sending|Waiting for this message|Decrypting message/, tag + ' no misleading wait in the status chat');
    if (phone && skin === 'dark') {
      const shot = path.join(out, 'status-bubble-' + tag + '.png');
      await page.screenshot({path: shot});
      if (process.env.STATUS_SHOT) fs.copyFileSync(shot, process.env.STATUS_SHOT);
    }
    await back(page, phone);
    await open(page, phone, 'Ana');
    const wait = page.locator('.u-row[data-id="$ana-wait"] .u-unavailable');
    assert.match(await wait.innerText(), /^⏳ Waiting for this message\s*\(WhatsApp is still sending it\)$/, tag + ' ordinary waiting bubble unchanged');
    assert.deepEqual(errors, [], tag + ' page errors');
    console.log('ok', tag);
    await ctx.close();
  }
  await browser.close();
  console.log('status_broadcast_browser: all ok');
})().catch(e => { console.error(e); process.exit(1); });
