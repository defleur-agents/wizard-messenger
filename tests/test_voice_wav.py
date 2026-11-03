"""Mac app voice notes arrive as PCM WAV; the server turns them into Ogg Opus for Telegram (needs opusenc)."""
import io, math, shutil, struct, unittest, wave
import unified


def pcm_wav(seconds=2.0, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(seconds * rate))))
    return buf.getvalue()


class VoiceWav(unittest.TestCase):
    def test_sniff(self):
        self.assertEqual(unified.sniff(pcm_wav(0.1)), 'audio/wav')

    @unittest.skipUnless(shutil.which('opusenc'), 'opusenc not installed')
    def test_wav_to_opus(self):
        data = pcm_wav(100)  # a long note, like the one that failed
        out = unified.wav_to_opus(data)
        self.assertEqual(out[:4], b'OggS')
        self.assertIn(b'OpusHead', out[:200])
        self.assertLess(len(out), len(data) / 5)

    @unittest.skipUnless(shutil.which('opusenc'), 'opusenc not installed')
    def test_garbage_is_refused(self):
        with self.assertRaises(Exception):
            unified.wav_to_opus(b'RIFF\x00\x00\x00\x00WAVEjunk')


class VoiceWebm(unittest.TestCase):
    """Safari/Mac app WebM is rewrapped to Ogg Opus on the server; the real length is checked against the claim."""

    @staticmethod
    def webm(seconds):
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as d:
            out = d + '/v.webm'
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=300:duration=%d' % seconds,
                            '-c:a', 'libopus', '-b:a', '32k', '-live', '1', '-f', 'webm', out], check=True)
            with open(out, 'rb') as f:
                return f.read()

    @unittest.skipUnless(shutil.which('mkvextract') and shutil.which('ffmpeg'), 'mkvextract/ffmpeg not installed')
    def test_webm_rewrap_and_length(self):
        data = self.webm(120)
        ogg = unified.webm_to_ogg(data)
        self.assertEqual(ogg[:4], b'OggS')
        self.assertAlmostEqual(unified.ogg_ms(ogg), 120000, delta=200)
        cut = unified.webm_to_ogg(data[:len(data) // 2])  # Safari can hand over a cut-off tail
        self.assertGreater(unified.ogg_ms(cut), 50000)

    def test_clipped_note_is_refused(self):
        upload = {'kind': 'voice', 'mime': 'audio/ogg', 'size': 29634, 'mxc': 'mxc://x/y', 'filename': 'voice-message.ogg', 'ms': 6931}
        with self.assertRaises(Exception) as e:
            unified.UnifiedInbox.media_content(None, upload, '', {'media': {'duration': 120000}})
        self.assertIn('0:06 of 2:00', str(e.exception))
        kind, content, media = unified.UnifiedInbox.media_content(None, {**upload, 'ms': 119500}, '', {'media': {'duration': 120000}})
        self.assertEqual(content['info']['duration'], 119500)


if __name__ == '__main__':
    unittest.main()
