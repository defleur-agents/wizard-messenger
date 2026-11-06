"""The real multi-network subclass must preserve base history isolation and voice warming."""
import tempfile
import time
import unittest
from unittest.mock import Mock
from connector_inbox import ConnectorInbox


class ConnectorHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = ConnectorInbox(self.tmp.name, Mock())
        self.store = self.inbox.store
        self.a = self.store.identity('line', '!line:messenger.internal', 'LINE fixture')
        self.b = self.store.identity('instagram', '!ig:messenger.internal', 'Instagram fixture')

    def tearDown(self):
        self.inbox.close()
        self.store._conn.close()
        self.tmp.cleanup()

    def event(self, mid, body='needle'):
        return {'type':'m.room.message','event_id':mid,'sender':'@peer:messenger.internal',
                'origin_server_ts':int(time.time()*1000),'content':{'msgtype':'m.text','body':body}}

    def test_v3_rooms_with_avatars_backfill_joined_members_once_in_batches(self):
        import json
        from connector_inbox import META_VERSION
        legacy = {'v':3, 'network':'line', 'kind':'group', 'avatars':{'@line_alice:messenger.internal':'mxc://synthetic/alice'},
                  'names':{'@line_alice:messenger.internal':'Alice Example'}}
        with self.store.db() as db:
            for identity in (self.a, self.b):
                db.execute('INSERT INTO room_meta VALUES (?,?)', (identity['address'], json.dumps(legacy)))
                db.execute("UPDATE identity SET kind='group' WHERE id=?", (identity['id'],))
        # Earlier versions may already have marked the picture-only scan done.
        self.store.put('meta_pictures_v%d' % META_VERSION, '1')
        def state(path):
            net = 'line' if '!line' in path else 'instagram'
            return [{'type':'m.bridge', 'sender':'@%sbot:messenger.internal' % net,
                     'content':{'protocol':{'id':net}, 'com.beeper.room_type.v2':'group', 'channel':{'displayname':'Synthetic group'}}},
                    {'type':'m.room.member', 'state_key':'@line_alice:messenger.internal',
                     'content':{'membership':'join', 'displayname':'Alice Example', 'avatar_url':'mxc://synthetic/alice'}}]
        self.inbox.mx = Mock(side_effect=state)
        self.inbox.room_meta = Mock(wraps=self.inbox.room_meta)
        before = self.store.seq
        self.inbox.refresh_pictures(batch=1)
        self.assertEqual(self.inbox.room_meta.call_count, 1)
        self.assertFalse(self.store.get('meta_members_v%d' % META_VERSION))
        self.inbox.refresh_pictures(batch=1)
        self.assertEqual(self.inbox.room_meta.call_count, 2)
        self.inbox.refresh_pictures(batch=1)
        self.assertEqual(self.store.get('meta_members_v%d' % META_VERSION), '1')
        self.inbox.refresh_pictures(batch=1)
        self.assertEqual(self.inbox.room_meta.call_count, 2)
        self.assertEqual(self.store.members(dict(self.a,kind='group'))[0]['name'], 'Alice Example')
        self.assertGreater(self.store.seq, before, 'membership-only changes reach an already-open composer')

    def test_connector_mutations_cannot_cross_thread_and_fts_tracks_redaction(self):
        self.inbox.ingest(self.a, {}, self.event('$one'))
        edit = self.event('$edit')
        edit['content'] = {'m.relates_to':{'rel_type':'m.replace','event_id':'$one'},
                           'm.new_content':{'msgtype':'m.text','body':'replacement'}}
        self.inbox.ingest(self.b, {}, edit)
        self.assertEqual(self.store.messages(self.a['person_id'])[0]['original'],'needle')
        self.inbox.ingest(self.b, {}, {'type':'m.room.redaction','redacts':'$one'})
        self.assertEqual(len(self.store.search('needle')['messages']),1)
        self.inbox.ingest(self.a, {}, edit)
        self.assertEqual(self.store.search('needle')['messages'],[])
        self.assertEqual(len(self.store.search('replacement')['messages']),1)
        self.inbox.ingest(self.a, {}, {'type':'m.room.redaction','redacts':'$one'})
        self.assertEqual(self.store.search('replacement')['messages'],[])
        self.inbox.ingest(self.a, {}, self.event('$one'))
        self.assertEqual(self.store.search('needle')['messages'],[])

    def test_connector_reactions_cannot_cross_thread(self):
        self.inbox.ingest(self.a, {}, self.event('$one'))
        reaction = {'type':'m.reaction','event_id':'$reaction','sender':'@peer:messenger.internal',
                    'content':{'m.relates_to':{'rel_type':'m.annotation','event_id':'$one','key':'OK'}}}
        self.inbox.ingest(self.b, {}, reaction)
        self.assertEqual(self.store.messages(self.a['person_id'])[0]['reactions'],[])
        self.inbox.ingest(self.a, {}, reaction)
        self.assertEqual(len(self.store.messages(self.a['person_id'])[0]['reactions']),1)

    def test_owner_ghost_recovery_uses_shared_history_for_both_networks(self):
        for identity, ghost in ((self.a, '@line_abc:messenger.internal'), (self.b, '@instagram_15550000000:messenger.internal')):
            event = self.event('$own-' + identity['id'])
            event['sender'] = ghost
            self.inbox.ingest(identity, {}, event)
            self.assertFalse(self.store.messages(identity['person_id'])[0]['outgoing'])
            with self.store.db() as db:
                db.execute('INSERT OR REPLACE INTO room_meta VALUES (?,?)', (identity['address'], '{}'))
            self.store.claim_own(ghost)
            self.assertTrue(self.store.messages(identity['person_id'])[0]['outgoing'])

    def test_connector_incoming_voice_uses_shared_warm_queue(self):
        event = self.event('$voice')
        event['content'] = {'msgtype':'m.audio','body':'voice.ogg','url':'mxc://fixture/voice',
                            'info':{'mimetype':'audio/ogg','size':10}}
        self.inbox.ingest(self.a, {}, event)
        self.assertEqual(self.inbox.warm_queue.get_nowait(),'$voice')


if __name__ == '__main__':
    unittest.main()
