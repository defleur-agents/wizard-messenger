"""The manifest-selected recipe must include the worker offered by its LINE UI."""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]


class LineInstalledRecipeTests(unittest.TestCase):
    def test_normal_recipe_contains_public_marker_watching_line_worker(self):
        installed = yaml.safe_load((ROOT / 'runtipi/docker-compose.yml').read_text())
        worker = installed['services']['line']
        self.assertEqual(set(worker['networks']), {'matrix-lane', 'connector-egress'})
        self.assertEqual(str(worker['user']), '1000:1000')
        self.assertIn('ghcr.io/humanitylabs-org/wizard-line-bridge:', worker['image'])
        self.assertIn('@sha256:', worker['image'])
        self.assertEqual(worker['command'], [
            'until [ -f /data/configured ]; do sleep 2; done; exec /usr/bin/matrix-line -c /data/config.yaml'])
        self.assertEqual(worker['depends_on'], {
            'connector-init': {'condition': 'service_completed_successfully'},
            'matrix': {'condition': 'service_healthy'}})
        self.assertTrue(installed['networks']['matrix-lane']['internal'])
        self.assertIn('connector-egress', installed['networks'])
        self.assertEqual(worker['volumes'], ['${APP_DATA_DIR}/data/line:/data'])
        self.assertEqual(worker['healthcheck']['test'], ['CMD-SHELL',
            'test ! -f /data/configured || curl --fail --silent http://127.0.0.1:29322/_matrix/mau/live >/dev/null'])
        self.assertTrue(worker['read_only'])
        self.assertEqual(worker['cap_drop'], ['ALL'])
        self.assertEqual(worker['restart'], 'unless-stopped')


if __name__ == '__main__':
    unittest.main()
