"""Explicit new Gold after actual human re-review; no holdout reset."""
import copy,unittest
from unittest.mock import patch
import test_quality_repairs as fixtures
from template_ai.quality_repairs import QualityRepairs
from template_ai.quality_repair_truth import plan,confirm,checked,KIND
from template_ai.quality_protocol import QualityProtocols,REPAIR
from template_ai.quality_jobs import EvaluationJobs,run_evaluation


class QualityRepairTruthTests(unittest.TestCase):
    setUp=fixtures.QualityRepairIssueTests.setUp
    build=fixtures.QualityRepairIssueTests.build
    critical=fixtures.QualityRepairIssueTests.critical
    issue_plan=fixtures.QualityRepairIssueTests.issue_plan

    def prepare(self):
        self.repairs=QualityRepairs(self.library);preview=self.issue_plan();self.issue=self.repairs.create_quality_issue(preview,'Reviewer','Original actual failed source retained',True)
        self.original=copy.deepcopy(self.issue);facts=self.store.facts(self.work['id']);observations=copy.deepcopy(facts['observations']);observations[0]['text']='Name: Synthetic corrected human reading'
        saved=self.store.save_facts(self.work['id'],observations,facts['revision'],self.work['revision'])
        self.store.confirm_facts(self.work['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.store.source_proof(self.work['id']),'Reviewer',True)
        root=self.repairs.root_plan(self.issue['id'],'WORK_SEGMENTATION','Recheck actual source after human correction','Current original reviewed',True,True);self.assertFalse(root['can_prepare_candidate'])
        old=self.store.get('QUALITY_GOLD',preview['gold_refs'][0]['id'])
        gold=self.gold.confirm(self.gold.plan(self.work['id'],old['rights'],old['domain_truth'],'Explicit new current human label version','Original source compared after historical re-review'),'Reviewer',True)
        self.dataset=self.sets.create(self.sets.plan('Current truth same exposed source',[gold['id']],True,True,'Same source and permanent original role, not new independent data'),'Reviewer',True)
        return plan(self.repairs,self.issue['id'],self.dataset['id'],'New current human facts after explicit historical re-review')

    def test_new_truth_unblocks_current_review_and_actual_replay_but_never_fresh_holdout(self):
        preview=self.prepare();before=list(self.store.db.execute("SELECT id,revision,payload FROM training_records WHERE kind IN ('GROUP_ROLE','QUALITY_HOLDOUT_USAGE') ORDER BY kind,id"))
        truth=confirm(self.repairs,preview,'Reviewer',True);self.assertEqual(checked(self.repairs,self.issue['id']),truth)
        root=self.repairs.root_plan(self.issue['id'],'WORK_SEGMENTATION','Reproduce using the explicitly corrected current human truth','Current original and newly approved Gold compared',True,True)
        self.assertTrue(root['can_prepare_candidate'],root['blockers']);review=self.repairs.confirm_root(root,'Reviewer',True)
        protocols=QualityProtocols(self.library);old=self.protocol['scope'];pipelines={side:pin['id'] for side,pin in old['pipelines'].items()}
        with self.assertRaises(ValueError):protocols.plan('Not fresh',self.dataset['id'],old['policy_id'],pipelines,'Copies cannot reset exposed source usage')
        replay=protocols.freeze(protocols.plan('Current truth diagnostic replay',self.dataset['id'],old['policy_id'],pipelines,'Same exposed contents, explicitly new current manual truth',repair_review_id=review['id']),'Reviewer',True)
        self.assertEqual(replay['scope']['purpose'],REPAIR)
        service=EvaluationJobs(self.library)
        for job in service.create_pair(replay['id'],'Reviewer',True).values():
            claimed=service.claim(job['id'],job['revision'],True);done=run_evaluation(self.library.root,job['id'],claimed['owner_token']);result=self.store.get('QUALITY_EVAL_RESULT',done['result_id'])
            self.assertFalse(result['quality_pass']);self.assertEqual(result['quality_gate'],'DESCRIPTIVE_REPAIR_ONLY_NOT_INDEPENDENT')
        self.assertEqual(self.repairs.current_issue(self.issue['id']),self.original)
        self.assertEqual(list(self.store.db.execute("SELECT id,revision,payload FROM training_records WHERE kind IN ('GROUP_ROLE','QUALITY_HOLDOUT_USAGE') ORDER BY kind,id")),before)

    def test_explicit_approval_and_late_audit_failure_leave_no_partial_truth_binding(self):
        preview=self.prepare()
        with self.assertRaises(ValueError):confirm(self.repairs,preview,'Reviewer',False)
        with patch.object(self.library,'event',side_effect=OSError('Synthetic late audit failure')):
            with self.assertRaises(OSError):confirm(self.repairs,preview,'Reviewer',True)
        self.assertIsNone(self.store.get(KIND,self.issue['id']));self.assertEqual(self.repairs.current_issue(self.issue['id']),self.original)

    def test_later_fact_edit_stales_new_truth_and_blocks_old_root_again(self):
        preview=self.prepare();confirm(self.repairs,preview,'Reviewer',True)
        facts=self.store.facts(self.work['id']);observations=copy.deepcopy(facts['observations']);observations[0]['text']='Another unconfirmed edit'
        self.store.save_facts(self.work['id'],observations,facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):checked(self.repairs,self.issue['id'])
        root=self.repairs.root_plan(self.issue['id'],'WORK_SEGMENTATION','Old review must not stay safe','Source changed again',True,True)
        self.assertFalse(root['can_prepare_candidate'])
