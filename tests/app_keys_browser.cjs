// 16.15 keyboard shortcuts (Wizard app-key contract: controls carry data-wz-key, the shared WizardApp client clicks
// the first visible enabled match; Messenger ships a fallback with the same rules that stands down when
// WizardApp.keys exists). Disposable ViewServer + synthetic chats (tests/agent_drafts_stage.py), 1280 mouse and
// 390 phone width:
// - j/k open the next/previous chat in list order, from the list and from an open chat (phone: list not on screen);
// - r focuses the open chat's composer; j typed there is text, not a shortcut; Alt+j does nothing;
// - / opens chat search; n opens New message; Escape stays Back (never marked);
// - the fallback ignores keys while WizardApp.keys exists.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR || '/home/oscar/.hermes/cache/scratch/agentkeys';
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
(async () => {
  const browser = await chromium.launch();
  for (const phone of [false, true]) {
    const tag = phone ? '390' : '1280';
    const ctx = await browser.newContext(phone ? {viewport: {width: 390, height: 844}} : {viewport: {width: 1280, height: 860}});
    await ctx.addCookies([{name: 'wizard_messenger_session', value: st.cookie, url: st.origin}]);
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
    await page.locator('.u-person', {hasText: 'Alice Example'}).first().waitFor(); await page.waitForTimeout(400);
    const marked = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-wz-key]')].map(e => [e.dataset.wzKey, e.dataset.wzKeyLabel])));
    for (const k of ['j', 'k', 'r', '/', 'n']) assert.ok(marked[k], tag + ': ' + k + ' is marked (' + JSON.stringify(marked) + ')');
    assert.equal(marked.Escape, undefined, tag + ': Escape is never marked');
    const order = await page.locator('.u-person').evaluateAll(els => els.map(e => e.querySelector('strong').textContent));
    assert.ok(order.length >= 2, tag + ': at least two chats staged');
    const openName = () => page.evaluate(() => document.querySelector('.u-thread-head .u-who-text strong')?.textContent || '');
    const press = async k => { await page.keyboard.press(k); await page.waitForTimeout(350); };
    await page.evaluate(() => document.activeElement?.blur());
    await press('j'); assert.equal(await openName(), order[0], tag + ': j opens the first chat');
    await press('j'); assert.equal(await openName(), order[1], tag + ': j again opens the second chat (from an open chat)');
    await press('k'); assert.equal(await openName(), order[0], tag + ': k goes back to the first chat');
    await press('Alt+j'); assert.equal(await openName(), order[0], tag + ': Alt+j is not a shortcut');
    await press('r');
    assert.equal(await page.evaluate(() => document.activeElement?.matches('.u-composer textarea')), true, tag + ': r focuses the composer');
    await press('j'); assert.equal(await openName(), order[0], tag + ': j typed in the composer stays text');
    assert.equal(await page.evaluate(() => document.activeElement.value.endsWith('j')), true, tag + ': the j landed in the composer');
    await page.evaluate(() => { const t = document.activeElement; t.value = ''; t.dispatchEvent(new Event('input', {bubbles: true})); t.blur(); });
    // The fallback stands down while the shared client provides keys.
    const ignored = await page.evaluate(() => {
      const had = 'keys' in window.WizardApp, prev = window.WizardApp.keys; window.WizardApp.keys = prev || {};
      const e = new KeyboardEvent('keydown', {key: 'j', bubbles: true, cancelable: true}); window.__messengerKeys.fallback(e);
      if (had) window.WizardApp.keys = prev; else delete window.WizardApp.keys;
      return !e.defaultPrevented;
    });
    assert.equal(ignored, true, tag + ': fallback ignores keys when WizardApp.keys exists');
    await press('/');
    assert.equal(await page.evaluate(() => document.activeElement?.matches('input.u-search')), true, tag + ': / opens chat search');
    // Escape stays Back: it closes the open chat, then the search (the app's own order).
    for (let i = 0; i < 4 && !(await page.locator('.u-fab').count()); i++) await press('Escape');
    await page.evaluate(() => document.activeElement?.blur());
    await page.locator('.u-fab').waitFor();
    await press('n');
    assert.ok(await page.locator('.u-newmsg, [role=dialog][aria-label="New chat"]').count(), tag + ': n opens New message');
    assert.deepEqual(errors, [], tag + ': no page errors');
    console.log('ok', tag, order.join(' > '));
    await ctx.close();
  }
  await browser.close();
  console.log('PASS app_keys_browser: j/k/r / n via data-wz-key, fallback rules');
})().catch(e => { console.error(e); process.exit(1); });
