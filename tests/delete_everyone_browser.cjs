/* Miguel (5 Nov 2026, Mac app): "Delete for everyone" on a sent Telegram voice note did nothing.
 * The Mac app's web view has no JavaScript confirm panel, so window.confirm() silently answers false and the
 * delete never left the box (Synapse held only the redaction his phone made later). This drives the exact production
 * message menu with a confirm() that behaves like that web view and requires the in-app sheet instead.
 * MESSENGER_SOURCE=<old unified.js> proves the base fails. */
const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const source = fs.readFileSync(process.env.MESSENGER_SOURCE || path.join(__dirname, '../static/unified.js'), 'utf8');
function fn(name) {
  const m = source.match(new RegExp('\\n  (async )?function ' + name + '\\('));
  assert.ok(m, 'missing ' + name);
  const start = m.index + 1, end = source.indexOf('\n  }\n', start);
  return source.slice(start, end + 4);
}
const fixture = `
const s = {}, view = {id: 'p1'}, store = {threads: {p1: {}}}, recent = [], QUICK = ['👍'], shown = {};
let lastFocus = null, connectorController = null;
const $ = id => document.getElementById(id);
const node = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; };
const button = (text, f, cls) => { const e = node('button', cls, text); e.type = 'button'; e.onclick = f; return e; };
const iconButton = (ic, label, f) => { const e = button(label, f); e.setAttribute('aria-label', label); return e; };
const icon = () => node('span'), bridged = n => n === 'telegram', grid = () => node('div');
const placeMenu = () => {}, outsideCloses = () => {}, hold = () => {}, syncBar = () => {}, startReply = () => {}, startEdit = () => {};
const react = () => {}, toast = () => {}, mediaURL = id => id, paintThread = () => {}, mergeMessages = () => {};
const error = e => { window.errors.push(e.message); };
const call = async (p, body) => { window.calls.push({p, body}); return {message: {}}; };
${fn('closeOverlay')}
${fn('overlay')}
${fn('ask')}
${fn('menu')}
${fn('del')}
window.openMenu = m => menu(m, document.querySelector('#bubble'));`;
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROMIUM});
  try {
    const p = await browser.newPage({viewport: {width: 1280, height: 800}}); const pageErrors = [];
    p.on('pageerror', e => pageErrors.push(e.message));
    p.on('dialog', d => { pageErrors.push('native dialog shown: ' + d.message()); d.dismiss(); });
    const voice = {id: '$voice', network: 'telegram', outgoing: true, msgtype: 'm.audio', media: {mime: 'audio/ogg'}, original: ''};
    async function setup() {
      await p.setContent('<div id="messenger"><div class="u-row"><div id="bubble"></div></div></div>');
      // Like the Mac app's web view: no confirm panel, the answer is always "no", nothing is shown.
      await p.evaluate(() => { window.calls = []; window.errors = []; window.confirms = 0; window.confirm = () => { window.confirms++; return false; }; });
      await p.evaluate(fixture);
    }
    // 1. Delete for everyone asks in the app and, on Delete, deletes for everyone.
    await setup(); await p.evaluate(m => openMenu(m), voice);
    await p.getByRole('menuitem', {name: 'Delete for everyone'}).click();
    await p.getByRole('dialog', {name: 'Delete for everyone?'}).waitFor({timeout: 2000});
    await p.getByRole('button', {name: 'Delete', exact: true}).click();
    await p.waitForFunction(() => window.calls.length === 1, null, {timeout: 2000});
    assert.deepEqual(await p.evaluate(() => window.calls), [{p: 'messages/%24voice/delete', body: {everyone: true}}]);
    assert.equal(await p.evaluate(() => window.confirms), 0, 'never relies on window.confirm');
    console.log('PASS Delete for everyone asks in the app and deletes for everyone');
    // 2. Keep cancels with nothing sent.
    await setup(); await p.evaluate(m => openMenu(m), voice);
    await p.getByRole('menuitem', {name: 'Delete for everyone'}).click();
    await p.getByRole('button', {name: 'Keep'}).click(); await p.waitForTimeout(200);
    assert.deepEqual(await p.evaluate(() => window.calls), [], 'Keep sends nothing');
    console.log('PASS Keep sends nothing');
    // 3. Delete for me needs no question.
    await setup(); await p.evaluate(m => openMenu(m), voice);
    await p.getByRole('menuitem', {name: 'Delete for me'}).click();
    await p.waitForFunction(() => window.calls.length === 1, null, {timeout: 2000});
    assert.deepEqual(await p.evaluate(() => window.calls[0].body), {everyone: false});
    console.log('PASS Delete for me');
    // 4. No native confirm() anywhere in Messenger's view.
    assert.equal(/[^.\w]confirm\(/.test(source.replace(/\/\/.*$/gm, '')), false, 'window.confirm() is silently "no" in the Mac app');
    assert.deepEqual(pageErrors, []); assert.deepEqual(await p.evaluate(() => window.errors), []);
    console.log('ALL PASS delete_everyone_browser');
  } finally { await browser.close(); }
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
