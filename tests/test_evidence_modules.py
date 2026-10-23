"""Actual worker failure/timeout must preserve outcomes without fabricated PASS."""
from pathlib import Path
import os,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from evidence_modules import run_modules


class EvidenceModuleTests(unittest.TestCase):
    def test_parallel_modules_really_overlap_and_keep_exact_canonical_order(self):
        code='''import unittest,time
from pathlib import Path
class Case(unittest.TestCase):
 def test_a(self):
  path=Path(__file__);path.with_suffix('.ready').write_text('ready')
  peer=path.parent/PEER
  deadline=time.monotonic()+5
  while not peer.exists() and time.monotonic()<deadline:time.sleep(.01)
  self.assertTrue(peer.exists(),'modules must overlap, not run sequentially')
'''
        for name,peer in (('test_peer_a','test_peer_b'),('test_peer_b','test_peer_a')):
            (self.root/(name+'.py')).write_text('PEER='+repr(peer+'.ready')+'\n'+code)
        ids=['test_peer_b.Case.test_a','test_peer_a.Case.test_a']
        result,errors,_=run_modules(ids,self.root/'parallel',test_root=self.root,module_timeout=15,workers=2)
        self.assertTrue(result.wasSuccessful());self.assertFalse(errors);self.assertEqual(list(result.records),ids)
        self.assertEqual(len({m['owned_pid'] for m in result.modules}),2)

    def test_parallel_timeout_preserves_other_module_success_and_no_fabricated_result(self):
        (self.root/'test_fast.py').write_text('import unittest\nclass Case(unittest.TestCase):\n def test_a(self):self.assertTrue(True)\n')
        (self.root/'test_slow.py').write_text('import unittest,time\nclass Case(unittest.TestCase):\n def test_a(self):time.sleep(30)\n')
        ids=['test_slow.Case.test_a','test_fast.Case.test_a']
        result,errors,_=run_modules(ids,self.root/'parallel',test_root=self.root,module_timeout=2,workers=2)
        self.assertFalse(result.wasSuccessful());self.assertTrue(errors)
        self.assertNotIn(ids[0],result.records);self.assertEqual(result.records[ids[1]]['status'],'PASS')
        slow=next(m for m in result.modules if m['module']=='test_slow')
        self.assertTrue(slow['timed_out']);self.assertFalse(slow['healthy']);self.assertEqual(slow['remaining_owned_pids'],[])

    def test_parallel_worker_budget_is_bounded_before_starting_processes(self):
        for value in (0,5,True,1.5):
            with self.assertRaises(ValueError):run_modules(['test_a.Case.test_a'],self.root/'never',workers=value)
        self.assertFalse((self.root/'never').exists())

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

    def test_fresh_worker_bootstraps_real_gui_font_database_before_test_module_execution(self):
        code='import unittest\nfrom PySide6.QtWidgets import QApplication\nfrom PySide6.QtGui import QFontDatabase\nclass Case(unittest.TestCase):\n def test_a(self):\n  self.assertIsNotNone(QApplication.instance())\n  self.assertGreater(len(QFontDatabase.families()),0)\n'
        result,errors,_=self.execute(code,['test_a'])
        self.assertTrue(result.wasSuccessful());self.assertFalse(errors);self.assertEqual(result.modules[0]['exit_code'],0)

    def test_abnormal_child_exit_keeps_actual_partial_journal_and_never_invents_remaining_tests(self):
        code='import unittest,os\nclass Case(unittest.TestCase):\n def test_a(self):pass\n def test_b(self):\n  if os.name=="posix":\n   import resource\n   resource.setrlimit(resource.RLIMIT_CORE,(0,0))\n   os.abort()\n  os._exit(7)\n def test_c(self):pass\n'
        result,errors,log=self.execute(code,['test_a','test_b','test_c'])
        self.assertFalse(result.wasSuccessful());self.assertEqual(len(result.records),1);self.assertEqual(next(iter(result.records.values()))['status'],'PASS')
        self.assertEqual(result.modules[0]['exit_code'],-6 if os.name=='posix' else 7);self.assertEqual(len(result.modules[0]['missing_test_ids']),2);self.assertEqual(errors[0]['type'],'OWNED_TEST_MODULE_PROCESS_FAILURE')
        if os.name=='posix':self.assertIn('Fatal Python error',(self.root/'live'/'timeout-stacks.log').read_text())

    def test_deadline_stops_only_owned_worker_and_descendant_without_success_receipt(self):
        marker=self.root/'child-pid'
        code='import unittest,subprocess,sys,time\nfrom pathlib import Path\nclass Case(unittest.TestCase):\n def test_a(self):\n  child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])\n  Path('+repr(str(marker))+').write_text(str(child.pid))\n  time.sleep(30)\n'
        result,errors,_=self.execute(code,['test_a'],timeout=2)
        self.assertFalse(result.wasSuccessful());self.assertTrue(result.modules[0]['timed_out']);self.assertFalse(result.records);self.assertTrue(errors)
        self.assertTrue(marker.exists(),'real child must start before measured timeout')
        if os.name=='posix':self.assertIn('test_owned_fixture.py',(self.root/'live'/'timeout-stacks.log').read_text())
        import psutil
        try:self.assertEqual(psutil.Process(int(marker.read_text())).status(),psutil.STATUS_ZOMBIE)
        except psutil.NoSuchProcess:pass
