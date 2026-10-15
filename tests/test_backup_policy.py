import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from template_ai.storage import Library
from template_ai import backup_policy as policy,relational_backup as bundle

PASSWORD='synthetic backup policy password'


class BackupPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=Library(self.root/'library');self.addCleanup(self.library.close)

    def archive(self,index):
        path=self.root/f'synthetic-{index}.tabi';plan=bundle.plan_backup(self.library)
        result=bundle.create_backup(self.library,path,PASSWORD,plan,True)
        return policy.record_result(self.library,result,now=index)

    def test_schedule_cas_offline_key_busy_sleep_catchup_and_clock_rollback_never_store_password(self):
        value=policy.configure(self.library,self.root,60,2,0,dict(include_sources=True,include_fonts=True),now=100)
        self.assertEqual(policy.due_state(value,159,True),'WAITING')
        self.assertEqual(policy.due_state(value,160,False),'PASSWORD_REQUIRED')
        self.assertEqual(policy.due_state(value,160,True,True),'WAITING_IDLE')
        self.assertEqual(policy.due_state(value,10000,True),'DUE')
        failed=policy.update_attempt(self.library,value,error='disk offline',now=10000)
        self.assertIsNone(failed['last_success']);self.assertEqual(failed['next_due'],10060)
        self.assertEqual(policy.due_state(failed,9999,True),'CLOCK_ROLLBACK_REVIEW')
        with self.assertRaisesRegex(ValueError,'版本'):policy.configure(self.library,self.root,60,expected_revision=0)
        self.assertEqual(policy.due_state(dict(failed,directory=str(self.root/'offline')),10061,True),'DESTINATION_OFFLINE')
        raw=self.library.db.execute('SELECT value FROM preferences').fetchall()
        self.assertNotIn(PASSWORD,str(raw));self.assertEqual(failed['closed_application_execution'],'UNAVAILABLE')
        with self.assertRaisesRegex(ValueError,'密碼'):policy.configure(self.library,self.root,60,options={'password':PASSWORD},expected_revision=failed['revision'])

    def test_history_only_records_real_complete_files_and_duplicate_receipt_is_idempotent(self):
        record=self.archive(1);self.assertTrue(policy.verify_record(record,PASSWORD)['complete'])
        self.assertEqual(len(policy.history(self.library)),1)
        result=dict(record,state='CREATED_AUTHENTICATED')
        self.assertEqual(policy.record_result(self.library,result)['id'],record['id'])
        with self.assertRaises(ValueError):policy.record_result(self.library,dict(result,state='PLANNED'))
        Path(record['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):policy.record_result(self.library,result)

    def test_retention_requires_confirmation_preserves_newest_and_complete_last_and_never_deletes_unknown_files(self):
        records=[self.archive(i) for i in (1,2,3)]
        unknown=self.root/'user-document.tabi';unknown.write_bytes(b'user owned unrelated')
        with self.assertRaises(ValueError):policy.retention(self.library,self.root,PASSWORD,1)
        result=policy.retention(self.library,self.root,PASSWORD,1,approved=True,now=100)
        self.assertEqual(result['state'],'APPLIED');self.assertEqual(len(result['items']),2)
        self.assertTrue(Path(records[-1]['path']).is_file())
        self.assertFalse(Path(records[0]['path']).exists());self.assertTrue(unknown.is_file())
        self.assertTrue(policy.verify_record(records[-1],PASSWORD)['complete'])
        again=policy.retention(self.library,self.root,PASSWORD,1,approved=True,now=100)
        self.assertEqual(again['items'],[])

    def test_age_window_is_union_with_latest_count_and_changed_file_is_never_removed(self):
        records=[self.archive(i) for i in (1,2,3)]
        first=Path(records[0]['path']);first.write_bytes(b'externally changed')
        kept=policy.retention(self.library,self.root,PASSWORD,1,retain_days=1,approved=True,now=100)
        self.assertTrue(all(Path(r['path']).exists() for r in records))
        result=policy.retention(self.library,self.root,PASSWORD,1,approved=True,now=100000)
        self.assertTrue(first.exists());self.assertEqual(first.read_bytes(),b'externally changed')
        self.assertIn('NOT_DELETED',{i['state'] for i in result['items']})

    def test_wrong_password_cancellation_and_no_verified_full_backup_stop_retention(self):
        records=[self.archive(i) for i in (1,2)]
        result=policy.retention(self.library,self.root,'wrong password',1,approved=True)
        self.assertEqual(result['state'],'BLOCKED_NO_VERIFIED_COMPLETE_BACKUP')
        result=policy.retention(self.library,self.root,PASSWORD,1,approved=True,cancel=lambda:True)
        self.assertEqual(result['state'],'CANCELLED');self.assertTrue(all(Path(r['path']).exists() for r in records))

    def test_race_after_move_retains_recovery_bytes_and_last_verified_backup(self):
        records=[self.archive(i) for i in (1,2)];original=policy.os.rename
        def race(source,target):
            original(source,target);Path(target).write_bytes(b'concurrent replacement retained')
        with patch.object(policy.os,'rename',side_effect=race):
            result=policy.retention(self.library,self.root,PASSWORD,1,approved=True)
        item=result['items'][0];self.assertEqual(item['state'],'RETENTION_RECOVERY')
        self.assertEqual(Path(item['recovery_path']).read_bytes(),b'concurrent replacement retained')
        self.assertEqual(Path(records[0]['path']).read_bytes(),b'concurrent replacement retained')
        self.assertTrue(Path(records[1]['path']).is_file())
        self.assertTrue(policy.recovery_entries(self.root))

    def test_last_complete_backup_disappearing_during_rotation_cannot_delete_older_recovery(self):
        records=[self.archive(i) for i in (1,2)];original=policy.os.rename
        def race(source,target):
            original(source,target);Path(records[1]['path']).unlink()
        with patch.object(policy.os,'rename',side_effect=race):
            result=policy.retention(self.library,self.root,PASSWORD,1,approved=True)
        self.assertEqual(result['items'][0]['state'],'RETENTION_RECOVERY')
        self.assertTrue(Path(result['items'][0]['recovery_path']).is_file())
