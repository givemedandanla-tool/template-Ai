"""Synthetic counterexamples for cluster denominators, not production quality."""
import copy
import unittest
from template_ai.quality_gold import DOMAINS
from template_ai.quality_domains import measured, unknown
from template_ai.quality_metrics import counts
from template_ai.quality_statistics import aggregate


class QualityStatisticsTests(unittest.TestCase):
    def fixture(self, n=100):
        thresholds = {name: dict(minimum_independent_groups=2, minimum_gold_objects=2,
                                minimum_precision=.9, minimum_recall=.9,
                                maximum_group_failure_rate=.1) for name in DOMAINS}
        thresholds['field_types']['required_classes'] = ['email', 'phone']
        thresholds['physical_size'] = dict(minimum_independent_groups=2, minimum_gold_objects=2,
                                          maximum_group_failure_rate=.1, maximum_absolute_error_mm=.02)
        policy = dict(thresholds=thresholds, confidence=.95, scope='SYNTHETIC_SELF_CHECK')
        rows = []
        for index in range(n):
            domains = {name: measured(counts(2, 0, 0), 2, 'SYNTHETIC_COUNTEREXAMPLE') for name in DOMAINS}
            domains['field_types'] = measured(None, 4, 'SYNTHETIC', per_class={kind: counts(2, 0, 0) for kind in ('email', 'phone')})
            domains['physical_size'] = measured(None, 2, 'SYNTHETIC_MM', errors_mm=[0, 0])
            rows.append(dict(source_hash=str(index), item_id=str(index), evaluation=dict(domains=domains, critical_errors={})))
        manifest = dict(group_components=[['CONTENT:' + str(i)] for i in range(n)],
                        independent_group_count=n, independence_scope_ready=True)
        return rows, manifest, policy

    def test_known_good_synthetic_groups_pass_math_without_publication(self):
        result = aggregate(*self.fixture())
        self.assertTrue(result['quality_pass'])
        self.assertFalse(result['automatic_recommendation_allowed'])
        self.assertEqual(result['confidence_scope'], 'PER_DOMAIN_PER_CLASS_MARGINAL_NOT_SIMULTANEOUS')

    def test_thousands_of_fields_from_one_related_group_are_one_sample(self):
        rows, manifest, policy = self.fixture()
        manifest['group_components'] = [sum(manifest['group_components'], [])]
        manifest['independent_group_count'] = 1
        result = aggregate(rows, manifest, policy)
        item = result['domains']['source_readability']['classes']['ALL']
        self.assertEqual(item['positive_independent_groups'], 1)
        self.assertEqual(item['gold_objects'], 200)
        self.assertFalse(result['quality_pass'])

    def test_zero_observed_errors_with_small_n_still_fails_uncertainty_bound(self):
        result = aggregate(*self.fixture(2))
        item = result['domains']['source_readability']['classes']['ALL']
        self.assertEqual(item['failed_independent_groups'], 0)
        self.assertGreater(item['failure_rate_interval']['upper'], .1)
        self.assertEqual(item['state'], 'FAILED_THRESHOLD')

    def test_rare_class_cannot_hide_behind_frequent_email(self):
        rows, manifest, policy = self.fixture()
        for row in rows[1:]: row['evaluation']['domains']['field_types']['per_class'].pop('phone')
        result = aggregate(rows, manifest, policy)
        self.assertEqual(result['domains']['field_types']['classes']['phone']['state'], 'EVIDENCE_INSUFFICIENT')
        self.assertEqual(result['domains']['field_types']['classes']['email']['state'], 'PASS')

    def test_unknown_source_retained_for_every_applicable_class(self):
        rows, manifest, policy = self.fixture()
        rows[0]['evaluation']['domains']['field_types'] = unknown('No legal gold')
        result = aggregate(rows, manifest, policy)
        for item in result['domains']['field_types']['classes'].values():
            self.assertEqual(item['unknown_source_units'], ['0'])
            self.assertEqual(item['state'], 'EVIDENCE_INSUFFICIENT')

    def test_critical_owner_error_blocks_even_when_all_aggregate_rates_pass(self):
        rows, manifest, policy = self.fixture()
        rows[0]['evaluation']['critical_errors']['person_owner_mismatch'] = 1
        result = aggregate(rows, manifest, policy)
        self.assertEqual(result['quality_gate'], 'FAILED_CRITICAL')
        self.assertFalse(result['quality_pass'])

    def test_missing_whole_group_is_not_silently_dropped(self):
        rows, manifest, policy = self.fixture()
        result = aggregate(rows[:-1], manifest, policy)
        self.assertEqual(result['missing_independent_groups'], ['99'])
        self.assertFalse(result['quality_pass'])

    def test_physical_mm_tolerance_uses_each_group_worst_failure(self):
        rows, manifest, policy = self.fixture()
        for row in rows[:20]: row['evaluation']['domains']['physical_size']['errors_mm'][0] = .03
        result = aggregate(rows, manifest, policy)
        item = result['domains']['physical_size']['classes']['ALL']
        self.assertEqual(item['failed_independent_groups'], 20)
        self.assertEqual(item['state'], 'FAILED_THRESHOLD')
        self.assertIsNone(item['descriptive_counts'])
