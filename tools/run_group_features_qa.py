#!/usr/bin/env python3
"""Forum-only synthetic acceptance + exact-source bundled release payload. No activation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not str(ROOT).startswith('/srv/work/messenger-mentions-reactions-'):
    raise SystemExit('Run only in the staged forum job through durable queue admission')
OUT = ROOT.parent / 'evidence'
OUT.mkdir(exist_ok=True)
env = dict(os.environ)
env['PLAYWRIGHT_MODULE'] = env.get('PLAYWRIGHT_MODULE', '/srv/work/morning-diff-deps-r4/node_modules/playwright')
env['NODE_PATH'] = str(Path(env['PLAYWRIGHT_MODULE']).parent)
env['SHELL_DIR'] = str(ROOT.parent / 'shell')
results = []
commands = [
    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_group_features.py', '-v'],
    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_unified.py', '-q'],
    ['node', '--test', 'tests/group_features.test.cjs', 'tests/reactions.test.cjs', 'tests/test_unified_view.cjs', 'tests/test_draft_attachment_recovery.cjs'],
    ['node', '--check', 'tests/group_features_browser.cjs'],
    ['node', 'tests/group_features_browser.cjs', str(OUT / 'browser')],
]
for n, argv in enumerate(commands):
    log = OUT / f'{n:02d}.log'
    with log.open('w') as f:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=240)
    results.append({'argv':argv, 'code':result.returncode, 'log':str(log)})
    (OUT / 'checks.json').write_text(json.dumps(results, indent=2))
    print(json.dumps(results[-1]), flush=True)
    if result.returncode:
        print(log.read_text()[-12000:], flush=True)
        raise SystemExit(result.returncode)
# Preserve all public source/recipes including parent LINE startup repair; never export an owner container.
archive = OUT / 'messenger-bundled-source.tar.gz'
with archive.open('wb') as f:
    subprocess.run(['git','archive','--format=tar.gz','HEAD'],cwd=ROOT,stdout=f,check=True)
files = subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
manifest = {p:hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files if (ROOT / p).is_file()}
(OUT / 'source-sha256.json').write_text(json.dumps(manifest,indent=2))
revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
(OUT / 'receipt.json').write_text(json.dumps({'source':revision,'version':'0.2.0-unified.15.15','tipi_version':56,'source_archive':str(archive),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'synthetic_only':True,'provider_round_trip':False,'image_built':False,'installed':False,'visual_review_required':True},indent=2))
(OUT / 'PASS').write_text('Synthetic feature checks passed. Screenshots require inspection; image/candidate publication, LINE acceptance, parity and activation are parent gates.\n')
