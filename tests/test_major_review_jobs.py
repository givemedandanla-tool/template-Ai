"""Actual original parser/AUTO_JOB ownership, FIFO, durable cancel/restart and isolation."""
import copy,json,os,subprocess,sys,threading,unittest
from pathlib import Path
import test_quality_source_review as fixture
from training_fixture import source_work
from template_ai.automatic_training import AutomaticTraining,run_automatic
from template_ai.major_review_jobs import plan,create
from template_ai.major_review_commands import execute
from template_ai.runtime_queue import RuntimeQueue
from template_ai.model import new_id
from template_ai.training_store import digest
from template_ai.quality_rechecks import blocked


class MajorReviewJobTests(unittest.TestCase):
    setUp=fixture.QualitySourceReviewTests.setUp
    source_plan=fixture.QualitySourceReviewTests.plan
    def make(self,twins=False,selected=None):
        if twins:self.twin_source,self.twin=source_work(self.library,self.root,'review-twin-job.svg')
        self.case=self.service.confirm_source(self.source_plan(),'Synthetic reviewer','Explicit source major scope',True);self.auto=AutomaticTraining(self.library);ids=selected or [self.work['id']]+([self.twin['id']] if twins else []);self.plan=plan(self.library,self.case['id'],ids);self.job=create(self.auto,self.plan,'Synthetic reviewer','Only original source reanalysis, no learning',True);return self.job
    def claim_run(self,job=None,**kwargs):
        job=job or self.job;current=self.auto.get(job['id']);claimed=self.auto.claim(current['id'],current['revision'],True,retry=True);return run_automatic(self.library.root,current['id'],claimed['owner']['token'],**kwargs)
    def test_real_original_parser_job_saves_comparison_and_keeps_business_data_and_quarantine(self):
        job=self.make();before=self.library.object_snapshot('ARTWORK',self.work['id']);result=self.claim_run();self.assertEqual(result['phase'],'COMPLETED');self.assertEqual(result['items'][0]['action'],'ANALYSED_PENDING_MANUAL_REVIEW');self.assertEqual(self.library.object_snapshot('ARTWORK',self.work['id']),before);self.assertTrue(blocked(self.store,self.work['id']));self.assertEqual(self.store.count('SEMANTIC_MODEL'),0);record=self.store.get('QUALITY_SOURCE_REANALYSIS',result['items'][0]['analysis_id']);self.assertTrue(record['suggestions']);self.assertFalse(record['formal_eligible']);self.assertFalse(record['semantic_model_used']);self.assertFalse(self.store.get('QUALITY_MAJOR_RECHECK',self.case['id'])['completed']);status=execute(self.library,'STATUS',dict(case_id=self.case['id']));self.assertEqual(status['summary']['states'],{'NEEDS_MANUAL':1})
    def test_actual_cancel_after_first_keeps_checkpoint_and_resume_skips_already_saved_source(self):
        job=self.make(True);cancel=threading.Event()
        def progress(row):
            if any(i['state']=='SUCCESS' for i in row['items']):cancel.set()
        first=self.claim_run(cancel=cancel,progress=progress);self.assertEqual(first['phase'],'CANCELLED');self.assertEqual(sum(i['state']=='SUCCESS' for i in first['items']),1);self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),1);saved=next(i['analysis_id'] for i in first['items'] if i['state']=='SUCCESS');record=self.store.get('QUALITY_SOURCE_REANALYSIS',saved);second=self.claim_run();self.assertEqual(second['phase'],'COMPLETED');self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),2);self.assertEqual(self.store.get('QUALITY_SOURCE_REANALYSIS',saved),record)
    def test_missing_source_failure_does_not_contaminate_other_success(self):
        self.make(True);path=Path(self.library.source(self.twin_source['id'])['current_path']);path.unlink();result=self.claim_run();self.assertEqual(result['phase'],'COMPLETED_WITH_EXCEPTIONS');self.assertEqual(sum(i['state']=='SUCCESS' for i in result['items']),1);self.assertEqual(sum(i['state']=='FAILED' for i in result['items']),1);self.assertTrue(blocked(self.store,self.work['id']));self.assertTrue(blocked(self.store,self.twin['id']));self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),1)
    def test_selected_subset_leaves_other_case_work_unscanned(self):
        self.make(True,selected=[self.work['id']]);result=self.claim_run();self.assertEqual(result['phase'],'COMPLETED');other=self.store.get('QUALITY_WORK_QUARANTINE',digest([self.case['id'],self.twin['id']]));self.assertEqual(other['review_state'],'UNSCANNED');self.assertTrue(blocked(self.store,self.twin['id']));self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),1)
    def test_stale_or_tampered_scope_never_enters_original_worker(self):
        self.make();bad=copy.deepcopy(self.plan);bad['items'][0]['source_id']=self.other_source['id']
        with self.assertRaises(ValueError):create(self.auto,bad,'Synthetic reviewer','Altered preview',True)
        work=self.library.artwork(self.work['id']);payload=copy.deepcopy(work['payload']);payload['slots'][0]['rect']['x']+=.1;self.library.save_artwork(work['id'],payload,work['revision'])
        with self.assertRaises(ValueError):self.auto.claim(self.job['id'],self.job['revision'],True)
        self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),0)
    def test_shared_fifo_claims_source_jobs_in_original_order_and_preserves_other_source(self):
        self.make(True,selected=[self.work['id']]);second=create(self.auto,plan(self.library,self.case['id'],[self.twin['id']]),'Synthetic reviewer','Second exact source scope',True);queue=RuntimeQueue(self.library);session=new_id();a=queue.enqueue('AUTO_JOB',self.job['id'],'Synthetic reviewer',session,True);b=queue.enqueue('AUTO_JOB',second['id'],'Synthetic reviewer',session,True)
        with self.assertRaises(ValueError):queue.claim(b,session)
        claimed=queue.claim(a,session);first=run_automatic(self.library.root,self.job['id'],claimed['owner']['token']);queue.finish(a['id'],claimed['owner']['token'],result=first);claimed=queue.claim(b,session);last=run_automatic(self.library.root,second['id'],claimed['owner']['token']);queue.finish(b['id'],claimed['owner']['token'],result=last);self.assertEqual(last['phase'],'COMPLETED');self.assertFalse(blocked(self.store,self.other_work['id']))
    def test_real_owned_process_exit_is_interrupted_and_requires_explicit_resume(self):
        self.make();script='''import sys,os\nfrom unittest.mock import patch\nfrom template_ai.storage import Library\nfrom template_ai.automatic_training import AutomaticTraining,run_automatic\nroot,identity=sys.argv[1:];lib=Library(root);auto=AutomaticTraining(lib);job=auto.get(identity);claimed=auto.claim(identity,job['revision'],True);lib.close()\nwith patch('template_ai.source_analysis.analyse_source',side_effect=lambda *args,**kwargs:os._exit(17)):run_automatic(root,identity,claimed['owner']['token'])\n''';result=subprocess.run([sys.executable,'-c',script,str(self.library.root),self.job['id']],capture_output=True,text=True,timeout=25);self.assertEqual(result.returncode,17,result.stderr[-500:]);self.assertEqual(self.auto.phase(self.auto.get(self.job['id'])),'INTERRUPTED');status=execute(self.library,'STATUS',dict(case_id=self.case['id']));self.assertEqual(status['summary']['states'],{'INTERRUPTED':1});self.assertEqual(status['summary']['checked'],0);self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),0);resumed=self.claim_run();self.assertEqual(resumed['phase'],'COMPLETED');self.assertEqual(self.store.count('QUALITY_SOURCE_REANALYSIS'),1)
    def test_restored_missing_source_has_saved_current_analysis_and_still_requires_manual_review(self):
        self.twin_source,self.twin=source_work(self.library,self.root,'review-initially-missing.svg');path=Path(self.library.source(self.twin_source['id'])['current_path']);original=path.read_bytes();path.unlink();self.case=self.service.confirm_source(self.source_plan(),'Synthetic reviewer','Unknown linked file stays pending',True);self.auto=AutomaticTraining(self.library);self.plan=plan(self.library,self.case['id'],[self.twin['id']]);self.job=create(self.auto,self.plan,'Synthetic reviewer','Recheck only restored exact source',True);path.write_bytes(original);result=self.claim_run();self.assertEqual(result['phase'],'COMPLETED');status=execute(self.library,'STATUS',dict(case_id=self.case['id']));row=next(row for row in status['rows'] if row['work_id']==self.twin['id']);self.assertEqual(row['effective_state'],'NEEDS_MANUAL');self.assertTrue(blocked(self.store,self.twin['id']));self.assertFalse(status['summary']['whole_corpus_safe'])
    def test_completed_analysis_cannot_be_claimed_as_new_training_or_review_approval(self):
        self.make();result=self.claim_run()
        with self.assertRaises(ValueError):self.auto.claim(result['id'],result['revision'],True)
        self.assertEqual(self.store.count('SEMANTIC_MODEL'),0);self.assertTrue(blocked(self.store,self.work['id']));self.assertEqual(self.store.get('QUALITY_MAJOR_RECHECK',self.case['id'])['state'],'REVIEW_REQUIRED')

if __name__=='__main__':unittest.main()
