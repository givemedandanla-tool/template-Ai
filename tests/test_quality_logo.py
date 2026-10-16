import copy
import unittest
import xml.etree.ElementTree as ET
from template_ai.quality_logo import components, validate_truth
from template_ai.model import Rect
from template_ai.quality_domains import evaluate_source
import test_quality_domains as fixtures
import test_quality_gold_sets as source_fixture


class QualityLogoTests(unittest.TestCase):
    def structure(self):
        node = ET.fromstring('<g id="brand"><path id="mark"/><text id="label">Synthetic</text></g>')
        bounds = dict(mark=Rect(1, 1, 2, 2), label=Rect(3, 1, 3, 1))
        source = dict(hash='0'*64, file_hashes=dict(svg='1'*64))
        truth = dict(root_id='brand', component_ids=['mark', 'label'],text_component_ids=['label'], review_reason='Synthetic exact authored components reviewed', original_correspondence_confirmed=True)
        return node, bounds, source, truth

    def test_explicit_whole_original_truth_rejects_truncated_or_unreviewed_components(self):
        node,bounds,source,truth=self.structure()
        result=validate_truth(truth,source,list(node.iter()),bounds)
        self.assertTrue(result['manually_verified']);self.assertEqual(result['text_component_ids'],['label'])
        for replacement in (['mark'], ['label'], []):
            with self.assertRaises(ValueError):validate_truth(dict(truth,component_ids=replacement),source,list(node.iter()),bounds)
        with self.assertRaises(ValueError):validate_truth(dict(truth,original_correspondence_confirmed=False),source,list(node.iter()),bounds)

    def test_missing_id_or_external_image_is_unknown_not_full_logo_proof(self):
        node,bounds,source,truth=self.structure();ET.SubElement(node,'path')
        self.assertFalse(components(node,source,bounds)['complete'])
        with self.assertRaises(ValueError):validate_truth(truth,source,list(node.iter()),bounds)
        node,bounds,source,truth=self.structure();ET.SubElement(node,'image',dict(id='external',href='https://example.invalid/logo.png'));bounds['external']=Rect(1,1,1,1)
        self.assertIn('EXTERNAL_COMPONENT_DEPENDENCY',components(node,source,bounds)['unresolved'])

    def score(self, truncate=False,semantic_text_ids=None,unreviewed=False):
        node,bounds,source,truth=self.structure()
        if semantic_text_ids is not None:truth['text_component_ids']=semantic_text_ids
        if unreviewed:truth.pop('text_component_ids')
        evidence=validate_truth(truth,source,list(node.iter()),bounds)
        gold,prediction,policy=fixtures.QualityDomainTests.fixture(self)
        rect=dict(x=60,y=2,w=6,h=3)
        gold['objects'].append(dict(id='gold-logo',slot_id='logo',kind='logo',owner=None,rect=rect,text='',object_type='LOGO_PART',classification='LOGO',component_truth=evidence))
        work=prediction['predictions'][0];work['slots'].append(dict(id='logo',kind='logo',owner=None))
        candidate=components(node,source,bounds)
        if truncate:candidate['component_ids']=['mark'];candidate['text_component_ids']=[]
        work['observations'].append(dict(id='pred-logo',slot_id='logo',region=rect,text='',object_type='LOGO_PART',classification='LOGO',component_prediction=candidate))
        return evaluate_source([gold],prediction,policy,complete_source_gold=True)

    def test_same_bbox_truncated_logo_is_critical_and_logo_text_remains_denominator(self):
        correct=self.score();bad=self.score(True)
        self.assertEqual(correct['domains']['whole_logo']['metrics']['tp'],1)
        self.assertEqual(bad['critical_errors']['truncated_or_misgrouped_logo'],1)
        self.assertEqual(bad['domains']['whole_logo']['metrics']['fn'],1)
        self.assertEqual(bad['domains']['text_candidates']['metrics']['fn'],1)

    def test_actual_path_tag_cannot_erase_human_confirmed_outlined_logo_text(self):
        result=self.score(semantic_text_ids=['mark','label'])
        text=result['domains']['text_candidates']
        self.assertEqual(text['required_gold'],25)
        self.assertEqual(text['metrics']['fn'],1)
        self.assertEqual(result['domains']['whole_logo']['metrics']['tp'],1)

    def test_no_manual_text_partition_keeps_logo_text_completeness_unknown(self):
        result=self.score(unreviewed=True)
        self.assertEqual(result['domains']['text_candidates']['state'],'EVIDENCE_INSUFFICIENT')
        self.assertIsNone(result['domains']['text_candidates']['metrics'])

    def test_manual_nested_outline_word_group_is_one_text_region_and_cannot_double_count_glyph(self):
        node=ET.fromstring('<g id="logo"><g id="word"><path id="glyph1"/><path id="glyph2"/></g><circle id="mark"/></g>')
        bounds=dict(word=Rect(1,1,4,2),glyph1=Rect(1,1,2,2),glyph2=Rect(3,1,2,2),mark=Rect(6,1,2,2))
        source=dict(hash='0'*64,file_hashes=dict(svg='1'*64));evidence=dict(root_id='logo',component_ids=['glyph1','glyph2','mark'],text_component_ids=['word'],review_reason='Manual complete outlined word correspondence',original_correspondence_confirmed=True)
        truth=validate_truth(evidence,source,list(node.iter()),bounds)
        self.assertEqual(truth['text_component_ids'],['word']);self.assertEqual(truth['text_paint_ids'],['glyph1','glyph2'])
        with self.assertRaises(ValueError):validate_truth(dict(evidence,text_component_ids=['word','glyph1']),source,list(node.iter()),bounds)


class ActualLogoPipelineTests(unittest.TestCase):
    setUp=source_fixture.QualityGoldSetTests.setUp

    def test_actual_renderer_source_pipeline_retains_all_authored_logo_components(self):
        from template_ai.importer import import_file
        from template_ai.quality_pipeline import QualityPipelines
        path=self.root/'authored-logo.svg'
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect id="card" width="90" height="54" fill="white"/><g id="brand-logo"><circle id="mark" cx="60" cy="10" r="2"/><text id="label" x="65" y="12" font-size="3">Synthetic Brand</text></g></svg>')
        source=self.library.add_source(path,import_file(path,self.library.assets))
        service=QualityPipelines(self.library);pipeline=service.freeze('Actual source Logo components',None,'Synthetic reviewer',True)
        prediction=service.predict_source(pipeline['id'],source['id'])
        logos=[obs for work in prediction['predictions'] for obs in work['observations'] if obs['classification']=='LOGO']
        self.assertEqual(len(logos),1)
        self.assertEqual(logos[0]['component_prediction']['component_ids'],['label','mark'])
        self.assertEqual(logos[0]['component_prediction']['original_correspondence'],'REQUIRES_HUMAN_REVIEW')
