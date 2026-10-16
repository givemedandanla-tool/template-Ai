"""Real local OCR and confirmed whole-logo metadata; race and snapshot failure boundaries."""
import json,unittest
from unittest.mock import patch
import test_quality_gold_sets as fixture
import test_quality_ocr as ocr_fixture
import test_trusted_samples as sample_fixture
from quality_acceptance_fixture import actual_positive_pair
from template_ai.qualified_coverage import QualifiedCoverage
from template_ai.quality_pipeline import QualityPipelines

class QualifiedCoverageEvidenceTests(unittest.TestCase):
    setUp=fixture.QualityGoldSetTests.setUp
    def test_verified_composite_logo_metadata_is_reused_without_reclassifying_unknown_as_plain_vector(self):
        actual_positive_pair(self,execute=False);report=QualifiedCoverage(self.library).report(collection='QUALITY_HOLDOUT');self.assertIn('TEXT_AND_VECTOR',report['facets']['logo']);self.assertIn('NO_LOGO',report['facets']['logo']);self.assertFalse(report['quality_pass_claim']);self.assertEqual(report['counts']['distinct_source_files'],2);self.assertEqual(report['counts']['declared_related_groups'],1);self.assertTrue(report['independence_unknown'])
    def test_actual_local_ocr_source_admission_counts_recorded_ocr_without_loading_model_again(self):
        source=ocr_fixture.QualityOcrTests.image_source(self);service=QualityPipelines(self.library);pipeline=service.freeze('Actual local source OCR metadata',None,'Synthetic reviewer',True,ocr_config=dict(languages=['eng'],psm=6));prediction=service.predict_source(pipeline['id'],source['id']);hypothesis=prediction['predictions'][0]
        self.assertTrue(hypothesis['evidence']['ocr']['executed']);payload={key:hypothesis[key] for key in ('crop','work_width','work_height','slots','company_bindings')};payload.update(visual_confirmed=True,analysis_evidence=hypothesis['evidence'],analysis_key=hypothesis['key'],analysis_version=hypothesis['analysis_version']);work=self.library.create_artwork(source['id'],'Authored source, actual OCR then human review',payload)
        observations=[{key:o[key] for key in ('id','slot_id','text','object_type','classification','region','prior_prediction')} for o in hypothesis['observations']];saved=self.store.save_facts(work['id'],observations,0,work['revision']);self.store.confirm_facts(work['id'],[o['id'] for o in observations],saved['revision'],saved['pins'],self.store.source_proof(work['id']),'Synthetic source author manual review',True);sample_fixture.admitted(self.store,work)
        with patch('template_ai.quality_ocr.execute',side_effect=AssertionError('Stats must not rerun OCR')):
            report=QualifiedCoverage(self.library).report()
        self.assertEqual(report['facets']['ocr']['LOCAL_OCR_EXECUTION_RECORDED_NATIVE_UNKNOWN'],[work['id']]);self.assertIn('UNKNOWN',report['facets']['native_text']);self.assertFalse(report['model_weights_loaded'])
    def test_source_change_during_count_is_rejected_without_persisting_false_complete_snapshot(self):
        sample_fixture.admitted(self.store,self.work);service=QualifiedCoverage(self.library);original=service.stamp;calls=[]
        def changed(work_id):
            calls.append(work_id)
            if len(calls)==2:
                from pathlib import Path
                Path(self.source['original_path']).write_text('<svg>changed actual source during metadata scan</svg>')
            return original(work_id)
        with patch.object(service,'stamp',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'來源／作品改變'):service.report()
        self.assertEqual(self.store.count('COVERAGE_SNAPSHOT'),0)
    def test_late_snapshot_audit_failure_rolls_back_and_stored_snapshot_has_no_copied_personal_labels(self):
        sample=sample_fixture.admitted(self.store,self.work);service=QualifiedCoverage(self.library);epoch=self.store.epoch;original=self.library.event
        def fail(identity,action):
            if action=='training_descriptive_coverage_snapshot_saved_not_quality_gate':raise OSError('Injected snapshot persistence failure')
            return original(identity,action)
        with patch.object(self.library,'event',side_effect=fail):
            with self.assertRaises(OSError):service.report()
        self.assertEqual(self.store.epoch,epoch);self.assertEqual(self.store.count('COVERAGE_SNAPSHOT'),0);report=service.report();saved=self.store.get('COVERAGE_SNAPSHOT',report['snapshot_id']);self.assertNotIn(sample['positive_labels'][0]['text'],json.dumps(saved,ensure_ascii=False));self.assertNotIn('source_name',saved['rows'][0]);self.assertNotIn('work_name',saved['rows'][0])
