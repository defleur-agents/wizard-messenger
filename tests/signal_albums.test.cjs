// Run on forum after test_signal_albums.py exports real converter-ingress rows.
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs');
const src = fs.readFileSync(__dirname + '/../static/unified.js', 'utf8');
const a = src.indexOf('  function albumPosts('), z = src.indexOf('  function nearBottom(', a);
assert(a >= 0 && z > a);
const albumPosts = new Function(src.slice(a, z) + '; return albumPosts;')();
const part = (i, extra={}) => ({id: ['$z-red','$a-green','$m-blue'][i], album: 'signal:native:1', identity_id: 'signal-fixture', network: 'signal', sender: 'Fixture', outgoing: false, timestamp: 1, msgtype: 'm.image', original: i === 0 ? 'Three photos' : '', media: {album_index: i, album_count: 3}, reactions: [], ...extra});

test('explicit ordinal wins over random event IDs and reversed delivery without mutating canonical rows', () => {
  const rows = [part(2), part(0), part(1)], before = structuredClone(rows), posts = albumPosts(rows);
  assert.equal(posts.length, 1); assert.deepEqual(posts[0].photos.map(p => p.id), ['$z-red','$a-green','$m-blue']);
  assert.equal(posts[0].original, 'Three photos'); assert.deepEqual(rows, before);
  assert.deepEqual(albumPosts(structuredClone(rows)), posts);
});
test('all distinct captions remain visible in tile order and canonical per-part captions survive', () => {
  const rows = [part(2, {original: 'Blue caption'}), part(0), part(1, {original: 'Green caption'})];
  const post = albumPosts(rows)[0];
  assert.equal(post.original, 'Three photos\n\nGreen caption\n\nBlue caption');
  assert.equal(post.photos[1].original, 'Green caption');
});
test('never crosses text, sender, identity, direction, network or distinct native-ID boundary', () => {
  const first = part(0);
  for (const other of [part(1, {sender:'Other'}), part(1, {identity_id:'other'}), part(1, {outgoing:true}), part(1, {network:'telegram'}), part(1, {album:'signal:other-native:1'}), part(1, {msgtype:'m.text',media:null})]) {
    assert.equal(albumPosts([first, other]).length, 2);
  }
  assert.equal(albumPosts([first, {id:'text',msgtype:'m.text',original:'Between'}, part(1)]).length, 3);
  assert.equal(albumPosts([part(0,{album:null}),part(1,{album:null})]).length, 2);
});
test('single image and Telegram timeline ordering remain unchanged', () => {
  const single = part(0,{album:null}); assert.strictEqual(albumPosts([single])[0], single);
  const rows = [part(2,{network:'telegram'}), part(0,{network:'telegram'}),part(1,{network:'telegram'})];
  assert.deepEqual(albumPosts(rows)[0].photos.map(p=>p.id), rows.map(p=>p.id));
});
test('reaction projection retains canonical part identity and deleted caption never leaks', () => {
  const rows = [part(0),part(1,{reactions:[{key:'👍',count:1,mine:true}]}),part(2)];
  assert.deepEqual(albumPosts(rows)[0].reactions, [{key:'👍',count:1,mine:true}]);
  assert.equal(rows[1].id, '$a-green'); assert.deepEqual(rows[0].reactions, []);
  rows[0].deleted = true;
  assert.equal(albumPosts(rows)[0].original, '');
});
test('actual old vs patched converter outputs through persisted public ingress rows', {skip: !process.env.SIGNAL_INGRESS_PROOF}, () => {
  const proof = JSON.parse(fs.readFileSync(process.env.SIGNAL_INGRESS_PROOF));
  assert.equal(albumPosts(proof.baseline).length, 4, 'old converter emits three independent images plus caption');
  for (const name of ['candidate','after_reaction','after_restart']) {
    const posts = albumPosts(proof[name]); assert.equal(posts.length,1,name);
    assert.deepEqual(posts[0].photos.map(p=>p.media.filename), ['red.png','green.png','blue.png']);
    assert.equal(posts[0].original,'Three photos');
    assert.deepEqual(posts[0].photos.map(p=>p.media.album_index),[0,1,2]);
  }
  const afterDelete = albumPosts(proof.after_part_delete)[0];
  assert.deepEqual(afterDelete.photos.filter(p=>!p.deleted).map(p=>p.id), ['$z-red','$m-blue']);
  assert.equal(afterDelete.photos[1].media.album_index,1);
});
