"""Actual converter/OCR/worker regression for the small observation adapter."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QFont, QImage, QPainter, QPdfWriter, QPageSize
from PySide6.QtWidgets import QApplication

from template_ai.review_tool.analysis import analyse_file


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" viewBox="0 0 60 30">
<rect id="card" x="0" y="0" width="60" height="30" fill="white"/>
<text id="person" x="5" y="8" font-size="3">Alice</text>
<text id="phone" x="5" y="15" font-size="3">0900-000-000</text>
<text id="email" x="5" y="22" font-size="3">hello@example.com</text></svg>'''


class ReviewAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'source.svg'
        self.source.write_text(SVG)

    def tearDown(self):
        self.temp.cleanup()

    def analyse(self, **kwargs):
        return analyse_file(self.source, self.root/'cache', **kwargs)

    def make_pdf(self):
        path = self.root/'two-pages.pdf'
        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QSizeF(60, 30), QPageSize.Unit.Millimeter))
        writer.setResolution(72)
        painter = QPainter(writer)
        painter.setFont(QFont('DejaVu Sans', 8))
        painter.drawText(5, 16, 'alice@example.com')
        writer.newPage()
        painter.drawText(5, 16, 'bob@example.com')
        painter.end()
        return path

    def make_image(self):
        path = self.root/'text.png'
        image = QImage(1200, 400, QImage.Format.Format_RGB32)
        image.fill('white')
        painter = QPainter(image)
        painter.setPen('black')
        painter.setFont(QFont('DejaVu Sans', 42))
        painter.drawText(35, 180, 'HELLO EXAMPLE')
        painter.end()
        self.assertTrue(image.save(str(path)))
        return path

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_real_svg_geometry_semantics_original_immutable_and_unknown_typography(self):
        before = self.source.read_bytes();events=[]
        result=self.analyse(progress_callback=events.append, ocr=False)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(result['source']['hash'], hashlib.sha256(before).hexdigest())
        self.assertEqual(result['status'], 'ANALYSED')
        self.assertEqual(len(result['works']), 1)
        work=result['works'][0]
        self.assertAlmostEqual(work['crop']['w'],60,places=3)
        fields={f['text']:f for f in work['fields']}
        self.assertEqual(fields['hello@example.com']['kind'],'email')
        self.assertEqual(fields['0900-000-000']['kind'],'mobile')
        for field in fields.values():
            self.assertIsNone(field['owner'])
            self.assertEqual(field['review_state'],'UNCHECKED')
            self.assertIsNone(field['measurements']['baseline']['value'])
            self.assertEqual(field['measurements']['container_bounds']['status'],'UNKNOWN')
            self.assertEqual(field['measurements']['distribution']['status'],'UNKNOWN')
            self.assertAlmostEqual(field['source_rect']['x'],field['rect']['x']+work['crop']['x'])
            self.assertEqual(field['prediction']['rect'],field['rect'])
        self.assertTrue(result['capabilities']['inkscape_conversion_executed'])
        self.assertTrue(result['capabilities']['vector_analysis_executed'])
        self.assertFalse(result['capabilities']['ocr_executed'])
        self.assertEqual(result['capabilities']['inkscape_runtime']['origin'],'EXTERNAL')
        self.assertTrue(work['geometry_relations'])
        ids={field['id'] for field in fields.values()}
        for relation in work['geometry_relations']:
            self.assertTrue(set(relation['field_ids'])<=ids)
            self.assertEqual(relation['alignment_status'],'UNKNOWN')
            self.assertEqual(relation['policy_status'],'NOT_EVALUATED')
            first=next(f for f in fields.values() if f['id']==relation['source'])
            second=next(f for f in fields.values() if f['id']==relation['target'])
            self.assertAlmostEqual(relation['measurements']['left_residual_mm']['value'],
                                   second['rect']['x']-first['rect']['x'])
        for key in ['original_evidence','analysis_evidence']:
            ref=result['pages'][0][key]
            self.assertEqual(hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest(),ref['sha256'])
        self.assertEqual(events[0]['stage'],'validate')
        self.assertTrue(any(e['stage']=='original_text' for e in events))
        checkpoint=next(e for e in events if 'checkpoint_path' in e)
        self.assertEqual(hashlib.sha256(Path(checkpoint['checkpoint_path']).read_bytes()).hexdigest(),checkpoint['checkpoint_sha256'])
        self.assertTrue(json.loads(Path(checkpoint['checkpoint_path']).read_text())['analysis_in_progress'])

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_reanalysis_has_stable_work_and_field_ids(self):
        first=self.analyse(ocr=False);second=self.analyse(ocr=False)
        self.assertEqual([w['id'] for w in first['works']],[w['id'] for w in second['works']])
        self.assertEqual([f['id'] for w in first['works'] for f in w['fields']],
                         [f['id'] for w in second['works'] for f in w['fields']])

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_unframed_multiple_size_notes_are_review_candidates(self):
        self.source.write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="160mm" height="60mm" viewBox="0 0 160 60">
<text id="a" x="10" y="15" font-size="3">a@example.com</text>
<text id="b" x="10" y="22" font-size="3">0900-000-000</text>
<text id="s1" x="10" y="40" font-size="3">60 x 30 mm</text>
<text id="c" x="100" y="15" font-size="3">b@example.com</text>
<text id="d" x="100" y="22" font-size="3">0912-000-000</text>
<text id="s2" x="100" y="40" font-size="3">60 x 30 mm</text></svg>''')
        result=self.analyse(ocr=False)
        self.assertEqual(len(result['works']),2)
        values=[f['text'] for w in result['works'] for f in w['fields']]
        self.assertIn('a@example.com',values);self.assertIn('b@example.com',values)
        for work in result['works']:
            self.assertFalse(work['reviewed'])
            self.assertTrue(any(i['code']=='WORK_RANGE_UNCONFIRMED' for i in work['issues']))
            self.assertEqual(work['evidence']['native_illustrator_mapping'],'UNKNOWN')

    def test_real_two_page_pdf_preserves_page_identity_and_preview(self):
        self.source=self.make_pdf()
        result=self.analyse(ocr=False)
        self.assertEqual(result['source']['page_count'],2)
        self.assertEqual([p['page'] for p in result['pages']],[1,2])
        self.assertEqual({w['page'] for w in result['works']},{1,2})
        for page in result['pages']:
            self.assertTrue(Path(page['image']).is_file())
            self.assertAlmostEqual(page['width_mm'],60,delta=.5)

    def test_real_page_one_survives_injected_second_page_import_failure(self):
        self.source=self.make_pdf()
        from template_ai.importer import import_file
        def fail_second(path,assets,page=1):
            if page==2:raise ValueError('synthetic second page conversion failure')
            return import_file(path,assets,page=page)
        with patch('template_ai.importer.import_file',side_effect=fail_second):
            result=self.analyse(ocr=False)
        self.assertEqual(result['status'],'PARTIAL')
        self.assertEqual([p['page'] for p in result['pages']],[1])
        self.assertTrue(result['works'])
        self.assertTrue(any(i['code']=='PAGE_IMPORT_FAILED' and i['page']==2 for i in result['issues']))

    @unittest.skipUnless(shutil.which('tesseract'), 'actual Tesseract is required')
    def test_actual_ocr_binary_stdin_handles_deep_unicode_image_and_model_paths(self):
        from template_ai.review_tool.analysis import _ocr_capability, _ocr_observations
        cap = _ocr_capability()
        self.assertTrue(cap['available'], cap.get('reason'))
        original = self.make_image()
        deep = self.root / '中文影像'
        while len(str(deep.resolve())) < 320:
            deep /= 'deep-image-location-' + 'a' * 24
        deep.mkdir(parents=True)
        image = deep / '待判讀的測試圖片.png'
        shutil.copyfile(original, image)
        before = image.read_bytes()
        model_dir = self.root / '繁體模型'
        while len(str(model_dir.resolve())) < 220:
            model_dir /= 'fixed-model-location-' + 'b' * 18
        model_dir.mkdir(parents=True)
        for language in ('eng', 'chi_tra'):
            shutil.copyfile(Path(cap['data_dir']) / (language + '.traineddata'),
                            model_dir / (language + '.traineddata'))
        selected = dict(cap, data_dir=str(model_dir.resolve()))
        real_popen = subprocess.Popen
        staged = []
        def launch(*args, **kwargs):
            directory = Path(kwargs['cwd'])
            for language in ('eng', 'chi_tra'):
                name = language + '.traineddata'
                self.assertEqual((directory / name).read_bytes(), (model_dir / name).read_bytes())
            staged.append(directory)
            return real_popen(*args, **kwargs)
        with patch('template_ai.ocr_runtime.uses_model_stage', return_value=True), \
                patch('template_ai.review_tool.analysis.subprocess.Popen', side_effect=launch) as launched:
            lines, proof = _ocr_observations({'image': str(image), 'width_mm': 120., 'height_mm': 40.}, selected)
        text = ' '.join(line['text'] for line in lines)
        self.assertIn('HELLO', text)
        self.assertIn('EXAMPLE', text)
        self.assertGreater(len(str(image.resolve())), 260)
        self.assertEqual(launched.call_args.args[0][1:3], ['stdin', 'stdout'])
        self.assertTrue(Path(launched.call_args.kwargs['stdin'].name).samefile(image))
        self.assertEqual(len(staged), 1)
        self.assertFalse(staged[0].exists())
        self.assertEqual(proof['model_transport'], 'VERIFIED_SHORT_LOCAL_STAGE')
        self.assertEqual(proof['image_transport'], 'STDIN_BINARY_IMAGE')
        self.assertEqual(set(proof['languages']), {'eng', 'chi_tra'})
        for line in lines:
            rect = line['rect']
            self.assertGreater(rect['w'], 0)
            self.assertGreater(rect['h'], 0)
            self.assertGreaterEqual(rect['x'], 0)
            self.assertGreaterEqual(rect['y'], 0)
            self.assertLessEqual(rect['x'] + rect['w'], 120.)
            self.assertLessEqual(rect['y'] + rect['h'], 40.)
        self.assertEqual(image.read_bytes(), before)

    @unittest.skipUnless(shutil.which('tesseract'), 'actual Tesseract is required')
    def test_actual_ocr_on_raster_does_not_fabricate_physical_sizes(self):
        self.source=self.make_image()
        result=self.analyse(ocr=True)
        self.assertTrue(result['capabilities']['ocr_available'])
        self.assertTrue(result['capabilities']['ocr_executed'])
        fields=[f for w in result['works'] for f in w['fields']]
        self.assertTrue(any('HELLO' in f['text'] for f in fields))
        for field in fields:
            self.assertIsNone(field['measurements']['width_mm']['value'])
            self.assertEqual(field['measurements']['width_mm']['status'],'UNKNOWN')
            self.assertEqual(field['evidence']['native_illustrator_mapping'],'UNKNOWN')
        self.assertTrue(any(i['code']=='PHYSICAL_SIZE_UNCALIBRATED' for i in result['issues']))

    def test_missing_ocr_keeps_manual_work_instead_of_empty_success(self):
        self.source=self.make_image()
        with patch.dict(os.environ,{'PATH':'/nonexistent','TEMPLATE_AI_TESSERACT':'/nonexistent/tesseract',
                                  'TEMPLATE_AI_BUNDLED_TESSERACT_ROOT':''}):
            result=self.analyse(ocr=True)
        self.assertFalse(result['capabilities']['ocr_available'])
        self.assertFalse(result['capabilities']['ocr_executed'])
        self.assertTrue(result['works'])
        self.assertEqual(result['works'][0]['fields'],[])
        self.assertEqual(result['status'],'PARTIAL')
        self.assertTrue(any(i['code']=='OCR_UNAVAILABLE' for i in result['issues']))

    def test_worker_uses_real_json_lines_protocol_and_actual_analysis(self):
        request=self.root/'request.json'
        request.write_text(json.dumps({'path':str(self.source),'cache_dir':str(self.root/'worker-cache'),'ocr':False}))
        env=os.environ.copy();env['QT_QPA_PLATFORM']='offscreen'
        process=subprocess.run([sys.executable,'-m','template_ai.review_tool.worker',str(request)],
                               cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=90)
        self.assertEqual(process.returncode,0,process.stderr[-1000:])
        events=[json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(events[0]['type'],'progress')
        self.assertEqual(events[-1]['type'],'result')
        self.assertTrue(events[-1]['result']['works'])
        self.assertTrue(any(e.get('checkpoint_path') for e in events))

    def test_worker_invalid_request_error_is_content_free(self):
        request=self.root/'invalid.json';request.write_text('{bad')
        process=subprocess.run([sys.executable,'-m','template_ai.review_tool.worker',str(request)],
                               cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
        self.assertEqual(process.returncode,1)
        error=json.loads(process.stdout.splitlines()[-1])
        self.assertEqual(error['type'],'error')
        self.assertNotIn(str(self.root),error['message'])
        self.assertNotIn('{bad',error['message'])


if __name__=='__main__':
    unittest.main()
