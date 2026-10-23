"""Real original dispatcher submission/cancellation and source comparison on major page."""
import threading,unittest
from unittest.mock import patch
import test_major_review_gui as fixture
from gui_wait import wait_for_gui
from template_ai.quality_rechecks import blocked
from template_ai.quality_repair_dialog import QualityRepairDialog
from template_ai.runtime_worker import run_isolated
APP=fixture.APP


class MajorReviewJobGuiTests(unittest.TestCase):
    setUp=fixture.MajorReviewGuiTests.setUp
    dispose=fixture.MajorReviewGuiTests.dispose
    wait=fixture.MajorReviewGuiTests.wait
    def case(self):
        self.page.preview();self.wait();self.d.consent.setChecked(True);self.d.confirm();self.wait();self.assertIsNotNone(self.page.case);self.page.table.selectRow(0)
    def preview_job(self):
        self.page.preview_job();self.wait();self.assertIsNotNone(self.page.job_plan,self.d.status.text())
    def start(self):
        self.d.consent.setChecked(True);self.d.confirm();self.assertTrue(wait_for_gui(lambda:self.page.analysis_job is not None and not self.panel.loading,15));identity=self.page.analysis_job['id'];self.assertTrue(wait_for_gui(lambda:self.store.get('AUTO_JOB',identity)['phase'] in ('COMPLETED','COMPLETED_WITH_EXCEPTIONS','CANCELLED','FAILED_SYSTEM') and not self.w.busy,20));return self.store.get('AUTO_JOB',identity)
    def test_actual_original_fifo_submit_and_saved_old_new_analysis_never_auto_approve(self):
        self.case();self.preview_job();self.assertEqual(self.store.count('AUTO_JOB'),0);job=self.start();self.assertEqual(job['phase'],'COMPLETED');self.assertEqual(self.store.count('SEMANTIC_MODEL'),0);self.assertTrue(blocked(self.store,self.work['id']));self.page.load_case(0);self.wait();self.assertIn('待人工 1',self.page.counts.text());self.page.table.selectRow(0);self.page.show_analysis();self.wait();text=self.d.details.toPlainText();self.assertIn('原判定',text);self.assertIn('新分析',text);self.assertIn('未使用語意模型',text);self.assertIn('COMPLETED',self.page.analysis_jobs.currentText());self.assertFalse(self.page.case['completed'])
    def test_selection_changed_after_job_preview_does_not_create_or_queue_job(self):
        self.case();self.preview_job();self.page.table.clearSelection();self.d.consent.setChecked(True)
        with self.assertRaises(ValueError):self.d.confirm()
        self.assertEqual(self.store.count('AUTO_JOB'),0)
    def test_reopened_existing_case_can_preview_exact_jobs_without_an_issue_form(self):
        self.case();other=QualityRepairDialog(self.panel);self.addCleanup(other.deleteLater);page=other.major_review;other.actor.setText('Synthetic reconnect reviewer');other.reason.setText('Read back same case and exact selected work');page.list_cases(0);self.wait();page.load_case(0);self.wait();page.table.selectRow(0);page.preview_job();self.wait();self.assertIsNotNone(page.job_plan,other.status.text());self.assertIsNone(other.issue);self.assertEqual(self.store.count('AUTO_JOB'),0)
    def test_completed_job_explicit_resume_reads_same_result_without_new_request_or_training(self):
        self.case();self.preview_job();job=self.start();count=self.library.db.execute('SELECT count(*) FROM runtime_requests').fetchone()[0];self.page.list_jobs();self.wait();self.d.consent.setChecked(True);self.page.resume_job();self.wait();self.assertIn('已完成落盤',self.page.job_notice.text());self.assertEqual(self.library.db.execute('SELECT count(*) FROM runtime_requests').fetchone()[0],count);self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),1);self.assertEqual(self.store.count('SEMANTIC_MODEL'),0)
    def test_stale_job_from_another_case_cannot_cancel_its_actual_waiting_request(self):
        from template_ai.major_review_jobs import plan,create
        from template_ai.automatic_training import AutomaticTraining
        from template_ai.quality_rechecks import QualityRechecks
        from template_ai.quality_repairs import QualityRepairs
        self.case();dispatcher=self.w.execution_queue;dispatcher.timer.stop();case_a=self.page.case;auto=AutomaticTraining(self.library);job=create(auto,plan(self.library,case_a['id'],[self.work['id']]),'Synthetic reviewer','Exact waiting analysis A',True);request=dispatcher.queue.enqueue('AUTO_JOB',job['id'],'Synthetic reviewer',dispatcher.session,True);repairs=QualityRepairs(self.library);issue=repairs.create_source_issue(repairs.plan_source_issue(self.other_work['id'],'SOURCE_FACTS',self.other_work['id'],'Separate actual source evidence'),'Synthetic reviewer','Explicit separate source issue',True);service=QualityRechecks(self.library);case_b=service.confirm_source(service.source_plan(issue_id=issue['id'],category='OTHER_SOURCE',correct_example='Separate correct example',wrong_example='Separate observed error'),'Synthetic reviewer','Distinct second case',True);self.page.cases.addItem('B',case_b['id']);self.page.cases.setCurrentIndex(self.page.cases.count()-1);self.page.case=case_b;self.assertEqual(self.page.analysis_jobs.count(),0);self.page.analysis_jobs.addItem('stale A row',job['id'])
        with self.assertRaisesRegex(ValueError,'不屬於'):self.page.cancel_job()
        self.assertEqual(dispatcher.queue.get(request['id'])['state'],'WAITING');dispatcher.cancel(request['id']);self.assertEqual(dispatcher.queue.get(request['id'])['state'],'CANCELLED')
    def test_cancel_only_selected_actual_shared_request_keeps_case_quarantine(self):
        self.case();self.preview_job();started=threading.Event();release=threading.Event();original=run_isolated
        def hold(*args,**kwargs):started.set();release.wait(5);return original(*args,**kwargs)
        try:
            with patch('template_ai.runtime_dispatch.run_isolated',side_effect=hold):
                self.d.consent.setChecked(True);self.d.confirm();self.assertTrue(wait_for_gui(started.is_set,10));self.page.cancel_job();release.set();self.assertTrue(wait_for_gui(lambda:not self.w.busy and self.w.execution_queue.active is None and not self.panel.loading,15))
            job=self.store.get('AUTO_JOB',self.page.analysis_jobs.currentData());self.assertEqual(job['phase'],'CANCELLED');self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),0);self.assertTrue(blocked(self.store,self.work['id']))
        finally:release.set()

if __name__=='__main__':unittest.main()
