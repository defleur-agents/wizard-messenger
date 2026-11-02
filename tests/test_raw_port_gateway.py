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

    def test_without_origins_nothing_changes(self):
        r, body = self.serve([], public_path='/')
        self.assertTrue(r.getheader('Content-Security-Policy').endswith("frame-ancestors 'self'"))
        self.assertIn('"path":"/"', body.replace('&quot;', '"'))


if __name__ == '__main__':
    unittest.main()
