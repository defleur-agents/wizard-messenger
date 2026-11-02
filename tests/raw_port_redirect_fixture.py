"""Raw-port redirect fixture (tests/raw_port_redirect_browser.cjs). Never mounts or reads owner data.

Starts a real trusted-owner ViewServer (MESSENGER_PUBLIC_PATH=/messenger/, allowed origins on box.test) as the raw
app port, plus a fixture gateway that strips /messenger and signs the owner proof like the owner ingress. The browser
test maps https://box.test:<port> onto these two listeners with request routing.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
from unittest.mock import patch

from trusted_owner_browser_fixture import BrowserEngine, SyntheticInbox
from test_trusted_owner import TOKEN, PASSWORD
from web import ViewServer
from trusted_owner import HEADER, sign_request

ORIGINS = ['https://box.test:8444', 'https://box.test:8796']
PASS_HEADERS = {k.lower(): k for k in ('Content-Type', 'Content-Length', 'Set-Cookie', 'Cache-Control',
                                       'Content-Security-Policy', 'Referrer-Policy', 'X-Content-Type-Options')}


def run():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); data = root / 'data'; data.mkdir()
        keys = {name: secrets.token_bytes(32) for name in ('proof', 'wrap')}
        for name, key in keys.items():
            (root / name).write_bytes(key); (root / name).chmod(0o600)
        env = {'MESSENGER_TRUST_WIZARD_OWNER': '1', 'MESSENGER_OWNER_PROOF_KEY_FILE': str(root / 'proof'),
               'MESSENGER_OWNER_WRAP_KEY_FILE': str(root / 'wrap'), 'MESSENGER_COOKIE_SECURE': '0',
               'MESSENGER_PUBLIC_PATH': '/messenger/', 'CONNECTORS_ENABLED': '0', 'UNIFIED_ENABLED': '0',
               'MESSENGER_REMOTE_REQUIRED': '0'}
        patcher = patch.dict(os.environ, env); patcher.start()
        server = ViewServer(('127.0.0.1', 0), BrowserEngine(data), TOKEN, ORIGINS)
        server.unified = SyntheticInbox()
        server.auth.remember_password(PASSWORD)
        threads = [threading.Thread(target=server.serve_forever, daemon=True)]

        class Gateway(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def handle_request(self):
                path = self.path[len('/messenger'):] if self.path.startswith('/messenger/') else self.path
                headers = {k: v for k, v in self.headers.items() if k.lower() not in (HEADER.lower(), 'authorization', 'connection')}
                headers[HEADER] = sign_request(keys['proof'], self.command, path)
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length) if length else None
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
                conn.request(self.command, path, body, headers); response = conn.getresponse(); payload = response.read()
                self.send_response(response.status)
                for key, value in response.getheaders():   # fixed allowlist, no CR/LF: test-only proxy
                    if key.lower() in PASS_HEADERS and not any(c in value for c in '\r\n'):
                        self.send_header(PASS_HEADERS[key.lower()], value)
                self.end_headers()
                try: self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError): pass
                finally: conn.close()
            do_GET = do_POST = handle_request

        gateway = ThreadingHTTPServer(('127.0.0.1', 0), Gateway)
        threads.append(threading.Thread(target=gateway.serve_forever, daemon=True))
        for t in threads: t.start()
        try:
            browser_env = dict(os.environ, RAW_BACKEND=f'http://127.0.0.1:{server.server_port}',
                               GATEWAY_BACKEND=f'http://127.0.0.1:{gateway.server_port}')
            subprocess.run(['node', 'tests/raw_port_redirect_browser.cjs'], env=browser_env, check=True)
        finally:
            gateway.shutdown(); gateway.server_close(); server.shutdown(); server.server_close(); patcher.stop()


if __name__ == '__main__':
    run()
