"""Composer pickers (Emoji / GIFs / Stickers): server side. The Telegram bridge's picker routes and Matrix are mocked."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import EngineError
from unified import UnifiedInbox, message_parts
from connectors import Connectors

STICKER = {'id': '-77', 'kind': 'sticker', 'emoji': '😺', 'mime': 'image/webp', 'w': 512, 'h': 512, 'thumb': 'mxc://messenger.internal/t1', 'thumb_mime': 'image/webp'}
GIF = {'id': '42', 'kind': 'gif', 'mime': 'video/mp4', 'w': 320, 'h': 180, 'duration': 2000, 'thumb': 'mxc://messenger.internal/t2'}


class PickerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.inbox = UnifiedInbox(self.tmp.name, Mock())
        self.tg = self.inbox.store.identity('telegram', '!tg', 'Zoe')
        self.wa = self.inbox.store.identity('whatsapp', '!wa', 'Bram')
        self.calls, self.sent = [], []

        def provision(path, method='GET', body=None, query=None, timeout=65):
            self.calls.append((path, query))
            if path == '/wizard/stickers':
                return {'recent': [STICKER, {'id': 'x;rm', 'thumb': 'javascript:1'}], 'favorites': [], 'packs': [{'short_name': 'Cats', 'title': 'Cats', 'count': 3}, {'short_name': '../x'}]}
            if path == '/wizard/gifs':
                return {'items': [GIF], 'next_offset': ''}
            if path == '/wizard/prepare/sticker/-77':
                return {'url': 'mxc://messenger.internal/full1', 'emoji': '😺', 'info': {'mimetype': 'image/webp', 'w': 256, 'h': 256, 'secret': 'x',
                        'fi.mau.bridged_sticker': {'network': 'telegram', 'id': '-77', 'pack_url': 'https://t.me/addstickers/Cats'}}}
            if path == '/wizard/prepare/gif/42':
                return {'url': 'mxc://messenger.internal/full2', 'info': {'mimetype': 'video/mp4', 'w': 320, 'h': 180, 'fi.mau.gif': True}}
            raise AssertionError(path)
        self.inbox.provision = provision

        def mx(path, method='GET', body=None, timeout=15):
            self.sent.append((path, method, body)); return {'event_id': '$e%d' % len(self.sent)}
        self.inbox.mx = mx

    def get(self, path):
        return self.inbox.dispatch('GET', '/api/unified/' + path, {}, {})

    def send(self, identity, payload):
        return self.inbox.dispatch('POST', '/api/unified/people/%s/send' % identity['person_id'], payload, {})

    def test_lists_hide_mxc_and_reject_bad_items(self):
        r = self.get('picker/stickers')
        self.assertEqual(r['recent'], [{'id': 'sticker-n77', 'emoji': '😺', 'thumb': True, 'mime': 'image/webp', 'w': 512, 'h': 512}])
        self.assertEqual([p['id'] for p in r['packs']], ['Cats'])
        self.assertNotIn('mxc://', repr(r))
        g = self.inbox.dispatch('GET', '/api/unified/picker/gifs', {}, {'q': ['  cats  ']})
        self.assertEqual(g['items'][0]['id'], 'gif-42')
        self.assertEqual(self.calls[-1], ('/wizard/gifs', {'q': 'cats'}))
        with self.assertRaises(EngineError):
            self.get('picker/stickers/..%2Fx')

    def test_sticker_sends_m_sticker_with_bridged_reference(self):
        self.get('picker/stickers')
        r = self.send(self.tg, {'pick': 'sticker-n77', 'client_id': 'wclient0001'})
        path, method, body = self.sent[-1]
        self.assertTrue(path.endswith('/send/m.sticker/wclient0001'))
        self.assertEqual(body['url'], 'mxc://messenger.internal/full1')
        self.assertEqual(body['info']['fi.mau.bridged_sticker']['pack_url'], 'https://t.me/addstickers/Cats')
        self.assertNotIn('secret', body['info'])
        self.assertEqual(r['message']['msgtype'], 'm.sticker')
        again = self.send(self.tg, {'pick': 'sticker-n77', 'client_id': 'wclient0001'})
        self.assertEqual((len(self.sent), again['event_id']), (1, r['event_id']), 'same client id never sends twice')

    def test_gif_sends_looping_video_flagged_gif(self):
        self.get('picker/gifs')
        r = self.send(self.tg, {'pick': 'gif-42', 'client_id': 'wclient0002', 'reply_to': None})
        path, _, body = self.sent[-1]
        self.assertIn('/send/m.room.message/', path)
        self.assertEqual((body['msgtype'], body['info']['fi.mau.gif'], body['url']), ('m.video', True, 'mxc://messenger.internal/full2'))
        self.assertTrue(r['message']['media']['gif'])

    def test_picks_are_telegram_only_and_must_be_fresh(self):
        self.get('picker/gifs')
        with self.assertRaises(EngineError) as e:
            self.send(self.wa, {'pick': 'gif-42', 'client_id': 'wclient0003'})
        self.assertEqual(e.exception.code, 'pick_unsupported')
        with self.assertRaises(EngineError) as e:
            self.send(self.tg, {'pick': 'gif-999', 'client_id': 'wclient0004'})
        self.assertEqual(e.exception.code, 'pick_expired')
        self.assertEqual(self.sent, [])

    def test_video_sticker_renders_as_looping_sticker(self):
        kind, _, media, _ = message_parts({'type': 'm.sticker', 'content': {'url': 'mxc://a/b', 'body': '😺', 'info': {'mimetype': 'video/webm', 'w': 512, 'h': 512}}})
        self.assertEqual((kind, media['sticker']), ('m.video', True))

    def test_picker_reads_carry_query_but_writes_never_do(self):
        manager = Connectors.__new__(Connectors)
        manager.owner, seen = '@owner:messenger.internal', []
        manager.config = lambda network: ('http://bridge', 'x' * 20)
        manager.reader = lambda base, path, method, body, token, timeout: seen.append((path, timeout)) or {}
        manager.writer = lambda **kw: seen.append((kw['path'], None)) or {}
        manager.request('telegram', '/wizard/gifs', query={'q': 'cat'}, timeout=55)
        manager.request('telegram', '/logout/all', 'POST', {}, query={'q': 'cat'})
        self.assertEqual(seen[0], ('/_matrix/provision/v3/wizard/gifs?q=cat&user_id=%40owner%3Amessenger.internal', 55))
        self.assertNotIn('q=cat', seen[1][0])


if __name__ == '__main__':
    unittest.main()
