// Desktop split (Miguel, 31 Oct 2026): "see the message list and the messages at the same time, like the session list
// and the chats in the chat interface". A wide Messenger window shows the chat list on the left and the open chat on the
// right; narrow windows keep the one-pane Inbox. Synthetic APIs only (no server, no accounts, nothing is sent).
// node tests/desktop_split_browser.cjs [outdir]   (PLAYWRIGHT_MODULE=<playwright>; WIZARD_WEB_DIR=<wizard-ux>/web reads
// the real Landscapes Light skin tokens from the shell CSS, else a fixed copy is used).
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const L = require('../static/app.js');
const root = path.resolve(process.env.MESSENGER_STATIC_DIR || path.join(__dirname, '../static'));
const out = path.resolve(process.argv[2] || process.env.EVIDENCE_DIR || 'desktop-split-shots'); fs.mkdirSync(out, {recursive: true});
const WEB = process.env.WIZARD_WEB_DIR || '';
const TYPES = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.woff2': 'font/woff2'};
const now = Date.now(), min = 60e3;
const NETS = ['whatsapp', 'telegram', 'signal', 'instagram', 'line'];
// Skin tokens as the Wizard shell posts them (appearance-host.js): the canvas is transparent when hosted.
const SKINS = {
  dark: {scheme: 'dark', canvas: 'transparent', base: '#05030c', surface: 'color-mix(in srgb, #f3efff 6%, transparent)', 'surface-raised': 'color-mix(in srgb, #f3efff 10%, transparent)', text: '#f3efff', 'text-secondary': '#b9b0d8', 'text-muted': '#a59abf', border: 'rgba(205,190,255,.24)', accent: '#b99bff', 'accent-soft': 'color-mix(in srgb, #b99bff 16%, transparent)', 'on-accent': '#05030c', glass: '#1d1533'},
  light: {scheme: 'light', canvas: 'transparent', base: '#f5f2ec', surface: 'color-mix(in srgb, #211c17 5%, transparent)', 'surface-raised': 'color-mix(in srgb, #211c17 9%, transparent)', text: '#211c17', 'text-secondary': '#62584c', 'text-muted': '#756958', border: '#d4c7b8', accent: '#674a29', 'accent-soft': '#e9ddcb', 'on-accent': '#ffffff', glass: '#ece6dc'},
};
// Landscapes Light: the shell's own palette for that skin (core/skins.js, painted from JS at runtime), turned into app
// tokens the way the shell's appearance-host.js does. Falls back to a fixed copy of the same values.
async function landscapesLight() {
  let t = {bg: '#EEF1F4', ink: '#111216', 'ink-2': 'rgba(17,18,22,.76)', 'ink-3': 'rgba(17,18,22,.54)', 'line-2': 'rgba(0,0,0,.26)', 'violet-2': '#4A30CC', 'sk-win': 'rgba(250,250,252,.85)'}, source = 'fixed copy of core/skins.js';
  try {
    const src = fs.readFileSync(path.join(WEB, 'core/skins.js'), 'utf8'), m = /id: 'landscapes-light'[\s\S]*?t: T\((\{[\s\S]*?\})\) \}/.exec(src);
    if (WEB && m) { t = new Function('return ' + m[1])(); source = 'core/skins.js'; }
  } catch { /* fixed copy */ }
  return {scheme: 'light', canvas: 'transparent', base: t.bg, surface: `color-mix(in srgb, ${t.ink} 6%, transparent)`, 'surface-raised': `color-mix(in srgb, ${t.ink} 10%, transparent)`,
    text: t.ink, 'text-secondary': t['ink-2'], 'text-muted': t['ink-3'], border: t['line-2'], accent: t['violet-2'], 'accent-soft': `color-mix(in srgb, ${t['violet-2']} 16%, transparent)`, 'on-accent': '#fffdf8',
    glass: 'linear-gradient(' + t['sk-win'] + ', ' + t['sk-win'] + '), linear-gradient(160deg, #9cc3e6, #f1e2c6 55%, #8fb08a)', source};
}
const NAMES = ['Ana Souza', 'Ben Okafor', 'Chloe Martin', 'Dev Patel', 'Elena Rossi', 'Farid Haddad', 'Grace Lee', 'Hiro Sato', 'Ines Duarte', 'Jonas Berg', 'Kira Novak', 'Liam Walsh', 'Maya Cohen', 'Nico Ferraro', 'Olga Petrova', 'Pablo Ruiz', 'Quinn Adler', 'Rosa Lima', 'Sam Turner', 'Tara Singh', 'Umar Khan', 'Vera Lind', 'Wes Carter', 'Xia Wang', 'Yusuf Demir', 'Zoe Hart', 'Arjun Rao', 'Bea Klein', 'Caio Prado', 'Dana Wolfe'];
function fixture() {
  const people = NAMES.map((name, i) => {
    const id = 'p' + i, net = NETS[i % NETS.length];
    return {id, display_name: name, identities: [{id: id + '-i', network: net, kind: 'person', label: name}], labels: [], unread: i % 7 === 3 ? 2 : 0, muted: false, low_priority: false,
      last: {text: 'Message number ' + i + ' from ' + name.split(' ')[0], timestamp: now - (i + 1) * 9 * min, outgoing: i % 4 === 0}, language: '', peer_read_ts: 0};
  });
  const threads = {};
  for (const p of people) threads[p.id] = Array.from({length: 8}, (_, k) => ({id: p.id + '-m' + k, sender: k % 2 ? '' : p.display_name, outgoing: !!(k % 2), original: (k % 2 ? 'My reply ' : 'Hi from ' + p.display_name.split(' ')[0] + ', line ') + k + (k === 3 ? ' with a somewhat longer sentence so the bubble wraps across a couple of lines on a desktop window.' : ''), translated: '', timestamp: now - (40 - k * 4) * min, identity_id: p.identities[0].id, network: p.identities[0].network, reactions: [], msgtype: 'm.text'}));
  return {people, threads};
}

(async () => {
  const browser = await chromium.launch(), observations = [], failures = [], unexercised = [], insertions = [];
  const seqOnlyControl = process.env.MESSENGER_SCROLL_INSERTION_CONTROL === 'seq-only';
  try {
  const scenes = process.env.MESSENGER_SCROLL_CAUSAL_ONLY === '1' || seqOnlyControl ? [['dark',1280]] : [['dark',1280], ['light',1280], ['dark',390], ['light',390]];
  for (const [skin, width] of scenes) {
    const tokens = SKINS[skin], {people, threads} = fixture(), drafts = [], updates = [];
    let draftSeq = 0, peopleReads = 0;
    let insertion = null;
    const ctx = await browser.newContext({viewport: {width, height: 860}, colorScheme: tokens.scheme});
    try {
    await ctx.addInitScript(([s, tk]) => {
      const noop = () => {};
      window.WizardApp = {ready: noop, update: {hold: () => ({release: noop})}, back: {register: noop}, on: noop, nav: {}, toast: noop, badge: {set: noop}};
      const mark = () => {
        const r = document.documentElement; if (!r) return false;
        r.dataset.wzHosted = ''; r.dataset.colorScheme = s; r.style.colorScheme = s;
        for (const [k, v] of Object.entries(tk)) if (!['glass', 'scheme', 'source'].includes(k)) r.style.setProperty('--wz-' + k, v);
        r.style.background = tk.glass; return true;
      };
      if (!mark()) new MutationObserver((_, o) => { if (mark()) o.disconnect(); }).observe(document, {childList: true});
    }, [tokens.scheme, tokens]);
    const page = await ctx.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const ownKey = '11'.repeat(32), peerKey = '22'.repeat(32);
    const own = {account_id: ownKey, npub: L.encodePublic(ownKey), display_name: 'Owner'};
    const dm = {group_id: 'ab'.repeat(32), members: [{member_id: peerKey, display_name: 'Private Alice'}, {member_id: ownKey}]};
    const PRIVATE = [{message_id: 'e'.repeat(64), group_id: dm.group_id, author: peerKey, direction: 'received', text: 'Hi there from the Wizard chat', created_at: (now - 3 * min) / 1000}];
    await page.route('https://messenger.test/**', async route => {
      const req = route.request(), url = new URL(req.url()), p = url.pathname.slice(1);
      const ok = result => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({ok: true, result})});
      const body = () => JSON.parse(req.postData() || '{}');
      if (p === 'api/view/session') return ok({authenticated: true, csrf_token: 'fixture'});
      if (p === 'api/status') return ok({state: 'ready', account_configured: true});
      if (p === 'api/identity') return ok({identity: own});
      if (p === 'api/contacts') return ok({contacts: []});
      if (p === 'api/invites') return ok({invites: []});
      if (p === 'api/dms') return ok({dms: [dm]});
      if (p.startsWith('api/dms/') && p.endsWith('/messages')) return ok({messages: PRIVATE, next_cursor: null});
      if (p === 'api/unified/people') { peopleReads++; return ok({people, seq: 5}); }
      if (p === 'api/unified/groups') return ok({groups: [], seq: 5});
      if (p === 'api/unified/directory') return ok({people: people.map(({id, display_name, identities}) => ({id, display_name, identities})), groups: []});
      if (p === 'api/unified/search') {
        const q = (url.searchParams.get('q') || '').toLowerCase();
        const hits = []; for (const pr of people) for (const m of threads[pr.id]) if (m.original.toLowerCase().includes(q)) hits.push({person_id: pr.id, message_id: m.id, display_name: pr.display_name, network: m.network, original: m.original, timestamp: m.timestamp});
        return ok({messages: hits.slice(0, 5), next_cursor: null});
      }
      const thread = /^api\/unified\/people\/([^/]+)$/.exec(p);
      if (thread) {
        const id = decodeURIComponent(thread[1]), pr = people.find(x => x.id === id);
        if (req.method() === 'POST') { Object.assign(pr, body()); return ok(pr); }
        return ok({person: pr, messages: threads[id], has_more: false, next_cursor: null, seq: 5, typing: []});
      }
      if (p.endsWith('/read')) return ok({});
      if (p === 'api/drafts' && req.method() === 'GET') return ok({drafts});
      if (p === 'api/drafts' && req.method() === 'POST') { const b = body(); const d = {id: 'd' + (++draftSeq), person_id: b.person_id, identity_id: b.identity_id, text: b.text || '', revision: 1, state: 'draft', attachments: [], created_by: {id: 'owner', name: 'You'}, updated: Date.now()}; drafts.push(d); return ok({draft: d}); }
      const dr = /^api\/drafts\/([^/]+)$/.exec(p);
      if (dr) {
        const d = drafts.find(x => x.id === dr[1]); if (!d) return route.fulfill({status: 404, contentType: 'application/json', body: JSON.stringify({ok: false, error: {code: 'not_found', message: 'gone'}})});
        if (req.method() === 'DELETE') { drafts.splice(drafts.indexOf(d), 1); return ok({}); }
        if (req.method() === 'POST') { const b = body(); Object.assign(d, {text: b.text, identity_id: b.identity_id, revision: d.revision + 1, updated: Date.now(), updated_by: {id: 'owner'}}); return ok({draft: d}); }
        return ok({draft: d});
      }
      if (p === 'api/unified/connectors') return ok({providers: NETS.map(n => ({network: n, label: n, supported: true, state: 'connected', flows: [], logins: [{id: 'l'}]}))});
      if (p.startsWith('api/unified/updates')) {
        for (let i = 0; i < 30 && !updates.length; i++) await new Promise(r => setTimeout(r, 100));
        return ok(updates.length ? updates.shift() : {seq: 5});
      }
      if (p.startsWith('api/') || p.startsWith('contacts/')) return ok({});
      const file = path.join(root, p || 'index.html');
      if (!file.startsWith(root) || !fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
      return route.fulfill({status: 200, contentType: TYPES[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file)});
    });

    await page.addInitScript(() => {
      window.__listRefreshes = 0;
      new MutationObserver(records => {
        for (const r of records) if (r.type === 'childList' && r.target.classList?.contains('u-list')) window.__listRefreshes++;
      }).observe(document, {childList: true, subtree: true});
    });
    const checkSource = require('./browser_source_custody.cjs')(page, root, out, skin+'-'+width);
    await page.goto('https://messenger.test/');
    await page.locator('.u-list .u-person', {hasText: 'Kira Novak'}).waitFor();
    await checkSource();
    const list = page.locator('.u-list');
    await list.evaluate(el => { el.scrollTop = 400; });
    const frames = () => page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
    await frames();
    const start = await list.evaluate(el => el.scrollTop);
    assert.ok(start > 300, 'probe starts with a genuinely scrolled list');
    const snapshot = async step => {
      await frames();
      const row = await page.evaluate(step => ({step, top: document.querySelector('.u-list')?.scrollTop,
        height: document.querySelector('.u-list')?.scrollHeight, refreshes: window.__listRefreshes}), step);
      observations.push({skin, width, start, ...row});
      if (Math.abs(row.top - start) >= 2) failures.push({skin, width, start, ...row});
    };
    const before = await page.evaluate(() => window.__listRefreshes);
    updates.push({seq: 6});
    await page.waitForFunction(before => window.__listRefreshes > before, before, {timeout: 6000});
    await snapshot('same-data-feed-refresh');
    // Continue after an observed failure to retain all comparison cases. Failure remains blocking at the end.
    await list.evaluate(el => { el.scrollTop = 400; }); await frames();
    await page.locator('.u-list .u-person', {hasText: 'Kira Novak'}).click();
    await page.locator('.u-who-text strong', {hasText: 'Kira Novak'}).waitFor();
    const save = page.waitForResponse(r => new URL(r.url()).pathname === '/api/drafts' && r.request().method() === 'POST', {timeout:6000});
    await page.locator('textarea[aria-label="Message"]').fill('Synthetic retained scroll draft');
    try { await save; }
    catch (error) {
      unexercised.push({skin,width,step:'draft-save',reason:'Selected source did not issue the fixture draft POST',
        pageErrors:errors,composer:await page.locator('textarea[aria-label="Message"]').inputValue()});
      continue;
    }
    assert.equal(drafts.find(d => d.person_id === 'p10')?.text, 'Synthetic retained scroll draft');
    if (width >= 640) {
      await snapshot('draft-save');
      if (process.env.MESSENGER_SCROLL_CAUSAL_ONLY === '1') continue;
      await page.locator('.u-list .u-person', {hasText: 'Maya Cohen'}).click();
      await page.locator('.u-who-text strong', {hasText: 'Maya Cohen'}).waitFor();
      await snapshot('switch-after-draft');
    } else {
      await page.locator('.u-back').click(); await list.waitFor(); await snapshot('phone-back-after-draft');
    }
    // A genuine synthetic feed inserts a row and changes content height; no app state is patched.
    await list.evaluate(el => { el.scrollTop = 400; }); await frames();
    const geometry = () => list.evaluate(el => ({height: el.scrollHeight, top: el.scrollTop, clientHeight: el.clientHeight,
      overflowY: getComputedStyle(el).overflowY, rows: [...el.querySelectorAll('.u-person')].map(r => r.dataset.pid),
      filters: [...document.querySelectorAll('#u-filters [aria-pressed="true"]')].map(e => e.textContent.trim()),
      extra: [...el.querySelectorAll('[data-pid="p-extra"]')].map(r => ({height: r.offsetHeight, connected: r.isConnected, text: r.textContent}))}));
    const beforeInsertion = await geometry(), oldHeight = beforeInsertion.height;
    insertion = {skin, width, seqOnlyControl, before: beforeInsertion, peopleReadsBefore: peopleReads};
    insertions.push(insertion);
    assert.ok(!beforeInsertion.rows.includes('p-extra'), 'feed row absent before insertion');
    // Oldest synthetic row: the owner's reading position stays above it, while document height genuinely grows.
    const extra = {...people[0], id:'p-extra', display_name:'Zed Synthetic Archive', identities:[{id:'p-extra-i',network:'telegram',kind:'person',label:'Zed Synthetic Archive'}],
      last:{text:'Older feed row',timestamp:now - 900 * min,outgoing:false}, unread:0};
    // apply(r) merges only r.people. A seq-only event redraws the cached list; mutating the server-side
    // people array cannot update the client's already serialized copy. Deliver the row ONLY through the feed.
    const event = seqOnlyControl ? {seq:7} : {seq:7, people:[extra]};
    const delivered = page.waitForResponse(async r => new URL(r.url()).pathname === '/api/unified/updates'
      && (await r.json()).result?.seq === 7, {timeout:6000});
    updates.push(event);
    insertion.response = await (await delivered).json();
    assert.deepEqual(insertion.response, {ok:true, result:event}, 'exact synthetic feed response delivered');
    if (!seqOnlyControl) assert.equal(insertion.response.result.people[0].id, extra.id);
    try {
      await page.waitForFunction(() => document.querySelector('.u-list [data-pid="p-extra"]')?.isConnected,
        null, {timeout:6000});
    } finally {
      await frames(); insertion.after = await geometry(); insertion.peopleReadsAfter = peopleReads;
      fs.writeFileSync(path.join(out, `insertion-${skin}-${width}.json`), JSON.stringify(insertion, null, 2));
    }
    assert.equal(insertion.peopleReadsAfter, insertion.peopleReadsBefore, 'insertion came from feed, not list refetch');
    assert.equal(insertion.after.extra.length, 1, 'exactly one rendered feed row');
    assert.equal(insertion.after.rows.length, beforeInsertion.rows.length + 1, 'feed adds one rendered row');
    assert.equal(insertion.after.rows.at(-1), extra.id, 'oldest feed row rendered last');
    assert.ok(insertion.after.height > oldHeight, 'feed insertion genuinely changes list height');
    assert.ok(insertion.after.height - oldHeight >= insertion.after.extra[0].height - 1, 'height grows by rendered feed row');
    await snapshot('height-changing-feed-refresh');
    await page.screenshot({path: path.join(out, `scroll-${skin}-${width}.png`)});
    assert.deepEqual(errors, [], 'no page errors');
    } finally { await ctx.close(); }
  }
  } finally {
    fs.writeFileSync(path.join(out, 'scroll-observations.json'), JSON.stringify({observations, failures, unexercised, insertions}, null, 2));
    await browser.close(); console.log('CLEANUP list_scroll browser closed');
  }
  assert.deepEqual(unexercised, [], 'scroll probe unexercised (not a reproduced regression)');
  assert.deepEqual(failures, [], 'list-scroll position changed');
  console.log('ALL PASS list_scroll_browser (two skins, desktop and phone; feed, draft, switch/Back)');
})().catch(e => { console.error(e); process.exitCode = 1; });
