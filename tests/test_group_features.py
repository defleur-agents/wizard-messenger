"""Only disposable synthetic rooms, members, provider adapter and timeline events."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from group_features import find_mentions, member_labels, mention_content, incoming_mentions
from unified import UnifiedInbox
from engine import timeline_row

ALICE = '@telegram_101:messenger.internal'
BOB = '@telegram_102:messenger.internal'
OWNER = '@owner:messenger.internal'


class GroupFeatures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        engine = Mock(); engine.status.return_value = {'state': 'locked'}
        self.inbox = UnifiedInbox(self.tmp.name, engine)
        self.store = self.inbox.store
        self.addCleanup(lambda: self.store._conn.close() if self.store._conn else None)
        self.identity = self.store.identity('telegram', '!synthetic', 'Synthetic group', 'group')
        self.pid = self.identity['person_id']
        self.meta = {'network': 'telegram', 'kind': 'group', 'names': {ALICE:'Alice Example', BOB:'Bob Example', OWNER:'Owner Example'},
                     'joined':[ALICE,BOB,OWNER], 'avatars':{ALICE:'mxc://synthetic.invalid/alice'}}
        with self.store.db() as db:
            db.execute('INSERT INTO room_meta VALUES (?,?)', ('!synthetic', json.dumps(self.meta)))
        self.inbox.mx = Mock(return_value={'event_id':'$synthetic-sent'})

    def ingest(self, ident, body, **content):
        self.inbox.ingest(self.identity, self.meta, {'event_id':ident,'type':'m.room.message','sender':ALICE,
                           'origin_server_ts':1000,'content':dict({'msgtype':'m.text','body':body}, **content)}, live=True)

    def test_member_picker_uses_joined_public_members_and_opaque_avatar_tags(self):
        members = self.inbox.timeline(self.pid)['person']['members']
        self.assertEqual({m['id'] for m in members}, {ALICE, BOB})
        self.assertNotIn('mxc:', json.dumps(members))
        self.assertTrue(members[0]['avatar'])

    def test_legacy_or_departed_member_metadata_cannot_forge_picker_members(self):
        self.meta['joined'] = [ALICE]
        with self.store.db() as db:
            db.execute('UPDATE room_meta SET json=? WHERE room=?',(json.dumps(self.meta),'!synthetic'))
        self.assertEqual([m['id'] for m in self.store.members(self.identity)],[ALICE])
        del self.meta['joined']
        with self.store.db() as db:
            db.execute('UPDATE room_meta SET json=? WHERE room=?',(json.dumps(self.meta),'!synthetic'))
        self.assertEqual(self.store.members(self.identity),[])

    def test_send_emits_standard_mentions_and_matrix_links_without_trusting_payload_ids(self):
        result = self.inbox.send(self.pid, {'text':'Hi @Alice Example!', 'client_id':'synthetic-send-123', 'mentions':[{'id':'@unrelated:example.org'}]})
        content = self.inbox.mx.call_args.args[2]
        self.assertEqual(content['m.mentions'], {'user_ids':[ALICE]})
        self.assertIn('https://matrix.to/#/' + ALICE, content['formatted_body'])
        self.assertEqual(result['message']['mentions'][0]['id'], ALICE)
        self.assertEqual(result['message']['original'], 'Hi @Alice Example!')

    def test_direct_message_and_unverified_network_do_not_claim_mentions(self):
        self.assertEqual(self.store.members(dict(self.identity,kind='person')), [])
        for net in ('line','instagram','facebook','twitter','linkedin','gmessages','dots','messenger'):
            members = self.store.members(dict(self.identity,network=net))
            self.assertTrue(members, net + ' still offers name autocomplete')
            self.assertTrue(all(m['native'] is False for m in members))
            self.assertEqual(find_mentions('Hi @Alice Example!', members), [])
            self.assertEqual(mention_content('Hi @Alice Example!', find_mentions('Hi @Alice Example!', members)), {})

    def test_non_native_send_is_plain_text_even_with_forged_mention_payload(self):
        with self.store.db() as db:
            db.execute("UPDATE identity SET network='line' WHERE id=?", (self.identity['id'],))
        result = self.inbox.send(self.pid, {'text':'Hi @Alice Example!', 'client_id':'plain-synthetic-send', 'mentions':[{'id':ALICE}]})
        content = self.inbox.mx.call_args.args[2]
        self.assertNotIn('m.mentions', content)
        self.assertNotIn('formatted_body', content)
        self.assertEqual(result['message']['mentions'], [])
        self.assertEqual(result['message']['original'], 'Hi @Alice Example!')

    def test_unicode_offsets_boundaries_longest_names_and_escaped_html(self):
        members = member_labels([{'id':ALICE,'name':'A & B'}, {'id':BOB,'name':'A'}])
        body = '😀 @A & B, mail@A and @A!'
        spans = find_mentions(body,members)
        self.assertEqual([s['id'] for s in spans],[ALICE,BOB])
        self.assertEqual(spans[0]['start'],3)
        content = mention_content(body,spans)
        self.assertIn('@A &amp; B</a>',content['formatted_body'])
        self.assertEqual(content['m.mentions']['user_ids'],[ALICE,BOB])

    def test_duplicate_names_require_disambiguated_identity_tokens(self):
        members = member_labels([{'id':ALICE,'name':'Same'}, {'id':BOB,'name':'Same'}])
        self.assertEqual(find_mentions('@Same',members),[])
        self.assertEqual(find_mentions('@' + members[1]['label'],members)[0]['id'],BOB)

    def test_incoming_owner_mentions_highlight_and_keep_normal_push_policy(self):
        self.store.push_enabled = True
        content = mention_content('Hi @Owner Example', [{'id':OWNER,'start':3,'end':17}])
        self.ingest('$mention','Hi @Owner Example',**content)
        row = self.inbox.row('$mention')
        self.assertTrue(row['mentioned']); self.assertEqual(row['mentions'][0]['id'],OWNER)
        self.assertEqual(self.store.people('group')[0]['unread_mentions'],1)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT message FROM push_intent').fetchone()[0],'matrix:$mention')
        self.store.update(self.pid, {'muted':True})
        self.ingest('$quiet','Hi',**{'m.mentions':{'user_ids':[OWNER]}})
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM push_intent').fetchone()[0],1)

    def test_plain_owner_name_does_not_forge_mention_and_malformed_metadata_is_safe(self):
        self.ingest('$plain','@Owner Example',**{'m.mentions':{'user_ids':'not-a-list'}})
        self.assertFalse(self.inbox.row('$plain')['mentioned'])
        self.assertEqual(incoming_mentions({'m.mentions':None},'hi',lambda _:True),([],False))

    def test_reactors_are_grouped_by_real_sender_and_unknown_identity_stays_count_only(self):
        self.ingest('$message','hello')
        self.store.react('$one','$message',ALICE,'👍',False)
        self.store.react('$two','$message',BOB,'❤️',False)
        self.store.react('$unknown','$message','@unknown:example.org','👍',False)
        rows = {r['key']:r for r in self.inbox.row('$message')['reactions']}
        self.assertEqual(rows['👍']['count'],2)
        self.assertEqual([u['name'] for u in rows['👍']['reactors']],['Alice Example'])
        self.assertFalse(rows['👍']['identities_complete'])
        self.assertEqual(rows['❤️']['reactors'][0]['name'],'Bob Example')
        self.store.redact('$one')
        self.assertEqual(self.inbox.row('$message')['reactions'][1]['count'],1)

    def test_deleted_mention_has_no_highlight_and_read_clears_unread_badge(self):
        self.ingest('$mention','Hi',**{'m.mentions':{'user_ids':[OWNER]}})
        self.inbox.read(self.pid,{'timestamp':1000})
        self.assertEqual(self.store.people('group')[0]['unread_mentions'],0)
        self.store.redact('$mention')
        self.assertFalse(self.inbox.row('$mention')['mentioned'])

    def test_reviewed_send_and_edit_keep_real_identity_metadata(self):
        preview = self.inbox.preview(self.pid, {'text':'Hi @Alice Example'})
        result = self.inbox.confirm(self.pid, {'preview_id':preview['id']})
        self.assertEqual(self.inbox.mx.call_args.args[2]['m.mentions']['user_ids'], [ALICE])
        self.inbox.edit(result['event_id'], {'text':'Hi @Bob Example'})
        edited = self.inbox.mx.call_args.args[2]['m.new_content']
        self.assertEqual(edited['m.mentions']['user_ids'], [BOB])
        self.assertEqual(self.inbox.row(result['event_id'])['mentions'][0]['id'], BOB)

    def test_translation_cannot_silently_remove_a_native_tag(self):
        from engine import EngineError
        self.store.update(self.pid, {'language':'fr'})
        self.inbox.translator.translate = Mock(return_value=('Bonjour Alice',None))
        preview = self.inbox.preview(self.pid, {'text':'Hi @Alice Example'})
        self.assertIn('changed a mention',preview['error'])
        with self.assertRaises(EngineError):
            self.inbox.confirm(self.pid, {'preview_id':preview['id']})
        self.inbox.confirm(self.pid, {'preview_id':preview['id'],'send_original':True})
        self.assertEqual(self.inbox.mx.call_args.args[2]['m.mentions']['user_ids'],[ALICE])

    def test_marmot_preserves_actual_pubkeys_and_aggregate_only_is_not_named(self):
        base={'message_id':'a'*64,'group_id':'b'*64,'from':'c'*64,'direction':'received'}
        r = timeline_row(dict(base,reactions={'by_emoji':{'👍':['d'*64],'❤️':3}}),'c'*64,{'d'*64:'Synthetic Peer'})['reactions']
        self.assertEqual(r[0]['reactors'][0]['id'],'d'*64)
        self.assertEqual(r[0]['reactors'][0]['name'],'Synthetic Peer')
        self.assertEqual(r[1]['reactors'],[])
        self.assertFalse(r[1]['identities_complete'])


if __name__ == '__main__': unittest.main()
