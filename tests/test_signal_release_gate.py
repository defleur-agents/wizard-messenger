"""Release-gate regression: no candidate regressions, hidden skips or arbitrary waivers."""
import copy
import unittest
from signal_release_gate import compare, strict_pass, STALE_UI

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
