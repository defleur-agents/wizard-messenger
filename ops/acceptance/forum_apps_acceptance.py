#!/usr/bin/env python3
"""Exact archived Messenger source acceptance. Parent admission; synthetic only; no activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
M = json.loads((ROOT / 'manifest.json').read_text())
OUT = ROOT / 'results'
phases = []

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def verify():
    for name, value in M['files'].items():
        assert digest(ROOT / name) == value, name
    for label, sha in M['source_refs'].items():
        with tarfile.open(ROOT / M['archives'][label]) as archive:
            assert archive.pax_headers.get('comment') == sha, ('archive-commit', label)
    assert M['no_activation'] and M['parent_admission_only']
    assert M['scope'] == 'messenger-only-source-browser'
    print(json.dumps({'manifest_verified': True, 'manifest_sha256': digest(ROOT / 'manifest.json')}), flush=True)

def group_members(pgid):
    found = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == pgid and fields[0] != 'Z':
                found.append(int(proc.name))
        except (OSError, ValueError, IndexError):
            pass
    return found

def run(name, argv, cwd=None, env=None, timeout=900, marker=None):
    start = time.monotonic()
    log = OUT / (name + '.log')
    timed_out = False
    with log.open('w') as output:
        proc = subprocess.Popen(argv, cwd=cwd or ROOT, env=env, stdout=output,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
            code = 124
    leftover = group_members(proc.pid)
    if leftover:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if code == 0:
            code = 125
    text = log.read_text(errors='replace')
    marker_ok = marker is None or marker in text
    if code == 0 and not marker_ok:
        code = 126
    row = {'name': name, 'argv': argv, 'exit_code': code, 'timed_out': timed_out,
           'elapsed_s': time.monotonic() - start, 'log_sha256': digest(log),
           'leftover_pids_killed': leftover, 'required_marker': marker, 'marker_found': marker_ok}
    phases.append(row)
    print(json.dumps(row), flush=True)
    return code

def isolated(argv):
    # Outer root only for private mounts/network; inner app uid avoids unmapped chown.
    return ['unshare', '--user', '--map-root-user', '--mount', '--net', '--pid', '--fork',
            '--mount-proc', '--kill-child=KILL', '/bin/sh', '-ec',
            'mount --make-rprivate /; mount -t tmpfs -o mode=1777 tmpfs /run; '
            'mkdir /run/messenger; chmod 0700 /run/messenger; ip link set lo up; '
            'exec unshare --user --map-user=1000 --map-group=1000 "$@"', 'fixture', *argv]

def path_preflight(remote):
    paths = [str(Path(remote) / d) + '/' + 'x' * 72 for d in ['tmp','home']]
    maximum = max(len(p.encode()) for p in paths)
    assert maximum < 108, ('AF_UNIX path budget exceeded', maximum, paths)
    return {'max_socket_path_bytes':maximum,'linux_limit':108,'suffix_budget':72}

def tool_assets(env):
    assets = ROOT / 'assets'; debs = assets / 'debs'; target = assets / 'root'
    debs.mkdir(parents=True); target.mkdir()
    packages = M['tool_packages']; before = digest(Path('/var/lib/dpkg/status'))
    # Authenticated download only; no host install/update/sudo. Pins from forum APT policy.
    # `apt-get download` is unprivileged, takes no dpkg lock and cannot install. The complete pinned closure
    # was resolved from the worker's own APT policy with `apt-get -s install opus-tools mkvtoolnix`.
    assert run('media-tool-download',['apt-get','download',*[k+'='+v for k,v in packages.items()]],
               debs,env,600)==0
    rows=[]
    for deb in sorted(debs.glob('*.deb')):
        assert run('extract-'+deb.name,['dpkg-deb','-x',str(deb),str(target)],env=env)==0
        rows.append({'file':deb.name,'sha256':digest(deb)})
    assert len(rows)==len(packages) and before==digest(Path('/var/lib/dpkg/status')), 'Complete pinned closure; host package status unchanged'
    (OUT/'tool-assets.json').write_text(json.dumps({'requested_pins':packages,'debs':rows,'host_status_unchanged':True},indent=2)+'\n')
    env['PATH']=str(target/'usr/bin')+':'+str(ROOT/'node/node_modules/node/bin')+':'+env['PATH']
    env['LD_LIBRARY_PATH']=':'.join(str(target/p) for p in ['usr/lib/x86_64-linux-gnu','lib/x86_64-linux-gnu'])

def junit(label):
    tree = ET.parse(OUT / (label + '.xml'))
    cases = tree.findall('.//testcase')
    result = {'cases': len(cases), 'skipped': [], 'errors': [], 'authority_cases': 0}
    for case in cases:
        identity = case.get('classname', '') + '::' + case.get('name', '')
        if 'test_remote_authority' in identity:
            result['authority_cases'] += 1
            assert case.find('skipped') is None, ('authority-skipped', identity)
        for kind in ['skipped', 'error', 'failure']:
            item = case.find(kind)
            if item is not None:
                result['skipped' if kind == 'skipped' else 'errors'].append({'test': identity, 'kind': kind, 'message': item.get('message', '')})
    (OUT / (label + '-counts.json')).write_text(json.dumps(result, indent=2) + '\n')
    assert result['cases'] > 0 and result['authority_cases'] > 0
    return result

def main():
    verify()
    budget = path_preflight(M['remote'])
    assert str(ROOT) == M['remote'] and str(ROOT).startswith('/srv/work/')
    assert not OUT.exists(), 'Fresh exclusive attempt only: never replace retained evidence'
    OUT.mkdir()
    for name in ['tmp', 'home', 'cache', 'browsers']:
        (ROOT / name).mkdir()
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(ROOT / 'home'),
           'TMPDIR': str(ROOT / 'tmp'), 'PYTHONDONTWRITEBYTECODE': '1',
           'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'XDG_CACHE_HOME': str(ROOT / 'cache'),
           'PLAYWRIGHT_BROWSERS_PATH': str(ROOT / 'browsers'),
           'AGENT_STAGE_DIR': str(ROOT / 'tmp/fixture-stage'),
           'EVIDENCE_DIR': str(OUT / 'fixture-evidence'),
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
    sources = {}
    # Real commit objects + exact tree/blob closure, not invented HEADs or remote refs.
    provenance = ROOT / 'provenance.git'
    assert run('provenance-init', ['git', 'init', '--bare', '-q', str(provenance)], env=env) == 0
    with (ROOT / 'messenger-provenance.pack').open('rb') as pack:
        subprocess.run(['git', '--git-dir=' + str(provenance), 'index-pack', '--stdin'], stdin=pack,
                       stdout=(OUT / 'provenance-index.log').open('w'), stderr=subprocess.STDOUT,
                       env=env, check=True, timeout=60)
    for label, sha in M['source_refs'].items():
        regenerated = ROOT / 'tmp' / (label + '-regenerated.tar')
        with regenerated.open('wb') as out:
            subprocess.run(['git', '--git-dir=' + str(provenance), 'archive', '--format=tar', sha],
                           stdout=out, env=env, check=True, timeout=60)
        assert digest(regenerated) == M['files'][M['archives'][label]], ('real-commit-tree-custody', label)
        dest = ROOT / label
        dest.mkdir()
        with tarfile.open(regenerated) as archive:
            archive.extractall(dest, filter='data')
        assert not subprocess.run(['git', '-C', str(dest), 'rev-parse', '--show-toplevel'],
                                  env=env, capture_output=True).returncode == 0, 'Archive must not inherit a worktree'
        sources[label] = dest
    (OUT / 'provenance.json').write_text(json.dumps({'mode': 'verified-commit-archives-not-worktrees',
        'source_refs': M['source_refs'], 'invented_refs': False}, indent=2) + '\n')
    candidate = sources['messenger-candidate']
    baseline_fixture=sources['messenger-baseline']/'tests/test_history_search_view.cjs'
    original_fixture=baseline_fixture.read_bytes()
    expected_original=subprocess.check_output(['git','--git-dir='+str(provenance),'show',
        M['messenger']['baseline']+':tests/test_history_search_view.cjs'],env=env)
    assert original_fixture==expected_original
    repaired_fixture=(candidate/'tests/test_history_search_view.cjs').read_bytes()
    baseline_fixture.write_bytes(repaired_fixture)
    (OUT/'baseline-fixture-adapter.json').write_text(json.dumps({
        'original_sha256':hashlib.sha256(original_fixture).hexdigest(),
        'adapter_sha256':hashlib.sha256(repaired_fixture).hexdigest(),
        'target':'tests/test_history_search_view.cjs','candidate_same_fixture':True,
        'app_source_changed':False,'original_results':'failed-r1-receipt.json: 355 cases,48 failures; not a pass',
        'reason':'Explicit node:vm browser globals/DOM methods; original assertions preserved'},indent=2)+'\n')
    interpreters = {}
    for label in ['messenger-baseline', 'messenger-candidate']:
        # Even one different pinned dependency (baseline pyasn1) gets its own environment.
        venv = ROOT / (label + '-venv')
        assert run(label + '-venv', [sys.executable, '-m', 'venv', str(venv)], env=env) == 0
        py = str(venv / 'bin/python')
        interpreters[label] = py
        requirements = [sources[label] / 'isolated_sender/requirements.txt', sources[label] / 'push_notifications/requirements.txt']
        assert run(label + '-dependencies', [py, '-m', 'pip', 'install', *sum((['-r', str(p)] for p in requirements), []),
                   'PyYAML==6.0.2', 'Pillow==11.1.0'], env=env) == 0
        assert run(label + '-dependencies-check', [py, '-m', 'pip', 'check'], env=env) == 0
        assert run(label + '-dependencies-freeze', [py, '-m', 'pip', 'freeze', '--all'], env=env) == 0
    py = interpreters['messenger-candidate']
    assert run('node-dependencies', ['npm', 'install', '--prefix', str(ROOT / 'node'), '--no-audit', '--no-fund',
               'playwright@1.56.1','node@22.22.3'], env=env) == 0
    tool_assets(env)
    env['NODE_PATH'] = str(ROOT / 'node/node_modules')
    env['PLAYWRIGHT_MODULE'] = str(ROOT / 'node/node_modules/playwright')
    assert run('chromium', ['node', str(ROOT / 'node/node_modules/playwright/cli.js'), 'install', 'chromium'], env=env) == 0
    (OUT/'path-preflight.json').write_text(json.dumps(budget,indent=2)+'\n')
    assert run('environment-preflight',isolated([py,str(ROOT/'environment_probe.py')]),env=env,marker='"environment_probe_pass": true')==0
    required = []
    counts = {}
    for label in ['messenger-baseline', 'messenger-candidate']:
        src = sources[label]
        e = dict(env, PYTHONPATH=str(src) + ':' + str(src / 'tests'))
        name = label + '-python'
        run(name, isolated([interpreters[label], '-m', 'pytest', '-q', '-ra', 'tests', '--junitxml=' + str(OUT / (label + '.xml'))]), src, e, 1800)
        counts[label] = junit(label)
        assert not counts[label]['skipped'], ('No full-suite skips admitted',label,counts[label]['skipped'])
        required.append(name)
        nodes = sorted(str(p.relative_to(src)) for p in (src / 'tests').glob('*.test.mjs'))
        assert nodes
        name = label + '-node'
        run(name, isolated(['node', '--test', *nodes]), src, e)
        required.append(name)
    name = 'candidate-parity'
    run(name, isolated([py, str(ROOT / 'app-parity-gate'), str(sources['messenger-baseline']), str(candidate),
        '--core', 'vendored', '--renames', str(candidate / 'docs/live-feature-renames.txt'), '--json']), env=env)
    required.append(name)
    # All comparisons use one exact harness; originals are diagnostics, not candidate passes.
    comparisons = {}
    for label in ['messenger-baseline', 'messenger-offered', 'messenger-prefixed', 'messenger-candidate']:
        name = label + '-scroll-comparison'
        comparisons[label] = run(name, isolated(['node', 'tests/list_scroll_browser.cjs', str(OUT / name)]), candidate,
            dict(env, MESSENGER_STATIC_DIR=str(sources[label] / 'static'),
                 MESSENGER_SCROLL_CAUSAL_ONLY='0' if label=='messenger-candidate' else '1'), 180,
            marker='ALL PASS list_scroll_browser' if label=='messenger-candidate' else None)
        if label == 'messenger-candidate':
            required.append(name)
    # No prototype/layout instrumentation; stop before unrelated menu checks.
    for label in ['messenger-offered', 'messenger-prefixed', 'messenger-candidate']:
        name = label + '-desktop-reproduction'
        run(name, isolated(['node', 'tests/desktop_split_browser.cjs', str(OUT / name)]), candidate,
            dict(env, MESSENGER_STATIC_DIR=str(sources[label] / 'static'), MESSENGER_STOP_AFTER_SCROLL='1'), 180,
            marker='ALL PASS desktop_scroll_causal' if label=='messenger-candidate' else None)
        if label=='messenger-candidate': required.append(name)
    # An expected exception is a cleanup control, NEVER a passing browser interaction phase.
    name = 'desktop-exception-cleanup-control'
    code = run(name, isolated(['node', 'tests/desktop_split_browser.cjs', str(OUT / name)]), candidate,
               dict(env, MESSENGER_FAIL_AFTER_LAUNCH='1'), 30, marker='CLEANUP desktop_split browser closed')
    cleanup = phases[-1]
    cleanup_ok = code == 1 and cleanup['marker_found'] and not cleanup['timed_out'] and not cleanup['leftover_pids_killed']
    for name, marker in M['browser_success_markers'].items():
        phase = 'candidate-browser-' + name
        run(phase, isolated(['node', 'tests/' + name + '_browser.cjs', str(OUT / name)]), candidate, env, 300, marker=marker)
        required.append(phase)
    rows = {row['name']: row for row in phases}
    assert len(required) == len(set(required)) and all(name in rows for name in required)
    # Causal classification. Gate = candidate passes real assertions + the deterministic common fixture
    # discriminates (at least one pre-fix control reproduces a mid-flow draft-save scroll reset).
    # Desktop controls are diagnostic: identical list code was observed pass in one run and fail in another.
    def classify(label, name, observed):
        text = (OUT / (name + '.log')).read_text(errors='replace'); code = rows[name]['exit_code']
        if code == 0: return 'passed-no-reproduction'
        if observed.get('unexercised'): return 'unexercised-selected-source-did-not-issue-draft-save'
        if any(x['step'] == 'draft-save' and abs(x['top'] - x['start']) >= 2 for x in observed.get('failures', [])): return 'reproduced-draft-save-scroll-reset'
        if 'AssertionError [ERR_ASSERTION]: list scroll kept after switching' in text: return 'reproduced-original-assertion'
        return 'other-failure'
    common = {}
    for label in ['messenger-baseline', 'messenger-offered', 'messenger-prefixed']:
        f = OUT / (label + '-scroll-comparison') / 'scroll-observations.json'
        common[label] = classify(label, label + '-scroll-comparison', json.loads(f.read_text()) if f.exists() else {})
    desktop = {label: classify(label, label + '-desktop-reproduction', {}) for label in ['messenger-offered', 'messenger-prefixed']}
    reproduction = {k: v.startswith('reproduced') for k, v in desktop.items()}
    common_negative = {k: v.startswith('reproduced') for k, v in common.items()}
    discriminates = any(common_negative[k] for k in ['messenger-offered', 'messenger-prefixed'])
    served = {}
    for f in sorted(OUT.glob('**/served-source-*.json')):
        d = json.loads(f.read_text()); served[str(f.relative_to(OUT))] = {'errors': d['errors'], 'rows': [(r['url'], r['scope'], r['sha256']) for r in d['rows']]}
    passed = all(rows[name]['exit_code'] == 0 for name in required) and cleanup_ok and discriminates and not any(v['errors'] for v in served.values())
    return {'messenger_source_browser_pass': passed, 'source_browser_pass': False,
            'scope': M['scope'], 'required_phases': required, 'junit_counts': counts,
            'scroll_comparison_exit_codes': comparisons, 'original_scroll_failure_reproduced': reproduction,
            'common_scroll_classification': common, 'desktop_scroll_classification': desktop,
            'common_draft_scroll_failure_reproduced': common_negative, 'causal_control_discriminates': discriminates,
            'served_source_custody': served,
            'baseline_suite_mode':'original runtime + candidate-identical browser VM fixture adapter',
            'exception_cleanup_control_pass': cleanup_ok, 'reused_passes': [],
            'release_accepted': False, 'live_activation': False,
            'remaining_gates': ['Exact-source integration image custody/packaging',
                'Canonical in-shell synthetic preview: two skins, live switching, desktop/phone and changed flows',
                'Notifications integration is separately owned; no Notifications acceptance claim'],
            'evidence_note': 'Hosted-token synthetic fixture screenshots are not an in-shell preview or device acceptance.'}

parser = argparse.ArgumentParser()
parser.add_argument('--self-check', action='store_true')
args = parser.parse_args()
if args.self_check:
    verify()
    print(json.dumps({'path_preflight':path_preflight(M['remote']),'namespace_argv':isolated(['true']),
        'no_namespace_or_tests_executed':True,'tool_packages':M['tool_packages']}))
    sys.exit(0)
if str(ROOT) != M['remote'] or OUT.exists():
    sys.exit('Refuse non-admitted path or existing evidence directory; stage a fresh exclusive attempt')
receipt = {'messenger_source_browser_pass': False, 'source_browser_pass': False,
           'release_accepted': False, 'live_activation': False, 'scope': M['scope'],
           'manifest_sha256': digest(ROOT / 'manifest.json'), 'candidate_sha': M['messenger']['candidate']}
try:
    receipt.update(main())
except Exception as exc:
    receipt['error'] = type(exc).__name__ + ': ' + str(exc)
finally:
    OUT.mkdir(exist_ok=True)
    receipt['phases'] = phases
    (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
sys.exit(0 if receipt['messenger_source_browser_pass'] else 1)
