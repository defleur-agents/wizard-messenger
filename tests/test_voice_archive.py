import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
import test_web
import unittest
TOKEN = test_web.TOKEN
import voice_archive
from engine import EngineError


class VoiceArchiveBoundary(unittest.TestCase):
    setUp = test_web.ViewBoundary.setUp
    tearDown = test_web.ViewBoundary.tearDown
    request = test_web.ViewBoundary.request
    session = test_web.ViewBoundary.session
    owner_headers = test_web.ViewBoundary.owner_headers

    def test_original_archive_boundary(self):
        self.server.engine.data = self.temp.name
        raw = b'\x00\xff\x01\x02' * 11000  # Unsupported audio is evidence, not a validation error.
        path = '/api/view/voice-original?' + urlencode(dict(take='../../existing', duration=120000, mime='audio/unknown', size=len(raw)))
        self.assertEqual(self.request('PUT', path, raw, {'Origin': 'https://wizard.example.com'})[0], 401)
        headers = self.owner_headers()
        no_csrf = dict(headers); del no_csrf['X-Messenger-CSRF']
        self.assertEqual(self.request('PUT', path, raw, no_csrf)[0], 403)
        self.assertEqual(self.request('PUT', path, raw, {'Authorization': 'Bearer ' + TOKEN})[0], 403)
        status, _, env = self.request('PUT', path, raw, headers)
        self.assertEqual(status, 200)
        receipt = env['result']
        self.assertEqual(receipt['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['head_hex'], raw[:32].hex())
        target = '/api/view/voice-original/' + receipt['id']
        self.assertEqual(self.request('GET', target)[0], 401)
        self.assertEqual(self.request('GET', target, headers={'Authorization': 'Bearer ' + TOKEN})[0], 403)
        self.assertEqual(self.request('GET', target, headers=headers)[2], raw)
        self.assertEqual(self.request('GET', '/api/view/voice-original/../../browser-auth.json', headers=headers)[0], 404)
        root = Path(self.temp.name) / 'voice-originals'
        self.assertEqual(root.stat().st_mode & 0o777, 0o700)
        for f in root.iterdir():
            self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads((root / (receipt['id'] + '.json')).read_text())['take'], '../../existing')
        self.assertEqual(self.request('PUT', path, raw, headers)[2]['result'], receipt)
        with self.assertRaises(EngineError):
            voice_archive.archive(root, b'x', dict(take='x', duration='nan', mime='', size=1))
        with self.assertRaises(EngineError):
            voice_archive.archive(root, b'x' * (voice_archive.MAX_BYTES + 1), dict(take='x', duration=0, mime='', size=voice_archive.MAX_BYTES+1))


class VoiceArchiveStorage(unittest.TestCase):
    def test_symlinks_budget_interruptions_and_corruption(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp); root = parent / 'archive'; outside = parent / 'outside'
            outside.mkdir(); (outside / 'private').write_bytes(b'not a recording')
            root.symlink_to(outside, target_is_directory=True)
            metadata = dict(take='existing', duration=120000, mime='audio/unknown', size=3)
            with self.assertRaises(EngineError): voice_archive.archive(root, b'raw', metadata)
            self.assertEqual((outside / 'private').read_bytes(), b'not a recording')
            root.unlink(); root.mkdir()
            receipt = voice_archive.archive(root, b'raw', metadata)
            key = receipt['id']; blob = root / (key + '.blob')
            blob.unlink(); blob.symlink_to(outside / 'private')
            with self.assertRaises(EngineError): voice_archive.readback(root, key)
            blob.unlink(); blob.write_bytes(b'raw'); blob.chmod(0o777)
            self.assertEqual(voice_archive.readback(root, key), b'raw')
            self.assertEqual(blob.stat().st_mode & 0o777, 0o600)
            manifest = root / (key + '.json'); manifest.write_text('{')
            with self.assertRaises(EngineError): voice_archive.readback(root, key)
            manifest.unlink(); blob.unlink()
            with patch.object(voice_archive, 'BUDGET', 2):
                with self.assertRaises(EngineError) as caught: voice_archive.archive(root, b'raw', metadata)
                self.assertEqual(caught.exception.code, 'archive_full')
            original_write = voice_archive._write
            def fail_manifest(fd, name, content):
                if name.endswith('.json'): raise OSError('fixture interrupted')
                original_write(fd, name, content)
            with patch.object(voice_archive, '_write', fail_manifest):
                with self.assertRaises(EngineError): voice_archive.archive(root, b'raw', metadata)
            self.assertFalse(manifest.exists())
            needed = len(b'raw') + len(json.dumps({k: v for k, v in receipt.items() if k != 'id'}, sort_keys=True).encode())
            with patch.object(voice_archive, 'BUDGET', needed):
                receipt = voice_archive.archive(root, b'raw', metadata)
            self.assertEqual(voice_archive.readback(root, receipt['id']), b'raw')
            exact = b'x' * voice_archive.MAX_BYTES
            receipt = voice_archive.archive(root, exact, dict(metadata, size=len(exact)))
            self.assertEqual(voice_archive.readback(root, receipt['id']), exact)


class VoiceArchiveUnixBoundary(VoiceArchiveBoundary):
    def setUp(self):
        super().setUp()
        from owner_unix import OwnerUnixServer
        import threading
        self.hop = OwnerUnixServer(str(Path(self.temp.name) / 'o.sock'), self.server)
        self.hop_thread = threading.Thread(target=self.hop.serve_forever, daemon=True)
        self.hop_thread.start()

    def tearDown(self):
        self.hop.shutdown(); self.hop.server_close(); self.hop_thread.join()
        super().tearDown()

    def request(self, method, path, body=None, headers=None):
        from tools.owner_ingress import UnixHTTP
        conn = UnixHTTP(str(Path(self.temp.name) / 'o.sock'))
        h = {'Host': 'wizard.example.com', 'Connection': 'close', **(headers or {})}
        if body is not None and not isinstance(body, bytes):
            h['Content-Type'] = 'application/json'; body = json.dumps(body)
        conn.request(method, path, body, headers=h)
        response = conn.getresponse(); raw = response.read(); status = response.status
        result_headers = dict(response.getheaders()); conn.close()
        return status, result_headers, json.loads(raw) if result_headers.get('Content-Type', '').startswith('application/json') else raw
