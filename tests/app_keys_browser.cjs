// 16.15 keyboard shortcuts (Wizard app-key contract: controls carry data-wz-key, the shared WizardApp client clicks
// the first visible enabled match; Messenger ships a fallback with the same rules that stands down when
// WizardApp.keys exists). Disposable ViewServer + synthetic chats (tests/agent_drafts_stage.py), 1280 mouse and
// 390 phone width:
// - j/k open the next/previous chat in list order, from the list and from an open chat (phone: list not on screen);
// - r focuses the open chat's composer; j typed there is text, not a shortcut; Alt+j does nothing;
// - / opens chat search; n opens New message; Escape stays Back (never marked);
// - the fallback ignores keys while WizardApp.keys exists.
// 16.17 keycaps sit on what the key does: j on the next chat's row, k on the previous one, r on the reply box, / on
// the visible Search; at phone width on a keyboard device the chat header has ↑/↓ (.u-step, data-step k/j) that
// carry k/j; the hidden .u-keys row keeps a key only while its target is off screen (touch phone: no ↑/↓).
// 16.18 one anchor: data-wz-key="j" means ⌥J. The fallback acts only in a standalone tab without WizardApp.keys, on ⌥+key
// matched by e.code (⌥J on a Mac types ∆); plain keys never act; a held key doesn't repeat; framed in Wizard it is inert
// (the shell routes ⌥+key). This test serves the shared client with its keys service removed so the fallback is what runs.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const dir = process.env.AGENT_STAGE_DIR || '/home/oscar/.hermes/cache/scratch/agentkeys';
const st = JSON.parse(fs.readFileSync(path.join(dir, 'state.json')));
(async () => {
  const browser = await chromium.launch();
  const routeShell = ctx => ctx.route('**/wizard-os-home/**', async r => {
    const u = new URL(r.request().url()), WEB = process.env.WIZARD_WEB_DIR || '';
    let body;
    if (!WEB) {
      if (!u.pathname.endsWith('/core/app-client.js')) return r.continue({url: 'http://127.0.0.1:8796' + u.pathname});
      body = await (await fetch('http://127.0.0.1:8796' + u.pathname)).text();
    } else {
      const f = path.join(WEB, u.pathname.replace(/^\/wizard-os-home\//, ''));
      if (!f.startsWith(WEB) || !fs.existsSync(f)) return r.fulfill({status: 404, body: ''});
      body = fs.readFileSync(f, 'utf8');
    }
    // No keys service in the shared client: the fallback under test is what handles keys.
    if (u.pathname.endsWith('/core/app-client.js')) body = body.replace(/^\s*keys,.*$/m, '').replace(/addEventListener\('keydown', onAppKey\);/, '');
    r.fulfill({contentType: u.pathname.endsWith('.css') ? 'text/css' : 'text/javascript', body});
  });
  for (const [phone, touch] of [[false, false], [true, false], [true, true]]) {
    const tag = phone ? (touch ? '390touch' : '390') : '1280';
    const ctx = await browser.newContext(phone ? {viewport: {width: 390, height: 844}, ...(touch ? {hasTouch: true, isMobile: true} : {})} : {viewport: {width: 1280, height: 860}});
    await ctx.addCookies([{name: 'wizard_messenger_session', value: st.cookie, url: st.origin}]);
    await routeShell(ctx);
    await ctx.addInitScript(() => { try { sessionStorage.clear(); } catch {} });
    const page = await ctx.newPage(), errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(st.origin + '/');
    await page.locator('.u-person', {hasText: 'Alice Example'}).first().waitFor(); await page.waitForTimeout(400);
    assert.equal(await page.evaluate(() => !!window.WizardApp && !('keys' in window.WizardApp)), true, tag + ': shared client served without keys');
    const marked = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-wz-key]')].map(e => [e.dataset.wzKey, e.dataset.wzKeyLabel])));
    for (const k of ['j', 'k', 'r', '/', 'n']) assert.ok(marked[k], tag + ': ' + k + ' is marked (' + JSON.stringify(marked) + ')');
    assert.equal(marked.Escape, undefined, tag + ': Escape is never marked');
    const order = await page.locator('.u-person').evaluateAll(els => els.map(e => e.querySelector('strong').textContent));
    assert.ok(order.length >= 2, tag + ': at least two chats staged');
    const openName = () => page.evaluate(() => document.querySelector('.u-thread-head .u-who-text strong')?.textContent || '');
    const press = async k => { await page.keyboard.press(k); await page.waitForTimeout(350); };
    const alt = k => press('Alt+' + k);
    // Where each key's keycap sits: 'quiet' (the hidden .u-keys row), 'row:<name>', 'step:<j|k>', 'textarea', 'search'.
    const keyAt = k => page.evaluate(k => [...document.querySelectorAll('[data-wz-key]')].filter(e => e.dataset.wzKey === k).map(e =>
      e.closest('.u-keys') ? 'quiet' : e.matches('.u-person') ? 'row:' + e.querySelector('strong').textContent : e.matches('.u-step') ? 'step:' + e.dataset.step
        : e.matches('textarea') ? 'textarea' : e.matches('button') && /search/i.test(e.getAttribute('aria-label') || e.title || '') ? 'search' : e.tagName.toLowerCase()).sort(), k);
    const steps = () => page.locator('.u-step:visible').count();
    await page.evaluate(() => document.activeElement?.blur());
    await press('j'); assert.equal(await openName(), '', tag + ': plain j does nothing');
    assert.deepEqual(await keyAt('j'), ['row:' + order[0]], tag + ': nothing open, j sits on the first row');
    assert.deepEqual(await keyAt('/'), ['search'], tag + ': / sits on the visible Search, not the quiet row');
    await alt('j'); assert.equal(await openName(), order[0], tag + ': ⌥j opens the first chat');
    assert.deepEqual(await keyAt('r'), ['textarea'], tag + ': r sits on the reply box');
    if (!phone) {
      assert.deepEqual(await keyAt('j'), ['row:' + order[1]], tag + ': j sits on the next row');
      assert.deepEqual(await keyAt('k'), ['quiet'], tag + ': first chat open, k has no row and stays quiet');
      assert.equal(await steps(), 0, tag + ': no ↑/↓ while the list is beside the chat');
    } else if (!touch) {
      assert.equal(await steps(), 2, tag + ': ↑/↓ in the chat header at phone width with a keyboard');
      assert.deepEqual(await keyAt('j'), ['step:j'], tag + ': j sits on ↓');
      assert.deepEqual(await keyAt('k'), ['quiet'], tag + ': first chat open, k stays quiet');
    } else {
      assert.equal(await steps(), 0, tag + ': no ↑/↓ on a touch-only phone');
      assert.deepEqual(await keyAt('j'), ['quiet'], tag + ': list off screen, j stays on the quiet row');
    }
    await alt('j'); assert.equal(await openName(), order[1], tag + ': ⌥j again opens the second chat (from an open chat)');
    if (!phone) assert.deepEqual(await keyAt('k'), ['row:' + order[0]], tag + ': k sits on the previous row');
    else if (!touch) {
      assert.deepEqual(await keyAt('k'), ['step:k'], tag + ': k sits on ↑');
      assert.deepEqual(await keyAt('j'), ['quiet'], tag + ': last chat open, j stays quiet');
    } else assert.deepEqual(await keyAt('k'), ['quiet'], tag + ': list off screen, k stays on the quiet row');
    if (phone && !touch) {   // ↓/↑ themselves step, like j/k
      await page.locator('.u-step[data-step="k"]:visible').click(); await page.waitForTimeout(350);
      assert.equal(await openName(), order[0], tag + ': ↑ opens the previous chat');
      await page.locator('.u-step[data-step="j"]:visible').click(); await page.waitForTimeout(350);
      assert.equal(await openName(), order[1], tag + ': ↓ opens the next chat');
    }
    await alt('k'); assert.equal(await openName(), order[0], tag + ': ⌥k goes back to the first chat');
    await press('k'); assert.equal(await openName(), order[0], tag + ': plain k does nothing');
    // ⌥J on a Mac: e.key is ∆, e.code KeyJ. A held key (repeat) does not step again.
    const synth = (init) => page.evaluate(init => { const e = new KeyboardEvent('keydown', {bubbles: true, cancelable: true, ...init}); document.body.dispatchEvent(e); return e.defaultPrevented; }, init);
    await synth({key: '∆', code: 'KeyJ', altKey: true}); await page.waitForTimeout(350);
    assert.equal(await openName(), order[1], tag + ': ⌥J by e.code (Mac ∆) opens the next chat');
    await synth({key: '˚', code: 'KeyK', altKey: true, repeat: true}); await page.waitForTimeout(350);
    assert.equal(await openName(), order[1], tag + ': a held ⌥K (repeat) does not step');
    await synth({key: '˚', code: 'KeyK', altKey: true}); await page.waitForTimeout(350);
    assert.equal(await openName(), order[0], tag + ': ⌥K by e.code goes back');
    assert.equal(await synth({key: 'j', code: 'KeyJ', altKey: true, ctrlKey: true}), false, tag + ': Ctrl+⌥J is not a shortcut');
    await alt('r');
    assert.equal(await page.evaluate(() => document.activeElement?.matches('.u-composer textarea')), true, tag + ': ⌥r focuses the composer');
    await press('j'); assert.equal(await openName(), order[0], tag + ': j typed in the composer stays text');
    assert.equal(await page.evaluate(() => document.activeElement.value.endsWith('j')), true, tag + ': the j landed in the composer');
    await alt('j'); assert.equal(await openName(), order[1], tag + ': ⌥j acts from inside the composer');
    assert.equal(await page.evaluate(() => [...document.querySelectorAll('.u-composer textarea')].some(t => /[∆j]j/.test(t.value) || t.value.includes('∆'))), false, tag + ': ⌥j typed nothing');
    await alt('k'); assert.equal(await openName(), order[0], tag + ': ⌥k back');
    await page.evaluate(() => { for (const t of document.querySelectorAll('.u-composer textarea')) { t.value = ''; t.dispatchEvent(new Event('input', {bubbles: true})); } document.activeElement?.blur(); });
    // The fallback stands down while the shared client provides keys.
    const ignored = await page.evaluate(() => {
      const prev = window.WizardApp; window.WizardApp = Object.assign(Object.create(prev), {keys: {list: () => []}});
      const swapped = window.WizardApp !== prev;
      const e = new KeyboardEvent('keydown', {key: 'j', code: 'KeyJ', altKey: true, bubbles: true, cancelable: true}); window.__messengerKeys.fallback(e);
      window.WizardApp = prev;
      return swapped && !e.defaultPrevented;
    });
    assert.equal(ignored, true, tag + ': fallback ignores keys when WizardApp.keys exists');
    await press('/'); assert.equal(await page.evaluate(() => !!document.activeElement?.matches('input.u-search')), false, tag + ': plain / does nothing');
    await alt('/');
    assert.equal(await page.evaluate(() => document.activeElement?.matches('input.u-search')), true, tag + ': ⌥/ opens chat search');
    // Escape stays Back: it closes the open chat, then the search (the app's own order).
    for (let i = 0; i < 4 && !(await page.locator('.u-fab').count()); i++) await press('Escape');
    await page.evaluate(() => document.activeElement?.blur());
    await page.locator('.u-fab').waitFor();
    await press('n'); assert.equal(await page.locator('.u-newmsg, [role=dialog][aria-label="New chat"]').count(), 0, tag + ': plain n does nothing');
    await alt('n');
    assert.ok(await page.locator('.u-newmsg, [role=dialog][aria-label="New chat"]').count(), tag + ': ⌥n opens New message');
    assert.deepEqual(errors, [], tag + ': no page errors');
    console.log('ok', tag, order.join(' > '));
    await ctx.close();
  }
  { // Framed in Wizard the shell routes ⌥+key: the fallback is inert (no chat opens, nothing prevented).
    const ctx = await browser.newContext({viewport: {width: 1280, height: 860}});
    await ctx.addCookies([{name: 'wizard_messenger_session', value: st.cookie, url: st.origin}]);
    await routeShell(ctx);
    await ctx.route('**/__wz_frame_host', r => r.fulfill({contentType: 'text/html', body: '<!doctype html><iframe id=f src="/" style="width:1200px;height:800px;border:0"></iframe>'}));
    const page = await ctx.newPage(); await page.goto(st.origin + '/__wz_frame_host');
    const fr = page.frameLocator('#f'), frame = page.frames().find(f => f !== page.mainFrame()) || (await (await page.$('#f')).contentFrame());
    await fr.locator('.u-person', {hasText: 'Alice Example'}).first().waitFor(); await page.waitForTimeout(400);
    await frame.evaluate(() => { document.activeElement?.blur(); window.focus(); });
    const prevented = await frame.evaluate(() => { const e = new KeyboardEvent('keydown', {key: 'j', code: 'KeyJ', altKey: true, bubbles: true, cancelable: true}); document.body.dispatchEvent(e); return e.defaultPrevented; });
    await page.waitForTimeout(350);
    assert.equal(prevented, false, 'framed: ⌥J left to the shell');
    assert.equal(await frame.evaluate(() => document.querySelector('.u-thread-head .u-who-text strong')?.textContent || ''), '', 'framed: fallback opens nothing');
    await ctx.close(); console.log('ok framed');
  }
  await browser.close();
  console.log('PASS app_keys_browser: ⌥ j/k/r/slash/n via data-wz-key, plain keys inert, keycaps on their targets, ↑/↓ at phone width, framed fallback inert');
})().catch(e => { console.error(e); process.exit(1); });
