"""Real recorded Node20 multi-file replay; raw JSONL did not capture testNumber.

The separately hashed enrichment recovers ONLY recorded TAP numbers for offline
parser regression. The queued dual-reporter run, not this replay, proves capture.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from signal_release_gate import compare, load_events


class RecordedNativeTransport(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).parent/'fixtures/signal_native_node20'
        self.meta = json.loads((fixture/'provenance.json').read_text())
        for name, digest in self.meta['sha256'].items():
            self.assertEqual(hashlib.sha256((fixture/name).read_bytes()).hexdigest(), digest)
        self.raw = [json.loads(x) for x in (fixture/'recorded.jsonl').read_text().splitlines()]
        self.events = [json.loads(x) for x in (fixture/'replay-enriched.jsonl').read_text().splitlines()]
        self.tap = (fixture/'recorded.tap').read_text()
        self.root = Path(self.meta['root'])
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def load(self, events=None, tap=None, root=None, code=1):
        (self.path/'events').write_text(''.join(json.dumps(e)+'\n' for e in (self.events if events is None else events)))
        (self.path/'tap').write_text(self.tap if tap is None else tap)
        return load_events(self.path/'events', root or self.root, self.path/'tap', code)

    def test_recorded_71_native_rows_preserved_not_global_enumeration(self):
        self.assertEqual(len(self.events), 71)
        numbers = [int(n) for n in re.findall(r'^(?:not )?ok (\d+) - ', self.tap, re.M)]
        for raw, enriched, number in zip(self.raw, self.events, numbers, strict=True):
            self.assertNotIn('testNumber', raw)
            self.assertEqual(enriched, dict(raw, testNumber=number))
        self.assertEqual(numbers[13:15], [3, 4])
        cases = self.load()
        result = compare(cases, copy.deepcopy(cases))
        self.assertEqual(result['original_case_count'], 71)
        self.assertEqual(len(result['inherited_baseline_failures']), 5)
        self.assertFalse(result['all_suite_green'])
        with self.assertRaisesRegex(AssertionError, 'testNumber'):
            self.load(events=self.raw)

    def test_native_number_counter_status_cancel_and_exit_negatives(self):
        for number in [None, False, 0, -1, '3', 2**53, 14]:
            bad = copy.deepcopy(self.events);bad[13]['testNumber'] = number
            with self.subTest(number=number), self.assertRaises(AssertionError):self.load(events=bad)
        for tap in [self.tap.replace('1..71\n','1..70\n'),
                    self.tap.replace('# pass 66\n','# pass 67\n'),
                    self.tap.replace('ok 3 - ', 'not ok 3 - ', 1),
                    self.tap[:self.tap.index('1..71\n')]]:
            with self.assertRaises(AssertionError):self.load(tap=tap)
        bad = copy.deepcopy(self.events);bad[13]['details']['error']={'failureType':'cancelledByParent'}
        with self.assertRaises(AssertionError):self.load(events=bad)
        for code in [0, 2, 124, -9]:
            with self.assertRaises(AssertionError):self.load(code=code)

    def test_wrapper_only_identity_and_normalized_assertion_frames(self):
        cases = self.load()
        other = Path('/srv/work/different-candidate/source')
        # Mechanical rebase of this recorded fixture is NOT fresh candidate evidence.
        events = json.loads(json.dumps(self.events).replace(str(self.root), str(other)))
        tap = self.tap.replace(str(self.root), str(other))
        candidate = self.load(events=events, tap=tap, root=other)
        self.assertEqual(cases, candidate)
        self.assertEqual(len(compare(cases, candidate)['inherited_baseline_failures']), 5)
        wrapper = 'tests/test_connector_login_runtime.cjs'
        self.assertIn(wrapper+'::'+wrapper, cases)
        self.assertIn(str(Path(self.events[0]['file']).relative_to(self.root))+'::'+self.events[0]['name'], cases)
        for index in [0, 13]:
            changed = copy.deepcopy(events);old = changed[index]['name'];changed[index]['name'] += ' '
            changed_tap = tap.replace(' - '+old+'\n', ' - '+old+' \n', 1)
            drift = self.load(events=changed, tap=changed_tap, root=other)
            with self.assertRaisesRegex(AssertionError, 'inventory'):compare(cases, drift)
        failed = next(i for i,e in enumerate(events) if e['type']=='test:fail')
        for mutation in ['frame', 'cause', 'expected']:
            changed = copy.deepcopy(events);error = changed[failed]['details']['error']
            if mutation=='frame':
                def frames(e):
                    e['stack'] = re.sub(r'(tests/[^\s:)]+:)(\d+)(:\d+)', lambda m:m[1]+str(int(m[2])+1)+m[3], e.get('stack',''))
                    if isinstance(e.get('cause'),dict):frames(e['cause'])
                frames(error)
            elif mutation=='cause':error.pop('cause', None)
            else:error['expected']='different expected value'
            drift = self.load(events=changed,tap=tap,root=other)
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):compare(cases,drift)
