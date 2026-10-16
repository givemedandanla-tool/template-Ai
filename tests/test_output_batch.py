from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from template_ai.output_batch import OutputBatch
from template_ai.background import file_digest
import test_multi_size as fixture

class OutputBatchTests(unittest.TestCase):
    setUp=fixture.MultiSizeTests.setUp
    tearDown=fixture.MultiSizeTests.tearDown
    requests=fixture.MultiSizeTests.requests
    def batch(self):return OutputBatch(self.workflow,self.workflow.plan(self.output,self.requests()))
    def configure(self,batch,overrides=None):
        result=batch.configure({row['id']:dict(name=Path(row['path']).name,action=(overrides or {}).get(row['id'],'CREATE')) for row in batch.items});fixture.approve_formats(self.workflow,batch.plan,150);return result

    def test_actual_mixed_final_preview_files_keep_sizes_formats_hashes_and_skips_separate(self):
        batch=self.batch();self.configure(batch,{'1':'SKIP'});before=self.library.template_snapshots();rows=batch.execute(approved=True,acknowledge_partial=True)
        self.assertEqual([r['status'] for r in rows],['SUCCESS','SKIPPED','SUCCESS','SUCCESS','SUCCESS','SUCCESS'])
        for row in rows:
            if row['status']=='SUCCESS':self.assertEqual(row['sha256'],file_digest(row['path']));self.assertEqual(Path(row['path']).parent.name,row['mode'])
        self.assertEqual(self.library.template_snapshots(),before)
        with self.assertRaisesRegex(ValueError,'僅可重試'):batch.execute(['0'],True,True,retry=True)

    def test_conflict_default_and_reserved_windows_names_fail_before_any_file_and_keep_plan_atomic(self):
        batch=self.batch();target=Path(batch.items[0]['path']);target.parent.mkdir();target.write_bytes(b'EXISTING')
        with self.assertRaises(FileExistsError):self.configure(batch)
        before=deepcopy(batch.items)
        with self.assertRaisesRegex(ValueError,'保留檔名'):batch.configure({r['id']:dict(name='CON.pdf' if r['id']=='0' else Path(r['path']).name,action='CREATE') for r in batch.items})
        self.assertEqual(batch.items,before);self.assertEqual(target.read_bytes(),b'EXISTING')

    def test_exact_failed_retry_preserves_all_success_and_is_bounded(self):
        import template_ai.output_batch as module
        batch=self.batch();self.configure(batch);real=module.export
        def fail(candidate,target,**kwargs):
            if str(target).endswith('.png'):raise PermissionError('SYNTHETIC permission failure')
            return real(candidate,target,**kwargs)
        with patch.object(module,'export',side_effect=fail):rows=batch.execute(approved=True,acknowledge_partial=True)
        successes={r['id']:r['sha256'] for r in rows if r['status']=='SUCCESS'};failed=[r['id'] for r in rows if r['status']=='FAILED'];self.assertEqual(failed,['1','4'])
        batch.execute(['1'],True,True,retry=True);self.assertEqual(batch.items[1]['status'],'SUCCESS');self.assertEqual(batch.items[4]['status'],'FAILED')
        for identity,sha in successes.items():self.assertEqual(file_digest(batch.items[int(identity)]['path']),sha)
        for _ in range(2):
            with patch.object(module,'export',side_effect=PermissionError('still denied')):batch.execute(['4'],True,True,retry=True)
        with self.assertRaisesRegex(ValueError,'最多3次'):batch.execute(['4'],True,True,retry=True)

    def test_explicit_overwrite_keeps_original_recovery_and_publishes_complete_result(self):
        batch=self.batch();target=Path(batch.items[0]['path']);target.parent.mkdir();target.write_bytes(b'OLD ORIGINAL')
        self.configure(batch,{'0':'OVERWRITE'});row=batch.execute(['0'],True,True)[0]
        self.assertEqual(row['status'],'SUCCESS');self.assertEqual(Path(row['recovery_path']).read_bytes(),b'OLD ORIGINAL');self.assertTrue(target.read_bytes().startswith(b'%PDF'));self.assertIsNone(row['stage_path'])

    def test_content_changed_during_overwrite_move_is_restored_and_never_replaced(self):
        import template_ai.output_batch as module
        batch=self.batch();target=Path(batch.items[0]['path']);target.parent.mkdir();target.write_bytes(b'OLD');self.configure(batch,{'0':'OVERWRITE'});rename=module.os.rename
        def race(left,right):Path(left).write_bytes(b'USER CHANGED');return rename(left,right)
        with patch.object(module.os,'rename',side_effect=race):row=batch.execute(['0'],True,True)[0]
        self.assertEqual(row['status'],'BLOCKED');self.assertFalse(row['retryable']);self.assertEqual(target.read_bytes(),b'USER CHANGED');self.assertEqual(Path(row['recovery_path']).read_bytes(),b'USER CHANGED')
        stage=Path(row['stage_path']);self.assertTrue(stage.name.startswith('.template-ai-STAGING_NOT_FINAL-'))
        with self.assertRaises(ValueError):batch.cleanup_stage('0')
        batch.cleanup_stage('0',True);self.assertFalse(stage.exists());self.assertEqual(target.read_bytes(),b'USER CHANGED')

    def test_late_destination_conflict_preserves_both_old_and_new_user_file(self):
        import template_ai.output_batch as module
        batch=self.batch();target=Path(batch.items[0]['path']);target.parent.mkdir();target.write_bytes(b'OLD');self.configure(batch,{'0':'OVERWRITE'})
        def race(stage,destination,check):destination.write_bytes(b'NEW USER FILE');raise FileExistsError('synthetic late conflict')
        with patch.object(module,'publish_complete',side_effect=race):row=batch.execute(['0'],True,True)[0]
        self.assertEqual(row['status'],'FAILED');self.assertEqual(target.read_bytes(),b'NEW USER FILE');self.assertEqual(Path(row['recovery_path']).read_bytes(),b'OLD')
        row=batch.execute(['0'],True,True,retry=True)[0];self.assertEqual(row['status'],'BLOCKED');self.assertEqual(target.read_bytes(),b'NEW USER FILE')

    def test_changed_inputs_during_encoding_leave_only_identified_diagnostic_stage(self):
        import template_ai.output_batch as module
        batch=self.batch();self.configure(batch);valid=[True];real=module.export
        def changed(*args,**kwargs):result=real(*args,**kwargs);valid[0]=False;return result
        with patch.object(module,'export',side_effect=changed):row=batch.execute(['0'],True,True,current_check=lambda:valid[0])[0]
        self.assertEqual(row['status'],'BLOCKED');self.assertFalse(Path(row['path']).exists());self.assertTrue(Path(row['stage_path']).exists());self.assertFalse(row['retryable'])
