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
from template_ai.model import Template
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from template_ai.source_links import VerifiedSource,fingerprint
from training_fixture import source_work
from test_noise_authoring import confirmed
from test_trusted_samples import admitted
APP=QApplication.instance() or QApplication([])


def frozen(store,samples,role='TRAIN',name='Synthetic Dataset'):
    plan=store.dataset_plan(name,[{'sample_id':s['id'],'role':role} for s in samples]);return store.create_dataset(plan,'Synthetic Reviewer',True)


class DatasetLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close);self.store=TrainingStore(self.library);self.source,self.work=source_work(self.library,self.root);confirmed(self.store,self.work);self.sample=admitted(self.store,self.work)
    def test_same_content_alias_identity_exact_dedup_and_group_split_prevented(self):
        source2,work2=source_work(self.library,self.root,'alias.svg');confirmed(self.store,work2);alias=admitted(self.store,work2);self.assertEqual(self.source['hash'],source2['hash']);self.assertNotEqual(self.source['id'],source2['id']);self.assertNotEqual(self.sample['label_slots'][0]['id'],alias['label_slots'][0]['id'])
        mixed=self.store.dataset_plan('wrong split',[{'sample_id':self.sample['id'],'role':'TRAIN'},{'sample_id':alias['id'],'role':'HOLDOUT'}]);self.assertTrue(mixed['errors'])
        with self.assertRaises(ValueError):self.store.create_dataset(mixed,'Reviewer',True)
        ds=frozen(self.store,[self.sample,alias]);self.assertEqual(len(ds['manifest']['exact_duplicates']),1);self.assertFalse(ds['manifest']['source_identities_merged']);self.assertEqual(ds['manifest']['near_similarity'],'UNKNOWN');representative=min(self.sample['id'],alias['id']);nonrep=max(self.sample['id'],alias['id'])
        with self.assertRaises(ValueError):self.store.geometry_learning_plan(ds['id'],nonrep,'duplicate learning')
        self.assertEqual(self.store.geometry_learning_plan(ds['id'],representative,'one representative')['entry']['sample_id'],representative)
    def test_global_whole_source_role_lock_holdout_and_unassigned_not_learned(self):
        ds=frozen(self.store,[self.sample],'HOLDOUT');plan=self.store.dataset_plan('attempt train',[{'sample_id':self.sample['id'],'role':'TRAIN'}]);self.assertTrue(plan['errors'])
        with self.assertRaises(ValueError):self.store.geometry_learning_plan(ds['id'],self.sample['id'],'holdout training')
        unassigned=frozen(self.store,[self.sample],'UNASSIGNED','unassigned')
        with self.assertRaises(ValueError):self.store.geometry_learning_plan(unassigned['id'],self.sample['id'],'not assigned')
        self.assertEqual(self.library.templates(),[])
    def test_manifest_reproducible_reopen_and_actual_geometry_draft_no_overwrite(self):
        p1=self.store.dataset_plan('dataset',[{'sample_id':self.sample['id'],'role':'TRAIN'}]);p2=self.store.dataset_plan('dataset',[{'sample_id':self.sample['id'],'role':'TRAIN'}]);self.assertEqual(p1,p2);ds=self.store.create_dataset(p1,'Reviewer',True);plan=self.store.geometry_learning_plan(ds['id'],self.sample['id'],'Learned Draft');draft=self.store.learn_dataset_sample(plan,self.store.source_proof(self.work['id']),'Reviewer',True);self.assertEqual(draft.state,'draft');self.assertEqual(draft.source_work_id,self.work['id']);self.assertEqual(draft.source_work_revision,self.work['revision']);self.assertEqual([s.rect for s in draft.slots],[s.rect for s in Template.from_dict(draft.to_dict()).slots]);self.assertEqual(self.store.sample_usage_impact(self.sample['id'])['template_ids'],[draft.id]);self.assertEqual(self.library.artwork(self.work['id']),self.work)
        with self.assertRaises(ValueError):self.store.geometry_learning_plan(ds['id'],self.sample['id'],'repeat')
        other=Library(self.library.root)
        try:self.assertTrue(TrainingStore(other).dataset_validity(ds['id'])['valid']);other._template_provenance(draft)
        finally:other.db.close()
    def test_revocation_blocks_new_learning_draft_publish_and_existing_reference(self):
        ds=frozen(self.store,[self.sample]);plan=self.store.geometry_learning_plan(ds['id'],self.sample['id'],'Draft');draft=self.store.learn_dataset_sample(plan,self.store.source_proof(self.work['id']),'Reviewer',True);transition=self.store.sample_transition_plan(self.sample['id'],'REVOKE');self.store.transition_sample(transition,'Reviewer','rights withdrawn',True);self.assertFalse(self.store.dataset_validity(ds['id'])['valid'])
        with self.assertRaises(ValueError):self.library.publish(draft)
        self.assertEqual(self.library.templates()[0].state,'draft');self.assertEqual(draft.state,'draft')
        with self.assertRaises(ValueError):self.store.learn_dataset_sample(plan,self.store.source_proof(self.work['id']),'Reviewer',True)
    def test_late_use_audit_failure_atomic_template_clock_usage_rollback(self):
        ds=frozen(self.store,[self.sample]);plan=self.store.geometry_learning_plan(ds['id'],self.sample['id'],'Atomic Draft');epoch=self.store.epoch;event=self.library.event
        def late(entity,action):
            event(entity,action)
            if action=='training_sample_geometry_use_recorded':raise RuntimeError('late provenance audit')
        with patch.object(self.library,'event',side_effect=late),self.assertRaises(RuntimeError):self.store.learn_dataset_sample(plan,self.store.source_proof(self.work['id']),'Reviewer',True)
        self.assertEqual(self.library.templates(),[]);self.assertEqual(self.store.count('USE'),0);self.assertEqual(self.store.epoch,epoch);self.assertEqual(self.library.db.execute('SELECT count(*) FROM template_edit_clocks').fetchone()[0],0)
    def test_false_source_proof_cannot_confirm_modified_source(self):
        facts=self.store.facts(self.work['id']);self.store.revoke_facts(facts['id'],facts['revision'],'reconfirm');facts=self.store.facts(self.work['id']);path=Path(self.source['original_path']);path.write_text('changed content');fake=VerifiedSource(str(path.resolve()),self.source['hash'],fingerprint(path.stat()))
        with self.assertRaises(ValueError):self.store.confirm_facts(facts['id'],[o['id'] for o in facts['observations']],facts['revision'],facts['pins'],fake,'Reviewer',True)
        self.assertIsNone(self.store.facts(facts['id'])['confirmation'])


class DatasetLearningGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close);self.store=TrainingStore(self.window.library);self.source,self.work=source_work(self.window.library,self.root);confirmed(self.store,self.work);self.sample=admitted(self.store,self.work);self.d=TrainingQualityDialog(self.window);self.addCleanup(self.d.close);self.p=self.d.dataset_panel;self.d.show();self.d.tabs.setCurrentWidget(self.p);self.p.name.setText('Synthetic Dataset');self.p.actor.setText('Synthetic Reviewer');self.p.table.item(0,0).setCheckState(Qt.Checked);self.p.table.cellWidget(0,1).setCurrentText('TRAIN');APP.processEvents()
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;self.window.close()
    def wait(self):
        for _ in range(300):
            APP.processEvents()
            if not self.p.running:return
            QTest.qWait(10)
        self.fail('bounded learning task did not finish')
    def test_actual_manifest_cancel_create_explicit_learning_draft_and_usage(self):
        QTest.mouseClick(self.p.preview_button,Qt.LeftButton);self.assertIn('source_group',self.p.details.toPlainText())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):QTest.mouseClick(self.p.create_button,Qt.LeftButton)
        self.assertEqual(self.store.count('DATASET'),0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.create_button,Qt.LeftButton)
        self.assertEqual(self.store.count('DATASET'),1);self.assertEqual(self.window.library.templates(),[]);self.p.template_name.setText('Real Geometric Draft')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.learn_button,Qt.LeftButton);self.wait()
        self.assertEqual(len(self.window.library.templates()),1);self.assertEqual(self.window.library.templates()[0].state,'draft');self.assertEqual(self.store.count('USE'),1);self.assertEqual(self.window.library.artwork(self.work['id']),self.work)
    def test_actual_changed_scope_confirmation_and_failed_source_controls_recover(self):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.p.create()
        self.p.template_name.setText('Draft')
        with patch('template_ai.dataset_panel.hash_source',side_effect=OSError('synthetic source failure')):self.p.learn();self.wait()
        self.assertIn('失敗',self.p.status.text());self.assertTrue(self.p.learn_button.isEnabled())
        def revoke(*args):self.store.transition_sample(self.store.sample_transition_plan(self.sample['id'],'REVOKE'),'Reviewer','during confirmation',True);return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=revoke):self.p.learn();self.wait()
        self.assertEqual(self.window.library.templates(),[]);self.assertIn('未完成',self.p.status.text());self.assertTrue(self.p.learn_button.isEnabled())
