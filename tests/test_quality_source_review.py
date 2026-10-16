"""User-evidence major review: exact immutable sources and current runtime quarantine."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.quality_rechecks import QualityRechecks,blocked
from template_ai.quality_repairs import QualityRepairs
from template_ai.demo import demo_template
from template_ai.layout import generate
from template_ai.candidate_risk import bind_source,verify_original_source
from training_fixture import source_work
APP=QApplication.instance() or QApplication([])


class QualitySourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.store=TrainingStore(self.library);self.service=QualityRechecks(self.library);self.repairs=QualityRepairs(self.library)
        self.source,self.work=source_work(self.library,self.root,'review-a.svg');self.other_source,self.other_work=source_work(self.library,self.root,'review-control.svg',note_text='unrelated-authored-control')
        issue=self.repairs.plan_source_issue(self.work['id'],'SOURCE_FACTS',self.work['id'],'Synthetic phone ownership error observed in original source');self.issue=self.repairs.create_source_issue(issue,'Synthetic reviewer','Verified original source example, no model inference',True)
    def plan(self):return self.service.source_plan(issue_id=self.issue['id'],category='PHONE_OWNER',correct_example='phone belongs to p1',wrong_example='phone assigned to p2',severity='CRITICAL')
    def publish(self):
        template=demo_template();template.source_id=self.source['id'];template.source_work_id=self.work['id'];template.source_work_revision=self.work['revision'];self.library.publish(template);return template
    def candidate(self,template):
        candidate=generate(template,[dict(name=['Alex Example'],title=['Designer'],phone=['+1 202 555 0100'],email=['alex@example.test'])],[],{},3);verify_original_source(candidate,self.library);bind_source(candidate,self.library,require_registered=True);return candidate
    def test_source_evidence_can_start_without_quality_protocol_and_preserves_original_records(self):
        before=self.library.object_snapshot('ARTWORK',self.work['id']);plan=self.plan();self.assertNotIn('protocol_id',plan);case=self.service.confirm_source(plan,'Synthetic reviewer','Confirm exact known dependency quarantine',True);self.assertEqual(case['state'],'REVIEW_REQUIRED');self.assertFalse(case['completed']);self.assertTrue(blocked(self.store,self.work['id']));self.assertFalse(blocked(self.store,self.other_work['id']));self.assertEqual(self.library.object_snapshot('ARTWORK',self.work['id']),before);self.assertTrue(case['plan']['unknown_unrecorded_dependencies']);self.assertFalse(case['plan']['whole_corpus_safe'])
    def test_source_and_work_denominators_keep_equal_bytes_as_distinct_logical_records(self):
        twin_source,twin=source_work(self.library,self.root,'review-twin.svg');self.assertNotEqual(twin_source['id'],self.source['id']);self.assertEqual(twin_source['hash'],self.source['hash']);plan=self.plan();self.assertEqual(plan['coverage']['affected_sources'],2);self.assertEqual(plan['coverage']['affected_works'],2);self.assertEqual({r['work_id'] for r in plan['rows']},{self.work['id'],twin['id']});self.assertTrue(all(r['dependency_match']=='RECORDED_DEPENDENCY' for r in plan['rows']))
    def test_exact_case_retry_is_idempotent_even_after_another_manual_edit(self):
        plan=self.plan();case=self.service.confirm_source(plan,'Synthetic reviewer','Confirm exact known scope',True);count=self.library.db.execute('SELECT count(*) FROM training_history').fetchone()[0];self.library.rename_artwork(self.work['id'],'newer human name');retry=self.service.confirm_source(json.loads(json.dumps(plan)),'Synthetic reviewer','Safe original case readback',True);self.assertTrue(retry['replayed']);self.assertEqual(retry['id'],case['id']);self.assertEqual(self.library.db.execute('SELECT count(*) FROM training_history').fetchone()[0],count)
    def test_modified_scope_or_changed_source_after_preflight_does_not_create_case(self):
        plan=self.plan();tampered=copy.deepcopy(plan);tampered['wrong_example']='another claim'
        with self.assertRaises(ValueError):self.service.confirm_source(tampered,'Synthetic reviewer','Wrong scope',True)
        work=self.library.artwork(self.work['id']);payload=copy.deepcopy(work['payload']);payload['slots'][0]['rect']['x']+=.1;self.library.save_artwork(work['id'],payload,work['revision'])
        with self.assertRaisesRegex(ValueError,'變更'):self.service.confirm_source(plan,'Synthetic reviewer','Stale plan',True)
        self.assertFalse(blocked(self.store,self.work['id']))
    def test_midtransaction_storage_failure_rolls_back_quarantine_and_case_together(self):
        plan=self.plan();original=self.service.store._write;count=[]
        def fail(kind,*args):
            count.append(kind)
            if kind=='QUALITY_MAJOR_RECHECK':raise OSError('synthetic disk write failure')
            return original(kind,*args)
        with patch.object(self.service.store,'_write',side_effect=fail):
            with self.assertRaises(OSError):self.service.confirm_source(plan,'Synthetic reviewer','Rollback actual partial SQLite writes',True)
        self.assertIn('QUALITY_WORK_QUARANTINE',count);self.assertFalse(blocked(self.store,self.work['id']));self.assertIsNone(self.store.get('QUALITY_MAJOR_RECHECK',plan['case_id']))
    def test_existing_qualified_candidate_loses_current_trust_without_template_mutation(self):
        template=self.publish();candidate=self.candidate(template);self.assertTrue(candidate.formal_eligible,candidate.risk);before=self.library.object_snapshot('TEMPLATE',template.id);case=self.service.confirm_source(self.plan(),'Synthetic reviewer','Quarantine original-source-derived published template',True);self.assertFalse(candidate.formal_eligible);self.assertTrue(any(c['id']=='CURRENT_MAJOR_REVIEW_TRUST' and c['status']=='UNKNOWN' for c in candidate.risk['conditions']));self.assertEqual(self.library.object_snapshot('TEMPLATE',template.id),before)
        with self.assertRaisesRegex(ValueError,'重大'):self.library._template_provenance(template)
        self.assertEqual(case['affected_templates'],1)
    def test_restart_reads_same_persistent_case_and_runtime_guard(self):
        template=self.publish();plan=self.plan();self.service.confirm_source(plan,'Synthetic reviewer','Durable exact case',True);other=Library(self.library.root)
        try:
            store=TrainingStore.bind(other);self.assertTrue(blocked(store,self.work['id']));self.assertEqual(store.get('QUALITY_MAJOR_RECHECK',plan['case_id'])['plan_digest'],plan['digest'])
            with self.assertRaises(ValueError):other._template_provenance(template)
        finally:other.close()
    def test_examples_and_literal_approval_are_required(self):
        with self.assertRaises(ValueError):self.service.source_plan(issue_id=self.issue['id'],category='PHONE_OWNER',correct_example='same',wrong_example='same')
        for approval in (False,1,'yes'):
            with self.assertRaises(ValueError):self.service.confirm_source(self.plan(),'Synthetic reviewer','No literal approval',approval)
        self.assertFalse(blocked(self.store,self.work['id']))

if __name__=='__main__':unittest.main()
