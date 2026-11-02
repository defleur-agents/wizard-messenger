"""The Messenger page tells app.js where its Wizard path lives, and only the box's Wizard origins may frame it."""
import http.client
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from trusted_owner_browser_fixture import BrowserEngine
from test_trusted_owner import TOKEN
from web import ViewServer


class GatewayMetaTest(unittest.TestCase):
    def serve(self, origins, public_path='/messenger/'):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        data = Path(temp.name) / 'data'; data.mkdir()
        env = {'MESSENGER_PUBLIC_PATH': public_path, 'CONNECTORS_ENABLED': '0', 'UNIFIED_ENABLED': '0',
               'MESSENGER_REMOTE_REQUIRED': '0', 'MESSENGER_COOKIE_SECURE': '0'}
        with patch.dict(os.environ, env):
            server = ViewServer(('127.0.0.1', 0), BrowserEngine(data), TOKEN, origins)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        conn.request('GET', '/'); r = conn.getresponse(); body = r.read().decode(); conn.close()
        return r, body

    def test_index_carries_the_wizard_path_and_box_origins(self):
        r, body = self.serve(['https://box.ts.net:8444', 'https://box.ts.net:8796'])
        meta = re.search(r'<meta name="messenger-gateway" content="([^"]*)">', body)
        self.assertIsNotNone(meta)
        cfg = json.loads(meta.group(1).replace('&quot;', '"'))
        self.assertEqual(cfg, {'path': '/messenger/', 'origins': ['https://box.ts.net:8444', 'https://box.ts.net:8796']})
        self.assertIn("frame-ancestors 'self' https://box.ts.net:8444 https://box.ts.net:8796", r.getheader('Content-Security-Policy'))

    def test_nothing_unsafe_reaches_the_csp_or_the_page(self):
        r, body = self.serve(['https://ok.ts.net:8444', "https://x.test; script-src *", 'http://plain.test', 'https://a"b.test'])
        csp = r.getheader('Content-Security-Policy')
        self.assertTrue(csp.endswith("frame-ancestors 'self' https://ok.ts.net:8444"), csp)
        cfg = json.loads(re.search(r'name="messenger-gateway" content="([^"]*)"', body).group(1).replace('&quot;', '"'))
        self.assertEqual(cfg['origins'], ['https://ok.ts.net:8444'])

    def test_the_owner_unix_hop_serves_the_same_page(self):
        """16.5 shipped gateway_origins() as a ViewServer method; the owner Unix hop copies attributes only, so every
        page load through the owner ingress raised AttributeError and Messenger never opened in Wizard."""
        import socket
        from owner_unix import OwnerUnixServer
        temp = tempfile.TemporaryDirectory(dir='/tmp'); self.addCleanup(temp.cleanup)
        data = Path(temp.name) / 'data'; data.mkdir()
        env = {'MESSENGER_PUBLIC_PATH': '/messenger/', 'CONNECTORS_ENABLED': '0', 'UNIFIED_ENABLED': '0',
               'MESSENGER_REMOTE_REQUIRED': '0', 'MESSENGER_COOKIE_SECURE': '0'}
        with patch.dict(os.environ, env):
            owner = ViewServer(('127.0.0.1', 0), BrowserEngine(data), TOKEN, ['https://box.ts.net:8444'])
        self.addCleanup(owner.server_close)
        hop = OwnerUnixServer(str(Path(temp.name) / 'o.sock'), owner)
        threading.Thread(target=hop.serve_forever, daemon=True).start()
        self.addCleanup(hop.server_close); self.addCleanup(hop.shutdown)
        s = socket.socket(socket.AF_UNIX); s.settimeout(5); s.connect(str(Path(temp.name) / 'o.sock'))
        s.sendall(b'GET / HTTP/1.1\r\nHost: box.ts.net:8444\r\nConnection: close\r\n\r\n')
        raw = b''
        while chunk := s.recv(65536): raw += chunk
        s.close()
        head, _, body = raw.partition(b'\r\n\r\n')
        self.assertTrue(head.startswith(b'HTTP/1.0 200') or head.startswith(b'HTTP/1.1 200'), head[:80])
        self.assertIn(b'name="messenger-gateway"', body)
        self.assertIn(b"frame-ancestors 'self' https://box.ts.net:8444", head)

    def test_without_origins_nothing_changes(self):
        r, body = self.serve([], public_path='/')
        self.assertTrue(r.getheader('Content-Security-Policy').endswith("frame-ancestors 'self'"))
        self.assertIn('"path":"/"', body.replace('&quot;', '"'))


if __name__ == '__main__':
    unittest.main()
