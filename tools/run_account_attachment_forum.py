"""Single admitted forum light job: fail-fast affected QA, historical A/B, then exact-base overlay/export.
No owner mounts, providers, native builds, live writes or activation. Invoke with immutable stage-manifest SHA.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
S = ROOT.parent
OUT = S / 'evidence'
FILES = ['unified.js', 'unified.css', 'connectors.js']
BASE_ARCHIVE = Path('/srv/work/share-people-messenger-4566306/evidence/messenger-image.tar')
BASE_ARCHIVE_SHA = '1a2e3e048f1ed25a2380f068feff2717238c4fdeed0b1488a58e404c155f9ee5'
BASE_MANIFEST = 'sha256:75dde49255cdb88b789103170b69c68517a7acc6a8523fec3ee0f2174235b84e'
BASE_CONFIG = 'sha256:6c68782818b973d40f4949189d34564d46218a3c78e57b986a826814d579b362'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')

def archive_identity(path):
    """Verify all named blob bytes, OCI reachability, exact config and ordered layer descriptors."""
    with tarfile.open(path) as t:
        for m in t.getmembers():
            if m.isfile() and m.name.startswith('blobs/sha256/'):
                h = hashlib.sha256()
                with t.extractfile(m) as f:
                    for b in iter(lambda: f.read(1024 * 1024), b''):
                        h.update(b)
                assert h.hexdigest() == m.name.rsplit('/', 1)[1], 'archive blob corrupt: ' + m.name
        index = json.load(t.extractfile('index.json'))
        roots = index['manifests']
        assert len(roots) == 1, 'single-image reachable root required'
        root = roots[0]
        body = json.load(t.extractfile('blobs/' + root['digest'].replace(':', '/')))
        assert 'config' in body and 'layers' in body, 'root must be a typed image manifest'
        config = json.load(t.extractfile('blobs/' + body['config']['digest'].replace(':', '/')))
        legacy = json.load(t.extractfile('manifest.json'))
        assert len(legacy) == 1
        assert legacy[0]['Config'] == 'blobs/' + body['config']['digest'].replace(':', '/')
        assert len(body['layers']) == len(config['rootfs']['diff_ids'])
        for d in [body['config'], *body['layers']]:
            assert t.getmember('blobs/' + d['digest'].replace(':', '/')).size == d['size']
        return {'manifest_digest': root['digest'], 'config_digest': body['config']['digest'],
                'raw_config': config, 'layer_descriptors': body['layers']}

def check_loaded(info, frozen):
    # Qualify exact verified archive identity BEFORE allowing serializer-only defaults.
    assert info['Id'] in (frozen['manifest_digest'], frozen['config_digest']), 'unqualified loaded ID'
    expected = dict(frozen['raw_config']['config'])
    # Observed classic Docker expansion from worker_identity.py SOURCE_DEFAULTS;
    # never erase a raw field, accept an unknown field, or normalize a nonempty value.
    defaults = {'Hostname': '', 'Domainname': '', 'User': '', 'AttachStdin': False,
                'AttachStdout': False, 'AttachStderr': False, 'Tty': False,
                'OpenStdin': False, 'StdinOnce': False, 'Image': '',
                'Entrypoint': None, 'OnBuild': None, 'Labels': None}
    extras = set(info['Config']) - set(expected)
    assert all(k in defaults and info['Config'][k] == defaults[k] for k in extras), 'nondefault image Config expansion'
    expected.update({k: defaults[k] for k in extras})
    assert info['Config'] == expected, 'full image Config drift'
    assert info['RootFS']['Layers'] == frozen['raw_config']['rootfs']['diff_ids'], 'ordered RootFS drift'
    assert info['Os'] == frozen['raw_config']['os'] and info['Architecture'] == frozen['raw_config']['architecture']
    return 'manifest_digest' if info['Id'] == frozen['manifest_digest'] else 'config_digest'

def tap_counts(text):
    return {k: int(v) for k, v in re.findall(r'^# (tests|pass|fail|cancelled|skipped) (\d+)\s*$', text, re.M)}

runs = []
ENV = {}

def run(name, argv, extra=None, cwd=ROOT, timeout=180, require=True):
    log = OUT / (name + '.log')
    with log.open('x') as f:
        p = subprocess.run(argv, cwd=cwd, env=dict(ENV, **(extra or {})), stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    text = log.read_text()
    runs.append({'name': name, 'argv': list(map(str, argv)), 'returncode': p.returncode,
                 'log': str(log), 'log_sha256': sha(log), 'counts': tap_counts(text)})
    dump(OUT / 'progress.json', runs)
    print(json.dumps(runs[-1]), flush=True)
    if require:
        assert p.returncode == 0, name + ' failed; retained log ' + str(log)
    return p.returncode, text

def main():
    global ENV
    assert str(S).startswith('/srv/work/messenger-account-attachment-composite-'), 'forum immutable stage only'
    assert len(sys.argv) == 2 and sha(S / 'stage-manifest.json') == sys.argv[1]
    manifest = json.loads((S / 'stage-manifest.json').read_text())
    for rel, h in manifest['files'].items():
        assert sha(S / rel) == h, 'staged input drift: ' + rel
    assert not OUT.exists(), 'fresh evidence only: preserve failed runs'
    OUT.mkdir()
    revision = manifest['revision']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == revision
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    deps = S / 'python-deps'
    lock = json.loads((S / 'python-deps-lock.json').read_text())
    assert not deps.exists(), 'fresh task-local Python dependency directory required'
    deps.mkdir()
    import zipfile
    for wheel in lock:
        path = S / 'wheels' / wheel['filename']
        assert sha(path) == wheel['sha256'], 'Python wheel hash drift'
        with zipfile.ZipFile(path) as archive:
            assert all(not n.startswith('/') and '..' not in Path(n).parts for n in archive.namelist())
            archive.extractall(deps)
    sys.path.insert(0, str(deps))
    ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(deps) + ':' + str(ROOT) + ':' + str(ROOT / 'tests'),
               PLAYWRIGHT_MODULE='/srv/work/morning-diff-deps-r4/node_modules/playwright',
               SHELL_DIR=str(S / 'attachment-shell' if (S / 'attachment-shell').exists() else S / 'shell'), AGENT_STAGE_DIR=str(OUT / 'synthetic-state'),
               EVIDENCE_DIR=str(OUT / 'attachment-browser'), STATIC_DIR=str(ROOT / 'static'))
    Path(ENV['AGENT_STAGE_DIR']).mkdir()
    inherited = manifest.get('inherited')
    if inherited:
        prior = Path(inherited['stage'])
        assert sha(prior / 'stage-manifest.json') == inherited['manifest_sha256']
        for rel, h in inherited['files'].items():
            assert sha(prior / rel) == h, 'inherited evidence drift: ' + rel
        prior_manifest = json.loads((prior / 'stage-manifest.json').read_text())
        for name in FILES:
            assert sha(ROOT / 'static' / name) == prior_manifest['files']['source/static/' + name]
        historical = json.loads((prior / 'evidence/historical-exact-case-comparison.json').read_text())
        inherited_skips = []
        dump(OUT / 'inherited-source-bound-evidence.json', inherited)
    else:
        run('packet-guards', [sys.executable, 'tests/test_composite_release_packet.py', '-v'])
        # Cheap checks and strict product negatives precede any image loading/build/export.
        for file in ['unified.js', 'connectors.js']:
            run('syntax-' + file, ['node', '--check', 'static/' + file])
        negatives = [
            ('old-overlap', 'baseline-unified.js', 'two overlapping selections use successive revisions, not a sticky false error',
             'REGRESSION_OVERLAPPING_ATTACHMENT_BATCH_LOST', r'\n\s+expected: 2\n\s+actual: 1\n'),
            ('old-autosave-navigation', 'pre-race-unified.js', 'caption-cleared autosave survives navigation during held upload to empty composer',
             'REGRESSION_AUTOSAVE_NAVIGATION_DELETED_ATTACHMENT_DRAFT', r'\n\s+expected: true\n\s+actual: false\n')]
        for name, src, case, marker, diagnostic in negatives:
            code, text = run(name, ['node', '--test', '--test-name-pattern=^' + case + '$', 'tests/test_draft_attachment_recovery.cjs'],
                             {'STATIC_JS': str(S / src)}, require=False)
            counts = tap_counts(text)
            assert code == 1 and re.search(r'^not ok \d+ - ' + re.escape(case) + r'\s*$', text, re.M)
            assert marker in text and "code: 'ERR_ASSERTION'" in text and re.search(diagnostic, text)
            assert counts.get('fail') == 1 and counts.get('cancelled') == 0
            assert 'TypeError' not in text and 'ReferenceError' not in text
        _, controller = run('candidate-17-controller', ['node', '--test', 'tests/test_draft_attachment_recovery.cjs'])
        assert tap_counts(controller) == {'tests': 17, 'pass': 17, 'fail': 0, 'cancelled': 0, 'skipped': 0}
        run('faithful-vm-contract', ['node', '--test', 'tests/unified_browser_context.test.cjs'])
        # Preserve original assertions: only the two named inherited suites may have source-proven historical failures.
        historical = {}
        reporter = str(ROOT / 'tools/qa_case_reporter.cjs')
        for file in ['test_agent_permissions_view.cjs', 'test_history_search_view.cjs']:
            sides = {}
            for side, tree in [('live-baseline', S / 'baseline'), ('combined-candidate', ROOT)]:
                case_report = OUT / (side + '-' + file + '.jsonl')
                code, text = run(side + '-' + file, ['node', '--test', '--test-reporter=tap', '--test-reporter-destination=stdout',
                    '--test-reporter=' + reporter, '--test-reporter-destination=' + str(case_report), 'tests/' + file], cwd=tree, require=False)
                rows = [json.loads(line) for line in case_report.read_text().splitlines() if line.startswith('{')]
                cases = [row for row in rows if row['type'] in ('test:pass', 'test:fail')]
                counts = tap_counts(text)
                assert cases and counts.get('tests') == len(cases), 'native TAP/case count mismatch'
                assert counts.get('pass') == sum(row['type'] == 'test:pass' and not row['skip'] for row in cases)
                assert counts.get('fail') == sum(row['type'] == 'test:fail' for row in cases)
                assert counts.get('skipped') == sum(bool(row['skip']) for row in cases) and counts.get('cancelled') == 0
                assert code == (1 if counts['fail'] else 0), 'exit/native TAP mismatch'
                assert 'ReferenceError' not in text and 'Unsupported fixture' not in text and 'unhandledRejection' not in text
                sides[side] = {'code': code, 'counts': counts, 'cases': cases}
            assert sides['live-baseline'] == sides['combined-candidate'], 'new case/error drift in ' + file
            historical[file] = sides
        dump(OUT / 'historical-exact-case-comparison.json', historical)
        # Discover all existing non-browser Node suites, not only test_*.cjs.
        node_files = sorted({*ROOT.glob('tests/test_*.cjs'), *ROOT.glob('tests/test_*.mjs'),
                             *ROOT.glob('tests/*.test.cjs'), *ROOT.glob('tests/*.test.mjs')})
        excluded = {'test_agent_permissions_view.cjs', 'test_history_search_view.cjs', 'test_draft_attachment_recovery.cjs', 'unified_browser_context.test.cjs'}
        inherited_skips = []
        for file in node_files:
            if file.name in excluded:
                continue
            _, text = run('node-' + file.name, ['node', '--test', str(file.relative_to(ROOT))])
            if tap_counts(text).get('skipped', 0):
                # Only baseline-identical optional skips, if any, are allowed and never reported as green cases.
                basefile = S / 'baseline/tests' / file.name
                assert basefile.exists() and sha(basefile) == sha(file), 'changed/new suite skip forbidden'
                _, old = run('baseline-skip-' + file.name, ['node', '--test', str(basefile)], cwd=S / 'baseline')
                assert tap_counts(old) == tap_counts(text)
                skip_lines = lambda s: re.findall(r'^ok .*# SKIP.*$', s, re.M)
                assert skip_lines(old) == skip_lines(text)
                inherited_skips.append({'file': file.name, 'counts': tap_counts(text), 'cases': skip_lines(text)})
        # Complete merged account/layout browser, actual shared palettes, stable decoded opacity + injected-negative gate.
        run('merged-account-layout', ['node', 'tests/account_setup_browser.cjs', str(OUT / 'account-layout')], timeout=240)
        run('existing-connectors-browser', ['node', 'tests/new_connectors_browser.cjs', str(OUT / 'existing-connectors')])
    # Real disposable ViewServer, only synthetic cookie/CSRF/data and provider mocks.
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
    with (OUT / 'synthetic-server.log').open('x') as log:
        server = subprocess.Popen([sys.executable, 'tests/agent_drafts_stage.py', str(port)], cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while not (Path(ENV['AGENT_STAGE_DIR']) / 'state.json').exists():
                assert server.poll() is None and time.monotonic() < deadline, 'synthetic server did not start'
                time.sleep(.1)
            run('merged-attachment-browser', ['node', 'tests/draft_attachment_recovery_browser.cjs'])
            run('existing-single-send', ['node', 'tests/single_send_browser.cjs'],
                {'PREVIEW_URL': 'http://127.0.0.1:%d/' % port, 'PREVIEW_API_URL': 'http://127.0.0.1:%d' % port,
                 'MESSENGER_API_TOKEN': 'synthetic-unused-by-cookie-path'}, timeout=120)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait(timeout=5)
    run('focused-python', [sys.executable, '-m', 'unittest', 'test_server_drafts', 'test_agent_send', 'test_photo_albums', 'test_web', '-v'], timeout=240)
    dump(OUT / 'qa-checkpoint.json', {'scoped_qa_pass': True, 'all_suites_green': not any(
        x['live-baseline']['code'] for x in historical.values()), 'historical': historical, 'inherited_skips': inherited_skips,
        'source_manifest_sha256': sys.argv[1], 'revision': revision, 'inherited': inherited, 'runs': runs})
    # Exact full tested original retained archive; no download/rebuild of any native engine.
    assert sha(BASE_ARCHIVE) == BASE_ARCHIVE_SHA, 'retained original image archive drift'
    frozen = archive_identity(BASE_ARCHIVE)
    assert frozen['manifest_digest'] == BASE_MANIFEST and frozen['config_digest'] == BASE_CONFIG
    live = json.loads((S / 'base-image.json').read_text())
    assert live['config'] == frozen['raw_config']['config']
    assert live['rootfs']['Layers'] == frozen['raw_config']['rootfs']['diff_ids']
    run('load-exact-original-base', ['docker', 'load', '-i', str(BASE_ARCHIVE)], timeout=180)
    inspect = lambda ref: json.loads(subprocess.check_output(['docker', 'image', 'inspect', ref]))[0]
    base = inspect('wizard-messenger:0.2.0-unified.15.14')
    base_kind = check_loaded(base, frozen)
    tag = 'wizard-messenger:account-attachment-' + revision[:12]
    run('build-overlay', ['docker', 'build', '--network=none', '--pull=false', '--build-arg', 'BASE=' + base['Id'],
                         '--build-arg', 'REVISION=' + revision, '-f', 'release/account-attachment.Dockerfile', '-t', tag, '.'], timeout=180)
    candidate = inspect(tag)
    expected = json.loads(json.dumps(base['Config']))
    expected['Labels']['org.opencontainers.image.revision'] = revision
    assert candidate['Config'] == expected, 'unexpected full candidate Config change'
    assert candidate['RootFS']['Layers'][:-1] == base['RootFS']['Layers'], 'not one exact static overlay layer'
    # No source bind-mount may shadow image bytes. Read full /app bytes in isolated, read-only UID1000 containers.
    script = 'import pathlib,hashlib,json;print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pathlib.Path("/app").rglob("*") if p.is_file()}))'
    trees = {}
    for key, image in [('base', base), ('candidate', candidate)]:
        _, text = run('image-files-' + key, ['docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
                     '--security-opt=no-new-privileges', '--user=1000:1000', '--entrypoint=python3', image['Id'], '-c', script])
        trees[key] = json.loads(text)
    changed = {p for p in set(trees['base']) | set(trees['candidate']) if trees['base'].get(p) != trees['candidate'].get(p)}
    assert changed == {'/app/static/' + name for name in FILES}
    for name in FILES:
        assert trees['candidate']['/app/static/' + name] == sha(ROOT / 'static' / name)
    archive = OUT / 'messenger-account-attachment-image.tar'
    run('export-overlay-image', ['docker', 'save', '-o', str(archive), tag], timeout=180)
    image_proof = archive_identity(archive)
    kind = check_loaded(candidate, image_proof)
    dump(OUT / 'image-identity.json', {'archive_path': str(archive), 'archive_sha256': sha(archive),
        'base_archive_sha256': BASE_ARCHIVE_SHA, 'base_manifest_digest': BASE_MANIFEST, 'base_config_digest': BASE_CONFIG,
        'base_loaded_id': base['Id'], 'base_loaded_id_kind': base_kind, 'loaded_id': candidate['Id'], 'loaded_id_kind': kind,
        'tag': tag, 'manifest_digest': image_proof['manifest_digest'], 'config_digest': image_proof['config_digest'],
        'config': candidate['Config'], 'rootfs': candidate['RootFS'], 'changed_app_files': sorted(changed)})
    for rel, h in manifest['files'].items():
        assert sha(S / rel) == h, 'post-run source/input drift: ' + rel
    dump(OUT / 'qa-receipt.json', {'scoped_qa_pass': True, 'historical_suite_failures_preserved': historical,
        'all_suites_green': not any(x['live-baseline']['code'] for x in historical.values()),
        'synthetic_only': True, 'live_provider_sends': 0, 'native_builds': 0, 'activation_performed': False,
        'revision': revision, 'source_manifest_sha256': sys.argv[1], 'runner_sha256': sha(Path(__file__)),
        'image_identity_sha256': sha(OUT / 'image-identity.json'), 'product': {name: sha(ROOT / 'static' / name) for name in FILES},
        'runs': runs, 'remaining': ['inspect fresh screenshots', 'parent fresh live/service/recipe/pin check', 'parent authorized lifecycle only']})

if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if OUT.exists():
            dump(OUT / 'FAILED.json', {'error': str(exc), 'type': type(exc).__name__, 'runs': runs})
        raise
