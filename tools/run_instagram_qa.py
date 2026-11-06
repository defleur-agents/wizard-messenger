#!/usr/bin/env python3
"""Queued forum-only synthetic Instagram acceptance. No provider/owner access."""
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
if not str(ROOT).startswith('/srv/work/messenger-instagram-'):
    raise SystemExit('Use the staged forum job through durable queue admission')
OUT = ROOT.parent / 'evidence'
OUT.mkdir(exist_ok=True)
env = dict(os.environ)
env.update(INSTAGRAM_SETUP_ONLY='1', SHELL_DIR=str(ROOT.parent / 'shell'), PLAYWRIGHT_MODULE='/srv/work/morning-diff-deps-r4/node_modules/playwright')
checks = []
for n, argv in enumerate([
    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_instagram_login.py', '-v'],
    ['node', 'tests/test_connector_login_runtime.cjs'],
    ['node', 'tests/test_connectors_view.cjs'],
    ['node', '--check', 'tests/account_setup_browser.cjs'],
    ['node', 'tests/account_setup_browser.cjs', str(OUT / 'browser')],
]):
    log = OUT / f'{n:02d}.log'
    with log.open('w') as f:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=240)
    checks.append({'argv': argv, 'code': result.returncode, 'log': str(log)})
    (OUT / 'checks.json').write_text(json.dumps(checks, indent=2))
    print(json.dumps(checks[-1]), flush=True)
    if result.returncode:
        print(log.read_text()[-16000:], flush=True)
        raise SystemExit(result.returncode)
(OUT / 'PASS').write_text('Synthetic Instagram acceptance passed; screenshots need inspection. Real owner pairing unverified. No image, packet or installation.\n')
