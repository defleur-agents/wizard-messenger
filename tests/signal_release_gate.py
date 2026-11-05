"""Fail-closed classification of native node:test results, not a green-suite waiver."""
from pathlib import Path
import json
import re

STALE_UI = {
    'connector settings retain agent controls; disabled connectors preserve Telegram',
    'owner chooses four policies; required remote review has no local Send fallback',
    'normal mode edits, reviews and requires a separate explicit Send click',
    'normal preview pending cannot expose Send or editable controls',
    'owner adds an agent: new key shown once, starts at No access, Draft-and-send needs a confirmation',
}

def normalize(value, root):
    if isinstance(value, str):
        return value.replace(str(root), '<SOURCE>')
    if isinstance(value, dict):
        return {k: normalize(v, root) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v, root) for v in value]
    return value

def load_events(path, root):
    events = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    summaries = [e for e in events if e['type'] == 'test:summary']
    assert summaries, 'native node:test summary missing'
    cases = {}
    for event in events:
        if event['type'] not in ('test:pass', 'test:fail'):
            continue
        file = str(Path(event['file']).relative_to(root)) if event.get('file') else '<no-file>'
        ident = file + '::' + event['name']
        assert ident not in cases, 'duplicate test ID: ' + ident
        details = event.get('details') or {}
        error = normalize(details.get('error'), root)
        # Stack locations within product code legitimately move with an album change.
        # Retain full stacks in events; match exact cause/message/actual/expected,
        # plus the unchanged original assertion's file/line/column here.
        def signature(e):
            result = {k: signature(v) if isinstance(v, dict) else v
                      for k, v in (e or {}).items() if k != 'stack'}
            frames = re.findall(r'<SOURCE>/(tests/[^\s:)]+:\d+:\d+)', (e or {}).get('stack', ''))
            if frames: result['assertion_frames'] = frames
            return result
        cases[ident] = dict(status=event['type'].split(':')[1], skip=event.get('skip', False),
                            todo=event.get('todo', False), line=event.get('line'), column=event.get('column'),
                            error=signature(error))
    assert cases, 'no executed tests'
    return cases

def strict_pass(cases, expected_skips=()):
    failures = {k:v for k,v in cases.items() if v['status'] != 'pass' or v['todo']}
    assert not failures, 'scoped test failures: ' + json.dumps(failures)
    skips = sorted(k.split('::', 1)[1] for k,v in cases.items() if v['skip'])
    assert skips == sorted(expected_skips), 'unexpected scoped skips: ' + repr(skips)
    return {'result':'scoped_pass', 'executed':len(cases)-len(skips), 'skips':skips}

def compare(baseline, candidate):
    assert baseline.keys() == candidate.keys(), 'original A/B case inventory differs'
    assert not any(v['skip'] or v['todo'] for v in baseline.values()), 'baseline skipped/todo test'
    assert not any(v['skip'] or v['todo'] for v in candidate.values()), 'candidate skipped/todo test'
    inherited, baseline_only, unexpected = {}, {}, {}
    for ident, current in candidate.items():
        old = baseline[ident]
        if current['status'] == 'fail':
            if old != current:
                unexpected[ident] = {'baseline':old, 'candidate':current}
                continue
            file, name = ident.split('::', 1)
            assert file == 'tests/test_agent_permissions_view.cjs' and name in STALE_UI, 'unclassified common failure: ' + ident
            serialized = json.dumps(current['error'])
            assert not re.search(r'ReferenceError|SyntaxError|Unsupported fixture|Unexpected API|is not defined', serialized), 'fixture/runtime error is not stale UI: ' + ident
            assert 'ERR_ASSERTION' in serialized or 'TypeError' in serialized, 'unknown inherited error signature: ' + ident
            inherited[ident] = current
        elif old['status'] == 'fail':
            baseline_only[ident] = old
    assert not unexpected, 'candidate-only or changed failure signatures: ' + json.dumps(unexpected)
    return {'result':'scoped_pass', 'suite_result':'inherited_baseline_failures' if inherited or baseline_only else 'all_original_tests_pass',
            'original_case_count':len(candidate), 'candidate_only_failures':{},
            'inherited_baseline_failures':inherited, 'baseline_only_incompatibilities':baseline_only,
            'all_suite_green':not bool(inherited or baseline_only),
            'scope':'same original test IDs and assertion/error signatures on exact live baseline and candidate; not a feature waiver'}
