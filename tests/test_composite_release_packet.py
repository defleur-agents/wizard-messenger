"""Browser-free release-packet guard tests; no Docker, network or owner state."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    assert spec is not None and spec.loader is not None
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

lifecycle = load('account_attachment_lifecycle')
worker = load('run_account_attachment_forum')

class PacketGuards(unittest.TestCase):
    def test_recipe_changes_only_messenger_image_and_release_metadata(self):
        before = {'config.json': (ROOT / 'runtipi/config.json').read_text(),
                  'docker-compose.yml': (ROOT / 'runtipi/docker-compose.yml').read_text(),
                  'wizard.md': (ROOT / 'wizard.md').read_text(), '.wizard-commit': lifecycle.BASE + '\n',
                  '.wizard-selection': json.dumps({'repo': 'humanitylabs-org/wizard-messenger', 'commit': lifecycle.BASE}) + '\n'}
        after = lifecycle.target(before, 'a' * 40, 'sha256:' + 'b' * 64, 56)
        self.assertEqual(after['wizard.md'], before['wizard.md'])
        expected = before['docker-compose.yml'].replace('  messenger:\n    image: ${MESSENGER_IMAGE:-wizard-messenger:0.2.0-unified.15.14}', '  messenger:\n    image: sha256:' + 'b' * 64)
        self.assertEqual(after['docker-compose.yml'], expected)
        self.assertEqual(after['docker-compose.yml'].count('${MESSENGER_IMAGE:-wizard-messenger:0.2.0-unified.15.14}'), 3)
        a, b = json.loads(before['config.json']), json.loads(after['config.json'])
        b['tipi_version'] = a['tipi_version']
        self.assertEqual(a, b)
        self.assertEqual(json.loads(after['.wizard-selection'])['commit'], 'a' * 40)

    def test_recipe_drift_is_rejected(self):
        with self.assertRaises(AssertionError):
            lifecycle.target({'config.json': '{}', 'docker-compose.yml': 'services: {}'}, 'a'*40, 'sha256:'+'b'*64, 56)

    def test_full_config_and_ordered_layers_and_typed_id(self):
        raw = {'config': {'User': '1000:1000', 'Env': ['A=B']}, 'rootfs': {'diff_ids': ['layer-a', 'layer-b']}, 'os': 'linux', 'architecture': 'amd64'}
        frozen = {'raw_config': raw, 'manifest_digest': 'manifest-id', 'config_digest': 'config-id'}
        info = {'Config': copy.deepcopy(raw['config']), 'RootFS': {'Layers': ['layer-a', 'layer-b']}, 'Os': 'linux', 'Architecture': 'amd64', 'Id': 'config-id'}
        self.assertEqual(worker.check_loaded(info, frozen), 'config_digest')
        info['Id'] = 'manifest-id'
        self.assertEqual(worker.check_loaded(info, frozen), 'manifest_digest')
        for field, value in [('Id', 'other-id'), ('Config', {'User':'0:0', 'Env':['A=B']}), ('RootFS', {'Layers':['layer-b','layer-a']}), ('RootFS', {'Layers':['layer-a']})]:
            bad = copy.deepcopy(info); bad[field] = value
            with self.assertRaises(AssertionError):
                worker.check_loaded(bad, frozen)

    def test_owner_settings_not_generated_recipe_hash(self):
        class Fake:
            obj = {'isEnabled': True, 'appEnv': '', 'dockerCompose': 'services: {slack: {}, instagram: {}}', 'sourceCompose': 'old source'}
            def req(self, method, path):
                return self.obj
        rt = Fake()
        prior = lifecycle.settings_hash(rt)
        rt.obj['sourceCompose'] = 'new generated image recipe'
        self.assertEqual(lifecycle.settings_hash(rt), prior)
        rt.obj['dockerCompose'] += '\n# owner edit'
        self.assertNotEqual(lifecycle.settings_hash(rt), prior)
        rt.obj['dockerCompose'] = 'services: {slack: {}, instagram: {}}'
        rt.obj['appEnv'] = 'SYNTHETIC=changed'
        self.assertNotEqual(lifecycle.settings_hash(rt), prior)

    def test_node20_native_tap_counts_not_summary_event(self):
        text = 'TAP version 13\n1..4\n# tests 4\n# suites 0\n# pass 3\n# fail 1\n# cancelled 0\n# skipped 0\n# todo 0\n'
        self.assertEqual(worker.tap_counts(text), {'tests':4, 'pass':3, 'fail':1, 'cancelled':0, 'skipped':0})

if __name__ == '__main__':
    unittest.main()
