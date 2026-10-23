"""Original-crop/candidate comparison uses real installed font outlines."""
import hashlib
from io import BytesIO
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QRawFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from template_ai.review_tool.font_dialog import FontReviewDialog


APP=QApplication.instance() or QApplication([])


def local_test_font():
    windows=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    choices=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
             Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),
             windows/'arial.ttf',windows/'segoeui.ttf']
    return next((p for p in choices if p.is_file()),None)


class ReviewFontDialogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.image=Path(self.temp.name)/'page.png'
        image=QImage(1000,500,QImage.Format.Format_RGB32);image.fill(QColor('white'))
        painter=QPainter(image);painter.fillRect(240,150,100,40,QColor('#114477'));painter.end()
        self.assertTrue(image.save(str(self.image)))
        self.before=hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.page=dict(image=str(self.image),width_mm=100,height_mm=50)
        self.work=dict(crop=dict(x=20,y=10,w=60,h=30),image=str(self.image))
        self.field=dict(id='field',text='Example 123',rect=dict(x=4,y=5,w=10,h=4))
        self.dialog=FontReviewDialog(self.page,self.work,self.field)

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.image.read_bytes()).hexdigest(),self.before)
        self.dialog.close();self.dialog.deleteLater();APP.sendPostedEvents();APP.processEvents()
        self.temp.cleanup()

    def show(self):
        self.dialog.show();APP.processEvents();self.dialog.load_families();APP.processEvents()

    def choose_family(self):
        self.show()
        self.dialog.filter_edit.setText('DejaVu Sans' if os.name!='nt' else 'Arial')
        APP.processEvents()
        if not self.dialog.family_list.count():
            self.dialog.filter_edit.clear();APP.processEvents()
        for i in range(self.dialog.family_list.count()):
            self.dialog.family_list.setCurrentRow(i)
            if self.dialog.render_candidate():return
        self.fail('No installed font could render the synthetic Latin example.')

    def test_original_crop_uses_page_image_and_work_offset(self):
        crop=self.dialog.source_crop
        self.assertEqual((crop.width(),crop.height()),(100,40))
        self.assertEqual(crop.pixelColor(50,20),QColor('#114477'))
        self.assertFalse(self.dialog.original_preview.image.isNull())

    def test_font_catalogue_is_deferred_until_dialog_event_loop(self):
        self.assertFalse(self.dialog.families_loaded)
        self.assertEqual(self.dialog.family_list.count(),0)
        self.show()
        self.assertTrue(self.dialog.families_loaded)
        self.assertGreater(self.dialog.family_list.count(),0)

    def test_family_choice_is_annotation_with_unknown_file_and_no_source_pt(self):
        self.choose_family()
        self.assertTrue(self.dialog.use_button.isEnabled())
        self.assertFalse(self.dialog.candidate_preview.image.isNull())
        self.assertIsNone(self.dialog.annotation())
        QTest.mouseClick(self.dialog.use_button,Qt.MouseButton.LeftButton)
        self.assertEqual(self.dialog.result(),QDialog.DialogCode.Accepted)
        annotation=self.dialog.annotation()
        self.assertEqual(annotation['method'],'HUMAN_VISUAL_REVIEW')
        self.assertEqual(annotation['font_file_identity'],'UNKNOWN')
        self.assertIsNone(annotation['file_sha256'])
        self.assertFalse(annotation['pt_confirmed'])
        self.assertFalse(annotation['native_source_font_identity_confirmed'])
        self.assertNotIn('font_size_pt',annotation)
        self.assertNotIn('source_pt',annotation)

    def test_filter_limits_display_without_claiming_other_fonts_absent(self):
        self.show();self.dialog.filter_edit.setText('no-such-example-family-0199')
        APP.processEvents()
        self.assertEqual(self.dialog.family_list.count(),0)
        self.assertFalse(self.dialog.use_button.isEnabled())

    def test_unknown_and_cancel_never_confirm_candidate(self):
        self.choose_family()
        QTest.mouseClick(self.dialog.unknown_button,Qt.MouseButton.LeftButton)
        self.assertTrue(self.dialog.kept_unknown)
        self.assertIsNone(self.dialog.annotation())
        self.assertEqual(self.dialog.result(),QDialog.DialogCode.Rejected)

    def test_missing_glyph_is_not_silently_substituted(self):
        self.dialog.text=chr(0x10ffff)
        self.show()
        self.assertFalse(self.dialog.render_candidate())
        self.assertFalse(self.dialog.use_button.isEnabled())
        self.assertIn('缺少',self.dialog.status_label.text())

    def test_missing_original_prevents_false_visual_confirmation(self):
        self.dialog.source_crop=QImage()
        self.show()
        self.assertFalse(self.dialog.render_candidate())
        self.assertFalse(self.dialog.use_button.isEnabled())
        self.assertIn('原稿裁切',self.dialog.status_label.text())

    def test_explicit_font_file_retains_real_hash_and_face(self):
        path=local_test_font()
        self.assertIsNotNone(path,'Expected an actual test font on this desktop platform.')
        self.show()
        self.assertTrue(self.dialog.load_font_file(path),self.dialog.status_label.text())
        self.dialog.accept_choice()
        annotation=self.dialog.annotation()
        self.assertEqual(annotation['font_file_identity'],'VERIFIED_LOCAL_FILE_FACE')
        self.assertEqual(annotation['file_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(annotation['face_index'],0)
        self.assertFalse(annotation['pt_confirmed'])

    def test_changed_font_file_is_not_accepted_as_previous_candidate(self):
        path=local_test_font();self.assertIsNotNone(path)
        owned=Path(self.temp.name)/'test-font.ttf';shutil.copy2(path,owned)
        self.show();self.assertTrue(self.dialog.load_font_file(owned))
        owned.write_bytes(owned.read_bytes()+b'\0')
        self.dialog.accept_choice()
        self.assertIsNone(self.dialog.annotation())
        self.assertFalse(self.dialog.use_button.isEnabled())

    def test_localized_family_alias_is_verified_against_real_font_name_table(self):
        from fontTools.ttLib import TTFont
        path=local_test_font();self.assertIsNotNone(path)
        with TTFont(path) as font:
            font['name'].setName('測試字型名稱',1,3,1,0x0404)
            font['name'].setName('測試字型名稱',16,3,1,0x0404)
            data=BytesIO();font.save(data)
        raw=QRawFont(QByteArray(data.getvalue()),96)
        self.assertTrue(raw.isValid())
        self.assertTrue(self.dialog._matches_family(raw,'測試字型名稱'))
        self.assertFalse(self.dialog._matches_family(raw,'Unrelated candidate family'))


if __name__=='__main__':unittest.main()
