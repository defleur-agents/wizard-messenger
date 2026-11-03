// Voice notes from a browser without WebCodecs' AudioEncoder (Safari before 26, the Mac app's web view) are M4A.
// Telegram plays M4A as a voice note, so the take goes out as it is instead of failing with
// "This device cannot prepare voice notes for Telegram yet". Anything else without an encoder still fails clearly.
// Run: M4A=<file.m4a> AAC=<file.aac> WEBM=<file.webm> NODE_PATH=<node_modules> node tests/voice_m4a_fallback_browser.cjs
const assert = require('assert'), fs = require('fs'), path = require('path');
const pw = require('playwright'), engine = pw[process.env.BROWSER || 'chromium'];
(async () => {
  const m4a = fs.readFileSync(process.env.M4A).toString('base64');
  const js = fs.readFileSync(path.join(__dirname, '../static/unified.js'), 'utf8');
  const browser = await engine.launch({args: ['--autoplay-policy=no-user-gesture-required']}), page = await browser.newPage();
  // A real secure origin: unified.js reads localStorage at load and AudioEncoder needs a secure context.
  await page.route('https://messenger.test/**', r => r.fulfill(r.request().url().endsWith('.js') ? {contentType: 'text/javascript', body: js}
    : {contentType: 'text/html', body: '<!doctype html><div id="messenger"></div><script src="/unified.js"></script>'}));
  await page.goto('https://messenger.test/');
  assert.equal(await page.evaluate(() => typeof window.MessengerUnified_toOggOpus), 'function', 'test hook loaded');
  const run = (b64, encoder, type) => page.evaluate(async ([b64, encoder, type]) => {
    const keep = window.AudioEncoder; if (encoder === 'none') delete window.AudioEncoder;
    if (encoder === 'broken') window.AudioEncoder = class { constructor() { throw new Error('opus unsupported'); } };
    try {
      const b = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      const o = await window.MessengerUnified_toOggOpus(new Blob([b], {type}));
      const u = new Uint8Array(await o.arrayBuffer());
      return {type: o.type, size: u.length, b64: u.length < 400000 ? btoa(String.fromCharCode(...u.subarray(0, 64))) : '', same: u.length === b.length && u.every((x, i) => x === b[i]), head: String.fromCharCode(...u.subarray(0, 4))};
    } catch (e) { return {error: e.message}; } finally { window.AudioEncoder = keep; }
  }, [b64, encoder, type]);
  const noEnc = await run(m4a, 'none', 'audio/mp4');
  assert.deepEqual([noEnc.type, noEnc.same], ['audio/mp4', true], 'M4A without AudioEncoder is sent as is: ' + JSON.stringify(noEnc));
  const broken = await run(m4a, 'broken', 'audio/mp4');
  assert.deepEqual([broken.type, broken.same], ['audio/mp4', true], 'M4A whose re-encode fails is sent as is: ' + JSON.stringify(broken));
  // With a working encoder an M4A this browser can decode still becomes Ogg Opus (Chromium builds without AAC fall back).
  assert.equal(await page.evaluate(() => typeof AudioEncoder), 'function', 'this browser has WebCodecs AudioEncoder');
  const decodes = await page.evaluate(async b64 => { try { await new OfflineAudioContext(1, 48000, 48000).decodeAudioData(Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer); return true; } catch { return false; } }, m4a);
  const withEnc = await run(m4a, 'real', 'audio/mp4');
  if (decodes) assert.equal(withEnc.head, 'OggS', 'with AudioEncoder, M4A still becomes Ogg Opus: ' + JSON.stringify(withEnc));
  else assert.deepEqual([withEnc.type, withEnc.same], ['audio/mp4', true], 'undecodable M4A is sent as is: ' + JSON.stringify(withEnc));
  const junk = await run(btoa('not audio at all, no container'), 'none', 'audio/aac');
  assert.match(junk.error || '', /cannot prepare voice notes/, 'unknown audio without an encoder still fails clearly');
  // Not M4A and no encoder (the Mac app's WebM, raw AAC): played once into the browser's M4A recorder.
  const aac = await run(fs.readFileSync(process.env.AAC).toString('base64'), 'none', 'audio/aac');
  assert.equal(aac.type, 'audio/mp4', 'AAC without an encoder is re-recorded as M4A: ' + JSON.stringify(aac));
  assert.equal(String.fromCharCode(...Buffer.from(aac.b64 || '', 'base64').subarray(4, 8)) || aac.ftyp, 'ftyp');
  // A WebM cut off mid-cluster still rewraps to Ogg Opus with the packets it has.
  const webm = fs.readFileSync(process.env.WEBM); const cut = webm.subarray(0, webm.length - 37);
  const trunc = await run(cut.toString('base64'), 'none', 'audio/webm');
  assert.equal(trunc.head, 'OggS', 'truncated WebM still rewraps: ' + JSON.stringify(trunc));
  console.log(JSON.stringify({aac: {type: aac.type, size: aac.size}, trunc: {head: trunc.head, size: trunc.size}, noEnc, broken, decodes, withEnc: {type: withEnc.type, head: withEnc.head}, junk}));
  console.log('pass');
  await browser.close();
})().catch(e => { console.error('FAIL', e.message); process.exit(1); });
