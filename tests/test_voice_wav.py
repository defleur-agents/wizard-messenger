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


if __name__ == '__main__':
    unittest.main()
