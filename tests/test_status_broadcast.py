"""The WhatsApp Status Broadcast chat is recognised by the bridge's portal id (m.bridge channel.id
status@broadcast), kept in room_meta; chats cached before that id was kept are re-read once."""
import json
import tempfile
import unittest
from unittest.mock import Mock

from connector_inbox import ConnectorInbox
from unified import is_status_chat

STATUS, CHAT = '!status:messenger.internal', '!family:messenger.internal'
BOT = '@whatsappbot:messenger.internal'


def state(channel_id, name):
    return [{'type': 'm.bridge', 'state_key': 'x', 'sender': BOT,
             'content': {'protocol': {'id': 'whatsapp'}, 'channel': {'id': channel_id, 'displayname': name}}},
            {'type': 'm.room.name', 'state_key': '', 'content': {'name': name}},
            {'type': 'm.room.member', 'state_key': '@whatsapp_1:messenger.internal', 'content': {'membership': 'join', 'displayname': 'Eric'}},
            {'type': 'm.room.member', 'state_key': '@whatsapp_2:messenger.internal', 'content': {'membership': 'join', 'displayname': 'Ana'}}]


class StatusRoomMeta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = ConnectorInbox(self.tmp.name, Mock())
        self.store = self.inbox.store
        rooms = {STATUS: state('status@broadcast', 'WhatsApp Status Broadcast'), CHAT: state('123-456@g.us', 'Family')}
        self.reads = []

        def mx(path, *a, **k):
            room = next(r for r in rooms if r in path or r.replace('!', '%21').replace(':', '%3A') in path)
            self.reads.append(room)
            return rooms[room]
        self.inbox.mx = mx

    def tearDown(self):
        self.inbox.close(); self.store._conn.close(); self.tmp.cleanup()

    def test_room_meta_keeps_the_portal_id(self):
        meta = self.inbox.room_meta(STATUS, {})
        self.assertEqual(meta['channel_id'], 'status@broadcast')
        self.assertTrue(is_status_chat('whatsapp', meta))
        other = self.inbox.room_meta(CHAT, {})
        self.assertFalse(is_status_chat('whatsapp', other))

    def test_old_cached_status_meta_is_reread_once(self):
        self.store.identity('whatsapp', STATUS, 'WhatsApp Status Broadcast', 'group')
        self.store.identity('whatsapp', CHAT, 'Family', 'group')
        for room, label in ((STATUS, 'WhatsApp Status Broadcast'), (CHAT, 'Family')):
            with self.store.db() as db:
                db.execute('INSERT INTO room_meta VALUES (?,?)', (room, json.dumps(
                    {'network': 'whatsapp', 'telegram': False, 'v': 3, 'kind': 'group', 'space': False, 'label': label, 'names': {}, 'avatars': {}, 'avatar': None})))
        self.inbox.refresh_status_rooms()
        self.assertEqual(self.reads, [STATUS])  # only the chat titled like the status chat
        with self.store.db() as db:
            meta = json.loads(db.execute('SELECT json FROM room_meta WHERE room=?', (STATUS,)).fetchone()[0])
        self.assertEqual(meta['channel_id'], 'status@broadcast')
        self.inbox.refresh_status_rooms()
        self.assertEqual(self.reads, [STATUS])  # once

    def test_failed_reread_keeps_the_cached_row(self):
        self.store.identity('whatsapp', STATUS, 'WhatsApp Status Broadcast', 'group')
        old = {'network': 'whatsapp', 'telegram': False, 'v': 3, 'kind': 'group', 'space': False, 'label': 'WhatsApp Status Broadcast', 'names': {}, 'avatars': {}, 'avatar': None}
        with self.store.db() as db:
            db.execute('INSERT INTO room_meta VALUES (?,?)', (STATUS, json.dumps(old)))

        def boom(*a, **k):
            raise OSError('homeserver down')
        self.inbox.mx = boom
        self.inbox.refresh_status_rooms()
        with self.store.db() as db:
            self.assertEqual(json.loads(db.execute('SELECT json FROM room_meta WHERE room=?', (STATUS,)).fetchone()[0]), old)
        self.assertFalse(self.store.get('meta_status_channel_v1'))
        self.assertNotIn(STATUS, self.inbox.rooms)


if __name__ == '__main__':
    unittest.main()
