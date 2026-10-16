"""Actual worker failure/timeout must preserve outcomes without fabricated PASS."""
from pathlib import Path
import os,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from evidence_modules import run_modules


class EvidenceModuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def execute(self,code,names,timeout=15):
        (self.root/'test_owned_fixture.py').write_text(code)
        ids=['test_owned_fixture.Case.'+name for name in names]
        return run_modules(ids,self.root/'live',test_root=self.root,module_timeout=timeout)

    def test_actual_child_failure_preserves_both_exact_outcomes_and_no_skip(self):
        result,errors,log=self.execute('import unittest\nclass Case(unittest.TestCase):\n def test_a(self):self.assertEqual(1,1)\n def test_b(self):self.fail("Synthetic actual child assertion")\n',['test_a','test_b'])
        self.assertFalse(result.wasSuccessful());self.assertEqual([r['status'] for r in result.records.values()],['PASS','FAIL']);self.assertFalse(errors)
        self.assertEqual(result.modules[0]['exit_code'],1);self.assertEqual(result.modules[0]['missing_test_ids'],[]);self.assertIn('Synthetic actual child assertion',log)

    def test_abnormal_child_exit_keeps_actual_partial_journal_and_never_invents_remaining_tests(self):
        code='import unittest,os\nclass Case(unittest.TestCase):\n def test_a(self):pass\n def test_b(self):\n  if os.name=="posix":\n   import resource\n   resource.setrlimit(resource.RLIMIT_CORE,(0,0))\n   os.abort()\n  os._exit(7)\n def test_c(self):pass\n'
        result,errors,log=self.execute(code,['test_a','test_b','test_c'])
        self.assertFalse(result.wasSuccessful());self.assertEqual(len(result.records),1);self.assertEqual(next(iter(result.records.values()))['status'],'PASS')
        self.assertEqual(result.modules[0]['exit_code'],-6 if os.name=='posix' else 7);self.assertEqual(len(result.modules[0]['missing_test_ids']),2);self.assertEqual(errors[0]['type'],'OWNED_TEST_MODULE_PROCESS_FAILURE')

    def test_deadline_stops_only_owned_worker_and_descendant_without_success_receipt(self):
        marker=self.root/'child-pid'
        code='import unittest,subprocess,sys,time\nfrom pathlib import Path\nclass Case(unittest.TestCase):\n def test_a(self):\n  child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])\n  Path('+repr(str(marker))+').write_text(str(child.pid))\n  time.sleep(30)\n'
        result,errors,_=self.execute(code,['test_a'],timeout=2)
        self.assertFalse(result.wasSuccessful());self.assertTrue(result.modules[0]['timed_out']);self.assertFalse(result.records);self.assertTrue(errors)
        self.assertTrue(marker.exists(),'real child must start before measured timeout')
        import psutil
        try:self.assertEqual(psutil.Process(int(marker.read_text())).status(),psutil.STATUS_ZOMBIE)
        except psutil.NoSuchProcess:pass
