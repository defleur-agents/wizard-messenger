// 16.14 friendliness pass (Miguel, 4 Nov 2026: "every app extremely friendly, easy to use, intuitive, and also mobile
// friendly"). Disposable ViewServer + synthetic chats (tests/agent_drafts_stage.py), 390x844 touch and 1280 mouse:
// - touch: every Inbox filter control (segments, network icons, +N, Filters, filter-menu rows) is a 44px target, and the
//   compose button still clears the filter rows; mouse keeps the compact sizes.
// - empty Low/Medium folders say what they are for and how a chat gets there (hold on touch, right-click with a mouse).
// - a filter that hides every chat offers one-tap "Clear filters", which brings the chats back.
// - message menus: Forward and Reply, Copy and Select text no longer share one icon.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR || '/home/oscar/.hermes/cache/scratch/agentkeys';
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
(async () => {
  const browser = await chromium.launch();
  for (const touch of [true, false]) {
    const tag = touch ? '390/touch' : '1280/mouse';
    const ctx = await browser.newContext(touch ? {viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}
                                               : {viewport: {width: 1280, height: 860}});
    await ctx.addCookies([{name: 'wizard_messenger_session', value: st.cookie, url: st.origin}]);
    // The view needs the shared WizardApp client: the live shell serves it (or WIZARD_WEB_DIR, a shell checkout).
    await ctx.route('**/wizard-os-home/**', r => {
      const u = new URL(r.request().url()), WEB = process.env.WIZARD_WEB_DIR || '';
      if (!WEB) return r.continue({url: 'http://127.0.0.1:8796' + u.pathname});
      const f = path.join(WEB, u.pathname.replace(/^\/wizard-os-home\//, ''));
      if (!f.startsWith(WEB) || !fs.existsSync(f)) return r.fulfill({status: 404, body: ''});
      r.fulfill({contentType: f.endsWith('.css') ? 'text/css' : 'text/javascript', body: fs.readFileSync(f)});
    });
    await ctx.addInitScript(() => { try { sessionStorage.clear(); } catch {} });
    const page = await ctx.newPage(), errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(st.origin + '/');
    await page.locator('.u-person', {hasText: 'Alice Example'}).first().waitFor(); await page.waitForTimeout(500);
    const tap = loc => touch ? loc.tap() : loc.click();
    // Targets.
    const sizes = await page.evaluate(() => [...document.querySelectorAll('.u-seg .u-seg-btn, .u-netrow .u-chip:not([hidden])')]
      .map(e => { const r = e.getBoundingClientRect(); return [e.getAttribute('aria-label') || e.textContent, r.width, r.height]; }));
    assert.ok(sizes.length >= 5, tag + ': filter controls present');
    for (const [name, w, h] of sizes) {
      if (touch) assert.ok(h >= 43.5 && w >= 43.5, tag + ': ' + name + ' is a 44px target (' + w + 'x' + h + ')');
      else assert.ok(h < 40, tag + ': ' + name + ' stays compact for a mouse (' + h + ')');
    }
    if (touch) {
      const fab = await page.locator('.u-fab').boundingBox(), rows = await page.locator('#u-filters').boundingBox();
      assert.ok(fab.y + fab.height <= rows.y + 0.5, tag + ': compose button clears the filter rows');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, tag + ': no sideways scroll');
      await tap(page.locator('.u-filter-btn'));
      const acts = await page.locator('.u-filter-menu .u-act').evaluateAll(els => els.map(e => e.getBoundingClientRect().height));
      assert.ok(acts.length && acts.every(h => h >= 43.5), tag + ': filter menu rows are 44px');
      await page.keyboard.press('Escape'); await page.waitForTimeout(200);
      if (await page.locator('.u-filter-menu').count()) await page.mouse.click(5, 5);
      await page.waitForTimeout(200);
    }
    // Empty Low folder explains itself.
    await tap(page.locator('.u-seg-btn[data-seg=low]'));
    const hint = await page.locator('.u-empty .u-empty-hint').textContent();
    assert.match(hint, /never notify/, tag + ': Low says what it does');
    assert.match(hint, touch ? /Hold a chat/ : /Right-click a chat/, tag + ': Low says how to put a chat there');
    // A network filter that hides everything offers Clear filters, which restores the chats.
    await tap(page.locator('.u-seg-btn[data-seg=medium]'));
    await tap(page.locator('.u-netrow .u-chip.net[data-filter="net:telegram"]'));
    const clear = page.locator('.u-empty .u-empty-clear'); await clear.waitFor();
    if (touch) { const b = await clear.boundingBox(); assert.ok(b.height >= 43.5, tag + ': Clear filters is a 44px target'); }
    await tap(clear);
    assert.equal(await page.locator('.u-netrow .u-chip.net[aria-pressed=true]').count(), 0, tag + ': network filter cleared');
    await tap(page.locator('.u-seg-btn[data-seg=all]'));
    await page.locator('.u-person', {hasText: 'Alice Example'}).first().waitFor();
    // Message menu icons are distinct.
    await tap(page.locator('.u-person', {hasText: 'Alice Example'}).first());
    const bubble = page.locator('.u-row:not(.outgoing) .u-message').first(); await bubble.waitFor(); await page.waitForTimeout(400);
    if (touch) await bubble.locator('.u-text, .bubble-text').first().tap(); else await bubble.click({button: 'right'});
    const items = page.locator('.u-actions .u-act'); await items.first().waitFor();
    const paths = await items.evaluateAll(els => Object.fromEntries(els.map(e => [e.textContent.trim(), [...e.querySelectorAll('path')].map(p => p.getAttribute('d')).join('|')])));
    assert.ok(paths['Reply'] && paths['Forward to Wizard'], tag + ': Reply and Forward present ' + Object.keys(paths));
    assert.notEqual(paths['Reply'], paths['Forward to Wizard'], tag + ': Forward has its own icon');
    if (paths['Select text']) assert.notEqual(paths['Select text'], paths['Copy'], tag + ': Select text has its own icon');
    assert.deepEqual(errors, [], tag + ': no page errors');
    console.log('ok', tag);
    await ctx.close();
  }
  await browser.close();
  console.log('PASS friendly_pass_browser: 44px touch filters, explained empty folders, Clear filters, distinct menu icons');
})().catch(e => { console.error(e); process.exit(1); });
