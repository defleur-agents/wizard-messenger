"""Admitted forum-only build/QA; no owner data, external accounts or deployment.

Submit this exact script through wizard_heavy_submit(host='forum', lane='heavy').
All outputs remain under the staged evidence directory. A source-only handoff is
not a passing build: runtime/binary/provenance and screenshots require this job.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT.parent
OUT = STAGE / ('evidence-preflight' if '--unit-only' in sys.argv else 'evidence')
OUT.mkdir(exist_ok=True)
assert str(ROOT).startswith('/srv/work/'), 'Linux/amd64 work belongs on forum /srv/work'
manifest = json.loads((STAGE / 'stage.json').read_text())
for filename, digest in manifest['source_files'].items():
    actual = hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()
    assert actual == digest, 'immutable source mismatch: ' + filename
assert shutil.disk_usage(STAGE).free >= 30 * 1024**3, 'full libsignal build needs 30 GiB free; no global pruning allowed'
proof = OUT / 'converter'
proof.mkdir(exist_ok=True)
(STAGE / 'scratch').mkdir(exist_ok=True)
ENV = dict(os.environ, PYTHONPATH=str(ROOT) + ':' + str(ROOT / 'tests'), TMPDIR=str(STAGE / 'scratch'),
           PYTHONDONTWRITEBYTECODE='1', NODE_PATH='/srv/work/morning-diff-deps-r4/node_modules',
           SIGNAL_SHELL_WEB=str(STAGE / 'shell-web'), OUT=str(OUT / 'browser'))
records = []

def run(name, argv, extra=None, timeout=600, required=True):
    started = time.monotonic()
    log = OUT / (name + '.log')
    try:
        with log.open('w') as output:
            p = subprocess.run(argv, cwd=ROOT, env=dict(ENV, **(extra or {})), stdout=output,
                               stderr=subprocess.STDOUT, timeout=timeout)
        code = p.returncode
    except subprocess.TimeoutExpired:
        code = 124
    item = {'name': name, 'argv': argv, 'returncode': code, 'log': str(log), 'seconds': round(time.monotonic()-started, 2)}
    records.append(item)
    (OUT / 'runs.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(item), flush=True)
    if required and code:
        raise RuntimeError('Failed ' + name + '; inspect ' + str(log))
    return code

container = None
receipt = {'pass': False, 'error': 'job interrupted before completion', 'source_revision':manifest['source_revision'], 'runs':records, 'deployed':False}
try:
    # Cheap regression failures surface before the full Rust/CGO build.
    receipt['phase'] = 'units'
    run('browser-vm-contract', ['node', '--test', 'tests/unified_browser_context.test.cjs'])
    run('schema-and-existing-photo-albums', [sys.executable, '-m', 'unittest', 'test_photo_albums', 'test_signal_albums.SignalAlbumSchemaTests', '-v'])
    node_tests = sorted({str(p.relative_to(ROOT)) for pattern in ['*.test.cjs', 'test_*.cjs'] for p in (ROOT/'tests').glob(pattern)})
    node_code = run('node-regressions', ['node', '--test', *node_tests], {'SIGNAL_INGRESS_PROOF':''}, required=False)
    node_log = (OUT/'node-regressions.log').read_text()
    skips = re.findall(r'^ok \d+ - (.*?) # SKIP.*$', node_log, re.M)
    expected_skips = ['actual old vs patched converter outputs through persisted public ingress rows']
    unit_receipt = {'pass': node_code == 0 and skips == expected_skips, 'phase': 'units', 'source_revision':manifest['source_revision'],
                    'runs': list(records), 'skipped_until_converter_built':skips,
                    'product_bytes_unchanged':manifest['test_fixture_repair']['product_bytes_unchanged'],
                    'deployed':False, 'build_started':False}
    (OUT/'unit-receipt.json').write_text(json.dumps(unit_receipt, indent=2)+'\n')
    (OUT/'qa-receipt.json').write_text(json.dumps(unit_receipt, indent=2)+'\n')
    assert skips == expected_skips, 'unexpected unit skips: ' + repr(skips)
    assert node_code == 0, 'Failed node-regressions; inspect ' + str(OUT/'node-regressions.log')
    if '--unit-only' in sys.argv:
        receipt = dict(unit_receipt, scope='unit-only preflight; build/integration NOT executed')
        sys.exit(0)
    receipt['phase'] = 'build'
    run('playwright-pin', ['node', '-e', "if(require('playwright/package.json').version!=='1.64.1')process.exit(1)"])
    tag = 'wizard-signal-bridge:0.2610.0-native-albums1-' + manifest['source_revision'][:12]
    run('full-pinned-signal-build', ['docker', 'build', '--platform=linux/amd64', '--progress=plain',
        '--iidfile', str(OUT/'signal-image-id.txt'), '-f', 'plumbing/signal-bridge/Dockerfile', '-t', tag, '.'], timeout=18000)
    run('signal-image-metadata', ['docker', 'image', 'inspect', tag])
    container = subprocess.check_output(['docker', 'create', '--network=none', '--entrypoint=/bin/true', tag], text=True).strip()
    run('converter-fixture-readback', ['docker','cp', container + ':/usr/share/wizard-signal-albums/.', str(proof)])
    run('final-runtime-version', ['docker', 'run', '--rm', '--network=none', '--entrypoint=/usr/bin/mautrix-signal', tag, '--version'])
    run('final-runtime-dependencies', ['docker', 'run', '--rm', '--network=none', '--entrypoint=/usr/bin/ldd', tag, '/usr/bin/mautrix-signal'])
    integration = {'SIGNAL_CONVERTER_FIXTURES': str(proof), 'SIGNAL_INGRESS_PROOF': str(OUT/'ingress.json')}
    run('real-converter-ingress', [sys.executable, '-m', 'unittest', 'test_signal_albums.SignalConverterIngressTests', '-v'], integration)
    assert (OUT/'ingress.json').is_file(), 'actual converter ingress proof was not produced'
    run('real-ingress-projection', ['node','--test','tests/signal_albums.test.cjs'], integration)
    assert re.search(r'^# skipped 0$', (OUT/'real-ingress-projection.log').read_text(), re.M), 'converter integration must not skip'
    run('two-skin-browser', ['node', 'tests/signal_album_browser.cjs'], integration, timeout=300)
    # Includes the unmodified Telegram connector. Signal config is never rewritten.
    run('compose-validation', ['docker','compose','-f','runtipi/docker-compose.yml','config','--quiet'],
        {'APP_DATA_DIR': str(OUT/'never-started-data'), 'APP_PORT':'0', 'APP_ID':'synthetic-messenger'})
    receipt = {'pass': True, 'source_revision': manifest['source_revision'], 'baseline_live_revision':manifest['baseline_live_revision'],
               'shell_revision': manifest['shell_revision'], 'synthetic_only': True, 'owner_data_read': False,
               'personal_account_auth': False, 'real_network_sends': 0, 'deployed': False,
               'image_tag': tag, 'runs': records,
               'limits': ['direct-media converter seam uses synthetic pointers; no provider download',
                          'Matrix recording endpoint checks mappings; no authenticated Signal ingress',
                          'Appearance hosted proxy, not installed shell or physical-device proof',
                          'screenshots must still be independently visually inspected',
                          'parent must pin rebuilt image/binary provenance and compose parallel repairs before activation']}
except Exception as error:
    receipt = {'pass': False, 'phase':receipt.get('phase', 'units'), 'error': str(error), 'source_revision':manifest['source_revision'], 'runs':records, 'deployed':False, 'build_started':any(r['name']=='full-pinned-signal-build' for r in records)}
finally:
    if container:
        subprocess.run(['docker','rm',container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (OUT/'qa-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
sys.exit(0 if receipt['pass'] else 1)
