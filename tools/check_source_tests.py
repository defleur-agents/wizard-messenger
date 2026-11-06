#!/usr/bin/env python3
"""Run all Python and browser-free Node suites against synthetic fixtures only."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
node_tests = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'tests').iterdir()
                    if p.suffix in ('.cjs', '.mjs') and
                    (p.name.startswith('test_') or '.test.' in p.name or p.name == 'thread_keys.cjs'))
node_tests += ['tests/group_features_fixture_boot.cjs', 'tests/remote_authority_ui.cjs',
               'push_notifications/tests/test_service_worker.cjs']
commands = [[sys.executable, '-m', 'pytest', '-q', 'tests', 'isolated_sender/tests',
             'push_notifications/tests', 'readiness/tests'], ['node', '--test', *node_tests]]
failed = False
for argv in commands:
    print('CHECK:', ' '.join(argv), flush=True)
    result = subprocess.run(argv, cwd=ROOT)
    print('CHECK_EXIT:', result.returncode, flush=True)
    failed |= result.returncode != 0
raise SystemExit(1 if failed else 0)
