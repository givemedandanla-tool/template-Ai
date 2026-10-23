"""實際 Tesseract 推論與版本／來源保護；不是以模擬字串代替OCR驗證。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QImage,QPainter
from PySide6.QtWidgets import QApplication

from template_ai.logo_assets import checked_payload
from template_ai.logo_ocr import capability,recognize,annotate
from template_ai.logo_store import LogoStore
from template_ai.storage import Library
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from install_ocr_models import install,FILES

APP=QApplication.instance() or QApplication([])


class LogoOcrTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.library=Library(self.root/'library');self.store=LogoStore(self.library)
        path=self.root/'synthetic.png';image=QImage(1000,300,QImage.Format_RGB32);image.fill(Qt.white)
        painter=QPainter(image);font=QFont('DejaVu Sans');font.setPixelSize(70);painter.setFont(font);painter.setPen(Qt.black);painter.drawText(50,150,'EXAMPLE BRAND');painter.end();image.save(str(path))
        self.payload=checked_payload(dict(image=str(path),svg='',source_width_mm=100,source_height_mm=30,crop=None))

    def tearDown(self):self.library.close();self.temp.cleanup()

    def test_real_local_inference_reports_words_geometry_and_only_unconfirmed_hints(self):
        context=capability();self.assertTrue(context['available'],context)
        self.assertEqual(set(context['languages']),{'eng','chi_tra'})
        result=recognize(self.payload);words=' '.join(r['text'] for r in result['words']).upper()
        self.assertIn('EXAMPLE',words);self.assertIn('BRAND',words)
        self.assertEqual(result['company_identity'],'UNCONFIRMED');self.assertEqual(result['native_editability'],'UNKNOWN')
        self.assertEqual(result['missing_languages'],[])
        for word in result['words']:
            rect=word['source_region_mm'];self.assertGreater(rect['w'],0);self.assertGreater(rect['h'],0)
            self.assertGreaterEqual(rect['x'],0);self.assertLessEqual(rect['x']+rect['w'],100)
        self.assertEqual(self.library.logos(),[])

    def test_actual_ocr_attaches_to_candidate_with_cas_and_never_approves_or_rewrites_image(self):
        candidate=self.store.propose(self.payload,90,54);before=Path(self.payload['image']).read_bytes()
        updated=annotate(self.store,candidate['id'],candidate['revision'])
        self.assertEqual(updated['state'],'PENDING');self.assertEqual(updated['revision'],candidate['revision']+1)
        self.assertTrue(updated['evidence']['ocr']['words'])
        self.assertEqual(Path(self.payload['image']).read_bytes(),before);self.assertEqual(self.library.logos(),[])
        with self.assertRaises(ValueError):annotate(self.store,candidate['id'],candidate['revision'])

    def test_missing_engine_and_changed_source_never_fabricate_ocr(self):
        with patch.dict('os.environ',{'TEMPLATE_AI_TESSERACT':str(self.root/'missing-tesseract')}):
            self.assertFalse(capability()['available'])
            with self.assertRaises(ValueError):recognize(self.payload)
        Path(self.payload['image']).write_bytes(b'not an image')
        with self.assertRaises(ValueError):recognize(self.payload)

    def test_rejected_during_inference_cannot_be_overwritten_by_late_ocr(self):
        candidate=self.store.propose(self.payload,90,54)
        def changed(_):
            self.store.reject(candidate['id'],candidate['revision'],'Synthetic concurrent rejection',True)
            return dict(words=[],method='NOT_COMMITTED')
        with patch('template_ai.logo_ocr.recognize',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'候選已變更'):annotate(self.store,candidate['id'],candidate['revision'])
        current=self.store.proposal(candidate['id']);self.assertEqual(current['state'],'REJECTED')
        self.assertNotIn('ocr',current['evidence'])

    def test_model_installer_refuses_changed_blob_and_never_overwrites_user_file(self):
        directory=self.root/'models';directory.mkdir()
        for name in FILES:(directory/name).write_bytes(b'Synthetic unexpected local model')
        with patch('urllib.request.urlopen') as fetch:
            with self.assertRaisesRegex(ValueError,'Git blob不符'):install(directory)
            fetch.assert_not_called()
        self.assertEqual((directory/'chi_tra.traineddata').read_bytes(),b'Synthetic unexpected local model')
