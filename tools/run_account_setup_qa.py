"""Durable forum-only synthetic QA and narrow static release payload; no deployment."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'evidence'
OUT.mkdir(exist_ok=True)
if not str(ROOT).startswith('/srv/work/'):
    raise SystemExit('Run only on forum /srv/work via wizard_heavy_submit')
env = dict(os.environ)
env['PLAYWRIGHT_MODULE'] = env.get('PLAYWRIGHT_MODULE', '/srv/work/morning-diff-deps-r4/node_modules/playwright')
env['NODE_PATH'] = str(Path(env['PLAYWRIGHT_MODULE']).parent)
env['SHELL_DIR'] = str(ROOT.parent / 'shell')
results = []
commands = [
    ['node', '--check', 'static/connectors.js'],
    ['node', '--check', 'static/unified.js'],
    ['node', 'tests/test_connectors_view.cjs'],
    ['node', 'tests/test_unified_view.cjs'],
    ['node', 'tests/account_setup_browser.cjs', str(OUT / 'account-setup')],
    ['node', 'tests/new_connectors_browser.cjs', str(OUT / 'existing-connectors')],
]
for i, argv in enumerate(commands):
    log = OUT / ('%02d.log' % i)
    with log.open('w') as f:
        run = subprocess.run(argv, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=180)
    results.append({'argv': argv, 'code': run.returncode, 'log': str(log)})
    (OUT / 'checks.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results[-1]), flush=True)
    if run.returncode:
        print(log.read_text()[-8000:], flush=True)
        raise SystemExit(run.returncode)
files = ['static/connectors.js', 'static/unified.js', 'static/unified.css', 'release/account-setup.Dockerfile']
manifest = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
(OUT / 'static-sha256.json').write_text(json.dumps(manifest, indent=2))
with tarfile.open(OUT / 'account-setup-static-overlay.tar.gz', 'w:gz') as tar:
    for p in files:
        tar.add(ROOT / p, arcname=p)
    tar.add(OUT / 'static-sha256.json', arcname='static-sha256.json')
(OUT / 'PASS').write_text('Synthetic account setup QA passed; visual inspection and parent composite parity/activation remain.\n')
print('PASS synthetic account setup QA; no provider navigation, no production changes', flush=True)
