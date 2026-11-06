"""Source-derived parser contracts for the disposable native /app/ mount.

Runs only under admitted QA. Uses real BaseHTTPRequestHandler.parse_request via
real ViewHandler inheritance; no server/browser/provider and no owner stores.
"""
import io
import unittest

from attachment_fixture_mount import AttachmentFixtureHandler
from web import ViewHandler


def parse(method, target, body=b'', version='HTTP/1.1'):
    handler = object.__new__(AttachmentFixtureHandler)
    handler.raw_requestline = f'{method} {target} {version}\r\n'.encode()
    handler.rfile = io.BytesIO(
        b'Host: 127.0.0.1:12345\r\n'
        b'Origin: http://127.0.0.1:12345\r\n'
        b'Cookie: wizard_messenger_session=synthetic-only\r\n'
        b'X-Messenger-CSRF: synthetic-csrf\r\n'
        + f'Content-Length: {len(body)}\r\n'.encode() + b'\r\n' + body)
    handler.wfile = io.BytesIO()
    handler.client_address = ('127.0.0.1', 12345)
    return handler, handler.parse_request()


class NativeAttachmentMountTests(unittest.TestCase):
    def test_parser_preserves_methods_headers_and_unread_body(self):
        for method in ('GET', 'POST', 'PUT', 'DELETE'):
            with self.subTest(method=method):
                body = b'{"revision":7}' if method != 'PUT' else b'\x89PNG\r\n\x00\xff'
                h, accepted = parse(method, '/app/api/drafts/d1/attachments?revision=7&name=a%2Bb.png', body)
                self.assertTrue(accepted)
                self.assertEqual(h.command, method)
                self.assertEqual(h.path, '/api/drafts/d1/attachments?revision=7&name=a%2Bb.png')
                self.assertEqual(h.headers['Cookie'], 'wizard_messenger_session=synthetic-only')
                self.assertEqual(h.headers['X-Messenger-CSRF'], 'synthetic-csrf')
                self.assertEqual(h.headers['Origin'], 'http://127.0.0.1:12345')
                self.assertEqual(h.headers['Content-Length'], str(len(body)))
                self.assertEqual(h.rfile.read(), body)

    def test_root_and_standalone_routes_unchanged(self):
        for target in ('/', '/api/drafts', '/app.js', '/app', '/application/', '/app?next=/app/'):
            with self.subTest(target=target):
                h, accepted = parse('GET', target)
                self.assertTrue(accepted)
                self.assertEqual(h.path, target)

    def test_document_and_assets_mount_once(self):
        for target, expected in (('/app/', '/'), ('/app/app.js?v=1', '/app.js?v=1'),
                                 ('/app/app/api/drafts', '/app/api/drafts')):
            with self.subTest(target=target):
                h, accepted = parse('GET', target)
                self.assertTrue(accepted)
                self.assertEqual(h.path, expected)

    def test_actual_production_handlers_not_replaced(self):
        for method in ('do_GET', 'do_POST', 'do_PUT', 'do_DELETE', '_authorize', '_dispatch', '_raw_body'):
            with self.subTest(method=method):
                self.assertIs(getattr(AttachmentFixtureHandler, method), getattr(ViewHandler, method))

    def test_native_parser_rejection_not_rewritten(self):
        h, accepted = parse('GET', '/app/api/drafts', version='HTTP/2.0')
        self.assertFalse(accepted)
        self.assertFalse(hasattr(h, 'path'), 'native rejection happens before target admission')
        self.assertTrue(h.close_connection)


if __name__ == '__main__':
    unittest.main(verbosity=2)
