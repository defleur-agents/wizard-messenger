import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('beta', Path(__file__).parents[1] / 'tools/beta.py')
assert spec is not None and spec.loader is not None
beta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beta)

class InstallationDocumentationTests(unittest.TestCase):
    """Keep current installation guidance separate from historical beta/build tooling."""
    root = Path(__file__).parents[1]

    def test_current_install_uses_the_public_recipe(self):
        readme = (self.root / 'README.md').read_text()
        self.assertIn('https://apps.aiwizards.com/v1/apps/humanitylabs-org/wizard-messenger', readme)
        self.assertIn('digest-pinned GHCR images', readme)
        self.assertNotIn('not publicly indexed', readme)
        self.assertNotIn('pull_policy: never', readme)
        # Documentation must describe the shipped recipe, not replace it.
        compose = (self.root / 'runtipi/docker-compose.yml').read_text()
        self.assertIn('ghcr.io/humanitylabs-org/wizard-messenger:', compose)
        self.assertIn('@sha256:', compose)
        self.assertNotIn('pull_policy: never', compose)
        manifest = (self.root / 'wizard.md').read_text()
        self.assertNotIn('Public indexing and recipient contact are not included.', manifest)
        self.assertIn('official public Wizard App Index', manifest)

    def test_store_classification_is_user_facing_not_packaging(self):
        readme = (self.root / 'README.md').read_text()
        self.assertIn('**Apps**', readme)
        self.assertIn('Agent apps have no user interface', readme)
        self.assertNotIn('places Messenger under **Agent apps**', readme)

    def test_private_beta_is_explicitly_historical(self):
        banner = (self.root / 'PRIVATE-BETA.md').read_text().split('## Required access')[0]
        self.assertIn('Historical instructions', banner)
        self.assertIn('0.1.2-beta.1 only', banner)
        self.assertIn('[README.md](README.md)', banner)

    def test_build_helper_is_not_an_installer(self):
        unified = (self.root / 'UNIFIED-INBOX.md').read_text()
        helper = unified[unified.index('`tools/build_unified_thales.py`'):]
        self.assertIn('developer-only', helper)
        self.assertIn('not a recipient installer', helper)
        self.assertIn('not required', helper)


class InstallTests(unittest.TestCase):
    def test_repeat_preserves_secret_and_data(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'owned'
            first = beta.configure(root, 'https://wizard.example/apps/messenger/', 19245)
            before = (root / '.env').read_bytes()
            (root / 'data').mkdir()
            (root / 'data/history').write_text('preserve')
            self.assertEqual(beta.configure(root, 'https://wizard.example/apps/messenger/', 19245), first)
            self.assertEqual((root / '.env').read_bytes(), before)
            self.assertEqual((root / 'data/history').read_text(), 'preserve')
            self.assertEqual((root / '.env').stat().st_mode & 0o777, 0o600)
            svc = json.loads((root / 'compose.json').read_text())['services']['messenger']
            self.assertEqual(svc['ports'], ['127.0.0.1:19245:8765'])
            self.assertIn('MESSENGER_COOKIE_SECURE=1', before.decode())
            self.assertIn('handle_path /apps/messenger/*', (root / 'route.caddy').read_text())
            with self.assertRaises(ValueError):
                beta.configure(root, 'https://other.example/apps/messenger/', 19245)

    def test_refuse_unowned_and_invalid_url(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'keep').write_text('owner')
            with self.assertRaises(ValueError):
                beta.configure(root, 'https://wizard.example/apps/messenger/', 19245)
            for url in ['http://wizard.example/apps/messenger/', 'https://u:p@wizard.example/apps/messenger/',
                        'https://wizard.example/apps/../', 'https://wizard.example/apps/messenger/?secret=x']:
                with self.assertRaises(ValueError):
                    beta.configure(root / 'child', url, 19245)
            self.assertFalse((root / 'child').exists())
            self.assertEqual((root / 'keep').read_text(), 'owner')
