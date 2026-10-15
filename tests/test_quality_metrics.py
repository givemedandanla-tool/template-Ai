import math
import unittest
from template_ai.quality_metrics import match_boxes,classification_metrics,wilson_interval,counts


def row(identity,x,w=10,kind='email',owner=None):return dict(id=identity,rect=dict(x=x,y=0,w=w,h=10),kind=kind,owner=owner)


class QualityMetricTests(unittest.TestCase):
    def test_maximum_cardinality_avoids_greedy_iou_false_missing_case(self):
        result=match_boxes([row('a',0),row('b',6)],[row('x',2),row('y',0,5)],.4)
        self.assertEqual({(p['gold_id'],p['prediction_id']) for p in result['matches']},{('a','y'),('b','x')});self.assertFalse(result['matching_uses_semantic_labels'])

    def test_matching_cannot_choose_correct_label_to_hide_spatially_best_misclassification(self):
        result=classification_metrics([row('gold',0,kind='email')],[row('wrong',0,kind='phone'),row('right',2,kind='email')],.5)
        self.assertEqual(result['matching']['matches'][0]['prediction_id'],'wrong');self.assertEqual(result['per_class']['email']['fn'],1);self.assertEqual(result['per_class']['phone']['fp'],1)

    def test_missing_extra_and_zero_denominators_are_not_fake_one_hundred_percent(self):
        empty=classification_metrics([],[],.5);self.assertIsNone(empty['detection']['precision']);self.assertIsNone(empty['detection']['recall']);self.assertIsNone(empty['quality_pass'])
        result=classification_metrics([row('a',0)],[row('extra',100,kind='phone')],.5)
        self.assertEqual(result['detection'],counts(0,1,1));self.assertEqual(len(result['cases']),2)

    def test_root_labels_can_permute_but_cross_person_contact_stays_critical(self):
        gold=[row('name1',0,kind='name',owner='p1'),row('name2',100,kind='name',owner='p2'),row('email',200,owner='p1')]
        predicted=[row('n1',0,kind='name',owner='p2'),row('n2',100,kind='name',owner='p1'),row('e',200,owner='p1')]
        result=classification_metrics(gold,predicted,.5);self.assertEqual(result['root_correspondence'],{'p1':'p2','p2':'p1'});self.assertEqual(result['critical_owner_errors'],1);self.assertEqual(result['per_class']['email']['tp'],1)

    def test_same_lexical_owner_without_name_anchor_is_unknown_not_identity_evidence(self):
        result=classification_metrics([row('g',0,owner='p1')],[row('p',0,owner='p1')],.5)
        self.assertEqual(result['unknown_owner_mappings'],1);self.assertEqual(result['known_owner_pairs'],0)

    def test_wilson_intervals_keep_small_sample_uncertainty_and_empty_unknown(self):
        self.assertIsNone(wilson_interval(0,0,.95));small=wilson_interval(1,1,.95);large=wilson_interval(100,100,.95)
        self.assertLess(small['lower'],.3);self.assertGreater(large['lower'],.9);self.assertEqual(small['independent_groups'],1)

    def test_invalid_box_duplicate_ids_budget_or_unapproved_match_policy_never_silently_drop(self):
        for threshold in (None,0,math.nan,True,2):
            with self.assertRaises(ValueError):match_boxes([],[],threshold)
        with self.assertRaises(ValueError):match_boxes([row('same',0),row('same',1)],[],.5)
        bad=row('bad',0);bad['rect']['w']=0
        with self.assertRaises(ValueError):match_boxes([bad],[],.5)
        with self.assertRaises(ValueError):match_boxes([row(str(i),i) for i in range(201)],[],.5)
