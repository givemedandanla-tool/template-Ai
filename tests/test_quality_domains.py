import copy
import unittest
from template_ai.quality_domains import evaluate_source
from template_ai.quality_gold import DOMAINS


class QualityDomainTests(unittest.TestCase):
    def fixture(self):
        # Pure synthetic arithmetic oracles, not actual inference/real-source evidence.
        def obj(identity,kind,owner,x):return dict(id=identity,slot_id=identity,kind=kind,owner=owner,rect=dict(x=x,y=1,w=1,h=1),text='synthetic',object_type='TEXT',classification='FIELD')
        objects=[obj('name1','name','p1',1),obj('name2','name','p2',3),obj('phone','phone','p1',5)]+[obj('email'+str(i),'email','p1',10+i*2) for i in range(20)]
        gold=dict(work_id='gold-work',source_id='synthetic-source',source_page=1,source_hash='0'*64,crop=dict(x=0,y=0,w=90,h=54),width_mm=90,height_mm=54,objects=objects,domain_truth={d:'MANUALLY_VERIFIED' for d in DOMAINS})
        work=dict(key='prediction-work',crop=copy.deepcopy(gold['crop']),work_width=90,work_height=54,slots=[dict(id=o['id'],kind=o['kind'],owner=o['owner']) for o in objects],observations=[dict(id='pred-'+o['id'],slot_id=o['id'],region=copy.deepcopy(o['rect']),text='synthetic',object_type='TEXT',classification='FIELD') for o in objects])
        prediction=dict(source_id=gold['source_id'],source_page=1,source_hash=gold['source_hash'],prediction_origin='ACTUAL_EXECUTED_SOURCE_ANALYSIS_NO_GOLD_ARGUMENT',predictions=[work])
        policy=dict(schema_version=2,matching_iou=.5,thresholds=dict(field_types=dict(required_classes=['name','phone','email']),physical_size=dict(maximum_absolute_error_mm=.02)))
        return gold,prediction,policy

    def test_unparsed_or_missing_gold_source_remains_required_and_all_rates_unknown(self):
        result=evaluate_source([],None,{},unresolved_reason='unregistered source without gold')
        self.assertEqual((result['required_source_pages'],result['unresolved_source_pages']),(1,1));self.assertTrue(all(d['metrics'] is None for d in result['domains'].values()));self.assertIsNone(result['quality_pass'])

    def test_correct_easy_fields_cannot_hide_one_known_cross_person_contact_error(self):
        gold,prediction,policy=self.fixture();prediction['predictions'][0]['slots'][2]['owner']='p2'
        result=evaluate_source([gold],prediction,policy,complete_source_gold=True)
        self.assertEqual(result['critical_errors']['person_owner_mismatch'],1);self.assertEqual(result['domains']['field_types']['per_class']['email']['tp'],20)
        self.assertEqual(result['domains']['person_ownership']['metrics']['fn'],1);self.assertIsNone(result['quality_pass'])

    def test_missing_entire_work_is_critical_and_all_missing_objects_remain_in_counts(self):
        gold,prediction,policy=self.fixture();prediction['predictions']=[]
        result=evaluate_source([gold],prediction,policy,complete_source_gold=True)
        self.assertEqual(result['critical_errors']['missing_work'],1);self.assertEqual(result['domains']['work_segmentation']['metrics']['fn'],1);self.assertEqual(result['conditional_per_class']['email']['fn'],20)
        self.assertGreater(result['domains']['person_ownership']['metrics']['fn'],0)

    def test_physical_size_has_mm_error_and_no_classification_precision_substitution(self):
        gold,prediction,policy=self.fixture();prediction['predictions'][0]['work_width']=91
        result=evaluate_source([gold],prediction,policy,complete_source_gold=True);physical=result['domains']['physical_size']
        self.assertEqual(physical['maximum_absolute_error_mm'],1);self.assertEqual(physical['within_explicit_tolerance'],0);self.assertIsNone(physical['metrics'])

    def test_incomplete_source_truth_cannot_turn_known_subset_into_hundred_percent(self):
        gold,prediction,policy=self.fixture();result=evaluate_source([gold],prediction,policy,complete_source_gold=False)
        self.assertTrue(all(row['metrics'] is None for row in result['domains'].values()));self.assertEqual(result['conditional_per_class']['email']['tp'],20)

    def test_whole_logo_and_customer_mapping_never_inferred_from_correct_field_boxes(self):
        gold,prediction,policy=self.fixture();result=evaluate_source([gold],prediction,policy,complete_source_gold=True)
        self.assertIsNone(result['domains']['whole_logo']['metrics']['precision']);self.assertEqual(result['domains']['whole_logo']['required_gold'],0);self.assertEqual(result['domains']['customer_style_mapping']['state'],'EVIDENCE_INSUFFICIENT')
        prediction['prediction_origin']='USER_SUPPLIED_RECORDS_NOT_EXECUTED_MODEL_INFERENCE'
        with self.assertRaises(ValueError):evaluate_source([gold],prediction,policy,complete_source_gold=True)
