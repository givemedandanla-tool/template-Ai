"""Run and persist actual admin-tool test IDs; no product-case inflation."""
import hashlib
import json
from pathlib import Path
import platform
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).parent))
from release_cache import write


class Result(unittest.TextTestResult):
    def addSuccess(self,test):
        super().addSuccess(test);self.rows.append(dict(id=test.id(),status='PASS'))
    def addFailure(self,test,err):
        super().addFailure(test,err);self.rows.append(dict(id=test.id(),status='FAIL'))
    def addError(self,test,err):
        super().addError(test,err);self.rows.append(dict(id=test.id(),status='ERROR'))
    def addSkip(self,test,reason):
        super().addSkip(test,reason);self.rows.append(dict(id=test.id(),status='SKIP',reason=reason))
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.rows=[]


if __name__=='__main__':
    output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent),pattern='test_release_speed.py')
    with (output/'admin-tests.log').open('w',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=Result).run(suite)
    expected=37
    success=result.wasSuccessful() and result.testsRun==expected and not result.skipped
    files=[*Path(__file__).parent.glob('release_*.py'),Path(__file__).parent/'test_release_speed.py',Path(__file__)]
    report=dict(scope='ADMIN_TOOL_SYNTHETIC_REGRESSION_NOT_PRODUCT_QUALIFICATION',status='PASS' if success else 'FAIL',
                command=[sys.executable,str(Path(__file__).relative_to(ROOT)),str(output)],python=platform.python_version(),
                expected=expected,executed=result.testsRun,skipped=len(result.skipped),exit_code=0 if success else 1,
                tests=result.rows,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    write(output/'admin-tests.json',report)
    print(json.dumps({key:report[key] for key in ('status','expected','executed','skipped','exit_code')}))
    raise SystemExit(report['exit_code'])
