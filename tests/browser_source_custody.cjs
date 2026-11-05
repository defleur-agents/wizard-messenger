// Passive network-body custody: no app state, DOM methods, or scroll handling is modified.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
module.exports = function sourceCustody(page, root, out, label) {
  const pending = [], rows = [], errors = [];
  page.on('response', response => {
    const u = new URL(response.url());
    if (u.origin !== 'https://messenger.test' || !u.pathname.endsWith('.js')) return;
    pending.push((async () => {
      const relative = decodeURIComponent(u.pathname.slice(1)), file = path.resolve(root, relative);
      const syntheticPlatform = u.pathname.startsWith('/wizard-os-home/core/');
      assert.ok(file.startsWith(root + path.sep), 'served script confined to selected snapshot');
      if (!syntheticPlatform) assert.equal(response.status(), 200, 'script HTTP status: ' + relative);
      const bytes = await response.body(), actual = hash(bytes), expected = syntheticPlatform ? null : hash(fs.readFileSync(file));
      if (!syntheticPlatform) assert.equal(actual, expected, 'selected source script bytes: ' + relative);
      const store = path.join(out, 'served-scripts'); fs.mkdirSync(store, {recursive:true});
      fs.writeFileSync(path.join(store, actual + '.js'), bytes);
      rows.push({status:response.status(), url:response.url(), resourceType:response.request().resourceType(), file:syntheticPlatform ? null : file, scope:syntheticPlatform?'synthetic-platform-fixture':'selected-app-source', sha256:actual, expected_sha256:expected});
    })().catch(error => errors.push(String(error))));
  });
  return async () => {
    await Promise.all(pending);
    fs.writeFileSync(path.join(out, 'served-source-' + label + '.json'), JSON.stringify({root, harness_sha256:hash(fs.readFileSync(__filename)), rows, errors}, null, 2));
    assert.deepEqual(errors, [], 'no served-script custody mismatch');
    for (const script of ['app.js', 'unified.js']) assert.ok(rows.some(r => new URL(r.url).pathname === '/' + script && r.resourceType === 'script'), 'actual script response: ' + script);
  };
};
