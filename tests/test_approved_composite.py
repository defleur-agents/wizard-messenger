"""Frozen 16.22 + current Signal boundary regression; synthetic state only."""
import unittest
from tests.test_signal_albums import SignalAlbumSchemaTests
from unified import message_parts


class ApprovedCompositeTests(SignalAlbumSchemaTests):
    def test_album_preview_and_approved_media_flags_survive_public_decoration(self):
        ev = self.event('$composite')
        ev['content'].update(body='Album caption', filename='part.png', **{
            'com.beeper.linkpreviews': [{'matched_url': 'https://example.org/', 'og:title': 'Preview', 'og:image': 'mxc://fixture/preview'}]})
        row = self.put(ev)
        self.assertEqual(row['media']['album_index'], 0)
        self.assertEqual(row['media']['album_count'], 3)
        self.assertEqual(row['links'][0]['title'], 'Preview')
        self.assertNotIn('mxc', row['media'])
        self.assertNotIn('mxc', row['links'][0])

    def test_approved_gif_and_sticker_flags_survive_signal_merge(self):
        for flag, public in [('fi.mau.gif', 'gif'), ('fi.mau.bridged_sticker', 'sticker')]:
            _, _, media, _ = message_parts({'msgtype': 'm.video', 'body': 'clip.mp4', 'url': 'mxc://fixture/clip', 'info': {'mimetype': 'video/mp4', flag: True}})
            self.assertTrue(media[public])


if __name__ == '__main__':
    unittest.main()
