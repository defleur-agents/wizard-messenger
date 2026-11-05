#!/usr/bin/env python3
"""Durable forum light-lane entry point; all data is synthetic."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if not str(root).startswith('/srv/work/'):
    raise SystemExit('Forum /srv/work only')
evidence = root / 'evidence/slack-instagram-workers'
evidence.mkdir(parents=True, exist_ok=True)
with (evidence / 'unit-tests.log').open('w') as log:
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_connector*.py', '-v'], cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=240)
(evidence / 'unit-test-result.json').write_text(json.dumps({'exit_code': result.returncode, 'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()}) + '\n')
print('connector unit tests exit=' + str(result.returncode), flush=True)
if result.returncode:
    raise SystemExit(result.returncode)
subprocess.run([sys.executable, 'tools/prove_slack_instagram_workers.py'], cwd=root, check=True, timeout=600)
print('Pinned-worker proof complete; see evidence/slack-instagram-workers/', flush=True)
