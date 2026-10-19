from copy import deepcopy
import unittest
from template_ai.design_ranking import rank,train_preferences,utility,FEATURES

def features(value=0):return {key:value for key in FEATURES}
def comparison(query):
    return dict(query_id=query,role='TRAIN',label_source='EXPLICIT_INDEPENDENT_COMPARISON',
                evidence_refs=['authored-judge:'+query],winner=features(0),loser=features(1))

class DesignRankingTests(unittest.TestCase):
    def test_many_queries_from_one_lineage_cannot_outvote_independent_sources(self):
        rows=[dict(comparison('q'+str(i)),source_group='g'+str(i)) for i in range(3)]
        rows[0]['winner'],rows[0]['loser']=rows[0]['loser'],rows[0]['winner']
        baseline=train_preferences(rows)
        variants=[dict(deepcopy(rows[0]),query_id='variant-'+str(i)) for i in range(80)]
        repeated=train_preferences(rows+variants)
        for a,b in zip(baseline['weights'],repeated['weights']):self.assertAlmostEqual(a,b,places=6)
        self.assertGreater(utility(features(0),repeated),utility(features(1),repeated))
        self.assertEqual(repeated['weighting'],'EQUAL_LINEAGE_THEN_QUERY_THEN_COMPARISON')

    def test_hard_checks_precede_score_and_formal_checks_are_separate(self):
        good=dict(id='good',family_id='f',configuration_ids=['a'],geometry_digest='x',
                  features=features(1),legal_preview_geometry=True,formal_eligible=False)
        illegal=dict(good,id='illegal',features=features(-100),legal_preview_geometry=False)
        result=rank([illegal,good],dict(version='1'))
        self.assertEqual(result['preferred_id'],'good')
        self.assertIsNone(rank([good],dict(version='1'),require_formal=True)['preferred_id'])

    def test_equal_score_uses_versioned_defaults_independent_of_candidate_order(self):
        rows=[dict(id=key,family_id=key,configuration_ids=['a'],geometry_digest=key,
                   features=features(0),legal_preview_geometry=True) for key in ('a','b')]
        policy=dict(version='1',family_order=['b','a'])
        self.assertEqual(rank(rows,policy)['preferred_id'],'b')
        self.assertEqual(rank(rows,policy),rank(list(reversed(rows)),policy))

    def test_explicit_pairwise_training_changes_utilities_without_probability_claim(self):
        model=train_preferences([comparison('q1'),comparison('q2')])
        self.assertGreater(utility(features(0),model),utility(features(1),model))
        self.assertEqual(model['score_kind'],'UNCALIBRATED_PAIRWISE_UTILITY')

    def test_own_scores_missing_evidence_and_heldout_cannot_be_training_labels(self):
        for changes in [dict(label_source='OLD_GEOMETRY_SCORE'),dict(evidence_refs=[]),dict(role='HOLDOUT')]:
            rows=[comparison('q1'),comparison('q2')];rows[0].update(changes)
            with self.assertRaises(ValueError):train_preferences(rows)

    def test_weight_tamper_and_one_query_do_not_pass(self):
        with self.assertRaises(ValueError):train_preferences([comparison('q1'),comparison('q1')])
        model=train_preferences([comparison('q1'),comparison('q2')]);model['weights'][0]+=1
        with self.assertRaises(ValueError):utility(features(0),model)
