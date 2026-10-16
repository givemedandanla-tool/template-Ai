import copy
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_quality_jobs as fixtures
import test_quality_gold_sets as gold_fixture
import test_coverage_batches as coverage_fixture
from template_ai.quality_gold import DOMAINS
from template_ai.quality_jobs import run_evaluation
from template_ai.quality_rechecks import QualityRechecks,blocked
from template_ai.coverage_batches import CoverageBatches
from template_ai.quality_reports import QualityReports


class QualityRecheckTests(unittest.TestCase):
    setUp=fixtures.QualityJobTests.setUp
    build=fixtures.QualityJobTests.build

    def critical(self,closed=False):
        base=gold_fixture.QualityGoldSetTests.plan(self)
        plan=self.gold.plan(self.work['id'],base['rights'],{d:'MANUALLY_VERIFIED' for d in DOMAINS},base['reason'],base['evidence'])
        with patch.object(gold_fixture.QualityGoldSetTests,'plan',return_value=plan):jobs=self.build()
        if closed:
            self.coverage=CoverageBatches(self.library)
            self.batch=self.coverage.create(self.coverage.plan_registered_sources([self.source['id']]),'Reviewer',True)
            member=self.coverage.members(self.batch['id'])['rows'][0]
            coverage_fixture.CoverageBatchTests.review_all(SimpleNamespace(service=self.coverage),member,self.work)
            self.closure=self.coverage.close(self.coverage.closure_plan(self.batch['id']),'Reviewer',True)
            self.assertTrue(self.coverage.closure_status(self.batch['id'])['current_complete'])
        job=jobs['BASELINE'];claimed=self.service.claim(job['id'],job['revision'],True)
        done=run_evaluation(self.library.root,job['id'],claimed['owner_token'])
        result=self.store.get('QUALITY_EVAL_RESULT',done['result_id'])
        self.assertTrue(any(result['critical_errors'].values()))
        self.rechecks=QualityRechecks(self.library)
        return self.rechecks.plan(self.protocol['id'],'BASELINE','PARSER')

    def test_actual_critical_result_finds_closed_historical_batch_and_quarantines_it(self):
        plan=self.critical(True)
        self.assertEqual([r['work_id'] for r in plan['rows']],[self.work['id']])
        self.assertIn(self.batch['id'],plan['rows'][0]['batch_ids'])
        old_receipt=self.store.get('COVERAGE_CLOSURE',self.closure['id'])
        case=self.rechecks.confirm(plan,'Reviewer','Confirmed common parser root failure',True)
        self.assertEqual(case['affected_works'],1)
        self.assertTrue(blocked(self.store,self.work['id']))
        self.assertFalse(self.coverage.closure_status(self.batch['id'])['current_complete'])
        self.assertEqual(self.store.get('COVERAGE_CLOSURE',self.closure['id']),old_receipt)
        self.assertEqual(self.library.templates(),[])
        self.assertTrue(self.store.get('QUALITY_PIPELINE_QUARANTINE',plan['pipeline_id']))

    def test_explicit_approval_and_disk_failure_cannot_partially_quarantine_history(self):
        plan=self.critical(True)
        with self.assertRaises(ValueError):self.rechecks.confirm(plan,'Reviewer','Needs explicit confirmation')
        with patch.object(self.library,'event',side_effect=sqlite3.OperationalError('synthetic disk full')):
            with self.assertRaises(sqlite3.OperationalError):self.rechecks.confirm(plan,'Reviewer','Confirmed common failure',True)
        self.assertFalse(blocked(self.store,self.work['id']))
        self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0)
        self.assertEqual(self.store.count('QUALITY_PIPELINE_QUARANTINE'),0)
        self.assertTrue(self.coverage.closure_status(self.batch['id'])['current_complete'])

    def test_no_new_human_fact_review_cannot_clear_quarantine_or_restore_safe_model(self):
        plan=self.critical(True);self.rechecks.confirm(plan,'Reviewer','Confirmed severe common failure',True)
        q=self.store.records('QUALITY_WORK_QUARANTINE',0,50)[0]
        with self.assertRaisesRegex(ValueError,'更新'):
            self.rechecks.resolve(q['id'],q['revision'],'Reviewer','Old facts are insufficient','Original unchanged',True)
        current=self.store.facts(self.work['id'])
        saved=self.store.save_facts(self.work['id'],current['observations'],current['revision'],self.library.artwork(self.work['id'])['revision'])
        self.store.confirm_facts(self.work['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.store.source_proof(self.work['id']),'Reviewer',True)
        resolved=self.rechecks.resolve(q['id'],q['revision'],'Reviewer','New source facts individually reviewed','Synthetic page source and exact owner correction reviewed',True)
        self.assertEqual(resolved['state'],'RESOLVED_AFTER_NEW_HUMAN_FACTS')
        self.assertFalse(blocked(self.store,self.work['id']))
        self.assertTrue(self.store.get('QUALITY_PIPELINE_QUARANTINE',plan['pipeline_id']))
        self.assertFalse(self.coverage.closure_status(self.batch['id'])['current_complete'])

    def test_no_acceptance_receipt_never_qualifies_quality_recommendations(self):
        status=QualityReports(self.library).recommendation_status('missing-decision')
        self.assertFalse(status['quality_verified_recommendation_allowed'])
        self.assertFalse(status['fallback_assumed_safe'])

    def test_legacy_review_without_version_snapshot_is_potential_impact_not_guessed_exact(self):
        from template_ai.model import new_id
        self.critical()
        with self.store.transaction():self.store._write('COVERAGE_REVIEW',new_id(),dict(work_id=self.work['id'],batch_id='synthetic-legacy-closed-batch',context_digest='historical-hash-without-recoverable-version'),0,'synthetic_legacy_review_format')
        plan=self.rechecks.plan(self.protocol['id'],'BASELINE','PARSER')
        self.assertEqual(len(plan['rows']),1)
        self.assertTrue(plan['rows'][0]['legacy_dependency_versions_unknown'])
        self.assertTrue(plan['unknown_unrecorded_dependencies'])
        self.assertFalse(blocked(self.store,self.work['id']))
