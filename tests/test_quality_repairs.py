"""Actual failed source receipts, explicit human root review and atomic isolation."""
import copy,unittest
from unittest.mock import patch
import test_quality_rechecks as fixtures
from template_ai.quality_repairs import QualityRepairs
from template_ai.quality_diagnostics import QualityDiagnostics
from template_ai.quality_protocol import QualityProtocols
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_rechecks import QualityRechecks


class QualityRepairIssueTests(unittest.TestCase):
    setUp=fixtures.QualityRecheckTests.setUp
    build=fixtures.QualityRecheckTests.build
    critical=fixtures.QualityRecheckTests.critical

    def issue_plan(self):
        self.critical();self.repairs=QualityRepairs(self.library)
        QualityProtocols(self.library).expose(self.protocol['id'],'Synthetic reviewer','Inspect actual critical source before proposing repair',True)
        diagnostics=QualityDiagnostics(self.library)
        rows=diagnostics.page(self.protocol['id'],'BASELINE',severity='CRITICAL')['rows'];self.assertTrue(rows)
        return self.repairs.plan_quality_issue(self.protocol['id'],'BASELINE',rows[0],self.work['id'])

    def test_actual_source_issue_and_reviewed_hypothesis_do_not_change_formal_data_or_claim_proven_root(self):
        plan=self.issue_plan();before=self.library.artwork(self.work['id']);templates=self.library.templates()
        self.assertTrue(plan['automatic_repair_allowed']);self.assertFalse(plan['root_cause_proven'])
        issue=self.repairs.create_quality_issue(plan,'Reviewer','Actual failed boundary under investigation',True)
        root=self.repairs.root_plan(issue['id'],'WORK_SEGMENTATION','Source boundary grouping may omit a work','Original and current human object labels reviewed',True,True)
        self.assertTrue(root['can_prepare_candidate']);review=self.repairs.confirm_root(root,'Reviewer',True)
        self.assertFalse(review['root_cause_proven']);self.assertFalse(review['formal_versions_changed'])
        self.assertEqual(self.library.artwork(self.work['id']),before);self.assertEqual(self.library.templates(),templates)
        self.assertEqual(self.store.count('QUALITY_REPAIR_CANDIDATE'),0);self.assertIsNone(self.store.get('SEMANTIC_ACTIVE','local-text'))

    def test_invented_case_and_unapproved_creation_cannot_impersonate_actual_failure(self):
        plan=self.issue_plan();bad=copy.deepcopy(plan['row']);bad['case']['reason']='INVENTED_FIXED_FAILURE'
        with self.assertRaises(ValueError):self.repairs.plan_quality_issue(self.protocol['id'],'BASELINE',bad,self.work['id'])
        with self.assertRaises(ValueError):self.repairs.create_quality_issue(plan,'Reviewer','No approval',False)
        self.assertEqual(self.store.count('QUALITY_REPAIR_ISSUE'),0)

    def test_changed_human_truth_blocks_stale_preview_and_requires_new_review(self):
        plan=self.issue_plan();facts=self.store.facts(self.work['id']);observations=copy.deepcopy(facts['observations']);observations[0]['text']='Synthetic revised human reading'
        self.store.save_facts(self.work['id'],observations,facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):self.repairs.create_quality_issue(plan,'Reviewer','Old preview must not be accepted',True)
        self.assertEqual(self.store.count('QUALITY_REPAIR_ISSUE'),0)

    def test_disputed_truth_and_missing_review_flags_remain_manual_without_candidate(self):
        self.repairs=QualityRepairs(self.library);plan=self.repairs.plan_source_issue(self.work['id'],'SOURCE_FACTS',self.work['id'],'Manually reported source uncertainty')
        issue=self.repairs.create_source_issue(plan,'Reviewer','Source inspection request',True)
        missing=self.repairs.root_plan(issue['id'],'FIELD_OWNER_SEMANTICS','Possible owner mismatch','Still checking the source')
        self.assertFalse(missing['can_prepare_candidate'])
        disputed=self.repairs.root_plan(issue['id'],'DISPUTED_GOLD','Conflicting human readings','No agreed original answer',True,True)
        self.assertFalse(disputed['can_prepare_candidate']);review=self.repairs.confirm_root(disputed,'Reviewer',True)
        self.assertEqual(review['state'],'MANUAL_REVIEW_REQUIRED');self.assertEqual(self.store.count('QUALITY_REPAIR_CANDIDATE'),0)

    def test_late_audit_failure_rolls_back_issue_and_directory_paging_is_readonly(self):
        plan=self.issue_plan()
        with patch.object(self.library,'event',side_effect=OSError('Synthetic late disk audit failure')):
            with self.assertRaises(OSError):self.repairs.create_quality_issue(plan,'Reviewer','No partial issue',True)
        self.assertEqual(self.store.count('QUALITY_REPAIR_ISSUE'),0)
        issue=self.repairs.create_quality_issue(plan,'Reviewer','Source bound issue',True);before=self.library.db.total_changes
        page=self.repairs.page(query=issue['id']);self.assertEqual(page['total'],1);self.assertEqual(page['limit'],50);self.assertEqual(self.library.db.total_changes,before)

    def test_dependency_preview_without_executed_failure_cannot_start_major_quarantine(self):
        pipeline=QualityPipelines(self.library).freeze('Metadata dependency preview',None,'Reviewer',True)
        service=QualityRechecks(self.library);before=self.library.db.total_changes
        dependencies=service.dependencies(pipeline['id'],'PARSER')
        self.assertEqual(self.library.db.total_changes,before);self.assertTrue(dependencies['unknown_unrecorded_dependencies'])
        with self.assertRaises(ValueError):service.confirm(dependencies,'Reviewer','Metadata is not a critical failure',True)
        self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0)

    def test_actual_issue_reuses_dependency_resolver_without_automatic_training_or_quarantine(self):
        plan=self.issue_plan();issue=self.repairs.create_quality_issue(plan,'Reviewer','Investigate actual fixed version',True)
        before=self.library.db.total_changes;impact=self.repairs.impact_plan(issue['id'],'PARSER')
        self.assertEqual(impact['dependencies'],QualityRechecks(self.library).dependencies(plan['pipeline_id'],'PARSER'))
        self.assertFalse(impact['root_cause_proven']);self.assertFalse(impact['automatic_quarantine']);self.assertFalse(impact['automatic_training'])
        self.assertEqual(self.library.db.total_changes,before)
