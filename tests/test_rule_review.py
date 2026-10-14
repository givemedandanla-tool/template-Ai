import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.noise import relative_region
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work, observations
APP=QApplication.instance() or QApplication([])


def pending_rule(store,root,name='example.svg',literal='已校稿',normalization='NONE'):
    source,work=source_work(store.library,root,name,note_text=literal);obs=observations(work);next(o for o in obs if o['id']=='note')['text']=literal
    facts=store.save_facts(work['id'],obs,0,1);facts=store.confirm_facts(work['id'],[o['id'] for o in obs],facts['revision'],facts['pins'],store.source_proof(work['id']),'Synthetic Reviewer',True)
    rule=store.propose_noise_rule(work['id'],'note',[{'work_id':work['id'],'observation_id':'observation-0'}],relative_region(work,next(o for o in obs if o['id']=='note')),normalization,facts['revision'],store.epoch,'Synthetic Reviewer',True,normalization=='NFC')
    return source,work,rule


class RuleReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close);self.store=TrainingStore(self.library);self.source,self.work,self.rule=pending_rule(self.store,self.root)
    def test_known_impact_low_scope_and_explicit_approval_immutable_history(self):
        before=self.library.artwork(self.work['id']);plan=self.store.rule_review_plan([self.rule['id']]);self.assertTrue(plan['batch_eligible']);row=plan['rows'][0];self.assertEqual(row['risk'],'LOW');self.assertEqual(row['affected_work_ids'],[self.work['id']]);self.assertFalse(row['templates_rewritten']);self.assertEqual(row['customer_identity'],'UNKNOWN')
        with self.assertRaises(ValueError):self.store.review_rules(plan,'APPROVE','Reviewer','checked')
        active=self.store.review_rules(plan,'APPROVE','Reviewer','checked exact source',True)[0];self.assertEqual(active['state'],'ACTIVE');self.assertEqual(active['revision'],2);self.assertEqual(self.store.history('RULE',active['id'])[0]['before']['state'],'PENDING');self.assertEqual(self.library.artwork(self.work['id']),before)
    def test_same_scope_low_batch_and_high_requires_individual_details(self):
        _,_,other=pending_rule(self.store,self.root,'second.svg','已審核');plan=self.store.rule_review_plan([self.rule['id'],other['id']]);self.assertTrue(plan['batch_eligible']);self.assertEqual(len(self.store.review_rules(plan,'APPROVE','Reviewer','same validated scope',True)),2)
        _,_,high=pending_rule(self.store,self.root,'high.svg','é','NFC');plan=self.store.rule_review_plan([high['id']]);self.assertEqual(plan['rows'][0]['risk'],'HIGH')
        forged=copy.deepcopy(plan);forged['rows'][0]['risk']='LOW';forged['batch_eligible']=True
        with self.assertRaises(ValueError):self.store.review_rules(forged,'APPROVE','Reviewer','forged caller after',True)
        self.assertEqual(self.store.review_rules(plan,'APPROVE','Reviewer','NFC manually compared',True,True)[0]['state'],'ACTIVE')
    def test_cross_scope_and_high_batch_cannot_bypass(self):
        _,_,other=pending_rule(self.store,self.root,'high.svg','é','NFC');plan=self.store.rule_review_plan([self.rule['id'],other['id']]);self.assertFalse(plan['batch_eligible'])
        with self.assertRaises(ValueError):self.store.review_rules(plan,'APPROVE','Reviewer','wrong batch',True,True)
        self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'PENDING')
    def test_stale_source_missing_evidence_and_bounded_impact_block_approval(self):
        plan=self.store.rule_review_plan([self.rule['id']]);Path(self.source['original_path']).write_text('changed');self.assertEqual(self.store.inspect_rule(self.rule['id'])['risk'],'BLOCK')
        with self.assertRaises(ValueError):self.store.review_rules(plan,'APPROVE','Reviewer','stale',True)
        current=self.store.rule_review_plan([self.rule['id']]);self.assertEqual(self.store.review_rules(current,'DEFER','Reviewer','missing source',True)[0]['state'],'DEFERRED')
        with patch.object(self.store,'scan_observations',return_value=([],False)):self.assertEqual(self.store.inspect_rule(self.rule['id'])['risk'],'BLOCK')
    def test_batch_late_audit_failure_rolls_back_all_and_CAS(self):
        _,_,other=pending_rule(self.store,self.root,'second.svg','已審核');plan=self.store.rule_review_plan([self.rule['id'],other['id']]);epoch=self.store.epoch;original=self.library.event;calls=0
        def late(entity,action):
            nonlocal calls
            original(entity,action)
            if action=='training_rule_approve':
                calls+=1
                if calls==2:raise RuntimeError('late second audit')
        with patch.object(self.library,'event',side_effect=late),self.assertRaises(RuntimeError):self.store.review_rules(plan,'APPROVE','Reviewer','checked',True)
        self.assertEqual(self.store.epoch,epoch);self.assertTrue(all(self.store.get('RULE',rid)['state']=='PENDING' for rid in plan['ids']));self.assertEqual(len(self.store.history('RULE',self.rule['id'])),1)
        self.store.review_rules(plan,'DEFER','Reviewer','defer',True)
        with self.assertRaises(ValueError):self.store.review_rules(plan,'REJECT','Reviewer','stale revision',True)
    def test_reject_defer_and_reopen_preserve_current_versions(self):
        plan=self.store.rule_review_plan([self.rule['id']]);deferred=self.store.review_rules(plan,'DEFER','Reviewer','needs check',True)[0];plan=self.store.rule_review_plan([deferred['id']]);rejected=self.store.review_rules(plan,'REJECT','Reviewer','not suitable',True)[0]
        other=Library(self.library.root)
        try:self.assertEqual(TrainingStore(other).get('RULE',rejected['id']),rejected)
        finally:other.db.close()


class RuleReviewGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close);self.store=TrainingStore(self.window.library);self.source,self.work,self.rule=pending_rule(self.store,self.root);self.d=TrainingQualityDialog(self.window);self.p=self.d.rules_panel;self.addCleanup(self.d.close);self.d.show();self.d.tabs.setCurrentWidget(self.p);self.p.actor.setText('Synthetic Reviewer');self.p.reason.setText('source and examples checked');self.p.table.selectRow(0);APP.processEvents()
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;self.window.close()
    def test_actual_filter_details_cancel_approve_and_history(self):
        self.assertEqual(self.p.rows[0]['risk'],'LOW');self.assertIn('positive_examples',self.p.details.toPlainText())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):QTest.mouseClick(self.p.approve_button,Qt.LeftButton)
        self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'PENDING')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.approve_button,Qt.LeftButton)
        self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'ACTIVE');self.p.state.setCurrentText('PENDING');self.assertEqual(self.p.table.rowCount(),0);self.p.state.setCurrentText('ACTIVE');self.assertEqual(self.p.table.rowCount(),1);self.p.search.setText('no-match');self.assertEqual(self.p.table.rowCount(),0)
    def test_stale_confirm_and_backend_failure_recover_controls(self):
        def stale(*args):self.store.review_rules(self.store.rule_review_plan([self.rule['id']]),'DEFER','Reviewer','other session',True);return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=stale):QTest.mouseClick(self.p.approve_button,Qt.LeftButton)
        self.assertIn('已變更',self.p.status.text());self.assertTrue(self.p.approve_button.isEnabled());self.assertEqual(self.store.get('RULE',self.rule['id'])['state'],'DEFERRED')
        with patch.object(self.p.store,'inspect_rule',side_effect=RuntimeError('forced failure')):self.p.reload()
        self.assertEqual(self.p.table.rowCount(),0);self.assertTrue(self.p.reload_button.isEnabled());self.p.reload();self.assertEqual(self.p.table.rowCount(),1)
