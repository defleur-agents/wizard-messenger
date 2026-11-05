"""Run real pytest fixtures and require exact positive collection/JUnit agreement."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest

class Collection:
    def pytest_collection_finish(self, session):
        self.ids = [item.nodeid for item in session.items]

if __name__ == '__main__':
    output, module = sys.argv[1:]
    output = Path(output)
    junit = output.with_suffix('.xml')
    collection = Collection()
    code = pytest.main(['-q', module, '--junitxml=' + str(junit), '-o', 'junit_family=xunit2'], plugins=[collection])
    ids = getattr(collection, 'ids', [])
    root = ET.parse(junit).getroot()
    cases = list(root.iter('testcase'))
    suites = list(root.iter('testsuite'))
    expected = json.loads((Path(__file__).with_name('signal_pytest_expected.json')).read_text())[module]
    statuses = [{'id': c.attrib.get('name'), 'classname': c.attrib.get('classname'),
                 'status': 'fail' if list(c) else 'pass'} for c in cases]
    ok = (code == 0 and ids == expected and len(ids) > 0 and len(cases) == len(ids)
          and len({(c.get('classname'), c.get('name')) for c in cases}) == len(ids)
          and all(s['status'] == 'pass' for s in statuses)
          and sum(int(s.get('tests', 0)) for s in suites) == len(ids)
          and all(int(s.get(k, 0)) == 0 for s in suites for k in ['skipped', 'failures', 'errors']))
    result = {'result': 'scoped_pass' if ok else 'fail', 'backend': 'pytest',
              'returncode': int(code), 'collected': ids, 'expected': expected,
              'tests_run': len(cases), 'skips': sum(int(s.get('skipped', 0)) for s in suites),
              'junit': str(junit), 'cases': statuses}
    output.write_text(json.dumps(result, indent=2) + '\n')
    sys.exit(0 if ok else 1)
