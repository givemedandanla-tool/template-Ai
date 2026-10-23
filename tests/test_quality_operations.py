import copy,json,hashlib,time
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from template_ai.gui import MainWindow
from template_ai.training_store import TrainingStore
from template_ai.source_scan import register_root,scan_files,save_scan
from template_ai.source_scan_dialog import SourceScanDialog
from template_ai.quality_evaluation import evaluation_plan,save_evaluation,compare_evaluations,create_repair,rollback_gate,recheck_plan,start_recheck
from template_ai.quality_evaluation_panel import EvaluationPanel,RecheckPanel
from training_fixture import source_work,observations
from test_noise_authoring import confirmed
from test_trusted_samples import admitted
from test_dataset_learning import frozen
from test_rule_review import pending_rule
from test_noise_hits import activate
APP=QApplication.instance() or QApplication([])
VERSIONS=dict(model='synthetic-model-1',parser='synthetic-parser-1',ocr='synthetic-ocr-1',rules='synthetic-rules-1')

class QualityOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.w=MainWindow(self.root/'data');self.addCleanup(self.w.library.db.close);self.store=TrainingStore(self.w.library);self.source,self.work=source_work(self.w.library,self.root);confirmed(self.store,self.work);self.sample=admitted(self.store,self.work);self.dataset=frozen(self.store,[self.sample],'HOLDOUT')
        from runtime_fixture import controlled_resources
        controlled_resources(self.w)
        self.predictions=[{'sample_id':self.sample['id'],'slot_id':s['id'],'kind':s['kind'],'owner':s['owner']} for s in self.sample['label_slots']]
    def evaluate(self,predictions=None,versions=None):
        p=evaluation_plan(self.store,self.dataset['id'],versions or VERSIONS,self.predictions if predictions is None else predictions);return save_evaluation(self.store,p,'Synthetic Reviewer',True)
    def test_fixed_holdout_confusion_denominators_zero_classes_unknown_and_critical_owners(self):
        predictions=copy.deepcopy(self.predictions);predictions[0]['kind']='phone';predictions[1]['owner']='p2';predictions.pop();predictions.append({'sample_id':self.sample['id'],'slot_id':'extra-box','kind':'email','owner':'p1'})
        p=evaluation_plan(self.store,self.dataset['id'],VERSIONS,predictions);self.assertEqual(p['gold_count'],4);self.assertEqual(p['predicted_count'],4);self.assertEqual(p['metrics']['name']['fn'],1);self.assertEqual(p['metrics']['phone']['fp'],1);self.assertEqual(p['metrics']['email']['fn'],1);self.assertEqual(p['metrics']['email']['fp'],1);self.assertEqual(p['critical_owner_errors'],1);self.assertEqual(p['gate'],'FAILED_CRITICAL');self.assertIsNone(p['metrics']['line']['recall']);self.assertFalse(p['automatic_recommendation_allowed'])
        good=evaluation_plan(self.store,self.dataset['id'],VERSIONS,self.predictions);self.assertEqual(good['gate'],'EVIDENCE_INSUFFICIENT');self.assertEqual(good['metrics']['name']['recall'],1);self.assertEqual(good['visual_consistency'],'NOT_EVALUATED')
    def test_wrong_role_duplicate_prediction_stale_sample_and_caller_after_rejected(self):
        with self.assertRaises(ValueError):evaluation_plan(self.store,self.dataset['id'],VERSIONS,self.predictions+[self.predictions[0]])
        p=evaluation_plan(self.store,self.dataset['id'],VERSIONS,self.predictions);forged=copy.deepcopy(p);forged['gate']='PASS'
        with self.assertRaises(ValueError):save_evaluation(self.store,forged,'Reviewer',True)
        source,work=source_work(self.w.library,self.root,'train.svg',note_text='independent train');confirmed(self.store,work);s=admitted(self.store,work);train=frozen(self.store,[s],'TRAIN')
        with self.assertRaises(ValueError):evaluation_plan(self.store,train['id'],VERSIONS,[])
        transition=self.store.sample_transition_plan(self.sample['id'],'REVOKE');self.store.transition_sample(transition,'Reviewer','rights revoked',True)
        with self.assertRaises(ValueError):save_evaluation(self.store,p,'Reviewer',True)
    def test_fair_AB_repair_isolation_exposed_holdout_and_two_bad_versions_never_safe(self):
        bad=copy.deepcopy(self.predictions);bad[0]['kind']='phone';a=self.evaluate(bad);b=self.evaluate(versions={**VERSIONS,'model':'synthetic-model-2'});comparison=compare_evaluations(self.store,a['id'],b['id']);self.assertEqual(comparison['failure_case_delta'],-1);self.assertFalse(comparison['quality_pass']);self.assertFalse(rollback_gate(self.store,a['id'],b['id'])['allowed'])
        before=self.w.library.templates();repair=create_repair(self.store,a['id'],'Semantic classifier hypothesis','candidate-model-3','Reviewer',True);self.assertEqual(repair['state'],'ISOLATED_PENDING_REGRESSION_AND_NEW_HOLDOUT');self.assertFalse(repair['can_activate']);self.assertEqual(self.w.library.templates(),before);self.assertTrue(self.store.get('HOLDOUT_EXPOSED',self.dataset['id'])['requires_new_independent_holdout']);self.assertTrue(evaluation_plan(self.store,self.dataset['id'],VERSIONS,self.predictions)['holdout_exposed_for_repair'])
        with self.assertRaises(ValueError):create_repair(self.store,b['id'],'No actual failure','candidate4','Reviewer',True)
    def test_evaluation_and_repair_late_audit_rollback_no_partial_trust_or_exposure(self):
        p=evaluation_plan(self.store,self.dataset['id'],VERSIONS,[])
        with patch.object(self.w.library,'event',side_effect=RuntimeError('late audit')),self.assertRaises(RuntimeError):save_evaluation(self.store,p,'Reviewer',True)
        self.assertEqual(self.store.count('EVALUATION'),0);e=self.evaluate([]);real=self.w.library.event
        def late(entity,action):
            real(entity,action)
            if action=='training_quality_repair_proposed':raise RuntimeError('late repair audit')
        with patch.object(self.w.library,'event',side_effect=late),self.assertRaises(RuntimeError):create_repair(self.store,e['id'],'hypothesis','candidate-model-3','Reviewer',True)
        self.assertEqual(self.store.count('QUALITY_REPAIR'),0);self.assertIsNone(self.store.get('HOLDOUT_EXPOSED',self.dataset['id']))
    def rule_sample(self):
        source,work,rule=pending_rule(self.store,self.root,'rule-seed.svg','RecheckSyntheticNote');rule=activate(self.store,rule);s,w=source_work(self.w.library,self.root,'ruled-future.svg',note_text='RecheckSyntheticNote');obs=observations(w);next(o for o in obs if o['id']=='note')['text']='RecheckSyntheticNote';facts=self.store.save_facts(w['id'],obs,0,w['revision']);self.store.confirm_facts(w['id'],[o['id'] for o in obs],facts['revision'],facts['pins'],self.store.source_proof(w['id']),'Reviewer',True);sample=admitted(self.store,w);return rule,sample
    def test_major_recheck_exact_historical_rule_dependencies_atomic_quarantine_and_gate(self):
        rule,sample=self.rule_sample();ds=frozen(self.store,[sample],'TRAIN','historical training');p=recheck_plan(self.store,rule['id']);self.assertEqual(p['direct_total'],1);self.assertTrue(p['complete']);old=copy.deepcopy(sample);case=start_recheck(self.store,p,[sample['id']],'Confirmed severe rule counterexample','Reviewer',True)
        self.assertEqual(case['state'],'REVIEW_REQUIRED');self.assertFalse(case['completed']);self.assertEqual(self.store.sample_state(sample['id']),'QUARANTINED');self.assertEqual(self.store.history('SAMPLE',sample['id'])[-1]['after']['state'],'APPROVED');self.assertEqual(self.store.sample_state(self.sample['id']),'APPROVED');self.assertEqual(self.w.library.artwork(sample['work_id'])['payload']['slots'],old['label_slots'])
        with self.assertRaises(ValueError):self.store.geometry_learning_plan(ds['id'],sample['id'],'not allowed')
    def test_major_recheck_stale_plan_and_late_audit_rollback_entire_scope(self):
        rule,sample=self.rule_sample();p=recheck_plan(self.store,rule['id']);real=self.w.library.event
        def late(entity,action):
            real(entity,action)
            if action=='training_major_recheck_started':raise RuntimeError('case audit failed')
        with patch.object(self.w.library,'event',side_effect=late),self.assertRaises(RuntimeError):start_recheck(self.store,p,[sample['id']],'Severe issue','Reviewer',True)
        self.assertEqual(self.store.get('SAMPLE',sample['id']),sample);self.assertEqual(self.store.count('MAJOR_RECHECK'),0)
        self.store.transition_sample(self.store.sample_transition_plan(sample['id'],'QUARANTINE'),'Reviewer','earlier action',True)
        with self.assertRaises(ValueError):start_recheck(self.store,p,[sample['id']],'stale','Reviewer',True)
    def test_scan_two_actual_hashes_incremental_alias_and_changed_readonly_offline(self):
        directory=self.root/'scan';directory.mkdir();a=directory/'001.svg';a.write_text('<svg>synthetic</svg>');b=directory/'002.svg';b.write_bytes(a.read_bytes());root=register_root(self.store,directory);before={p.name:p.read_bytes() for p in directory.iterdir()};result=scan_files(root,{},stable_wait=.05);self.assertEqual({r['state'] for r in result['entries']},{'DUPLICATE_ALIAS_KEEP_IDENTITY'});self.assertFalse(result['source_imported']);root=save_scan(self.store,root,result);again=scan_files(root,{},stable_wait=.05);self.assertEqual({r['state'] for r in again['entries']},{'UNCHANGED'});a.write_text('changed source');changed=scan_files(root,{},stable_wait=.05);self.assertEqual(next(r for r in changed['entries'] if r['path']==str(a))['state'],'CONTENT_CHANGED_REVIEW_REQUIRED');a.write_bytes(before[a.name]);self.assertEqual({p.name:p.read_bytes() for p in directory.iterdir()},before)
        directory.rename(self.root/'offline');offline=scan_files(root,{});r=save_scan(self.store,root,offline);self.assertEqual(r['last_scan'],root['last_scan']);self.assertFalse(offline['complete']);self.assertEqual(offline['state'],'ROOT_OFFLINE');self.assertEqual(self.w.library.artwork(self.work['id']),self.work)
    def test_scan_changing_bytes_are_waiting_not_imported_and_stale_root_save_rejected(self):
        directory=self.root/'scan';directory.mkdir();path=directory/'changing.svg';path.write_text('first');root=register_root(self.store,directory);from template_ai.source_scan import hash_source as real
        calls=0
        def mutate(p,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2:path.write_text('second')
            return real(p,**kwargs)
        with patch('template_ai.source_scan.hash_source',side_effect=mutate):result=scan_files(root,{},stable_wait=.05)
        self.assertEqual(result['entries'][0]['state'],'WAIT_STABLE');save_scan(self.store,root,result)
        with self.assertRaises(ValueError):save_scan(self.store,root,result)
    def test_actual_scan_worker_and_quality_panels_cancel_save_repair_and_recheck(self):
        directory=self.root/'scan';directory.mkdir();(directory/'input.svg').write_text('synthetic');root=register_root(self.store,directory);d=SourceScanDialog(self.w);self.addCleanup(d.deleteLater);d.roots.setCurrentIndex(d.roots.findData(root['id']));d.scan();end=time.monotonic()+5
        while d.running and time.monotonic()<end:APP.processEvents();QTest.qWait(10)
        self.assertFalse(d.running);self.assertFalse(self.w.busy);self.assertTrue(d.scan_button.isEnabled());self.assertIn('新來源候選',d.details.toPlainText())
        panel=EvaluationPanel(self.w);self.addCleanup(panel.deleteLater);panel.predictions.setPlainText('[]');panel.preview();self.assertIsNotNone(panel.plan)
        with patch('template_ai.quality_evaluation_panel.QMessageBox.question',return_value=QMessageBox.No):panel.save()
        self.assertEqual(self.store.count('EVALUATION'),0)
        with patch('template_ai.quality_evaluation_panel.QMessageBox.question',return_value=QMessageBox.Yes):panel.save()
        self.assertEqual(self.store.count('EVALUATION'),1)
        with patch('template_ai.quality_evaluation_panel.QInputDialog.getText',side_effect=[('synthetic hypothesis',True),('candidate-new',True)]),patch('template_ai.quality_evaluation_panel.QMessageBox.question',return_value=QMessageBox.Yes):panel.repair()
        self.assertEqual(self.store.count('QUALITY_REPAIR'),1);self.assertIn('holdout',panel.status.text())
        rule,sample=self.rule_sample();recheck=RecheckPanel(self.w);self.addCleanup(recheck.deleteLater);recheck.rules.setCurrentIndex(recheck.rules.findData(rule['id']));recheck.preview();recheck.table.item(0,0).setCheckState(Qt.Checked);recheck.reason.setText('Actual severe synthetic counterexample')
        with patch('template_ai.quality_evaluation_panel.QMessageBox.question',return_value=QMessageBox.No):recheck.start()
        self.assertEqual(self.store.sample_state(sample['id']),'APPROVED')
        with patch('template_ai.quality_evaluation_panel.QMessageBox.question',return_value=QMessageBox.Yes):recheck.start()
        self.assertEqual(self.store.sample_state(sample['id']),'QUARANTINED');self.assertIn('REVIEW_REQUIRED',recheck.status.text())

    def test_resource_pause_keeps_scan_pending_and_resume_returns_actual_result(self):
        from dataclasses import replace
        from gui_wait import wait_for_gui
        directory=self.root/'pressure-scan';directory.mkdir();(directory/'input.svg').write_text('owned scan candidate')
        root=register_root(self.store,directory);dialog=SourceScanDialog(self.w);self.addCleanup(dialog.deleteLater)
        dialog.roots.setCurrentIndex(dialog.roots.findData(root['id']))
        snapshot=self.w.runtime.monitor.snapshot
        self.w.runtime.monitor.snapshot=lambda:replace(snapshot(),cpu_percent=100)
        dialog.scan();self.w.source_watch.debounce.stop();self.w.source_watch.dispatch()
        self.assertTrue(dialog.running);self.assertFalse(dialog.scan_button.isEnabled())
        self.assertIn(root['id'],self.w.source_watch.pending);self.assertFalse(self.w.source_watch.running)
        self.assertIsNone(self.store.get('SCAN_ROOT',root['id'])['last_success'])
        self.assertEqual(self.store.count('SCAN_CANDIDATE'),0);self.assertIn('CPU_PRESSURE',dialog.status.text())
        self.w.runtime.monitor.snapshot=snapshot
        self.assertTrue(wait_for_gui(lambda:not dialog.running,5),'resource recovery did not finish real scan')
        self.assertTrue(dialog.scan_button.isEnabled());self.assertFalse(self.w.busy)
        self.assertIsNotNone(self.store.get('SCAN_ROOT',root['id'])['last_success'])
        self.assertEqual(self.store.count('SCAN_CANDIDATE'),1);self.assertIn('新來源候選',dialog.details.toPlainText())
