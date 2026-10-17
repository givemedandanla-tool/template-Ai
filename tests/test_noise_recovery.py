from gui_wait import dispose_main_window
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.noise import relative_region
from template_ai.noise_authoring_dialog import NoiseAuthoringDialog
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work,observations
from test_rule_review import pending_rule
from test_noise_hits import activate
from test_noise_authoring import confirmed
APP=QApplication.instance() or QApplication([])


class NoiseRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close);self.store=TrainingStore(self.library);self.source,self.work,self.rule=pending_rule(self.store,self.root);self.rule=activate(self.store,self.rule);self.future_source,self.future=source_work(self.library,self.root,'future.svg');self.facts=confirmed(self.store,self.future)
    def state(self,work):return next(r for r in self.store.noise_decisions(work['id']) if r['observation_id']=='note')['state']
    def white(self):return self.store.propose_whitelist(self.future['id'],'note',[{'work_id':self.future['id'],'observation_id':'observation-0'}],relative_region(self.future,next(o for o in self.facts['observations'] if o['id']=='note')),'NONE',self.facts['revision'],self.store.epoch,'Reviewer',True)
    def test_local_keep_and_pending_whitelist_are_different_from_global_approved_keep(self):
        self.assertEqual(self.state(self.future),'EXCLUDED_RULE');self.store.local_keep(self.future['id'],['note'],0,self.facts['revision'],True);self.assertEqual(self.state(self.future),'KEPT_LOCAL')
        _,third=source_work(self.library,self.root,'third.svg');confirmed(self.store,third);self.assertEqual(self.state(third),'EXCLUDED_RULE')
        white=self.white();self.assertEqual(white['state'],'PENDING');self.assertEqual(self.state(third),'EXCLUDED_RULE');activate(self.store,white);self.assertEqual(self.state(third),'KEPT_WHITELIST');self.assertEqual(self.library.artwork(self.future['id']),self.future)
    def test_disable_rollback_new_candidate_and_reapproval_keep_history_monotonic(self):
        plan=self.store.rule_version_plan(self.rule['id'],'DISABLE');self.assertTrue(plan['impact_complete']);self.assertIn(self.future['id'],{r['work_id'] for r in plan['matches']});disabled=self.store.apply_rule_version(plan,'Reviewer','disable false noise',True);self.assertEqual(disabled['state'],'DISABLED');self.assertEqual(self.state(self.future),'INCLUDED')
        plan=self.store.rule_version_plan(self.rule['id'],'ROLLBACK',2);restored=self.store.apply_rule_version(plan,'Reviewer','restore exact prior configuration',True);self.assertEqual(restored['state'],'PENDING');self.assertGreater(restored['revision'],disabled['revision']);self.assertEqual(self.state(self.future),'INCLUDED');activate(self.store,restored);self.assertEqual(self.state(self.future),'EXCLUDED_RULE');self.assertEqual(len(self.store.history('RULE',self.rule['id'])),5)
    def test_change_from_current_manual_source_has_exact_preview_and_pending_activation(self):
        _,newwork,_=pending_rule(self.store,self.root,'new.svg','已審核');facts=self.store.facts(newwork['id']);zone=relative_region(newwork,next(o for o in facts['observations'] if o['id']=='note'));counters=[{'work_id':newwork['id'],'observation_id':'observation-0'}];proposal,_=self.store.replacement_rule(newwork['id'],'note',counters,zone,'NONE','Reviewer','EXCLUDE');plan=self.store.rule_version_plan(self.rule['id'],'CHANGE',replacement=proposal)
        kwargs=dict(rule_id=self.rule['id'],work_id=newwork['id'],observation_id='note',counterexamples=counters,zone=zone,normalization='NONE',expected_rule_revision=self.rule['revision'],expected_facts_revision=facts['revision'],expected_epoch=self.store.epoch,actor='Reviewer',reason='new observed literal',approved=True)
        with self.assertRaises(ValueError):self.store.change_rule_candidate(**kwargs,expected_plan_digest='forged')
        changed=self.store.change_rule_candidate(**kwargs,expected_plan_digest=plan['digest']);self.assertEqual(changed['literal'],'已審核');self.assertEqual(changed['state'],'PENDING');self.assertEqual(self.state(self.future),'INCLUDED');self.assertEqual(self.store.history('RULE',changed['id'])[0]['before']['literal'],'已校稿')
    def test_exact_sample_dependency_invalidation_no_other_sample_or_source_changed(self):
        with self.store.transaction():
            affected=self.store._write('SAMPLE','dependent',{'state':'APPROVED','rule_dependencies':[{'id':self.rule['id'],'revision':2}]},0,'test_fixture');other=self.store._write('SAMPLE','unrelated',{'state':'APPROVED','rule_dependencies':[]},0,'test_fixture')
        plan=self.store.rule_version_plan(self.rule['id'],'DISABLE');self.assertEqual(plan['sample_ids'],['dependent']);self.assertFalse(plan['existing_models_decontaminated']);self.store.apply_rule_version(plan,'Reviewer','disable',True);self.assertEqual(len(self.store.get('SAMPLE',affected['id'])['invalidations']),1);self.assertEqual(self.store.get('SAMPLE',other['id']),other);self.assertEqual(self.library.artwork(self.future['id']),self.future)
    def test_stale_plan_tampered_after_and_late_audit_rollback_do_not_partial_apply(self):
        plan=self.store.rule_version_plan(self.rule['id'],'DISABLE');before=copy.deepcopy(self.store.get('RULE',self.rule['id']));hits=self.store.records('HIT');epoch=self.store.epoch;event=self.library.event
        def late(entity,action):
            event(entity,action)
            if action=='training_noise_hit_recorded':raise RuntimeError('late refreshed hit audit')
        with patch.object(self.library,'event',side_effect=late),self.assertRaises(RuntimeError):self.store.apply_rule_version(plan,'Reviewer','disable',True)
        self.assertEqual(self.store.get('RULE',self.rule['id']),before);self.assertEqual(self.store.records('HIT'),hits);self.assertEqual(self.store.epoch,epoch)
        forged=copy.deepcopy(plan);forged['after']['literal']='malicious';saved=self.store.apply_rule_version(forged,'Reviewer','recomputed',True);self.assertEqual(saved['literal'],'已校稿')
        with self.assertRaises(ValueError):self.store.apply_rule_version(plan,'Reviewer','stale',True)
    def test_whitelist_requires_noncontradictory_real_refs_and_source_freshness(self):
        with self.assertRaises(ValueError):self.store.propose_whitelist(self.future['id'],'note',[{'work_id':self.work['id'],'observation_id':'note'}],relative_region(self.future,next(o for o in self.facts['observations'] if o['id']=='note')),'NONE',self.facts['revision'],self.store.epoch,'Reviewer',True)
        Path(self.future_source['original_path']).write_text('changed')
        with self.assertRaises(ValueError):self.white()


class NoiseRecoveryGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close);self.store=TrainingStore(self.window.library);self.source,self.work,self.rule=pending_rule(self.store,self.root);self.rule=activate(self.store,self.rule);_,self.future=source_work(self.window.library,self.root,'future.svg');self.facts=confirmed(self.store,self.future);self.d=TrainingQualityDialog(self.window);self.addCleanup(self.d.close);self.d.show();APP.processEvents()
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;dispose_main_window(self.window)
    def test_actual_keep_whitelist_approve_and_disabled_rollback_controls(self):
        hits=self.d.hits_panel;self.d.tabs.setCurrentWidget(hits);hits.search.setText(self.future['id']+' 已校稿');hits.table.selectRow(0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(hits.keep_button,Qt.LeftButton)
        self.assertEqual(hits.rows[0]['current']['state'],'KEPT_LOCAL')
        wizard=NoiseAuthoringDialog(self.store,self.future['id'],'note','Reviewer',self.d,action='KEEP');self.addCleanup(wizard.close);wizard.show();wizard.table.selectRow(0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(wizard.save_button,Qt.LeftButton)
        self.assertEqual(wizard.saved_rule['action'],'KEEP');self.assertEqual(wizard.saved_rule['state'],'PENDING')
        rules=self.d.rules_panel;self.d.tabs.setCurrentWidget(rules);rules.actor.setText('Reviewer');rules.reason.setText('exact reviewed recovery');rules.reload();rules.table.selectRow(next(i for i,r in enumerate(rules.rows) if r['id']==self.rule['id']))
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(rules.disable_button,Qt.LeftButton)
        self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'DISABLED');rules.reload();rules.table.selectRow(next(i for i,r in enumerate(rules.rows) if r['id']==self.rule['id']))
        with patch.object(QInputDialog,'getInt',return_value=(2,True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(rules.rollback_button,Qt.LeftButton)
        self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'PENDING');self.assertTrue(rules.rollback_button.isEnabled())
    def test_actual_changed_candidate_preview_and_cancel_source_epoch_stale(self):
        wizard=NoiseAuthoringDialog(self.store,self.future['id'],'note','Reviewer',self.d,replace_rule_id=self.rule['id'],reason='version correction');self.addCleanup(wizard.close);wizard.show();wizard.table.selectRow(0);wizard.preview();self.assertTrue(wizard.change_plan);self.assertIn('version_impact',wizard.details.toPlainText())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):QTest.mouseClick(wizard.save_button,Qt.LeftButton)
        self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'ACTIVE')
        def stale(*args):self.store.local_keep(self.future['id'],['note'],0,self.facts['revision'],True);return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=stale):QTest.mouseClick(wizard.save_button,Qt.LeftButton)
        self.assertIsNone(wizard.saved_rule);self.assertTrue(wizard.save_button.isEnabled());self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'ACTIVE')
