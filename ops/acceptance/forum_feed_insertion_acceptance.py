#!/usr/bin/env python3
"""Sole failed r2 phase repair. Synthetic source proof; admitted by parent, never activation."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results'
phases = []
run: Callable[..., Any]
isolated: Callable[..., Any]
path_preflight: Callable[..., Any]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def verified_inputs():
    m = json.loads((ROOT / 'manifest.json').read_text())
    for name, expected in m['files'].items():
        assert digest(ROOT / name) == expected, name
    assert m['no_activation'] and m['parent_admission_only']
    old = Path(m['inherited_root'])
    for name, expected in m['inherited_files'].items():
        assert digest(old / name) == expected, ('inherited file changed', name)
    prior = json.loads((ROOT / 'inherited-r2-receipt.json').read_text())
    assert prior == json.loads((old / 'results/receipt.json').read_text())
    assert prior['manifest_sha256'] == m['inherited_manifest_sha256']
    assert prior['candidate_sha'] == m['inherited_candidate']
    rows = {r['name']: r for r in prior['phases']}
    assert [n for n in prior['required_phases'] if rows[n]['exit_code'] != 0] == ['messenger-candidate-scroll-comparison']
    for row in prior['phases']:
        assert digest(old / 'results' / (row['name'] + '.log')) == row['log_sha256'], row['name']
    assert prior['causal_control_discriminates'] and prior['exception_cleanup_control_pass']
    assert all(not r['errors'] for r in prior['served_source_custody'].values())
    for counts in prior['junit_counts'].values():
        assert not counts['skipped'] and not counts['errors'] and counts['cases'] > 0
    # REUSE the hash-verified r2 timeout, process-group cleanup and exact nested namespace implementation.
    tree = ast.parse((old / 'forum_apps_acceptance.py').read_text())
    names = {'group_members', 'run', 'isolated', 'path_preflight'}
    functions: list[ast.stmt] = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in functions if isinstance(n, ast.FunctionDef)} == names
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<verified-r2-helpers>', 'exec'), globals())
    budget = path_preflight(m['remote'])
    assert str(m['remote']).startswith('/srv/work/')
    tools = json.loads((ROOT / 'tool-closure.json').read_text())
    for name, expected in tools.items():
        assert digest(old / name) == expected, ('tool closure changed', name)
    return m, old, prior, budget

def extract_sources(m, env):
    provenance = ROOT / 'provenance.git'
    subprocess.run(['git', 'init', '--bare', '-q', str(provenance)], env=env, check=True)
    with (ROOT / 'messenger-provenance.pack').open('rb') as pack:
        subprocess.run(['git', '--git-dir=' + str(provenance), 'index-pack', '--stdin'], stdin=pack,
                       stdout=subprocess.DEVNULL, env=env, check=True, timeout=60)
    sources = {}
    for label, sha in m['source_refs'].items():
        archive_path = ROOT / (label + '.tar')
        regenerated = ROOT / 'tmp' / (label + '.tar')
        with regenerated.open('wb') as output:
            subprocess.run(['git', '--git-dir=' + str(provenance), 'archive', '--format=tar', sha],
                           stdout=output, env=env, check=True, timeout=60)
        assert digest(regenerated) == digest(archive_path), ('real commit archive custody', label)
        source = ROOT / label
        source.mkdir()
        with tarfile.open(archive_path) as archive:
            assert archive.pax_headers['comment'] == sha
            archive.extractall(source, filter='data')
        sources[label] = source
    expected = json.loads((ROOT / 'source-files.json').read_text())
    for label, files in expected.items():
        actual = {str(p.relative_to(sources[label])): digest(p) for p in sources[label].rglob('*') if p.is_file()}
        assert actual == files, ('complete source closure', label)
    candidate_files = expected['messenger-candidate']
    old_files = json.loads((ROOT / 'inherited-source-files.json').read_text())['messenger-candidate']['files']
    changed = sorted(n for n in set(candidate_files) | set(old_files) if candidate_files.get(n) != old_files.get(n))
    assert changed == sorted(m['allowed_changed_files']), changed
    assert all(n.startswith(('tests/', 'docs/', 'ops/acceptance/')) for n in changed)
    assert {n:h for n,h in candidate_files.items() if n.startswith('static/')} == {n:h for n,h in old_files.items() if n.startswith('static/')}
    return sources, {'original_git_head': m['inherited_candidate'], 'new_git_head':m['source_refs']['messenger-candidate'],
        'runtime_and_static_files_identical':True, 'complete_changed_files':changed,
        'changed_file_hashes':{n:{'old':old_files.get(n), 'new':candidate_files.get(n)} for n in changed},
        'inherited_subtree_hashes':m['inherited_source_subtrees'], 'new_tests_not_claimed_as_old_head_tests':True}

def main(m, old, prior, budget):
    assert str(ROOT) == m['remote'] and not OUT.exists(), 'Fresh admitted root only; never overwrite evidence'
    OUT.mkdir()
    for name in ['tmp','home','cache']:
        (ROOT / name).mkdir()
    node_root = old / 'node/node_modules'
    env = {'PATH':str(node_root / 'node/bin') + ':/usr/local/bin:/usr/bin:/bin',
        'HOME':str(ROOT / 'home'), 'TMPDIR':str(ROOT / 'tmp'), 'XDG_CACHE_HOME':str(ROOT / 'cache'),
        'PLAYWRIGHT_BROWSERS_PATH':str(old / 'browsers'), 'NODE_PATH':str(node_root),
        'PLAYWRIGHT_MODULE':str(node_root / 'playwright'), 'PYTHONDONTWRITEBYTECODE':'1',
        'GIT_CONFIG_NOSYSTEM':'1', 'GIT_CONFIG_GLOBAL':'/dev/null'}
    sources, closure = extract_sources(m, env)
    candidate = sources['messenger-candidate']
    save(OUT / 'source-closure.json', closure)
    save(OUT / 'path-preflight.json', budget)
    # Browser-only repair: no Python/media suites are replayed. Their exact non-skipped r2 evidence is inherited.
    assert run('focused-node', isolated(['node','--test','tests/list-scroll.test.mjs']), candidate, env,
               marker='# pass 4') == 0
    common = ['node', 'tests/list_scroll_browser.cjs']
    run('messenger-candidate-scroll-comparison', isolated(common + [str(OUT / 'messenger-candidate-scroll-comparison')]),
        candidate, dict(env, MESSENGER_STATIC_DIR=str(candidate / 'static')), 180,
        marker='ALL PASS list_scroll_browser')
    run('seq-only-negative-control', isolated(common + [str(OUT / 'seq-only-negative-control')]),
        candidate, dict(env, MESSENGER_STATIC_DIR=str(candidate / 'static'), MESSENGER_SCROLL_INSERTION_CONTROL='seq-only'), 90,
        marker='CLEANUP list_scroll browser closed')
    run('prefixed-draft-causal-control', isolated(common + [str(OUT / 'prefixed-draft-causal-control')]),
        candidate, dict(env, MESSENGER_STATIC_DIR=str(sources['messenger-prefixed'] / 'static'),
                        MESSENGER_SCROLL_CAUSAL_ONLY='1'), 90, marker='CLEANUP list_scroll browser closed')
    rows = {r['name']:r for r in phases}
    positive = json.loads((OUT / 'messenger-candidate-scroll-comparison/scroll-observations.json').read_text())
    expected_scenes = {('dark',1280), ('light',1280), ('dark',390), ('light',390)}
    scene_ok = {(x['skin'],x['width']) for x in positive['insertions']} == expected_scenes and len(positive['insertions']) == 4
    for insertion in positive['insertions']:
        assert not insertion['seqOnlyControl']
        assert insertion['response']['result']['people'][0]['id'] == 'p-extra'
        assert insertion['after']['rows'][-1] == 'p-extra' and len(insertion['after']['extra']) == 1
        assert len(insertion['after']['rows']) == len(insertion['before']['rows']) + 1
        assert insertion['after']['height'] > insertion['before']['height']
        assert insertion['peopleReadsBefore'] == insertion['peopleReadsAfter']
    neg = json.loads((OUT / 'seq-only-negative-control/scroll-observations.json').read_text())
    assert len(neg['insertions']) == 1
    insertion = neg['insertions'][0]
    negative_ok = (insertion['seqOnlyControl'] and insertion['response'] == {'ok':True, 'result':{'seq':7}}
        and insertion['before']['rows'] == insertion['after']['rows'] and not insertion['after']['extra']
        and insertion['before']['height'] == insertion['after']['height']
        and insertion['peopleReadsBefore'] == insertion['peopleReadsAfter']
        and rows['seq-only-negative-control']['exit_code'] == 1
        and 'page.waitForFunction: Timeout' in (OUT / 'seq-only-negative-control.log').read_text())
    control = json.loads((OUT / 'prefixed-draft-causal-control/scroll-observations.json').read_text())
    causal_ok = (rows['prefixed-draft-causal-control']['exit_code'] == 1 and not control['unexercised']
        and any(x['step']=='draft-save' and abs(x['top']-x['start']) >= 2 for x in control['failures']))
    served = {}
    for file in sorted(OUT.glob('**/served-source-*.json')):
        record = json.loads(file.read_text())
        assert not record['errors']
        served[str(file.relative_to(OUT))] = {'sha256':digest(file), 'rows':record['rows'], 'errors':record['errors']}
    for skin,width in expected_scenes:
        record = served[f'messenger-candidate-scroll-comparison/served-source-{skin}-{width}.json']
        assert any(r['sha256'] == m['candidate_unified_sha256'] and r['resourceType']=='script'
            and r['url']=='https://messenger.test/unified.js' for r in record['rows'])
    no_leaks = all(not r['timed_out'] and not r['leftover_pids_killed'] and r['marker_found'] for r in phases)
    passed = (rows['messenger-candidate-scroll-comparison']['exit_code'] == 0 and scene_ok
        and not positive['failures'] and not positive['unexercised'] and negative_ok and causal_ok and no_leaks)
    reused = [dict(r, origin='inherited-r2', original_candidate_sha=prior['candidate_sha'],
        receipt_sha256=m['files']['inherited-r2-receipt.json']) for r in prior['phases']
        if r['name'] in prior['required_phases'] and r['exit_code']==0]
    return {'messenger_source_browser_pass':passed, 'source_browser_pass':False,
        'mode':'exact-app-closure-inheritance-plus-repaired-phase', 'source_closure':closure,
        'reused_passes':reused, 'inherited_junit_counts':prior['junit_counts'],
        'inherited_causal_control_discriminates':prior['causal_control_discriminates'],
        'inherited_exception_cleanup_control_pass':prior['exception_cleanup_control_pass'],
        'inherited_receipt_sha256':m['files']['inherited-r2-receipt.json'],
        'inherited_manifest_sha256':m['inherited_manifest_sha256'],
        'inherited_failure_replaced_not_rewritten':'messenger-candidate-scroll-comparison',
        'positive_scenes_pass':scene_ok, 'seq_only_control_discriminates':negative_ok,
        'prefixed_draft_control_discriminates':causal_ok, 'served_source_custody':served,
        'release_accepted':False, 'live_activation':False,
        'remaining_gates':prior['remaining_gates']}

def entry():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    # Local preflight does not need old worker files, and executes no namespace/test/browser.
    if args.self_check:
        m = json.loads((ROOT / 'manifest.json').read_text())
        assert all(digest(ROOT / n)==h for n,h in m['files'].items())
        assert len((m['remote'] + '/home/' + 'x'*72).encode()) < 108
        print(json.dumps({'sealed_inputs_match':True, 'no_tests_or_namespaces_executed':True,
            'manifest_sha256':digest(ROOT / 'manifest.json')}))
        return 0
    m = json.loads((ROOT / 'manifest.json').read_text())
    assert str(ROOT)==m['remote'] and not OUT.exists(), 'Refuse overwrite or nonadmitted location'
    receipt = {'messenger_source_browser_pass':False, 'source_browser_pass':False, 'release_accepted':False,
        'live_activation':False, 'candidate_sha':m['source_refs']['messenger-candidate'],
        'manifest_sha256':digest(ROOT / 'manifest.json')}
    try:
        m,old,prior,budget = verified_inputs()
        receipt.update(main(m,old,prior,budget))
    except Exception as error:
        receipt['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        OUT.mkdir(exist_ok=True)
        receipt['phases'] = phases
        save(OUT / 'receipt.json', receipt)
        print(json.dumps(receipt), flush=True)
    return 0 if receipt['messenger_source_browser_pass'] else 1

if __name__ == '__main__':
    sys.exit(entry())
