"""Pinned Instagram login contract; synthetic only, never live bridge traffic."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors import Connectors, PROVIDERS
from connector_sender import LocalOwnerSender, LOGIN_ERRORS, sanitized_login_error
from engine import EngineError


class InstagramLoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / 'connectors.json').write_text(json.dumps({'instagram': {'enabled': True, 'url': 'http://instagram:29330'}}))
        (root / 'connector-secrets.json').write_text(json.dumps({'instagram': {'provisioning': 'synthetic-test-only'}}))
        self.writer = Mock()
        self.controller = Connectors(root, writer=self.writer)

    def call(self, action, payload):
        return self.controller.dispatch('POST', ['instagram', action], payload)

    def test_all_pinned_flows_and_no_unapproved_flow(self):
        self.assertEqual(PROVIDERS['instagram'].flows, ('instagram', 'android', 'instagram-password'))
        for flow in PROVIDERS['instagram'].flows:
            self.writer.return_value = {'login_id': 'p', 'step_id': 'cookies', 'type': 'cookies', 'cookies': {'fields': []}}
            self.call('start', {'flow': flow})
            self.assertIn('/login/start/' + flow + '?', self.writer.call_args.kwargs['path'])
        with self.assertRaises(EngineError): self.call('start', {'flow': 'arbitrary'})

    def test_credentials_code_approval_checkpoint_and_complete(self):
        def step(kind, suffix, **params):
            return {'login_id': 'p', 'step_id': 'fi.mau.meta.instagram.' + suffix, 'type': kind, **params}
        steps = [
            step('user_input', 'credentials', user_input={'fields': [{'id': 'password', 'type': 'password'}]}),
            step('user_input', 'totp', user_input={'fields': [{'id': 'code', 'type': '2fa_code'}]}),
            step('display_and_wait', 'afad_wait', display_and_wait={'type': 'nothing'}, instructions='Approve in Instagram'),
            step('cookies', 'web_checkpoint', cookies={'url': 'https://www.instagram.com/challenge/synthetic', 'extract_js': 'never expose', 'fields': [{'id': 'sessionid', 'required': True, 'sources': [{'type': 'cookie', 'name': 'sessionid'}]}]}),
            {'type': 'complete', 'instructions': 'Connected'},
        ]
        self.writer.side_effect = steps
        current = self.call('start', {'flow': 'android'})
        for fields in ({'password': 'synthetic-password'}, {'code': '123456'}, {}, {'sessionid': 'synthetic-session'}):
            payload = {k: current[k] for k in ('login_id', 'step_id', 'type', 'txn_id') if k in current}
            current = self.call('step', {**payload, 'fields': fields})
            self.assertNotIn('synthetic-password', repr(self.controller.pending))
            self.assertNotIn('never expose', repr(current))
        self.assertEqual(current['type'], 'complete')
        self.assertNotIn('instagram', self.controller.pending)
        self.assertTrue(any('/display_and_wait?' in c.kwargs['path'] for c in self.writer.call_args_list))

    def test_unknown_reason_passthrough_only_to_instagram_owner(self):
        sender = LocalOwnerSender()
        path = '/_matrix/provision/v3/login/step/p/credentials/user_input?user_id=%40owner%3Amessenger.internal'
        for network in ('instagram', 'slack'):
            error = HTTPError('http://synthetic.invalid', 400, 'synthetic', {}, io.BytesIO(json.dumps({'errcode': 'FI.MAU.META_UNINFORMATIVE_ERROR', 'error': 'The password you entered is incorrect.'}).encode()))
            with patch.object(sender.opener, 'open', side_effect=error), self.assertRaises(EngineError) as exc:
                sender(network=network, base='http://' + network + (':29330' if network == 'instagram' else ':29335'), path=path, method='POST', body={'password': 'test-secret'})
            self.assertEqual('incorrect' in str(exc.exception), network == 'instagram')

    def test_instagram_runs_in_the_private_in_app_browser(self):
        import browser_signin
        self.assertEqual(browser_signin.GENERIC['instagram'][0], 'instagram')
        self.assertIn(browser_signin.GENERIC['instagram'][0], PROVIDERS['instagram'].flows)
        seen = {}
        class FakeSession:
            def __init__(self, network, width, height, mobile, url=None, user_agent=None, step=None):
                seen.update(network=network, url=url, mobile=mobile, fields=[f['id'] for f in step['cookies']['fields']])
                self.id = 'synthetic'
        controller = Mock()
        controller.raw_start.return_value = ({'type': 'cookies', 'cookies': {'url': 'https://www.instagram.com/accounts/login/', 'fields': [{'id': 'sessionid'}, {'id': 'csrftoken'}, {'id': 'ds_user_id'}]}}, None)
        with patch.object(browser_signin, 'Session', FakeSession), patch.object(browser_signin.threading, 'Thread'):
            result = browser_signin.BrowserSignIn(controller).dispatch('POST', ['start'], {'network': 'instagram', 'flow': 'instagram', 'width': 400, 'height': 700}, {})
        controller.raw_start.assert_called_once_with('instagram', 'instagram')
        self.assertEqual(result, {'id': 'synthetic', 'title': 'Instagram'})
        self.assertEqual(seen, {'network': 'instagram', 'url': 'https://www.instagram.com/accounts/login/', 'mobile': False, 'fields': ['sessionid', 'csrftoken', 'ds_user_id']})

    def test_reasonless_rejection_names_code_and_points_to_browser_sign_in(self):
        sender = LocalOwnerSender()
        path = '/_matrix/provision/v3/login/step/p/credentials/user_input?user_id=%40owner%3Amessenger.internal'
        for body in ({'errcode': 'M_FORBIDDEN'}, {'errcode': 'bad code <b>', 'error': ''}, {}):
            error = HTTPError('http://synthetic.invalid', 403, 'synthetic', {}, io.BytesIO(json.dumps(body).encode()))
            with patch.object(sender.opener, 'open', side_effect=error), self.assertRaises(EngineError) as exc:
                sender(network='instagram', base='http://instagram:29330', path=path, method='POST', body={'password': 'test-secret'})
            text = str(exc.exception)
            self.assertIn('Sign in with browser (recommended)', text)
            self.assertNotIn('Bridge sign-in could not complete', text)
            self.assertNotIn('<b>', text)
            self.assertEqual('M_FORBIDDEN' in text, body.get('errcode') == 'M_FORBIDDEN')

    def test_redaction_encoding_structure_and_cap(self):
        body = {'password': 'p@ss word', 'code': '654321', 'cookies': {'sessionid': 'short-secret'}}
        result = sanitized_login_error('Wrong password p@ss word p%40ss%20word p%40ss+word; 654321 short-secret https://instagram.com/?secret=x person@example.com sessionid=othersecret <b>Try again</b>\u202e', body, 'private-auth')
        for secret in ('p@ss', 'p%40ss', '654321', 'short-secret', 'othersecret', 'https://', 'example.com', '<b>', '\u202e'):
            self.assertNotIn(secret, result)
        self.assertIn('Wrong password', result)
        self.assertIn('Try again', result)
        self.assertLessEqual(len(sanitized_login_error('A useful sign-in explanation. ' * 30)), 300)
        for text in (None, {'error': 'dump'}, '{"password":"secret"}', 'x' * 5000, 'Traceback private dump'):
            self.assertEqual(sanitized_login_error(text), '')

    def test_later_step_cannot_echo_previous_password_and_cancel_cleans_hashes(self):
        sender = LocalOwnerSender()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"type":"user_input"}'
        route = '/_matrix/provision/v3/login/step/p/credentials/user_input?user_id=%40owner%3Amessenger.internal'
        with patch.object(sender.opener, 'open', return_value=response):
            sender(network='instagram', base='http://instagram:29330', path=route, method='POST', body={'password': 'tinysecret'})
        self.assertNotIn('tinysecret', repr(sender._login_redactions))
        error = HTTPError('http://synthetic.invalid', 400, 'synthetic', {}, io.BytesIO(json.dumps({'error': 'Verification for tinysecret failed.'}).encode()))
        with patch.object(sender.opener, 'open', side_effect=error), self.assertRaises(EngineError) as exc:
            sender(network='instagram', base='http://instagram:29330', path=route.replace('credentials', 'code'), method='POST', body={'code': '123456'})
        self.assertNotIn('tinysecret', str(exc.exception))
        with patch.object(sender.opener, 'open', return_value=response):
            sender(network='instagram', base='http://instagram:29330', path='/_matrix/provision/v3/login/cancel/p?user_id=%40owner%3Amessenger.internal', method='POST', body={})
        self.assertEqual(sender._login_redactions, {})

    def test_specific_known_reasons(self):
        cases = {'FI.MAU.META_RATE_LIMITED': 'limiting', 'FI.MAU.META_AFAD_STOPPED': 'declined', 'FI.MAU.META_ACCOUNT_RECOVERY_REQUIRED': 'not a verification code', 'FI.MAU.META_PASSKEY_MANDATORY': 'passkey', 'FI.MAU.META_MISSING_COOKIES': 'missing', 'FI.MAU.META_WEB_CHECKPOINT_CAPTCHA': 'CAPTCHA'}
        sender = LocalOwnerSender()
        path = '/_matrix/provision/v3/login/start/android?user_id=%40owner%3Amessenger.internal'
        for code, reason in cases.items():
            error = HTTPError('http://synthetic.invalid', 400, 'synthetic', {}, io.BytesIO(json.dumps({'errcode': code, 'error': 'raw-secret-never-returned'}).encode()))
            with patch.object(sender.opener, 'open', side_effect=error), self.assertRaises(EngineError) as exc:
                sender(network='instagram', base='http://instagram:29330', path=path, method='POST', body={})
            self.assertIn(reason, str(exc.exception))
            self.assertNotIn('raw-secret', str(exc.exception))


if __name__ == '__main__': unittest.main()
