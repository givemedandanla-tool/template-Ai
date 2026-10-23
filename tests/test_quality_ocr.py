import copy
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QFont,QColor
import test_quality_gold_sets as fixtures
from template_ai.quality_ocr import parse_tsv,freeze,verify
from template_ai.quality_pipeline import QualityPipelines
from template_ai.importer import import_file

APP=QApplication.instance() or QApplication([])
HEADER='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'


class QualityOcrTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp

    def image_source(self):
        image=QImage(1200,720,QImage.Format_ARGB32);image.fill(QColor('white'));image.setDotsPerMeterX(11811);image.setDotsPerMeterY(11811)
        painter=QPainter(image);font=QFont('DejaVu Sans');font.setPixelSize(48);painter.setFont(font);painter.setPen(QColor('black'));painter.drawText(60,140,'Email: qa@example.test');painter.drawText(60,240,'Name: Alex Example');painter.end()
        path=self.root/'authored-ocr-source.png';self.assertTrue(image.save(str(path)))
        return self.library.add_source(path,import_file(path,self.library.assets))

    def test_actual_local_tesseract_pipeline_runs_without_gold_and_preserves_observations(self):
        source=self.image_source();service=QualityPipelines(self.library);pipeline=service.freeze('Actual local English OCR',None,'Synthetic reviewer',True,ocr_config=dict(languages=['eng'],psm=6))
        before=self.store.epoch
        with patch.object(service.store,'facts',side_effect=AssertionError('No holdout facts as OCR inputs')):
            result=service.predict_source(pipeline['id'],source['id'])
        self.assertTrue(result['capabilities']['ocr_executed'])
        observations=[o for work in result['predictions'] for o in work['observations']]
        self.assertTrue(any(o.get('semantic',{}).get('semantic_type')=='email' for o in observations))
        self.assertTrue(all('ocr_word_confidences' in o for o in observations))
        self.assertEqual(self.store.epoch,before)
        self.assertFalse(pipeline['manifest']['ocr']['raw_text_confidence_filter'])

    def test_low_confidence_tsv_words_are_not_silently_removed_or_clipped(self):
        raw=HEADER+'5\t1\t1\t1\t1\t1\t10\t10\t20\t10\t0.5\tEmail:\n5\t1\t1\t1\t1\t2\t35\t10\t40\t10\t1.0\tqa@example.test\n'
        result=parse_tsv(raw,100,100,90,54)
        self.assertEqual(result[0]['text'],'Email: qa@example.test')
        self.assertEqual(result[0]['word_confidences'],[.5,1.0])
        self.assertEqual(result[0]['rect'],dict(x=9,y=5.4,w=58.5,h=5.4))

    def test_invalid_nonempty_or_oversized_tsv_is_failure_not_empty_success(self):
        for row in ('5\t1\t1\t1\t1\t1\tbad\t1\t2\t2\t50\tReal text\n','5\t1\t1\t1\t1\t1\t99\t1\t20\t2\t50\tReal text\n','5\t1\t1\t1\t1\t1\t1\t1\t2\t2\t50\t'+'x'*2049+'\n'):
            with self.assertRaises(ValueError):parse_tsv(HEADER+row,100,100,90,54)
        with self.assertRaises(ValueError):parse_tsv('no valid engine output',100,100,90,54)

    def test_immutable_language_model_tamper_blocks_actual_pipeline(self):
        service=QualityPipelines(self.library);pipeline=service.freeze('Model hash pin',None,'Reviewer',True,ocr_config=dict(languages=['eng'],psm=11))
        model=Path(pipeline['manifest']['ocr']['models'][0]['path']);model.write_bytes(b'synthetic corrupt traineddata')
        self.assertFalse(service.validity(pipeline['id'])['valid'])
        with self.assertRaises(ValueError):service.predict_source(pipeline['id'],self.source['id'])

    def test_language_snapshot_retains_actual_older_bytes_when_installed_pack_changes(self):
        from template_ai.logo_ocr import capability
        original=capability();record=freeze(self.library.assets,dict(languages=['eng'],psm=11))
        different=self.root/'different-installed-models';different.mkdir();(different/'eng.traineddata').write_bytes(b'not the actual frozen language model')
        with patch('template_ai.logo_ocr.capability',return_value=dict(original,data_dir=str(different))):verify(record)
        self.assertNotEqual(Path(record['models'][0]['path']).read_bytes(),b'not the actual frozen language model')

    def test_unassigned_ocr_line_is_retained_and_blocks_false_complete_text_rate(self):
        import test_quality_domains as domain_fixture
        from template_ai.quality_domains import evaluate_source
        gold,prediction,policy=domain_fixture.QualityDomainTests.fixture(self)
        line=dict(key=[1,1,1,1],text='Unassigned source text',rect=dict(x=1,y=60,w=30,h=4))
        prediction['predictions'][0]['evidence']=dict(ocr=dict(unassigned_source_text_lines=[line]))
        result=evaluate_source([gold],prediction,policy,complete_source_gold=True)
        self.assertEqual(result['domains']['text_candidates']['state'],'EVIDENCE_INSUFFICIENT')
        self.assertTrue(any(c.get('reason')=='UNASSIGNED_SOURCE_TEXT_OUTSIDE_PREDICTED_WORKS' for c in result['cases']))
