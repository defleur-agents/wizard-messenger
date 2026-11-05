"""Offline guards for the Signal-only lifecycle packet: no Docker, no WAM, no live reads beyond the recipe copy given."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import signal_only_lifecycle as L  # noqa: E402

RECIPE = ROOT / 'runtipi/docker-compose.yml'


class SignalOnlyPacket(unittest.TestCase):
    def before(self):
        text = RECIPE.read_text()
        # The base recipe differs from the packaged branch only in the Signal stanza; restore the live stanza.
        text = text.replace('image: ${SIGNAL_IMAGE:-wizard-signal-bridge:0.2610.0-native-albums1}\n    pull_policy: never\n', 'image: ' + L.SIGNAL_OLD + '\n')
        return {'config.json': json.dumps({'tipi_version': 55}), 'docker-compose.yml': text, 'wizard.md': '', '.wizard-commit': L.BASE + '\n', '.wizard-selection': '{}'}

    def test_only_messenger_and_signal_images_change(self):
        before = self.before()
        after = L.target(before, 'a' * 40, 'sha256:' + 'b' * 64, 56)
        import difflib
        delta = [l[1:].strip() for l in difflib.ndiff(before['docker-compose.yml'].splitlines(), after['docker-compose.yml'].splitlines()) if l[:1] in '+-']
        self.assertEqual(sorted(delta), sorted([
            'image: ' + L.SIGNAL_OLD, 'image: ${MESSENGER_IMAGE:-wizard-messenger:0.2.0-unified.15.14}',
            'image: sha256:' + 'b' * 64, 'image: ' + L.SIGNAL_IMAGE, 'pull_policy: never']))
        self.assertEqual(json.loads(after['config.json'])['tipi_version'], 56)
        self.assertEqual(after['.wizard-commit'], 'a' * 40 + '\n')

    def test_refuses_unexpected_signal_stanza(self):
        before = self.before()
        before['docker-compose.yml'] = before['docker-compose.yml'].replace(L.SIGNAL_OLD, 'other')
        with self.assertRaises(AssertionError):
            L.target(before, 'a' * 40, 'sha256:' + 'b' * 64, 56)

    def test_pins_are_the_frozen_identities(self):
        self.assertEqual(L.SIGNAL_IMAGE, 'sha256:14f0f9454b11cb334dc165abe55c6ac30af896abd2ddb5c2e1ed137a8027f6ba')
        self.assertEqual(L.BASE_IMAGE, 'sha256:75dde49255cdb88b789103170b69c68517a7acc6a8523fec3ee0f2174235b84e')
        prov = json.loads((ROOT / 'plumbing/connectors-provenance.json').read_text())['signal']
        self.assertEqual((prov['image'], prov['binary_sha256']), (L.SIGNAL_IMAGE, L.SIGNAL_BINARY))
        self.assertTrue(prov['custom_build'] and not prov['official_upstream_binary'])


if __name__ == '__main__':
    unittest.main()
