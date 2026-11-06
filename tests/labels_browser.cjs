// Labels (6 Nov 2026): a label is the owner's own group of chats. Create one, put ANY chat in it (person, group, merged), filter by it, rename/delete.
// Synthetic APIs only, stateful label catalogue; two skins x phone/desktop screenshots. node tests/labels_browser.cjs [outdir]
// (inherited header) Inbox tweaks (Miguel, 30 Oct 2026): readable selected chips on hosted skins (transparent canvas), icon-only platform
// chips, no bottom tab bar, and a Low priority folder that keeps chats out of the Inbox, unread counts and the badge.
// node tests/inbox_tweaks_browser.cjs [outdir]   (needs playwright via PLAYWRIGHT_MODULE). Synthetic APIs only.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const L = require('../static/app.js');
const root = path.resolve(__dirname, '../static'), out = path.resolve(process.argv[2] || 'inbox-tweaks-shots');
fs.mkdirSync(out, {recursive: true});
const TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml'};
const now = Date.now(), min = 60e3;
const ident = (id, net, kind, label) => [{id: id + '-i', network: net, kind, label}];
const person = (id, name, net, text, ago, extra = {}) => ({id, display_name: name, identities: ident(id, net, 'person', name), labels: [], unread: 0, muted: false, low_priority: false, last: {text, timestamp: now - ago * min, outgoing: false}, language: '', peer_read_ts: 0, ...extra});
// Skin tokens as the Wizard shell posts them: the canvas is transparent when hosted (APPEARANCE.md).
const SKINS = {
  dark: {canvas: 'transparent', base: '#05030c', surface: 'color-mix(in srgb, #f3efff 6%, transparent)', 'surface-raised': 'color-mix(in srgb, #f3efff 10%, transparent)', text: '#f3efff', 'text-secondary': '#b9b0d8', 'text-muted': '#a59abf', border: 'rgba(205,190,255,.24)', accent: '#b99bff', 'accent-soft': 'color-mix(in srgb, #b99bff 16%, transparent)', 'on-accent': '#05030c', glass: '#1d1533'},
  light: {canvas: 'transparent', base: '#f5f2ec', surface: 'color-mix(in srgb, #211c17 5%, transparent)', 'surface-raised': 'color-mix(in srgb, #211c17 9%, transparent)', text: '#211c17', 'text-secondary': '#62584c', 'text-muted': '#756958', border: '#d4c7b8', accent: '#674a29', 'accent-soft': '#e9ddcb', 'on-accent': '#ffffff', glass: '#ece6dc'},
};
(async () => {
  const browser = await chromium.launch(), summary = [];
  for (const scheme of ['dark', 'light']) for (const [label, viewport] of [['390', {width: 390, height: 844}], ['1280', {width: 1280, height: 860}]]) {
    const PEOPLE = [
      person('james', 'James Carter', 'whatsapp', 'On my way', 2, {unread: 1}),
      person('kenji', 'Kenji Tanaka', 'line', 'See you tomorrow', 40),
      person('marco', 'Marco Bianchi', 'telegram', 'Invoice sent', 300, {unread: 3, identities: [{id: 'marco-t', network: 'telegram', kind: 'person', label: 'Marco'}, {id: 'marco-s', network: 'signal', kind: 'person', label: 'Marco'}]}),
    ];
    const GROUPS = [
      {...person('fam', 'Family', 'whatsapp', 'Dinner Sunday?', 12, {unread: 2}), identities: ident('fam', 'whatsapp', 'group', 'Family')},
      {...person('dev', 'Wizard devs', 'telegram', 'Shipped', 20), identities: ident('dev', 'telegram', 'group', 'Wizard devs')},
    ];
    // Stateful stand-in for the box: the catalogue (WizardOS seeded, empty) and labels carried by chats.
    let catalog = ['WizardOS'], rev = 1; const calls = [];
    const counts = () => catalog.map(name => ({name, chats: [...PEOPLE, ...GROUPS].filter(x => x.labels.includes(name)).length}));
    const cat = extra => ({labels: counts(), rev, ...extra});
    const canon = n => catalog.find(x => x.toLowerCase() === n.toLowerCase());
    const ctx = await browser.newContext({viewport, deviceScaleFactor: 2, colorScheme: scheme});
    await ctx.addInitScript(([s, tokens]) => {
      const noop = () => {};
      window.WizardApp = {ready: noop, update: {hold: () => ({release: noop})}, back: {register: noop}, on: noop, nav: {}, toast: noop, badge: {set: noop}};
      const mark = () => {
        const r = document.documentElement; if (!r) return false;
        r.dataset.wzHosted = ''; r.dataset.colorScheme = s; r.style.colorScheme = s;
        for (const [k, v] of Object.entries(tokens)) if (k !== 'glass') r.style.setProperty('--wz-' + k, v);
        r.style.background = tokens.glass;
        return true;
      };
      if (!mark()) new MutationObserver((_, o) => { if (mark()) o.disconnect(); }).observe(document, {childList: true});
    }, [scheme, SKINS[scheme]]);
    const page = await ctx.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const ownKey = '11'.repeat(32);
    const own = {account_id: ownKey, npub: L.encodePublic(ownKey), display_name: 'Owner'};
    await page.route('https://messenger.test/**', async route => {
      const req = route.request(), url = new URL(req.url()), p = url.pathname.slice(1);
      const body = () => JSON.parse(req.postData() || '{}');
      const ok = result => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({ok: true, result})});
      const bad = (status, message) => route.fulfill({status, contentType: 'application/json', body: JSON.stringify({ok: false, error: {code: 'invalid_input', message}})});
      if (p === 'api/view/session') return ok({authenticated: true, csrf_token: 'fixture'});
      if (p === 'api/status') return ok({state: 'ready', account_configured: true});
      if (p === 'api/identity') return ok({identity: own});
      if (p === 'api/contacts') return ok({contacts: []});
      if (p === 'api/invites') return ok({invites: []});
      if (p === 'api/dms') return ok({dms: []});
      if (p === 'api/unified/people') return ok({people: PEOPLE, seq: 5});
      if (p === 'api/unified/groups') return ok({groups: GROUPS, seq: 5});
      if (p === 'api/unified/labels' && req.method() === 'GET') return ok(cat());
      if (p === 'api/unified/labels') { calls.push(['create', body()]); const n = body().name.trim(); if (!canon(n)) { catalog.push(n); catalog.sort(); rev++; } return ok(cat({label: canon(n)})); }
      if (p === 'api/unified/labels/rename') {
        const {from, to} = body(); calls.push(['rename', from, to]); const cur = canon(from); if (!cur) return bad(404, 'Label not found');
        catalog = catalog.filter(x => x !== cur); if (!canon(to)) catalog.push(to); catalog.sort();
        for (const x of [...PEOPLE, ...GROUPS]) x.labels = [...new Set(x.labels.map(l => l === cur ? (canon(to) || to) : l))].sort(); rev++; return ok(cat());
      }
      if (p === 'api/unified/labels/delete') { const {name} = body(); calls.push(['delete', name]); catalog = catalog.filter(x => x !== name); for (const x of [...PEOPLE, ...GROUPS]) x.labels = x.labels.filter(l => l !== name); rev++; return ok(cat()); }
      let m = /^api\/unified\/people\/([^/]+)\/labels$/.exec(p);
      if (m) {
        const pr = [...PEOPLE, ...GROUPS].find(x => x.id === decodeURIComponent(m[1])); const names = body().labels; calls.push(['labels', pr.id, names]);
        pr.labels = [...new Set(names.map(n => canon(n) || n))].sort(); for (const n of pr.labels) if (!catalog.includes(n)) { catalog.push(n); catalog.sort(); } rev++;
        return ok({labels: pr.labels, catalog: counts(), rev});
      }
      const thread = /^api\/unified\/people\/([^/]+)$/.exec(p);
      if (thread) {
        const id = decodeURIComponent(thread[1]), pr = [...PEOPLE, ...GROUPS].find(x => x.id === id);
        if (req.method() === 'POST') { Object.assign(pr, body()); return ok(pr); }
        return ok({person: pr, messages: [], has_more: false, next_cursor: null, seq: 5, typing: []});
      }
      if (p.endsWith('/read')) return ok({});
      if (p === 'api/unified/connectors') return ok({providers: [
        {network: 'whatsapp', label: 'WhatsApp', supported: true, state: 'connected', flows: [], logins: [{id: 'l'}]},
        {network: 'telegram', label: 'Telegram', supported: true, state: 'connected', flows: [], logins: [{id: 'l'}]},
        {network: 'signal', label: 'Signal', supported: true, state: 'connected', flows: [], logins: [{id: 'l'}]},
        {network: 'line', label: 'LINE', supported: true, state: 'connected', flows: [], logins: [{id: 'l'}]}]});
      if (p.startsWith('api/unified/updates')) { await new Promise(r => setTimeout(r, 20000)); return ok({seq: 5}); }
      if (p.startsWith('api/')) return ok({});
      const file = path.join(root, p || 'index.html');
      if (!file.startsWith(root) || !fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
      return route.fulfill({status: 200, contentType: TYPES[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file)});
    });
    const shot = name => page.screenshot({path: path.join(out, `${name}-${label}-${scheme}.png`)});
    const rows = () => page.locator('.u-list > .u-person strong').allTextContents();
    const tall = async (loc, what) => { for (const b of await loc.all()) { const r = await b.boundingBox(); assert.ok(r && r.height >= 44 - 0.5 && r.width >= 44 - 0.5, what + ' tap target >= 44px: ' + JSON.stringify(r)); } };
    await page.goto('https://messenger.test/');
    await page.locator('.u-person', {hasText: 'James Carter'}).waitFor({timeout: 15000});

    // 1. An empty label exists in Filters from the start (WizardOS seeded) and shows the how-to empty state.
    const chip = page.locator('#u-filters .u-chip[data-filter="label:WizardOS"]');
    await chip.waitFor({timeout: 5000});
    await chip.click();
    assert.equal(await page.locator('.u-person').count(), 0, 'empty label shows no chats');
    const empty = await page.locator('.u-empty').innerText();
    assert.match(empty, /No chats in WizardOS yet/); assert.match(empty, /Labels/);
    await shot('empty-label');
    await page.locator('[data-filter=all]').click();

    // 2. Hold/right-click a PERSON (not just groups): Labels in the row menu, tick WizardOS.
    await page.locator('.u-person', {hasText: 'James Carter'}).click({button: 'right'});
    await page.getByRole('menuitem', {name: 'Labels'}).click();
    const sheet = page.locator('.u-sheet');
    assert.equal(await sheet.getAttribute('aria-label'), 'Labels');
    const row = sheet.getByRole('checkbox', {name: 'WizardOS'});
    await row.click();
    assert.equal(await row.getAttribute('aria-checked'), 'true', 'tick registers at once');
    await tall(sheet.locator('.u-label-row'), 'label row'); await tall(sheet.locator('.u-label-new input, .u-label-new button'), 'New label');
    // 3. New label from the same sheet; ticks it too.
    await sheet.getByLabel('New label').fill('Taxes'); await sheet.getByRole('button', {name: 'Add'}).click();
    assert.equal(await sheet.getByRole('checkbox', {name: 'Taxes'}).getAttribute('aria-checked'), 'true');
    await shot('labels-sheet');
    await page.waitForTimeout(200);
    assert.deepEqual(calls.filter(c => c[0] === 'labels').at(-1), ['labels', 'james', ['WizardOS', 'Taxes']]);
    // Outside tap closes the sheet (the dim area), and Back-less: the list is still there.
    await page.mouse.click(viewport.width - 4, 4);
    assert.equal(await page.locator('.u-sheet').count(), 0, 'outside tap closes the sheet');
    assert.ok((await rows()).includes('James Carter'), 'still on the list');

    // 4. A group and a merged person (two identities) from the chat info sheet.
    await page.locator('.u-person', {hasText: 'Family'}).click();
    await page.locator('.u-who, .u-head-title, header .u-who-text').first().click();
    await page.locator('.u-sheet').waitFor();
    assert.equal(await page.locator('.u-sheet h3', {hasText: 'Labels'}).count(), 1, 'Labels in the info sheet');
    await page.locator('.u-sheet').getByRole('checkbox', {name: 'WizardOS'}).click();
    await shot('info-sheet');
    await page.mouse.click(viewport.width - 4, 4);
    assert.equal(await page.locator('.u-sheet').count(), 0);
    await page.evaluate(() => history.back()).catch(() => {});
    if (await page.locator('.u-person').count() === 0) await page.getByRole('button', {name: /back/i}).first().click().catch(() => {});
    await page.locator('.u-person', {hasText: 'Marco Bianchi'}).click({button: 'right'});
    await page.getByRole('menuitem', {name: 'Labels'}).click();
    await page.locator('.u-sheet').getByRole('checkbox', {name: 'WizardOS'}).click();
    await page.waitForTimeout(200);
    await page.mouse.click(viewport.width - 4, 4);
    assert.deepEqual(calls.filter(c => c[0] === 'labels').map(c => c[1]).sort(), ['fam', 'james', 'james', 'marco'].sort().filter((x, i, a) => true));

    // 5. Filter: all networks that carry it.
    await page.locator('#u-filters .u-chip[data-filter="label:WizardOS"]').click();
    assert.deepEqual((await rows()).sort(), ['Family', 'James Carter', 'Marco Bianchi']);
    assert.equal(await page.locator('.u-person').count(), 3);
    await shot('filtered');

    // 6. Manage labels: reachable from the filters, rename, delete (two taps), create.
    await page.locator('#u-filters .u-chip[data-filter="manage-labels"]').click();
    const mg = page.locator('.u-sheet.u-manage-labels'); await mg.waitFor();
    await tall(mg.locator('.u-label-act'), 'manage action');
    await mg.getByLabel('New label name').fill('Ideas'); await mg.getByRole('button', {name: 'Create'}).click();
    await mg.locator('.u-label-manage', {hasText: 'Ideas'}).waitFor();
    await mg.locator('.u-label-manage', {hasText: 'Taxes'}).getByRole('button', {name: 'Rename'}).click();
    await mg.getByLabel('Rename Taxes').fill('Tax 2026'); await mg.getByRole('button', {name: 'Save'}).click();
    await mg.locator('.u-label-manage', {hasText: 'Tax 2026'}).waitFor();
    await shot('manage');
    await mg.locator('.u-label-manage', {hasText: 'Ideas'}).getByRole('button', {name: 'Delete'}).click();
    await mg.getByRole('button', {name: 'Delete label?'}).click();
    await page.waitForTimeout(200);
    assert.ok(!(await mg.innerText()).includes('Ideas'), 'deleted');
    assert.deepEqual(calls.filter(c => c[0] !== 'labels').map(c => c[0]), ['create', 'rename', 'delete']);
    await page.mouse.click(viewport.width - 4, 4);
    assert.equal(await page.locator('.u-sheet').count(), 0);
    assert.deepEqual((await rows()).sort(), ['Family', 'James Carter', 'Marco Bianchi'], 'chats survive label edits');
    // Deleting the label you are looking at falls back to All instead of an empty dead end.
    await page.locator('#u-filters .u-chip[data-filter="manage-labels"]').click();
    await page.locator('.u-sheet .u-label-manage', {hasText: 'WizardOS'}).getByRole('button', {name: 'Delete'}).click();
    await page.getByRole('button', {name: 'Delete label?'}).click(); await page.waitForTimeout(200);
    await page.mouse.click(viewport.width - 4, 4);
    assert.equal(await page.locator('#u-filters .u-chip[data-filter="label:WizardOS"]').count(), 0);
    assert.equal(await page.locator('.u-person').count(), 5, 'filter fell back to All, every chat is still there');
    assert.deepEqual(errors, [], 'no page errors');
    summary.push(`${scheme}-${label}: ok`);
    await ctx.close();
  }
  await browser.close();
  console.log(summary.join('\n'));
})().catch(e => { console.error(e); process.exit(1); });
