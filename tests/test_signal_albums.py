"""Signal album metadata is explicit, validated and never inferred from clocks.

The converter integration class requires BOTH JSON outputs from the Dockerfile's
same Go fixture before/after patch. Hand-written schema cases are not ingress proof.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from unified import UnifiedInbox

MARKER = 'org.wizard.signal.album'


class SignalAlbumSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inbox = UnifiedInbox(self.tmp.name, Mock())
        self.inbox.mx = Mock(return_value={'event_id': '$receipt'})
        self.identity = self.inbox.store.identity('signal', '!fixture:test', 'Signal fixture')
        self.inbox.owner = '@owner:test'

    def event(self, key='$part', **marker):
        return {'type': 'm.room.message', 'event_id': key, 'sender': '@fixture:test', 'origin_server_ts': 1700000000000,
                'content': {'msgtype': 'm.image', 'body': 'photo.png', 'url': 'mxc://fixture/photo',
                            'info': {'mimetype': 'image/png'}, MARKER: dict(id='native:1', index=0, count=3, **marker)}}

    def put(self, event, identity=None):
        self.inbox.ingest(identity or self.identity, {}, event)
        return self.inbox.row(event['event_id'])

    def test_valid_metadata_persists_and_survives_public_decoration(self):
        row = self.put(self.event())
        self.assertEqual(row['album'], 'signal:native:1')
        self.assertEqual(row['media']['album_index'], 0)
        self.assertEqual(row['media']['album_count'], 3)
        self.assertEqual(row['media']['filename'], 'photo.png')
        self.assertNotIn('mxc', row['media'])

    def test_invalid_marker_types_and_limits_never_group(self):
        bad = [None, [], '', {}, {'id': '', 'index': 0, 'count': 3}, {'id': 'x'*201, 'index': 0, 'count': 3}]
        for field, values in [('id', [1, True, [], {}]), ('index', [True, False, -1, 3, 0.0, '0', None]),
                              ('count', [True, 1, 101, 3.0, '3', None])]:
            bad.extend(dict({'id': 'native:1', 'index': 0, 'count': 3}, **{field: value}) for value in values)
        for i, group in enumerate(bad):
            with self.subTest(group=group):
                ev = self.event('$bad%d' % i); ev['content'][MARKER] = group
                self.assertFalse(self.put(ev)['album'])

    def test_unmarked_same_timestamp_is_never_grouped(self):
        for i in range(3):
            ev = self.event('$plain%d' % i); del ev['content'][MARKER]
            self.assertFalse(self.put(ev)['album'])

    def test_other_network_text_and_invalid_media_ignore_signal_marker(self):
        for i, network in enumerate(['telegram', 'whatsapp', 'matrix']):
            identity = self.inbox.store.identity(network, '!other%d:test' % i, 'Other')
            self.assertFalse(self.put(self.event('$network%d' % i), identity)['album'])
        for i, changes in enumerate([{'msgtype': 'm.text'}, {'msgtype': 'm.video'}, {'url': ''}, {'url': 'https://fixture/photo'}, {'url': {'bad': 1}}]):
            ev = self.event('$kind%d' % i); ev['content'].update(changes)
            self.assertFalse(self.put(ev)['album'])

    def test_caption_and_link_preview_keep_per_part_owner_without_private_uris(self):
        ev = self.event(); ev['content'].update(body='Three photos', filename='red.png', **{
            'com.beeper.linkpreviews': [{'matched_url': 'https://example.org/', 'og:title': 'Fixture', 'og:image': 'mxc://fixture/preview'}]})
        row = self.put(ev)
        self.assertEqual(row['original'], 'Three photos')
        self.assertEqual(row['media']['filename'], 'red.png')
        self.assertEqual(row['links'][0]['title'], 'Fixture')
        self.assertNotIn('mxc', row['links'][0])
        self.assertNotIn('mxc', row['media'])

    def test_album_actions_respect_text_boundary_direction_identity_and_sender(self):
        for i in range(3):
            ev = self.event('$scope%d' % i); ev['content'][MARKER]['index'] = i
            if i == 1: ev['content']['msgtype'] = 'm.text'
            self.put(ev)
        self.assertEqual([r['id'] for r in self.inbox.album_rows('$scope0')], ['$scope0'])
        ev = self.event('$outgoing'); ev['sender'] = self.inbox.owner; self.put(ev)
        self.assertEqual([r['id'] for r in self.inbox.album_rows('$scope2')], ['$scope2'])
        ev = self.event('$sender'); ev['sender'] = '@other:test'; self.put(ev)
        self.assertEqual([r['id'] for r in self.inbox.album_rows('$outgoing')], ['$outgoing'])
        other = self.inbox.store.identity('signal', '!other:test', 'Other room')
        self.put(self.event('$room'), other)
        self.assertEqual([r['id'] for r in self.inbox.album_rows('$sender')], ['$sender'])


@unittest.skipUnless(os.environ.get('SIGNAL_CONVERTER_FIXTURES'), 'requires actual pinned Go converter fixture outputs')
class SignalConverterIngressTests(SignalAlbumSchemaTests):
    def test_actual_converter_output_ingests_reorders_reacts_restarts_and_deletes_native_parts(self):
        root = Path(os.environ['SIGNAL_CONVERTER_FIXTURES'])
        candidate = json.loads((root / 'candidate.json').read_text())
        baseline = json.loads((root / 'baseline.json').read_text())
        self.assertEqual(len(candidate), 3)
        self.assertEqual(len(baseline), 4)
        proof = {}
        # Baseline/candidate are genuine converter outputs for the same DataMessage.
        baseline_inbox = UnifiedInbox(str(Path(self.tmp.name) / 'baseline'), Mock())
        old = baseline_inbox.store.identity('signal', '!baseline:test', 'Baseline')
        for event in baseline:
            baseline_inbox.ingest(old, {}, event)
        proof['baseline'] = baseline_inbox.store.messages(old['person_id'])
        for event in [candidate[2], candidate[0], candidate[1]]: self.put(event)
        # Retry/delayed re-delivery must not create rows or reorder mapped parts.
        self.put(candidate[2])
        rows = self.inbox.store.messages(self.identity['person_id'])
        self.assertEqual(len(rows), 3)
        self.assertEqual([r['id'] for r in rows], ['$m-blue', '$z-red', '$a-green'])
        proof['candidate'] = rows
        self.assertEqual([r['media']['album_index'] for r in self.inbox.album_rows('$a-green')], [0, 1, 2])
        self.assertEqual([r['media']['filename'] for r in self.inbox.album_rows('$a-green')], ['red.png', 'green.png', 'blue.png'])
        self.assertEqual([r['original'] for r in self.inbox.album_rows('$a-green')], ['Three photos', '', ''])
        self.inbox.ingest(self.identity, {}, {'type': 'm.reaction', 'event_id': '$reaction', 'sender': '@other:test',
            'content': {'m.relates_to': {'rel_type': 'm.annotation', 'event_id': '$a-green', 'key': '👍'}}})
        self.assertEqual(self.inbox.row('$a-green')['reactions'][0]['key'], '👍')
        self.assertEqual(self.inbox.row('$z-red')['reactions'], [])
        proof['after_reaction'] = self.inbox.store.messages(self.identity['person_id'])
        again = UnifiedInbox(self.tmp.name, Mock())
        proof['after_restart'] = again.store.messages(self.identity['person_id'])
        self.assertEqual(proof['after_restart'], proof['after_reaction'])
        # Outgoing fixtures retain one redaction per real native Matrix event.
        sent = self.inbox.store.identity('signal', '!sent:test', 'Sent fixture')
        for ev in candidate:
            ev = copy.deepcopy(ev); ev['event_id'] += '-sent'; ev['sender'] = self.inbox.owner
            self.put(ev, sent)
        self.inbox.mx.reset_mock()
        deleted = self.inbox.delete('$a-green-sent', {'everyone': True})
        paths = [call.args[0] for call in self.inbox.mx.call_args_list]
        self.assertEqual(len(paths), 3)
        for key in ['z-red', 'a-green', 'm-blue']:
            self.assertTrue(any('%24' + key + '-sent' in path for path in paths), paths)
        self.assertTrue(all(row['deleted'] for row in deleted['messages']))
        # A remote native part redaction deletes exactly that part, not its siblings.
        self.inbox.ingest(self.identity, {}, {'type': 'm.room.redaction', 'redacts': '$a-green'})
        self.assertTrue(self.inbox.row('$a-green')['deleted'])
        self.assertEqual(self.inbox.row('$a-green')['media']['album_index'], 1)
        self.assertNotIn('mxc', json.loads(self.inbox.store.message('$a-green')['media']))
        self.assertFalse(self.inbox.row('$z-red')['deleted'])
        proof['after_part_delete'] = self.inbox.store.messages(self.identity['person_id'])
        if out := os.environ.get('SIGNAL_INGRESS_PROOF'):
            Path(out).write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
