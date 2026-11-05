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

def tap_escape(value):
    # Same escaping as Node's native TAP reporter (including control characters).
    for char, escaped in [('\b', r'\b'), ('\f', r'\f'), ('\t', r'\t'),
                          ('\n', r'\n'), ('\r', r'\r'), ('\v', r'\v')]:
        value = value.replace(char, escaped)
    return value.replace('\\', '\\\\').replace('#', r'\#')


def validate_transport(events, tap_path, returncode):
    """Require paired, complete native TAP + JSONL; Node 20 has no summary event.

    The admitted suites are flat node:test cases, not describe()/nested suites.
    Reject any other shape rather than silently miscounting it. TAP is only a
    transport/completeness witness; IDs and assertion signatures stay in JSONL.
    """
    results = [e for e in events if e['type'] in ('test:pass', 'test:fail')]
    assert results, 'no executed tests'
    assert all(e.get('nesting') == 0 and (e.get('details') or {}).get('type') != 'suite'
               for e in results), 'unsupported nested/suite transport'
    assert all(not (e.get('skip') and e.get('todo')) for e in results), 'skip and todo overlap'
    counts = dict(tests=len(results), suites=0, passed=0, failed=0, cancelled=0, skipped=0, todo=0)
    expected_rows = []
    for number, event in enumerate(results, 1):
        skip, todo = event.get('skip', False), event.get('todo', False)
        assert all(isinstance(flag, (bool, str)) for flag in (skip, todo)), 'invalid skip/todo flag'
        error = (event.get('details') or {}).get('error') or {}
        assert error.get('failureType') != 'cancelledByParent', 'cancelled native test'
        category = ('skipped' if skip else 'todo' if todo else
                    'passed' if event['type'] == 'test:pass' else 'failed')
        counts[category] += 1
        row = ('ok' if event['type'] == 'test:pass' else 'not ok') + f' {number} - ' + tap_escape(event['name'])
        if skip or todo:
            flag = skip or todo
            row += ' # ' + ('SKIP' if skip else 'TODO')
            if isinstance(flag, str):
                row += ' ' + tap_escape(flag)
        expected_rows.append(row)
    tap = Path(tap_path).read_text()
    assert tap.startswith('TAP version 13\n'), 'native TAP header missing'
    fields = [('tests', 'tests'), ('suites', 'suites'), ('pass', 'passed'), ('fail', 'failed'),
              ('cancelled', 'cancelled'), ('skipped', 'skipped'), ('todo', 'todo')]
    pattern = r'^1\.\.(\d+)\n' + ''.join(r'# '+label+r' (\d+)\n' for label, _ in fields)
    pattern += r'# duration_ms (?:\d+(?:\.\d+)?)(?:[eE][+-]?\d+)?\n\Z'
    terminal = re.search(pattern, tap, re.MULTILINE)
    assert terminal, 'native TAP terminal plan/counts missing or truncated'
    body = tap[:terminal.start()]
    assert not re.search(r'^(?:1\.\.|Bail out!)', body, re.MULTILINE), 'duplicate TAP plan or bailout'
    rows = re.findall(r'^(?:not )?ok\b[^\n]*', body, re.MULTILINE)
    assert rows == expected_rows, 'native TAP/JSONL case inventory or statuses differ'
    assert int(terminal[1]) == len(results), 'native TAP plan/JSONL count mismatch'
    for index, (_, key) in enumerate(fields, 2):
        assert int(terminal[index]) == counts[key], 'native TAP count mismatch: ' + key
    assert type(returncode) is int and returncode == (1 if counts['failed'] else 0), 'runner exit/case mismatch'
    # Newer Node versions may also emit native summaries. Never manufacture one.
    # Validate every supplied summary against its file scope or the whole run.
    seen = set()
    for summary in (e for e in events if e['type'] == 'test:summary'):
        file = summary.get('file')
        assert file not in seen, 'duplicate native summary'
        seen.add(file)
        scoped = [e for e in results if not file or e.get('file') == file]
        assert scoped, 'native summary has unknown file scope'
        expected = dict(counts) if not file else dict(tests=len(scoped), suites=0, passed=0,
                                                     failed=0, cancelled=0, skipped=0, todo=0)
        if file:
            for event in scoped:
                key = ('skipped' if event.get('skip') else 'todo' if event.get('todo') else
                       'passed' if event['type'] == 'test:pass' else 'failed')
                expected[key] += 1
        actual = summary.get('counts')
        assert isinstance(actual, dict), 'native summary counts missing'
        for key, value in dict(expected, topLevel=len(scoped)).items():
            assert type(actual.get(key)) is int and actual[key] == value, 'native summary count mismatch: ' + key


def load_events(path, root, tap_path, returncode):
    text = Path(path).read_text()
    assert text.endswith('\n'), 'native JSONL missing or truncated'
    events = [json.loads(line) for line in text.splitlines()]
    assert all(e['type'] in ('test:pass', 'test:fail', 'test:summary') for e in events), 'unexpected native event'
    validate_transport(events, tap_path, returncode)
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
