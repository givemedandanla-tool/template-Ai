"""Human conclusions are pinned to newer complete facts; old receipt is no future trust."""
import copy,unittest
from pathlib import Path
import test_quality_source_review as fixture
from test_noise_authoring import confirmed
from template_ai.major_review_findings import plan,confirm
from template_ai.major_review_commands import execute
from template_ai.quality_rechecks import blocked
from template_ai.training_store import digest
from training_fixture import observations


class MajorReviewFindingTests(unittest.TestCase):
    setUp=fixture.QualitySourceReviewTests.setUp
    source_plan=fixture.QualitySourceReviewTests.plan
    def case(self):
        self.case_record=self.service.confirm_source(self.source_plan(),'Synthetic reviewer','Actual source evidence before human re-review',True);self.unit_id=digest([self.case_record['id'],self.work['id']]);return self.case_record
    def finding(self,name='CHECKED_OK'):return plan(self.service,self.case_record['id'],self.unit_id,name,'Original source and all observed fields manually compared')
    def test_only_new_complete_confirmed_current_facts_can_release_work_and_not_models(self):
        self.case()
        with self.assertRaises(ValueError):self.finding()
        facts=self.store.save_facts(self.work['id'],observations(self.work),0,self.work['revision'])
        with self.assertRaises(ValueError):self.finding()
        self.store.confirm_facts(self.work['id'],[row['id'] for row in facts['observations']],facts['revision'],facts['pins'],self.store.source_proof(self.work['id']),'Synthetic reviewer',True);value=self.finding();self.assertFalse(value['model_quality_released']);row=confirm(self.service,value,'Synthetic reviewer','Checked original source and newer facts',True);self.assertEqual(row['state'],'RESOLVED_AFTER_NEW_HUMAN_FACTS');self.assertEqual(row['review_state'],'CHECKED_OK');self.assertFalse(blocked(self.store,self.work['id']));self.assertFalse(blocked(self.store,self.other_work['id']));self.assertFalse(self.store.get('QUALITY_MAJOR_RECHECK',self.case_record['id'])['completed'])
    def test_preexisting_approval_cannot_self_approve_new_recheck(self):
        confirmed(self.store,self.work);self.case()
        with self.assertRaisesRegex(ValueError,'更新'):self.finding('REAPPROVED')
        self.assertTrue(blocked(self.store,self.work['id']))
    def test_pending_error_and_unknown_findings_retain_quarantine(self):
        self.case()
        for finding in ('ERROR_NEEDS_FIX','NEEDS_MANUAL','BLOCKED','UNKNOWN'):
            value=self.finding(finding);row=confirm(self.service,value,'Synthetic reviewer','Explicit pending conclusion, no approval',True);self.assertEqual(row['review_state'],finding);self.assertTrue(blocked(self.store,self.work['id']));self.assertEqual(row['state'],'REVIEW_REQUIRED')
    def test_verified_exclusion_does_not_turn_lost_source_into_trusted_work(self):
        self.case();Path(self.library.source(self.source['id'])['current_path']).unlink();value=self.finding('EXCLUDED_HOLD');self.assertIsNone(value['source_proof']);row=confirm(self.service,value,'Synthetic reviewer','Offline source excluded from intended trusted use',True);self.assertEqual(row['state'],'EXCLUDED_HOLD');self.assertTrue(blocked(self.store,self.work['id']));status=execute(self.library,'STATUS',dict(case_id=self.case_record['id']));self.assertEqual(status['summary']['states'],{'EXCLUDED_VERIFIED':1});self.assertFalse(status['summary']['whole_corpus_safe'])
    def test_changed_facts_or_tampered_finding_prevents_release(self):
        self.case();facts=confirmed(self.store,self.work);value=self.finding();wrong=copy.deepcopy(value);wrong['evidence']='different evidence'
        with self.assertRaises(ValueError):confirm(self.service,wrong,'Synthetic reviewer','Wrong preview',True)
        self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):confirm(self.service,value,'Synthetic reviewer','Changed facts',True)
        self.assertTrue(blocked(self.store,self.work['id']))
    def test_idempotent_finding_readback_does_not_duplicate_approval_events(self):
        self.case();confirmed(self.store,self.work);value=self.finding();saved=confirm(self.service,value,'Synthetic reviewer','Same exact current human evidence',True);before=self.library.db.execute('SELECT count(*) FROM training_history').fetchone()[0];again=confirm(self.service,value,'Synthetic reviewer','Read original receipt only',True);self.assertTrue(again['replayed']);self.assertEqual(saved['revision'],again['revision']);self.assertEqual(self.library.db.execute('SELECT count(*) FROM training_history').fetchone()[0],before)
    def test_explicit_reopen_preserves_history_and_requires_facts_newer_than_reopen(self):
        from template_ai.major_review_findings import reopen_plan,reopen
        self.case();facts=confirmed(self.store,self.work);confirm(self.service,self.finding(),'Synthetic reviewer','Initial exact human review',True);value=reopen_plan(self.service,self.case_record['id'],self.unit_id);reopened=reopen(self.service,value,'Synthetic reviewer','New doubt requires fresh manual facts',True);self.assertEqual(reopened['state'],'REVIEW_REQUIRED');self.assertTrue(blocked(self.store,self.work['id']))
        with self.assertRaises(ValueError):self.finding()
        again=reopen(self.service,value,'Synthetic reviewer','Read saved original reopen',True);self.assertTrue(again['replayed']);facts=self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision']);self.store.confirm_facts(self.work['id'],[o['id'] for o in facts['observations']],facts['revision'],facts['pins'],self.store.source_proof(self.work['id']),'Synthetic reviewer',True);confirm(self.service,self.finding('REAPPROVED'),'Synthetic reviewer','New facts after reopening',True);self.assertFalse(blocked(self.store,self.work['id']))
    def test_stale_reopen_preview_does_not_overwrite_new_facts(self):
        from template_ai.major_review_findings import reopen_plan,reopen
        self.case();facts=confirmed(self.store,self.work);confirm(self.service,self.finding(),'Synthetic reviewer','Initial review',True);value=reopen_plan(self.service,self.case_record['id'],self.unit_id);self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):reopen(self.service,value,'Synthetic reviewer','Stale reopen',True)
    def test_new_source_work_or_fact_revision_invalidates_old_release_receipt(self):
        self.case();facts=confirmed(self.store,self.work);confirm(self.service,self.finding(),'Synthetic reviewer','First actual review',True);self.assertFalse(blocked(self.store,self.work['id']));self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision']);self.assertTrue(blocked(self.store,self.work['id']));status=execute(self.library,'STATUS',dict(case_id=self.case_record['id']));self.assertEqual(status['summary']['states'],{'STALE_REVIEW':1});self.assertEqual(status['summary']['checked'],0)

if __name__=='__main__':unittest.main()
