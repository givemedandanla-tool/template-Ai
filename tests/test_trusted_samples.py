from gui_wait import dispose_main_window
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work,observations
from test_noise_authoring import confirmed
APP=QApplication.instance() or QApplication([])
RIGHTS={'basis':'OWNED','reference':'Anonymous synthetic SVG author record','use':'GEOMETRY_TRAINING_LOCAL'}


def admitted(store,work):
    plan=store.sample_approval_plan(work['id'],RIGHTS);return store.approve_sample(plan,store.source_proof(work['id']),'Synthetic Reviewer',True)


class TrustedSamplesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close);self.source,self.work=source_work(self.library,self.root);self.store=TrainingStore(self.library);self.facts=confirmed(self.store,self.work)
    def test_admission_preserves_labels_does_not_train_and_reopen_positive_negative_separation(self):
        obs=copy.deepcopy(self.facts['observations']);next(o for o in obs if o['id']=='observation-0')['prior_prediction']='Wrong Synthetic Prediction';facts=self.store.save_facts(self.work['id'],obs,self.facts['revision'],1);facts=self.store.confirm_facts(self.work['id'],[o['id'] for o in obs],facts['revision'],facts['pins'],self.store.source_proof(self.work['id']),'Reviewer',True)
        sample=admitted(self.store,self.work);self.assertEqual(self.store.sample_state(sample['id']),'APPROVED');self.assertFalse(sample['used_for_training']);self.assertEqual(len(sample['positive_labels']),4);self.assertEqual(sample['negative_predictions'][0]['prior_prediction'],'Wrong Synthetic Prediction');self.assertTrue(all(p['text']!='Wrong Synthetic Prediction' for p in sample['positive_labels']));self.assertEqual(self.library.templates(),[]);self.assertEqual(self.library.artwork(self.work['id']),self.work)
        other=Library(self.library.root)
        try:self.assertEqual(TrainingStore(other).sample_state(sample['id']),'APPROVED')
        finally:other.db.close()
    def test_rights_visual_unknown_missing_coverage_and_unapproved_admission_blocked(self):
        for rights in ({'basis':'UNKNOWN','reference':'x','use':'GEOMETRY_TRAINING_LOCAL'},{'basis':'OWNED','reference':'','use':'GEOMETRY_TRAINING_LOCAL'},{'basis':'OWNED','reference':'x','use':'NEURAL_REMOTE'}):self.assertTrue(self.store.sample_approval_plan(self.work['id'],rights)['errors'])
        plan=self.store.sample_approval_plan(self.work['id'],RIGHTS)
        with self.assertRaises(ValueError):self.store.approve_sample(plan,self.store.source_proof(self.work['id']),'Reviewer')
        record=self.store.facts(self.work['id']);self.store.revoke_facts(record['id'],record['revision'],'partial coverage');record=self.store.facts(self.work['id']);self.store.confirm_facts(record['id'],['note'],record['revision'],record['pins'],self.store.source_proof(record['id']),'Reviewer',True);self.assertTrue(self.store.sample_approval_plan(self.work['id'],RIGHTS)['errors'])
        payload=copy.deepcopy(self.work['payload']);payload['visual_confirmed']=False;self.library.save_artwork(self.work['id'],payload,1);self.assertTrue(self.store.sample_approval_plan(self.work['id'],RIGHTS)['errors']);self.assertEqual(self.store.count('SAMPLE'),0)
    def test_source_work_facts_and_cache_changes_invalidate_approved_sample(self):
        sample=admitted(self.store,self.work);Path(self.source['image']).write_bytes(b'broken cache');self.assertEqual(self.store.sample_state(sample['id']),'STALE_SOURCE_CACHE')
        with self.assertRaises(ValueError):admitted(self.store,self.work)
        record=self.store.facts(self.work['id']);self.store.revoke_facts(record['id'],record['revision'],'changed truth');self.assertEqual(self.store.sample_state(sample['id']),'STALE')
    def test_current_admission_dedup_stale_scope_and_late_audit_rollback(self):
        plan=self.store.sample_approval_plan(self.work['id'],RIGHTS);proof=self.store.source_proof(self.work['id']);epoch=self.store.epoch
        with patch.object(self.library,'event',side_effect=RuntimeError('late sample audit')),self.assertRaises(RuntimeError):self.store.approve_sample(plan,proof,'Reviewer',True)
        self.assertEqual(self.store.count('SAMPLE'),0);self.assertEqual(self.store.epoch,epoch)
        sample=self.store.approve_sample(plan,proof,'Reviewer',True)
        with self.assertRaises(ValueError):admitted(self.store,self.work)
        self.assertEqual(self.store.count('SAMPLE'),1);self.assertEqual(self.store.sample_state(sample['id']),'APPROVED')
        with self.assertRaises(ValueError):self.store.approve_sample(plan,proof,'Reviewer',True)
    def test_quarantine_revoke_exact_usage_impact_preserves_history_and_templates(self):
        sample=admitted(self.store,self.work)
        with self.store.transaction():
            self.store._write('DATASET','dataset',{'entries':[{'sample_id':sample['id']}]},0,'test_fixture');self.store._write('USE','use',{'sample_id':sample['id'],'template_id':'draft-template'},0,'test_fixture');self.store._write('JOB','job',{'items':[{'sample_id':sample['id']}]},0,'test_fixture')
        plan=self.store.sample_transition_plan(sample['id'],'QUARANTINE');self.assertEqual(plan['impact']['dataset_ids'],['dataset']);self.assertEqual(plan['impact']['template_ids'],['draft-template']);self.assertEqual(plan['impact']['job_ids'],['job']);self.assertFalse(plan['impact']['models_decontaminated']);quarantined=self.store.transition_sample(plan,'Reviewer','needs independent correction',True);self.assertEqual(self.store.sample_state(sample['id']),'QUARANTINED')
        with self.assertRaises(ValueError):self.store.transition_sample(plan,'Reviewer','stale',True)
        revoked=self.store.transition_sample(self.store.sample_transition_plan(sample['id'],'REVOKE'),'Reviewer','withdraw rights',True);self.assertEqual(self.store.sample_state(sample['id']),'REVOKED');self.assertGreater(revoked['revision'],quarantined['revision']);self.assertEqual(self.library.artwork(self.work['id']),self.work)


class TrustedSamplesGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close);self.source,self.work=source_work(self.window.library,self.root);self.store=TrainingStore(self.window.library);confirmed(self.store,self.work);self.d=TrainingQualityDialog(self.window);self.p=self.d.samples_panel;self.addCleanup(self.d.close);self.d.show();self.d.tabs.setCurrentWidget(self.p);self.p.basis.setCurrentText('OWNED');self.p.reference.setText(RIGHTS['reference']);self.p.actor.setText('Synthetic Reviewer');APP.processEvents()
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;dispose_main_window(self.window)
    def wait(self):
        for _ in range(300):
            APP.processEvents()
            if not self.p.running:return
            QTest.qWait(10)
        self.fail('bounded sample verification failed to finish')
    def test_actual_preview_cancel_admit_and_revoke_without_training(self):
        QTest.mouseClick(self.p.preview_button,Qt.LeftButton);self.assertIn('positive_labels',self.p.details.toPlainText())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):QTest.mouseClick(self.p.admit_button,Qt.LeftButton);self.wait()
        self.assertEqual(self.store.count('SAMPLE'),0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.admit_button,Qt.LeftButton);self.wait()
        self.assertEqual(self.store.count('SAMPLE'),1);self.assertEqual(self.window.library.templates(),[]);self.assertEqual(self.p.table.rowCount(),1);self.p.table.selectRow(0);self.p.reason.setText('synthetic withdrawal')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.revoke_button,Qt.LeftButton)
        self.assertEqual(self.store.sample_state(self.p.rows[0]['id']),'REVOKED');self.assertEqual(self.window.library.artwork(self.work['id']),self.work)
    def test_actual_failed_worker_and_scope_changed_during_confirmation_controls_recover(self):
        with patch('template_ai.trusted_samples_panel.healthy_source',return_value=False):QTest.mouseClick(self.p.admit_button,Qt.LeftButton);self.wait()
        self.assertIn('失敗',self.p.status.text());self.assertTrue(self.p.admit_button.isEnabled())
        def changed(*args):record=self.store.facts(self.work['id']);self.store.revoke_facts(record['id'],record['revision'],'during confirm');return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=changed):QTest.mouseClick(self.p.admit_button,Qt.LeftButton);self.wait()
        self.assertEqual(self.store.count('SAMPLE'),0);self.assertIn('未准入',self.p.status.text());self.assertTrue(self.p.reload_button.isEnabled())
