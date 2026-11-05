"""Release-gate regression: no candidate regressions, hidden skips or arbitrary waivers."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from signal_release_gate import compare, load_events, strict_pass, STALE_UI


class NativeReportTransport(unittest.TestCase):
    """Synthetic parser inputs only; no changes to product/browser assertions."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.events_path = self.root / 'native.jsonl'
        self.tap_path = self.root / 'native.tap'
        self.events = [dict(type='test:pass', name='works', file=str(self.root/'tests/original.cjs'),
                            nesting=0, line=59, column=1, skip=False, todo=False, details={})]
        self.tap = ('TAP version 13\n# Subtest: works\nok 1 - works\n'
                    '  ---\n  duration_ms: 1\n  ...\n1..1\n# tests 1\n# suites 0\n'
                    '# pass 1\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n# duration_ms 2.5\n')

    def load(self, events=None, tap=None, code=0, text=None):
        self.events_path.write_text(text if text is not None else
                                    ''.join(json.dumps(e)+'\n' for e in (self.events if events is None else events)))
        self.tap_path.write_text(self.tap if tap is None else tap)
        return load_events(self.events_path, self.root, self.tap_path, code)

    def test_node20_no_summary_event_accepts_complete_native_tap(self):
        cases = self.load()
        self.assertEqual(list(cases), ['tests/original.cjs::works'])
        self.assertEqual(strict_pass(cases)['executed'], 1)
        self.assertEqual(cases['tests/original.cjs::works']['line'], 59)

    def test_missing_bad_or_duplicate_tap_counts_and_plan_fail_closed(self):
        for label, value in [('tests', 1), ('suites', 0), ('pass', 1), ('fail', 0),
                             ('cancelled', 0), ('skipped', 0), ('todo', 0)]:
            for replacement in ['', f'# {label} {value+1}\n', f'# {label} -1\n']:
                with self.subTest(label=label, replacement=replacement):
                    with self.assertRaises(AssertionError):
                        self.load(tap=self.tap.replace(f'# {label} {value}\n', replacement))
        for tap in ['', self.tap.replace('1..1\n', ''), self.tap.replace('1..1\n', '1..2\n'),
                    self.tap.replace('1..1\n', '1..1\n1..1\n'), self.tap.replace('TAP version 13\n', '')]:
            with self.subTest(tap=tap), self.assertRaises(AssertionError):
                self.load(tap=tap)
        self.load()
        self.tap_path.unlink()
        with self.assertRaises(FileNotFoundError):
            load_events(self.events_path, self.root, self.tap_path, 0)

    def test_truncated_or_extra_transport_fails_closed(self):
        for tap in [self.tap[:-1], self.tap[:self.tap.index('1..1')],
                    self.tap[:self.tap.index('# duration_ms')], self.tap+'ok 2 - surprise\n']:
            with self.subTest(tap=tap), self.assertRaises(AssertionError):
                self.load(tap=tap)
        for text in ['', json.dumps(self.events[0]), json.dumps(self.events[0])+'\n{"type":',
                     json.dumps(self.events[0])+'\n\n']:
            with self.subTest(text=text), self.assertRaises((AssertionError, ValueError)):
                self.load(text=text)

    def test_same_count_case_status_directive_or_inventory_mismatch_rejected(self):
        for tap in [self.tap.replace('ok 1 - works', 'ok 1 - other'),
                    self.tap.replace('ok 1 - works', 'not ok 1 - works'),
                    self.tap.replace('ok 1 - works', 'ok 1 - works # SKIP'),
                    self.tap.replace('ok 1 - works', 'ok 2 - works')]:
            with self.subTest(tap=tap), self.assertRaises(AssertionError):
                self.load(tap=tap)
        for events in [[], self.events*2, [dict(self.events[0], nesting=1)]]:
            with self.subTest(events=events), self.assertRaises(AssertionError):
                self.load(events=events)
        # Even matching TAP names/counts cannot hide duplicate file::name IDs.
        tap = self.tap.replace('1..1\n', 'ok 2 - works\n1..2\n').replace('# tests 1', '# tests 2').replace('# pass 1', '# pass 2')
        with self.assertRaisesRegex(AssertionError, 'duplicate test ID'):
            self.load(events=self.events*2, tap=tap)

    def test_fail_exit_must_match_native_counts_and_cases(self):
        failed = [dict(self.events[0], type='test:fail', details={'error':{'code':'ERR_ASSERTION'}})]
        tap = self.tap.replace('ok 1 - works', 'not ok 1 - works').replace('# pass 1', '# pass 0').replace('# fail 0', '# fail 1')
        self.assertEqual(self.load(events=failed, tap=tap, code=1)['tests/original.cjs::works']['status'], 'fail')
        for code in [0, 2, 124, -9]:
            with self.subTest(code=code), self.assertRaises(AssertionError):
                self.load(events=failed, tap=tap, code=code)
        with self.assertRaises(AssertionError):
            self.load(code=1)

    def test_skip_and_todo_counts_are_not_executed_passes_or_hidden_failures(self):
        skipped = [dict(self.events[0], skip='optional converter')]
        tap = self.tap.replace('ok 1 - works', 'ok 1 - works # SKIP optional converter').replace('# pass 1', '# pass 0').replace('# skipped 0', '# skipped 1')
        cases = self.load(events=skipped, tap=tap)
        self.assertEqual(strict_pass(cases, ['works'])['executed'], 0)
        with self.assertRaises(AssertionError):
            strict_pass(cases)
        for bad in [tap.replace('# skipped 1', '# skipped 0'), tap.replace('# pass 0', '# pass 1')]:
            with self.assertRaises(AssertionError):
                self.load(events=skipped, tap=bad)
        for status in ['pass', 'fail']:
            todo = [dict(self.events[0], type='test:'+status, todo='pending')]
            tap = self.tap.replace('ok 1 - works', ('ok' if status == 'pass' else 'not ok')+' 1 - works # TODO pending').replace('# pass 1', '# pass 0').replace('# todo 0', '# todo 1')
            cases = self.load(events=todo, tap=tap)
            with self.assertRaises(AssertionError):
                strict_pass(cases)
            with self.assertRaises(AssertionError):
                compare(cases, cases)

    def test_optional_real_native_summaries_must_match_counts_and_scope(self):
        counts = dict(tests=1, suites=0, passed=1, failed=0, cancelled=0, skipped=0, todo=0, topLevel=1)
        summary = dict(type='test:summary', counts=counts)
        self.load(events=self.events+[summary])
        self.load(events=self.events+[dict(summary, file=self.events[0]['file']), summary])
        for key in counts:
            bad = dict(summary, counts=dict(counts, **{key:counts[key]+1}))
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.load(events=self.events+[bad])
        for bad in [dict(summary, counts={}), dict(summary, counts=dict(counts, tests=True)),
                    dict(summary, file=str(self.root/'unknown.cjs'))]:
            with self.assertRaises(AssertionError):
                self.load(events=self.events+[bad])
        with self.assertRaises(AssertionError):
            self.load(events=self.events+[summary, summary])
        with self.assertRaises(AssertionError):
            self.load(events=self.events+[summary], tap=self.tap[:-1])


class SignalReleaseGate(unittest.TestCase):
    def case(self, status='pass', **kw):
        return dict(status=status, skip=False,todo=False,line=59,column=1,error=None,**kw)
    def test_exact_stale_failure_is_separate_from_scoped_success(self):
        name=sorted(STALE_UI)[0]; ident='tests/test_agent_permissions_view.cjs::'+name
        failed=self.case('fail');failed['error']={'name':'Error','code':'ERR_TEST_FAILURE','cause':{'code':'ERR_ASSERTION','message':'button Review agent drafts'}}
        a={ident:failed,'tests/original.cjs::works':self.case()}
        result=compare(a,copy.deepcopy(a))
        self.assertEqual(result['result'],'scoped_pass');self.assertEqual(result['suite_result'],'inherited_baseline_failures')
        self.assertFalse(result['all_suite_green']);self.assertEqual(list(result['inherited_baseline_failures']),[ident])
        b=copy.deepcopy(a);b[ident]['error']['cause']['message']='different failure'
        with self.assertRaises(AssertionError):compare(a,b)
        b=copy.deepcopy(a);b['tests/original.cjs::works']['status']='fail'
        with self.assertRaises(AssertionError):compare(a,b)
        b=copy.deepcopy(a);b['tests/original.cjs::works']['skip']=True
        with self.assertRaises(AssertionError):compare(a,b)
        b=copy.deepcopy(a);del b[ident]
        with self.assertRaises(AssertionError):compare(a,b)
        b=copy.deepcopy(a);b[ident]=self.case()
        self.assertEqual(list(compare(a,b)['baseline_only_incompatibilities']),[ident])
    def test_fixture_errors_and_unclassified_common_failures_never_authorize_build(self):
        ident='tests/test_agent_permissions_view.cjs::'+sorted(STALE_UI)[0]
        failed=self.case('fail');failed['error']={'name':'ReferenceError','message':'location is not defined'}
        with self.assertRaises(AssertionError):compare({ident:failed},{ident:failed})
        failed['error']={'code':'ERR_ASSERTION','message':'different behavior'}
        with self.assertRaises(AssertionError):compare({'tests/other.cjs::wrong':failed},{'tests/other.cjs::wrong':failed})
        with self.assertRaises(AssertionError):strict_pass({ident:failed})
        skipped=self.case();skipped['skip']='unexpected'
        with self.assertRaises(AssertionError):strict_pass({ident:skipped})
        self.assertEqual(strict_pass({'tests/current.cjs::works':self.case()})['executed'],1)
