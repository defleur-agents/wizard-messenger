"""Incoming message display: WhatsApp decrypt-retry edits that carry media, GIF/animated-sticker flags,
@mention pills and media the bridge could not deliver (expired on WhatsApp)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import inbox_feed
import unified
from unified import UnifiedInbox, message_parts, unavailable_media, substitute_mentions, mention_pills

GHOST = '@whatsapp_lid-111:messenger.internal'
OTHER = '@whatsapp_316123:messenger.internal'
WAITING = 'Decrypting message from WhatsApp failed, waiting for sender to re-send... ([learn more](https://faq.whatsapp.com/1))'


def photo(url='mxc://messenger.internal/abc', body='image.jpg', **extra):
    return dict({'msgtype': 'm.image', 'body': body, 'url': url, 'info': {'mimetype': 'image/jpeg', 'w': 640, 'h': 480, 'size': 1000}}, **extra)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        engine = Mock()
        engine.status.return_value = {'state': 'locked'}
        self.inbox = UnifiedInbox(self.tmp.name, engine)
        self.inbox.matrix_token = lambda: 'x'
        self.g = self.inbox.store.identity('whatsapp', '!g', 'Family', 'group')
        self.meta = {'network': 'whatsapp', 'kind': 'group', 'label': 'Family',
                     'names': {GHOST: 'Ana (WA)', OTHER: '+31 6 1234 5678 (WA)', '@owner:messenger.internal': 'Miguel'}}
        self.inbox.rooms['!g'] = self.meta

    def event(self, eid, content, sender=GHOST, etype='m.room.message', ts=1000):
        return {'event_id': eid, 'type': etype, 'sender': sender, 'origin_server_ts': ts, 'content': content}

    def ingest(self, *events):
        for e in events:
            self.inbox.ingest(self.g, self.meta, e)

    def rows(self):
        return {m['id']: m for m in self.inbox.store.messages(self.g['person_id'])}


class EditToMediaTests(Base):
    def test_decrypt_retry_edit_turns_placeholder_into_photo(self):
        self.ingest(self.event('$n', {'msgtype': 'm.notice', 'body': WAITING, 'fi.mau.whatsapp.undecryptable': True}))
        self.assertEqual(self.rows()['$n']['unavailable'], 'waiting')
        self.ingest(self.event('$e', {'msgtype': 'm.image', 'body': '* look', 'm.new_content': photo(body='look', filename='image.jpg'),
                                      'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$n'}}))
        row = self.rows()['$n']
        self.assertEqual(row['msgtype'], 'm.image')
        self.assertEqual(row['original'], 'look')
        self.assertEqual((row['media']['w'], row['media']['thumb']), (640, True))
        self.assertNotIn('unavailable', row)
        self.assertFalse(row['edited'])  # the bridge finishing delivery is not an edit by the sender
        # The media endpoint serves the new picture.
        with patch.object(self.inbox, 'media_blob', return_value=('blob', 'image/jpeg')) as blob:
            self.inbox.media('$n', 'full')
        self.assertEqual(blob.call_args.args[0], 'mxc://messenger.internal/abc')
        # The chat list shows a photo, not the bridge sentence.
        last = self.inbox.store.people('group')[0]['last']
        self.assertEqual((last['msgtype'], last['text']), ('m.image', 'look'))

    def test_edit_from_someone_else_is_ignored(self):
        self.ingest(self.event('$n', {'msgtype': 'm.notice', 'body': WAITING}))
        self.ingest(self.event('$e', {'msgtype': 'm.image', 'body': '* x', 'm.new_content': photo(),
                                      'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$n'}}, sender=OTHER))
        self.assertEqual(self.rows()['$n']['msgtype'], 'm.text')

    def test_gif_and_file_edits_and_caption_edit(self):
        self.ingest(self.event('$n', {'msgtype': 'm.notice', 'body': WAITING}))
        gif = {'msgtype': 'm.video', 'body': 'video.mp4', 'url': 'mxc://messenger.internal/gif',
               'info': {'mimetype': 'video/mp4', 'fi.mau.gif': True, 'fi.mau.loop': True, 'fi.mau.autoplay': True, 'fi.mau.no_audio': True}}
        self.ingest(self.event('$e', {'msgtype': 'm.video', 'body': '* video.mp4', 'm.new_content': gif, 'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$n'}}))
        row = self.rows()['$n']
        self.assertEqual((row['msgtype'], row['media']['gif']), ('m.video', True))
        self.assertEqual(self.inbox.store.people('group')[0]['last'].get('gif'), True)
        # A later caption edit of the same media is a real edit and keeps the media.
        self.ingest(self.event('$p', photo(body='first', filename='image.jpg')))
        self.ingest(self.event('$c', {'msgtype': 'm.image', 'body': '* second', 'm.new_content': photo(body='second', filename='image.jpg'),
                                      'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$p'}}))
        row = self.rows()['$p']
        self.assertEqual((row['msgtype'], row['original'], row['edited']), ('m.image', 'second', True))
        # A text-only caption edit on a photo keeps the photo.
        self.ingest(self.event('$c2', {'msgtype': 'm.text', 'body': '* third', 'm.new_content': {'msgtype': 'm.text', 'body': 'third'},
                                       'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$p'}}))
        row = self.rows()['$p']
        self.assertEqual((row['msgtype'], row['original'], row['media']['mime']), ('m.image', 'third', 'image/jpeg'))

    def test_text_edits_still_work(self):
        self.ingest(self.event('$t', {'msgtype': 'm.text', 'body': 'helo'}))
        self.ingest(self.event('$e', {'msgtype': 'm.text', 'body': '* hello', 'm.new_content': {'msgtype': 'm.text', 'body': 'hello'},
                                      'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$t'}}))
        row = self.rows()['$t']
        self.assertEqual((row['original'], row['edited']), ('hello', True))

    def test_repair_applies_latest_edit_to_stuck_rows_once(self):
        self.ingest(self.event('$n', {'msgtype': 'm.notice', 'body': WAITING}))
        chunk = {'chunk': [
            {'event_id': '$old', 'sender': GHOST, 'origin_server_ts': 2000, 'content': {'m.new_content': {'msgtype': 'm.text', 'body': 'Failed to bridge photo, please view it on the WhatsApp app'}}},
            {'event_id': '$new', 'sender': GHOST, 'origin_server_ts': 3000, 'content': {'m.new_content': photo(body='caption', filename='image.jpg')}},
        ]}
        with patch('unified.http', return_value=chunk) as http:
            self.inbox.repair_rows()
            self.inbox.repair_rows()
        self.assertEqual(http.call_count, 1)
        self.assertIn('/_matrix/client/v1/rooms/%21g/relations/%24n/m.replace', http.call_args.args[1])
        row = self.rows()['$n']
        self.assertEqual((row['msgtype'], row['original']), ('m.image', 'caption'))
        self.assertEqual(self.inbox.store.get('repair_waiting_v1'), '1')


class GifTests(Base):
    def test_gif_and_animated_sticker_flags(self):
        wa = {'msgtype': 'm.video', 'body': '', 'url': 'mxc://x/a', 'info': {'mimetype': 'video/mp4', 'fi.mau.gif': True, 'fi.mau.loop': True, 'fi.mau.no_audio': True}}
        self.assertTrue(message_parts({'type': 'm.room.message', 'content': wa})[2]['gif'])
        tg = {'msgtype': 'm.video', 'body': 'sticker.webm', 'url': 'mxc://x/b', 'info': {'mimetype': 'video/webm', 'thumbnail_url': 'mxc://x/t',
              'fi.mau.bridged_sticker': True, 'fi.mau.telegram.animated_sticker': True, 'fi.mau.gif': True}}
        media = message_parts({'type': 'm.room.message', 'content': tg})[2]
        self.assertTrue(media['sticker'])
        self.assertNotIn('gif', media)
        plain = {'msgtype': 'm.video', 'body': 'clip.mp4', 'url': 'mxc://x/c', 'info': {'mimetype': 'video/mp4', 'duration': 4000}}
        media = message_parts({'type': 'm.room.message', 'content': plain})[2]
        self.assertNotIn('gif', media)
        self.assertEqual(media['duration'], 4000)
        self.ingest(self.event('$g', wa), self.event('$s', tg))
        rows = self.rows()
        self.assertTrue(rows['$g']['media']['gif'])
        self.assertTrue(rows['$s']['media']['sticker'])
        self.assertEqual(unified.media_label('m.video', {'gif': True}), 'GIF')
        self.assertEqual(unified.media_label('m.video', {'sticker': True}), 'Sticker')
        self.assertEqual(unified.media_label('m.image', {'mime': 'image/gif'}), 'GIF')

    def test_static_gif_thumb_serves_the_animation(self):
        self.ingest(self.event('$i', {'msgtype': 'm.image', 'body': 'a.gif', 'url': 'mxc://messenger.internal/gif1', 'info': {'mimetype': 'image/gif', 'size': 5000}}))
        with patch.object(self.inbox, 'media_blob', return_value=('blob', 'image/gif')) as blob:
            self.inbox.media('$i', 'thumb')
        self.assertEqual(blob.call_args.kwargs.get('thumb', False), False)
        self.assertEqual(blob.call_args.kwargs.get('raw_thumb', False), False)
        self.ingest(self.event('$j', photo(url='mxc://messenger.internal/jpg')))
        with patch.object(self.inbox, 'media_blob', return_value=('blob', 'image/jpeg')) as blob:
            self.inbox.media('$j', 'thumb')
        self.assertTrue(blob.call_args.kwargs['thumb'])

    def test_reparse_backfills_gif_flag_and_mentions(self):
        old = {'msgtype': 'm.video', 'body': '', 'url': 'mxc://x/a', 'info': {'mimetype': 'video/mp4'}}
        self.ingest(self.event('$g', old))
        self.inbox.store.add_message('$m', self.g, 'Ana (WA)', False, 'hi +31 6 1234 5678 (WA) !!', 1500)
        events = {
            '$g': self.event('$g', dict(old, info={'mimetype': 'video/mp4', 'fi.mau.gif': True})),
            '$m': self.event('$m', {'msgtype': 'm.text', 'body': 'hi +31 6 1234 5678 (WA) !!', 'format': 'org.matrix.custom.html',
                                    'formatted_body': 'hi <a href="https://matrix.to/#/%s">+31 6 1234 5678 (WA)</a> !!' % OTHER,
                                    'm.mentions': {'user_ids': [OTHER]}}, ts=1500),
        }
        self.inbox.mx = Mock(side_effect=lambda path, *a, **k: events[unified.unquote(path.rsplit('/', 1)[1])])
        self.inbox.repair_rows()
        rows = self.rows()
        self.assertTrue(rows['$g']['media']['gif'])
        self.assertEqual(rows['$m']['original'], 'hi @+31 6 1234 5678 !!')
        self.assertNotIn('(WA)', rows['$m']['original'])
        self.assertEqual(self.inbox.store.get('repair_reparse_v1'), '1')


class MentionTests(Base):
    def html(self, body, formatted, users):
        return {'msgtype': 'm.text', 'body': body, 'format': 'org.matrix.custom.html', 'formatted_body': formatted, 'm.mentions': {'user_ids': users}}

    def test_whatsapp_pill_becomes_best_known_name(self):
        # A one-to-one chat with that person is named, so their mention shows that name instead of the number.
        dm = self.inbox.store.identity('whatsapp', '!dm', 'Bram')
        with self.inbox.store.db() as db:
            db.execute('INSERT OR REPLACE INTO room_meta VALUES (?,?)', ('!dm', json.dumps({'network': 'whatsapp', 'kind': 'person', 'label': 'Bram', 'names': {OTHER: '+31 6 1234 5678 (WA)'}})))
        self.assertTrue(dm)
        self.ingest(self.event('$m', self.html('welcome +31 6 1234 5678 (WA) and Ana (WA)!!',
                                               'welcome <a href="https://matrix.to/#/%s">+31 6 1234 5678 (WA)</a> and <a href="https://matrix.to/#/%s">Ana (WA)</a>!!' % (OTHER, GHOST),
                                               [OTHER, GHOST])))
        row = self.rows()['$m']
        self.assertEqual(row['original'], 'welcome @Bram and @Ana!!')
        self.assertEqual([m['text'] for m in row['mentions']], ['@Bram', '@Ana'])
        self.assertEqual(row['mentions'][0], {'text': '@Bram', 'net': 'whatsapp', 'acc': '316123'})
        self.assertIsNone(row['media'])  # mentions never make a text line look like an attachment

    def test_owner_mention_is_marked_and_uses_his_name(self):
        self.inbox.store.remember_own_names('whatsapp', ['Miguel Ortiz', '+34600000000'])
        self.ingest(self.event('$m', self.html('hey Miguel (WA) look', 'hey <a href="https://matrix.to/#/%40owner%3Amessenger.internal">Miguel (WA)</a> look',
                                               ['@owner:messenger.internal'])))
        row = self.rows()['$m']
        self.assertEqual(row['original'], 'hey @Miguel Ortiz look')
        self.assertEqual(row['mentions'], [{'text': '@Miguel Ortiz', 'me': True}])

    def test_telegram_username_pill_keeps_username(self):
        t = self.inbox.store.identity('telegram', '!t', 'Devs', 'group')
        meta = {'network': 'telegram', 'kind': 'group', 'names': {'@telegram_9:messenger.internal': 'Zoe'}}
        self.inbox.ingest(t, meta, self.event('$t', self.html('ping @zoe_dev now', 'ping <a href="https://matrix.to/#/@telegram_9:messenger.internal">@zoe_dev</a> now',
                                                             ['@telegram_9:messenger.internal']), sender='@telegram_8:messenger.internal'))
        row = {m['id']: m for m in self.inbox.store.messages(t['person_id'])}['$t']
        self.assertEqual(row['original'], 'ping @zoe_dev now')
        self.assertEqual(row['mentions'][0]['text'], '@zoe_dev')

    def test_mentions_without_pills_and_bad_html_are_safe(self):
        self.ingest(self.event('$a', {'msgtype': 'm.text', 'body': 'Ana (WA) hi', 'm.mentions': {'user_ids': [GHOST]}}))
        self.assertEqual(self.rows()['$a']['original'], '@Ana hi')
        self.ingest(self.event('$b', {'msgtype': 'm.text', 'body': 'plain', 'formatted_body': '<a href="https://matrix.to/#/!room:x">room</a>'}))
        self.assertNotIn('mentions', self.rows()['$b'])
        self.assertEqual(mention_pills({'formatted_body': 5}), [])
        self.assertEqual(substitute_mentions('abc', [('@u:x', 'zzz')], lambda u, t: ('N', {})), ('abc', []))

    def test_edit_recomputes_mentions(self):
        self.ingest(self.event('$m', {'msgtype': 'm.text', 'body': 'hi'}))
        new = self.html('hi Ana (WA)', 'hi <a href="https://matrix.to/#/%s">Ana (WA)</a>' % GHOST, [GHOST])
        self.ingest(self.event('$e', {'msgtype': 'm.text', 'body': '* hi', 'm.new_content': new, 'm.relates_to': {'rel_type': 'm.replace', 'event_id': '$m'}}))
        row = self.rows()['$m']
        self.assertEqual((row['original'], row['mentions'][0]['text']), ('hi @Ana', '@Ana'))


class UnavailableMediaTests(Base):
    def test_expired_whatsapp_media_is_a_placeholder_everywhere(self):
        self.assertEqual(unavailable_media('Failed to bridge photo, please view it on the WhatsApp app'), ('photo', ''))
        self.assertEqual(unavailable_media('Failed to bridge voice message, please view it on the WhatsApp app'), ('voice', ''))
        self.assertEqual(unavailable_media('Failed to bridge video attachment, please view it on the WhatsApp app\n\nso funny'), ('video', 'so funny'))
        self.assertEqual(unavailable_media('Failed to bridge media after re-requesting it from your phone: media no longer available on phone\n\n'), ('media', ''))
        self.assertIsNone(unavailable_media('Failed to bridge the gap, he said'))
        self.assertIsNone(unavailable_media('hello'))
        self.ingest(self.event('$x', {'msgtype': 'm.notice', 'body': 'Failed to bridge sticker, please view it on the WhatsApp app', 'fi.mau.whatsapp.failed_media': {}}))
        self.ingest(self.event('$y', {'msgtype': 'm.notice', 'body': 'Failed to bridge photo, please view it on the WhatsApp app\n\nour trip'}, ts=2000))
        rows = self.rows()
        self.assertEqual((rows['$x']['unavailable'], rows['$x']['original']), ('sticker', ''))
        self.assertEqual((rows['$y']['unavailable'], rows['$y']['original']), ('photo', 'our trip'))
        last = self.inbox.store.people('group')[0]['last']
        self.assertEqual((last['unavailable'], last['text']), ('photo', 'our trip'))
        with self.inbox.store.db() as db:
            row = db.execute("SELECT 'group' AS kind, original, msgtype, media, sender FROM message WHERE id='$y'").fetchone()
        self.assertEqual(inbox_feed.preview(row), 'Ana (WA): 📷 Photo not available · our trip')
        # Reply quotes use the same words.
        self.ingest(self.event('$r', {'msgtype': 'm.text', 'body': 'nice', 'm.relates_to': {'m.in_reply_to': {'event_id': '$y'}}}, ts=3000))
        self.assertEqual(self.rows()['$r']['reply']['text'], '📷 Photo not available · our trip')


if __name__ == '__main__':
    unittest.main()
