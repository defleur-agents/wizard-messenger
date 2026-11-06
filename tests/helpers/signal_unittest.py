"""Machine-readable native unittest execution with zero skips on scoped gates."""
import json
import sys
import unittest
from pathlib import Path

class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []
    def addSuccess(self, test):
        super().addSuccess(test); self.cases.append({'id':test.id(),'status':'pass'})
    def addFailure(self, test, err):
        super().addFailure(test, err); self.cases.append({'id':test.id(),'status':'failure','error':self._exc_info_to_string(err,test)})
    def addError(self, test, err):
        super().addError(test, err); self.cases.append({'id':test.id(),'status':'error','error':self._exc_info_to_string(err,test)})
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.cases.append({'id':test.id(),'status':'skip','reason':reason})
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err: self.cases.append({'id':subtest.id(),'status':'subtest_failure','error':self._exc_info_to_string(err,test)})

if __name__ == '__main__':
    output, *names = sys.argv[1:]
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
    ok = result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses and result.testsRun > 0
    Path(output).write_text(json.dumps({'result':'scoped_pass' if ok else 'fail','tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses),
        'cases':result.cases},indent=2)+'\n')
    sys.exit(0 if ok else 1)
