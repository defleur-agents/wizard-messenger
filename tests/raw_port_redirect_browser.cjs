// Messenger opened on its raw app port moves itself to its Wizard path instead of a dead "Couldn't reach" card.
// Run through tests/raw_port_redirect_fixture.py (real trusted-owner ViewServer + signing gateway). The browser
// sees https://box.test:<port>; requests are routed onto the fixture listeners, nothing leaves the machine.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const RAW = process.env.RAW_BACKEND, GW = process.env.GATEWAY_BACKEND;
const RAW_URL = 'https://box.test:9245/';
const shell = frame => `<!doctype html><title>Wizard</title><body>${frame ? `<iframe id="w" src="${frame}" style="width:390px;height:700px"></iframe>` : 'shell'}</body>`;

(async () => {
  const browser = await chromium.launch({headless: true});
  const results = [];
  async function scenario(name, fn, {gatewayBouncesBack = false} = {}) {
    const context = await browser.newContext({viewport: {width: 390, height: 844}, ignoreHTTPSErrors: true});
    await context.addInitScript(() => {
      const noop = () => {};
      window.WizardApp = {ready: noop, update: {hold: () => ({release: noop})}, back: {register: noop}, on: noop, nav: {}, toast: noop, titlebar: {set: async () => false}};
    });
    const seen = [];
    await context.route('**/*', async route => {
      const u = new URL(route.request().url());
      seen.push(u.href);
      if (u.pathname.startsWith('/wizard-os-home/')) return route.fulfill({status: 200, contentType: 'application/javascript', body: ''});
      if (u.hostname === 'evil.test') return route.fulfill({status: 200, contentType: 'text/html', body: shell(u.searchParams.get('frame'))});
      if (u.hostname === '127.0.0.1') return route.continue();
      if (u.hostname !== 'box.test') return route.abort();
      if (u.port === '9245') return route.fulfill({response: await route.fetch({url: RAW + u.pathname + u.search})});
      if (u.pathname.startsWith('/messenger/')) {
        if (gatewayBouncesBack && route.request().isNavigationRequest()) return route.fulfill({status: 200, contentType: 'text/html', body: `<script>location.replace(${JSON.stringify(RAW_URL)})</script>`});
        return route.fulfill({response: await route.fetch({url: GW + u.pathname + u.search})});
      }
      return route.fulfill({status: 200, contentType: 'text/html', body: shell(u.searchParams.get('frame'))});
    });
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    if (process.env.DEBUG_NET) page.on('response', r => { if (r.url().includes('/api/')) r.text().then(t => console.log('DEBUG net', r.status(), r.url(), t.slice(0, 160))).catch(() => {}); });
    try { await fn(page, seen); results.push('ok   ' + name); }
    catch (e) { results.push('FAIL ' + name + ': ' + e.message); process.exitCode = 1; }
    if (errors.length) { results.push('FAIL ' + name + ' page errors: ' + errors.join(' | ')); process.exitCode = 1; }
    await context.close();
  }
  // On the Wizard path the owner gateway vouches for the owner (trusted-owner 200, enabled); the raw port refuses
  // the same call with trusted_gateway_required, which is what used to end on the dead card.
  const opened = async target => {
    const r = await target.evaluate(async () => { const x = await fetch('api/view/trusted-owner', {cache: 'no-store'}); return {status: x.status, body: await x.json()}; });
    assert.equal(r.status, 200); assert.equal(r.body.result.enabled, true);
    assert.doesNotMatch(await target.evaluate(() => document.getElementById('gate-description')?.textContent || ''), /Couldn't reach/);
  };
  const settled = async (page, url) => { await page.waitForURL(url, {timeout: 15000}); await page.waitForTimeout(1500); assert.equal(page.url(), url); };

  await scenario('top-level raw port with the Wizard as referrer goes to that origin\'s /messenger/', async page => {
    await page.goto(RAW_URL, {referer: 'https://box.test:8796/'});
    await settled(page, 'https://box.test:8796/messenger/');
    await opened(page);
  });
  await scenario('top-level raw port with no referrer goes to the box\'s first Wizard origin', async page => {
    await page.goto(RAW_URL);
    await settled(page, 'https://box.test:8444/messenger/');
  });
  await scenario('a Wizard window framing the raw port moves the frame onto the shell\'s own origin', async page => {
    await page.goto('https://box.test:8796/?frame=' + encodeURIComponent(RAW_URL));
    let f;
    for (let i = 0; i < 60 && !(f = page.frames().find(x => x.url() === 'https://box.test:8796/messenger/')); i++) await page.waitForTimeout(250);
    assert.ok(f, 'frame moved to https://box.test:8796/messenger/: ' + page.frames().map(x => x.url()));
    await f.waitForLoadState('load'); await page.waitForTimeout(1000);
    assert.equal(f.url(), 'https://box.test:8796/messenger/');
    await opened(f);
    assert.equal(page.url(), 'https://box.test:8796/?frame=' + encodeURIComponent(RAW_URL));     // the shell itself stays
  });
  await scenario('an arbitrary referrer is never a destination', async (page, seen) => {
    await page.goto(RAW_URL, {referer: 'https://evil.test/'});
    await settled(page, 'https://box.test:8444/messenger/');
    assert.ok(!seen.some(u => u.startsWith('https://evil.test/messenger')));
  });
  await scenario('a foreign page cannot frame the raw port (CSP) and never receives a redirect', async (page, seen) => {
    await page.goto('https://evil.test/?frame=' + encodeURIComponent(RAW_URL));
    await page.waitForTimeout(2500);
    assert.ok(!seen.some(u => u.startsWith('https://evil.test/messenger')));
    const f = page.frames().find(x => x !== page.mainFrame());
    assert.ok(!f || !f.url().startsWith('https://box.test:8') , 'frame did not move to a Wizard origin: ' + (f && f.url()));
    assert.equal(page.url().startsWith('https://evil.test/'), true);
  });
  await scenario('one attempt only: a gateway that sends the page back leaves it on the card, no loop', async (page, seen) => {
    await page.goto(RAW_URL);
    await page.waitForURL('https://box.test:8444/messenger/', {timeout: 15000}).catch(() => {});
    await page.waitForURL(RAW_URL, {timeout: 15000});
    await page.waitForTimeout(3000);
    assert.equal(page.url(), RAW_URL);
    assert.equal(seen.filter(u => u === 'https://box.test:8444/messenger/').length, 1);
    await page.locator('#gate').waitFor({state: 'visible'});
  }, {gatewayBouncesBack: true});
  await scenario('the Wizard path itself never redirects', async (page, seen) => {
    await page.goto('https://box.test:8444/messenger/', {referer: 'https://box.test:8796/'});
    await opened(page);
    await page.waitForTimeout(1000);
    assert.equal(page.url(), 'https://box.test:8444/messenger/');
    assert.ok(!seen.some(u => u.startsWith('https://box.test:8796/messenger')));
  });
  await scenario('a different host name (local http) is never redirected to the box\'s origins', async page => {
    await page.goto(RAW + '/');
    await page.waitForTimeout(2500);
    assert.equal(page.url(), RAW + '/');
  });
  await browser.close();
  console.log(results.join('\n'));
  if (!process.exitCode) console.log('PASS raw-port redirect: referrer, no referrer, framed, foreign referrer/frame, loop guard, gateway path, other host');
})().catch(e => { console.error(e); process.exit(1); });
