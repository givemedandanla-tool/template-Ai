import copy
import sqlite3
import unittest
from unittest.mock import patch
import test_quality_jobs as fixture
from template_ai.quality_jobs import run_evaluation
from template_ai.quality_reports import QualityReports


class QualityReportTests(unittest.TestCase):
    setUp = fixture.QualityJobTests.setUp
    build = fixture.QualityJobTests.build

    def completed(self):
        jobs = self.build()
        for job in jobs.values():
            claimed = self.service.claim(job['id'], job['revision'], True)
            run_evaluation(self.library.root, job['id'], claimed['owner_token'])
        self.reports = QualityReports(self.library)
        return self.reports.plan(self.protocol['id'])

    def test_actual_pair_same_scope_denominators_and_insufficient_blocks_decision(self):
        plan = self.completed()
        self.assertTrue(plan['fair_comparison'])
        self.assertEqual(plan['denominators']['declared_gold_objects'], 5)
        self.assertEqual(plan['fixed_cases'], [])
        self.assertEqual(plan['new_cases'], [])
        self.assertFalse(plan['candidate_decision_eligible'])
        report = self.reports.save(plan, 'Reviewer', True)
        with self.assertRaises(ValueError): self.reports.decide(report['id'], 'Reviewer', 'Cannot pass incomplete evidence', True)
        self.assertEqual(self.store.count('QUALITY_VERSION_DECISION'), 0)

    def test_result_tampering_or_wrong_denominator_cannot_make_fair_pair(self):
        self.completed()
        job = self.service.get(self.jobs['CANDIDATE']['id'])
        result = self.store.get('QUALITY_EVAL_RESULT', job['result_id'])
        result['declared_gold_works'] += 1
        with self.store.transaction(): self.store._write('QUALITY_EVAL_RESULT', result['id'], result, result['revision'], 'synthetic_corruption')
        with self.assertRaisesRegex(ValueError, '指紋|分母不同'): self.reports.plan(self.protocol['id'])

    def test_source_receipt_digest_change_is_not_ignored(self):
        self.completed()
        job = self.service.get(self.jobs['BASELINE']['id'])
        result = self.store.get('QUALITY_EVAL_ITEM', job['items'][0]['result_id'])
        result['evaluation']['cases'] = []
        with self.store.transaction(): self.store._write('QUALITY_EVAL_ITEM', result['id'], result, result['revision'], 'synthetic_receipt_change')
        with self.assertRaisesRegex(ValueError, '指紋'): self.reports.plan(self.protocol['id'])

    def test_exposing_answers_preserves_report_but_prevents_new_quality_approval(self):
        plan = self.completed(); report = self.reports.save(plan, 'Reviewer', True)
        self.reports.protocols.expose(self.protocol['id'], 'Reviewer', 'Investigate actual source cases', True)
        current = self.reports.plan(self.protocol['id'])
        self.assertFalse(current['fair_comparison'])
        self.assertFalse(current['candidate_decision_eligible'])
        self.assertEqual(self.store.get('QUALITY_PAIR_REPORT', report['id']), report)

    def test_report_audit_failure_rolls_back_and_does_not_change_business_data(self):
        plan = self.completed()
        templates = self.library.templates()
        with patch.object(self.library, 'event', side_effect=sqlite3.OperationalError('synthetic disk full')):
            with self.assertRaises(sqlite3.OperationalError): self.reports.save(plan, 'Reviewer', True)
        self.assertEqual(self.store.count('QUALITY_PAIR_REPORT'), 0)
        self.assertEqual(self.library.templates(), templates)
        self.assertEqual(self.store.count('SAMPLE'), 0)
