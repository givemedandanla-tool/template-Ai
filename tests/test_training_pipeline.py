import copy
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.training_pipeline import run_training_job,LIVE_OWNERS
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work,observations
from test_trusted_samples import admitted
from test_dataset_learning import frozen
APP=QApplication.instance() or QApplication([])


def pipeline_samples(store,root,count=2):
    result=[];works=[]
    for i in range(count):
        literal='已校稿 '+str(i);source,work=source_work(store.library,root,'pipeline-'+str(i)+'.svg',note_text=literal);rows=observations(work);next(o for o in rows if o['id']=='note')['text']=literal;facts=store.save_facts(work['id'],rows,0,1);store.confirm_facts(work['id'],[o['id'] for o in rows],facts['revision'],facts['pins'],store.source_proof(work['id']),'Synthetic Reviewer',True);result.append(admitted(store,work));works.append(work)
    return result,works


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close);self.store=TrainingStore(self.library);self.samples,self.works=pipeline_samples(self.store,self.root);self.dataset=frozen(self.store,self.samples)
    def job(self):return self.store.create_training_job(self.store.training_job_plan(self.dataset['id'],[s['id'] for s in self.samples],'Pipeline Draft'),'Synthetic Reviewer',True)
    def claim(self,job):
        result=self.store.claim_training_job(job['id'],job['revision'],True);self.addCleanup(lambda:LIVE_OWNERS.discard(result['owner']['token']));return result
    def test_real_worker_connection_durable_success_exact_use_source_unchanged(self):
        job=self.claim(self.job());updates=[];result=run_training_job(self.library.root,job['id'],job['owner']['token'],progress=updates.append);self.assertEqual(result['phase'],'COMPLETED');self.assertTrue(all(i['state']=='SUCCESS' for i in result['items']));self.assertEqual(len(self.library.templates()),2);self.assertTrue(all(t.state=='draft' for t in self.library.templates()));self.assertEqual(self.store.count('USE'),2);self.assertEqual([self.library.artwork(w['id']) for w in self.works],self.works);self.assertEqual([len([i for i in u['items'] if i['state']=='SUCCESS']) for u in updates],[1,2,2]);self.assertFalse(self.store.get('WORKER','geometry-worker')['active'])
        with self.assertRaises(ValueError):self.store.claim_training_job(result['id'],result['revision'],True)
    def test_cooperative_cancel_after_actual_item_then_reopen_resume_no_success_rerun(self):
        job=self.claim(self.job());cancel=threading.Event()
        def progress(result):
            if any(i['state']=='SUCCESS' for i in result['items']):cancel.set()
        stopped=run_training_job(self.library.root,job['id'],job['owner']['token'],cancel,progress);self.assertEqual(stopped['phase'],'CANCELLED');self.assertEqual(sum(i['state']=='SUCCESS' for i in stopped['items']),1);first=next(i['template_id'] for i in stopped['items'] if i['state']=='SUCCESS');other=Library(self.library.root)
        try:
            store=TrainingStore(other);current=store.get('JOB',job['id']);resumed=store.claim_training_job(job['id'],current['revision'],True);done=run_training_job(other.root,job['id'],resumed['owner']['token']);self.assertEqual(done['phase'],'COMPLETED');self.assertEqual(len(other.templates()),2);self.assertIn(first,[i['template_id'] for i in done['items']]);self.assertTrue(all(i['attempts']==1 for i in done['items']))
        finally:other.db.close()
    def test_source_failure_isolated_other_valid_item_completes_and_failed_retry_explicit(self):
        job=self.claim(self.job());bad_id=job['items'][0]['sample_id'];work=self.store.get('SAMPLE',bad_id)['work_id'];source=self.library.source(self.library.artwork(work)['source_id']);Path(source['current_path']).write_text('changed')
        result=run_training_job(self.library.root,job['id'],job['owner']['token']);self.assertEqual(result['phase'],'COMPLETED_WITH_EXCEPTIONS');self.assertEqual([i['state'] for i in result['items']],['FAILED','SUCCESS']);self.assertEqual(len(self.library.templates()),1)
        with self.assertRaises(ValueError):self.store.claim_training_job(result['id'],result['revision'],True)
        retry=self.store.claim_training_job(result['id'],result['revision'],True,True);second=run_training_job(self.library.root,result['id'],retry['owner']['token']);self.assertEqual(second['items'][1]['attempts'],1);self.assertEqual(second['items'][0]['attempts'],2);self.assertEqual(len(self.library.templates()),1)
    def test_live_owner_cross_window_double_claim_CAS_and_stale_worker_rejected(self):
        original=self.job();claimed=self.claim(original);other=Library(self.library.root)
        try:
            store=TrainingStore(other)
            with self.assertRaises(ValueError):store.claim_training_job(claimed['id'],claimed['revision'],True)
            with self.assertRaises(ValueError):store.claim_training_job(original['id'],original['revision'],True)
            with self.assertRaises(ValueError):store.request_training_cancel(claimed['id'],'wrong owner')
        finally:other.db.close()
        self.store.request_training_cancel(claimed['id'],claimed['owner']['token']);cancelled=run_training_job(self.library.root,claimed['id'],claimed['owner']['token']);self.assertEqual(cancelled['phase'],'CANCELLED');self.assertEqual(self.library.templates(),[])
    def test_dead_owner_is_interrupted_manual_resume_only_preserves_scope(self):
        job=self.claim(self.job());LIVE_OWNERS.discard(job['owner']['token']);self.assertEqual(self.store.training_job_state(job['id']),'INTERRUPTED')
        with self.assertRaises(ValueError):self.store.claim_training_job(job['id'],job['revision'])
        resumed=self.store.claim_training_job(job['id'],job['revision'],True);done=run_training_job(self.library.root,job['id'],resumed['owner']['token']);self.assertEqual(done['phase'],'COMPLETED')
        history=self.store.history('JOB',job['id']);self.assertEqual([h['revision'] for h in history],[6,5,4,3,2,1]);self.assertEqual([h['action'] for h in reversed(history)],['training_job_created','training_job_claimed','training_job_claimed','training_item_success','training_item_success','training_job_completed'])
    def test_late_item_audit_failure_rolls_back_template_USE_result_and_stops_system(self):
        job=self.claim(self.job())
        def hook(original):
            def event(entity,action):
                original(entity,action)
                if action=='training_training_item_success':raise RuntimeError('late atomic item audit failure')
            return event
        with self.assertRaises(RuntimeError):run_training_job(self.library.root,job['id'],job['owner']['token'],audit_hook=hook)
        failed=self.store.get('JOB',job['id']);self.assertEqual(failed['phase'],'FAILED_SYSTEM');self.assertTrue(all(i['state']=='READY' for i in failed['items']));self.assertEqual(self.library.templates(),[]);self.assertEqual(self.store.count('USE'),0);self.assertFalse(self.store.get('WORKER','geometry-worker')['active'])
    def test_existing_geometric_result_reused_no_duplicate_output_or_use(self):
        sample=self.samples[0];plan=self.store.geometry_learning_plan(self.dataset['id'],sample['id'],'Existing Draft');first=self.store.learn_dataset_sample(plan,self.store.source_proof(sample['work_id']),'Reviewer',True);job=self.claim(self.job());result=run_training_job(self.library.root,job['id'],job['owner']['token']);self.assertEqual(result['phase'],'COMPLETED');self.assertEqual(sum(i['state']=='REUSED' for i in result['items']),1);self.assertEqual(len(self.library.templates()),2);self.assertEqual(self.store.count('USE'),2);self.assertIn(first.id,[i['template_id'] for i in result['items']])
    def test_holdout_revoke_wrong_role_and_caller_after_do_not_train(self):
        plan=self.store.training_job_plan(self.dataset['id'],[s['id'] for s in self.samples],'Draft');forged=copy.deepcopy(plan);forged['items'][0]['sample_revision']=999;job=self.store.create_training_job(forged,'Reviewer',True);self.assertEqual(job['items'][0]['sample_revision'],1)
        self.store.transition_sample(self.store.sample_transition_plan(self.samples[0]['id'],'REVOKE'),'Reviewer','withdraw',True)
        with self.assertRaises(ValueError):self.store.create_training_job(plan,'Reviewer',True)
        self.assertEqual(self.library.templates(),[])
        _,holdout_work=source_work(self.library,self.root,'held.svg',note_text='保留集範例');obs=observations(holdout_work);next(o for o in obs if o['id']=='note')['text']='保留集範例';facts=self.store.save_facts(holdout_work['id'],obs,0,1);self.store.confirm_facts(holdout_work['id'],[o['id'] for o in obs],facts['revision'],facts['pins'],self.store.source_proof(holdout_work['id']),'Reviewer',True);held=admitted(self.store,holdout_work);held_dataset=frozen(self.store,[held],'HOLDOUT','held dataset')
        with self.assertRaises(ValueError):self.store.training_job_plan(held_dataset['id'],[held['id']],'forbidden holdout')


class PipelineGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close);self.store=TrainingStore(self.window.library);self.samples,self.works=pipeline_samples(self.store,self.root);self.dataset=frozen(self.store,self.samples);self.d=TrainingQualityDialog(self.window);self.addCleanup(self.d.close);self.p=self.d.queue_panel;self.d.show();self.d.tabs.setCurrentWidget(self.p);self.p.prefix.setText('Actual Queue Draft');self.p.actor.setText('Synthetic Reviewer')
        for i in range(self.p.items.rowCount()):self.p.items.item(i,0).setCheckState(Qt.Checked)
        APP.processEvents()
        from runtime_fixture import controlled_resources
        controlled_resources(self.window)
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;self.window.close()
    def wait(self):
        for _ in range(1000):
            APP.processEvents()
            if not self.p.running:return
            QTest.qWait(10)
        self.fail('bounded queue failed to finish')
    def test_actual_preflight_confirm_worker_progress_and_controls_restored(self):
        QTest.mouseClick(self.p.preview_button,Qt.LeftButton);self.assertIn('GEOMETRY_DRAFT_ONLY',self.p.details.toPlainText())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.create_button,Qt.LeftButton);self.wait()
        job=self.store.records('JOB')[0];self.assertEqual(job['phase'],'COMPLETED');self.assertEqual(len(self.window.library.templates()),2);self.assertIn('SUCCESS2',self.p.progress_label.text());self.assertTrue(self.p.create_button.isEnabled());self.assertFalse(self.window.busy);self.assertFalse(self.p.cancel_button.isEnabled());self.assertEqual([self.window.library.artwork(w['id']) for w in self.works],self.works)
    def test_actual_cancel_during_worker_then_resume_without_duplicate_success(self):
        entered=threading.Event();release=threading.Event();original=TrainingStore.source_proof
        def blocked(store,wid):entered.set();release.wait(3);return original(store,wid)
        with patch('template_ai.training_store.TrainingStore.source_proof',blocked),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            QTest.mouseClick(self.p.create_button,Qt.LeftButton)
            for _ in range(300):
                APP.processEvents()
                if entered.is_set():break
                QTest.qWait(10)
            self.assertTrue(entered.is_set());QTest.mouseClick(self.p.cancel_button,Qt.LeftButton);release.set();self.wait()
        cancelled=self.store.records('JOB')[0];self.assertEqual(cancelled['phase'],'CANCELLED');self.assertEqual(sum(i['state']=='SUCCESS' for i in cancelled['items']),1);self.p.reload();self.p.jobs_table.selectRow(0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.resume_button,Qt.LeftButton);self.wait()
        completed=self.store.get('JOB',cancelled['id']);self.assertEqual(completed['phase'],'COMPLETED');self.assertEqual(len(self.window.library.templates()),2);self.assertTrue(all(i['attempts']==1 for i in completed['items']))
    def test_actual_stale_confirmation_worker_error_and_close_guard_preserve_results(self):
        def changed(*args):self.store.transition_sample(self.store.sample_transition_plan(self.samples[0]['id'],'REVOKE'),'Reviewer','during confirm',True);return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=changed):QTest.mouseClick(self.p.create_button,Qt.LeftButton)
        self.assertEqual(self.store.count('JOB'),0);self.assertFalse(self.p.running);self.assertTrue(self.p.create_button.isEnabled())
        self.p.running=True;self.d.reject();self.assertTrue(self.d.isVisible());self.p.running=False
    def test_actual_worker_start_failure_is_interrupted_and_controls_recover_for_resume(self):
        with patch('template_ai.runtime_dispatch.run_training_job',side_effect=RuntimeError('worker start failed')),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.create_button,Qt.LeftButton);self.wait()
        job=self.store.records('JOB')[0];self.assertEqual(self.store.training_job_state(job['id']),'INTERRUPTED');self.assertIn('已停止',self.p.status.text());self.assertFalse(self.window.busy);self.assertTrue(self.p.resume_button.isEnabled());self.assertEqual(self.window.library.templates(),[])
        self.p.reload();self.p.jobs_table.selectRow(0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.resume_button,Qt.LeftButton);self.wait()
        self.assertEqual(self.store.get('JOB',job['id'])['phase'],'COMPLETED');self.assertEqual(len(self.window.library.templates()),2)
