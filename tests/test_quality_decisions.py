import sqlite3
import unittest
from unittest.mock import patch
import test_quality_gold_sets as fixtures
from quality_acceptance_fixture import actual_positive_pair
from template_ai.quality_reports import QualityReports
import test_quality_rechecks as recheck_fixture
import test_quality_jobs as job_fixture


class QualityDecisionTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp
    build=job_fixture.QualityJobTests.build
    critical=recheck_fixture.QualityRecheckTests.critical

    def test_actual_authored_source_qualification_explicit_acceptance_and_withdraw_preserve_business_data(self):
        fixture=actual_positive_pair(self);service=QualityReports(self.library);before=self.library.db.execute('SELECT id,payload FROM templates ORDER BY id').fetchall()
        plan=service.plan(fixture['protocol']['id']);self.assertTrue(plan['candidate_decision_eligible'])
        report=service.save(plan,'Synthetic author',True);decision=service.decide(report['id'],'Synthetic author','Synthetic fixture state-transition test only',True)
        self.assertTrue(service.recommendation_status(decision['id'])['quality_verified_recommendation_allowed'])
        service.withdraw(decision['id'],'Synthetic author','Withdraw fixture acceptance',True)
        status=service.recommendation_status(decision['id']);self.assertFalse(status['quality_verified_recommendation_allowed']);self.assertFalse(status['fallback_assumed_safe'])
        self.assertEqual(self.store.get('QUALITY_VERSION_DECISION',decision['id']),decision)
        self.assertEqual(self.library.db.execute('SELECT id,payload FROM templates ORDER BY id').fetchall(),before)

    def test_actual_qualified_decision_disk_failure_rolls_back_without_replacing_prior_version(self):
        fixture=actual_positive_pair(self);service=QualityReports(self.library);report=service.save(service.plan(fixture['protocol']['id']),'Synthetic author',True)
        with patch.object(self.library,'event',side_effect=sqlite3.OperationalError('synthetic full disk during explicit decision')):
            with self.assertRaises(sqlite3.OperationalError):service.decide(report['id'],'Synthetic author','Synthetic transaction test',True)
        self.assertEqual(self.store.count('QUALITY_VERSION_DECISION'),0)
        self.assertEqual(self.store.get('QUALITY_PAIR_REPORT',report['id']),report)

    def test_known_bad_actual_parser_blocks_previously_accepted_version_and_new_id_clone(self):
        from template_ai.quality_pipeline import QualityPipelines
        fixture=actual_positive_pair(self);service=QualityReports(self.library)
        report=service.save(service.plan(fixture['protocol']['id']),'Synthetic author',True)
        decision=service.decide(report['id'],'Synthetic author','Fixture transition test',True)
        self.assertTrue(service.recommendation_status(decision['id'])['quality_verified_recommendation_allowed'])
        plan=self.critical(True);self.rechecks.confirm(plan,'Reviewer','Known common parser ROOT failure',True)
        self.assertFalse(service.recommendation_status(decision['id'])['quality_verified_recommendation_allowed'])
        clone=QualityPipelines(self.library).freeze('New name and ID, unchanged actual parser',None,'Reviewer',True)
        self.assertNotEqual(clone['id'],plan['pipeline_id']);self.assertTrue(service.component_blocked(clone['id']))
        self.assertTrue(service.component_blocked(decision['pipeline_id']))
        self.assertEqual(self.store.get('QUALITY_VERSION_DECISION',decision['id']),decision)
