"""Real selected-scope semantic training reuses the existing AUTO worker."""
import copy,threading,unittest
from unittest.mock import patch
import test_semantic_learning as fixtures
from template_ai.automatic_training import AutomaticTraining,run_automatic
from template_ai.quality_repairs import QualityRepairs
from template_ai.quality_repair_training import create
from template_ai.runtime_queue import RuntimeQueue
from template_ai.runtime_worker import run_isolated
from template_ai.training_pipeline import LIVE_OWNERS
from template_ai.storage import Library
from template_ai.model import new_id
from test_runtime_execution import ALLOW,HOLD


class RepairCandidateTrainingTests(unittest.TestCase):
    setUp=fixtures.SemanticLearningTests.setUp
    work=fixtures.SemanticLearningTests.work

    def preparation(self):
        self.repairs=QualityRepairs(self.library);self.auto=AutomaticTraining(self.library)
        plan=self.repairs.plan_source_issue(self.train['id'],'SOURCE_FACTS',self.train['id'],'Unclassified authored title under investigation')
        issue=self.repairs.create_source_issue(plan,'Reviewer','Inspect actual confirmed source',True)
        root=self.repairs.root_plan(issue['id'],'FIELD_OWNER_SEMANTICS','Candidate text classifier may resolve title ambiguity','Human labels and original source reviewed',True,True)
        review=self.repairs.confirm_root(root,'Reviewer',True)
        return review,self.service.plan(self.roles)

    def run_direct(self,job,cancel=None,admission=None):
        claimed=self.auto.claim(job['id'],job['revision'],True)
        try:return run_automatic(self.library.root,job['id'],claimed['owner']['token'],cancel=cancel,admission=admission)
        finally:LIVE_OWNERS.discard(claimed['owner']['token'])

    def test_actual_fifo_owned_children_create_only_isolated_models_and_preserve_source_truth(self):
        review,plan=self.preparation();before=self.service.store.facts(self.train['id']);queue=RuntimeQueue(self.library);session=new_id()
        jobs=[create(self.auto,review['id'],plan,'Operator',True) for _ in range(2)]
        requests=[queue.enqueue('AUTO_JOB',j['id'],'Operator',session,True) for j in jobs]
        with self.assertRaises(ValueError):queue.claim(requests[1],session)
        models=[]
        for request in requests:
            claimed=queue.claim(queue.get(request['id']),session)
            done=run_isolated(self.library.root,'AUTO_JOB',claimed['id'],claimed['owner']['token'],admission=lambda:ALLOW)
            queue.finish(request['id'],claimed['owner']['token'],result=done)
            self.assertEqual(done['phase'],'COMPLETED');self.assertTrue(done['candidate_id']);models.append(done['model_id'])
            candidate=self.service.store.get('QUALITY_REPAIR_CANDIDATE',done['candidate_id']);self.assertFalse(candidate['can_activate']);self.assertFalse(candidate['quality_pass'])
            self.assertEqual(self.service.store.get('SEMANTIC_MODEL',done['model_id'])['state'],'PENDING')
        self.assertEqual(len(set(models)),2);self.assertIsNone(self.service.store.get('SEMANTIC_ACTIVE','local-text'))
        self.assertEqual(self.service.store.facts(self.train['id']),before);self.assertFalse(self.library.templates());self.assertEqual(self.service.store.count('SAMPLE'),0)

    def test_cancel_pause_resume_same_job_and_completed_result_cannot_be_retrained(self):
        review,plan=self.preparation();job=create(self.auto,review['id'],plan,'Operator',True);cancel=threading.Event();cancel.set()
        done=self.run_direct(job,cancel=cancel);self.assertEqual(done['phase'],'CANCELLED');self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0)
        done=self.run_direct(done,admission=lambda:HOLD);self.assertEqual(done['phase'],'PAUSED_RESOURCES');self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0)
        done=self.run_direct(done,admission=lambda:ALLOW);self.assertEqual(done['phase'],'COMPLETED');self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),1)
        with self.assertRaises(ValueError):self.auto.claim(done['id'],done['revision'],True)
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),1);self.assertFalse(self.service.store.get('WORKER','automatic-worker')['active'])

    def test_stale_human_training_source_blocks_claim_before_worker_lease_or_model(self):
        review,plan=self.preparation();job=create(self.auto,review['id'],plan,'Operator',True);facts=self.service.store.facts(self.validation['id']);rows=copy.deepcopy(facts['observations']);rows[0]['text']='Synthetic changed source label'
        self.service.store.save_facts(self.validation['id'],rows,facts['revision'],self.validation['revision'])
        with self.assertRaises(ValueError):self.auto.claim(job['id'],job['revision'],True)
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0);self.assertIsNone(self.service.store.get('WORKER','automatic-worker'))

    def test_late_candidate_link_audit_failure_rolls_back_model_candidate_and_role_lock(self):
        review,plan=self.preparation();job=create(self.auto,review['id'],plan,'Operator',True);original=Library.event
        def fail(library,subject,action,*args,**kwargs):
            if action=='training_repair_candidate_job_result_linked':raise OSError('Synthetic late candidate link failure')
            return original(library,subject,action,*args,**kwargs)
        with patch.object(Library,'event',new=fail):
            with self.assertRaises(OSError):self.run_direct(job,admission=lambda:ALLOW)
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0);self.assertEqual(self.service.store.count('QUALITY_REPAIR_CANDIDATE'),0)
        self.assertEqual(self.service.store.count('GROUP_ROLE'),0);self.assertFalse(self.service.store.get('WORKER','automatic-worker')['active'])

    def test_confirmed_holdout_family_discovery_cannot_enter_already_planned_training_job(self):
        from training_fixture import source_work
        from test_noise_authoring import confirmed
        from template_ai.quality_gold import QualityGold,DOMAINS,USE
        from template_ai.quality_sets import QualitySets
        from template_ai.quality_groups import QualityGroups
        review,plan=self.preparation();job=create(self.auto,review['id'],plan,'Operator',True)
        source,work=source_work(self.library,self.root,'independent-quality-source.svg');confirmed(self.service.store,work)
        gold=QualityGold(self.library);truth=gold.confirm(gold.plan(work['id'],dict(basis='OWNED',reference='Authored fixture original only',use=USE),{d:'INSUFFICIENT_EVIDENCE' for d in DOMAINS},'Manual original truth versions','Authored evidence'),'Reviewer',True)
        sets=QualitySets(self.library);sets.create(sets.plan('Reserved holdout before candidate starts',[truth['id']],True,True,'Independent role reservation, no accuracy claim'),'Reviewer',True)
        train_source=self.library.source(self.train['source_id']);groups=QualityGroups(self.library)
        groups.confirm_link(groups.link_plan('CONTENT:'+train_source['hash'],'CONTENT:'+source['hash'],'SAME_DESIGN_FAMILY','Newly confirmed related source family','Original design relation reviewed'),'Reviewer',True)
        with self.assertRaisesRegex(ValueError,'HOLDOUT|家族|角色|holdout'):self.auto.claim(job['id'],job['revision'],True)
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0);self.assertIsNone(self.service.store.get('WORKER','automatic-worker'))
