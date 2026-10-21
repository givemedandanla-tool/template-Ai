"""Real process survival and bounded progress publication across platforms."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_evidence import EvidenceResult
from template_ai.batch_import import BatchStore,preflight
from template_ai.storage import Library
from template_ai.training_pipeline import owner_alive


class WindowsReleaseSafetyTests(unittest.TestCase):
    def child(self):
        child=subprocess.Popen([sys.executable,'-c',
            "import time; print('READY',flush=True); time.sleep(30)"],
            stdout=subprocess.PIPE,text=True)
        def close():
            if child.poll() is None:child.terminate()
            child.wait(timeout=5)
            child.stdout.close()
        self.addCleanup(close)
        self.assertEqual(child.stdout.readline(),'READY\n')
        return child

    def test_training_liveness_probe_does_not_terminate_live_foreign_process(self):
        child=self.child()
        self.assertTrue(owner_alive(dict(pid=child.pid,token='external-owner')))
        self.assertIsNone(child.poll())

    def test_batch_recovery_keeps_live_foreign_owner_and_original_work(self):
        child=self.child()
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);source=root/'synthetic.svg'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
            library=Library(root/'data')
            try:
                store=BatchStore(library)
                batch=store.create(preflight([source],[]),True)
                batch=store.claim(batch['id'],batch['revision'],batch['items'][0]['id'])
                batch=store.mutate(batch['id'],batch['revision'],'SYNTHETIC_FOREIGN_OWNER',
                    lambda data:data.update(owner=dict(pid=child.pid,session='external-owner')))
                self.assertEqual(store.recover(),[])
                self.assertIsNone(child.poll())
                self.assertEqual(store.get(batch['id']),batch)
            finally:library.close()

    def progress(self,folder):
        return EvidenceResult(io.StringIO(),True,0,progress_path=Path(folder)/'progress.json')

    def test_windows_sharing_conflict_retries_and_publishes_complete_progress(self):
        with tempfile.TemporaryDirectory() as raw:
            result=self.progress(raw);actual=os.replace;attempts=[]
            def replace(source,target):
                attempts.append((source,target))
                if len(attempts)==1:
                    error=PermissionError('synthetic Windows reader sharing conflict')
                    error.winerror=32
                    raise error
                return actual(source,target)
            with patch('run_evidence.os.replace',side_effect=replace):
                result.startTest(unittest.FunctionTestCase(lambda:None))
            data=json.loads(result.progress_path.read_text())
            self.assertEqual((data['started'],data['completed']),(1,0))
            self.assertFalse(data['formal_complete'])
            self.assertFalse(result.progress_path.with_suffix('.tmp').exists())

    def test_unrelated_permission_error_is_not_hidden_by_progress_retry(self):
        with tempfile.TemporaryDirectory() as raw:
            result=self.progress(raw)
            with patch('run_evidence.os.replace',side_effect=PermissionError('real permission failure')) as replace:
                with self.assertRaises(PermissionError):result.startTest(unittest.FunctionTestCase(lambda:None))
            self.assertEqual(replace.call_count,1)
            self.assertFalse(result.progress_path.exists())

    def test_persistent_windows_denial_fails_with_a_bounded_number_of_attempts(self):
        with tempfile.TemporaryDirectory() as raw:
            result=self.progress(raw);error=PermissionError('persistent Windows denial');error.winerror=5
            with patch('run_evidence.os.replace',side_effect=error) as replace:
                with self.assertRaises(PermissionError):result.startTest(unittest.FunctionTestCase(lambda:None))
            self.assertGreater(replace.call_count,1)
            self.assertLessEqual(replace.call_count,16)
            self.assertFalse(result.progress_path.exists())
