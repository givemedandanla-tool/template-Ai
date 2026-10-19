"""Independent authored sources exercise the installed converters and Qt raster."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QMarginsF, QRectF, QSizeF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPageLayout, QPageSize, QPdfWriter
from PySide6.QtWidgets import QApplication, QDialog

from template_ai.background import file_digest
from template_ai.importer import import_file
from template_ai.recovery_diagnostics import issue, shareable_report, export_shareable
from template_ai.source_recovery import compare_images
from template_ai.visual_font_match import match_fonts

APP=QApplication.instance() or QApplication([])
FONTS=Path('/usr/share/fonts/truetype/dejavu')


class LocalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_actual_inkscape_retains_original_semantic_text_separately_from_appearance(self):
        source=self.root/'private-client.svg'
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><text x="4" y="15" font-size="6">Alex <tspan font-weight="bold">Example</tspan></text></svg>')
        before=source.read_bytes();result=import_file(source,self.root/'assets')
        self.assertEqual(Path(result['semantic_svg']).read_bytes(),before)
        self.assertEqual(result['recovery']['semantic_status'],'ORIGINAL_TEXT')
        self.assertEqual(result['recovery']['counts']['text_nodes'],1)
        self.assertIn('semantic_svg',result['file_hashes'])
        self.assertTrue(import_file(source,self.root/'assets')['reused'])
        Path(result['semantic_svg']).write_text('corrupt')
        self.assertFalse(import_file(source,self.root/'assets')['reused'])
        self.assertEqual(source.read_bytes(),before)

    def test_visual_comparison_rejects_real_missing_content(self):
        a=QImage(200,100,QImage.Format_RGB32);a.fill(QColor('white'))
        painter=QPainter(a);painter.fillRect(QRectF(10,10,120,40),QColor('black'));painter.end()
        b=QImage(200,100,QImage.Format_RGB32);b.fill(QColor('white'))
        self.assertEqual(compare_images(a,a)['status'],'WITHIN_POLICY')
        self.assertEqual(compare_images(a,b)['status'],'REVIEW_REQUIRED')

    def test_shareable_report_rebuilds_fixed_values_and_excludes_all_private_payloads(self):
        secret='PRIVATE_customer_9999_C:/Users/Person/SecretFont.ttf'
        local=dict(source_kind=secret,semantic_status='NO_TEXT',counts=dict(text_nodes=2,path_nodes=4,private=secret),
            issues=[dict(issue('FONT_AMBIGUOUS'),message=secret,remedy=secret),dict(code=secret,log=secret)],
            source_path=secret,text=secret,font=secret,image=secret,sha256=secret)
        public=export_shareable(local,self.root/'support.json')
        self.assertNotIn(secret,json.dumps(public))
        self.assertEqual(public['source_kind'],'UNKNOWN')
        self.assertEqual(public['counts'],dict(text_nodes=2,path_nodes=4))
        self.assertEqual(len(public['issues']),2)

    def test_semantic_failure_does_not_turn_appearance_into_font_truth(self):
        from template_ai.source_recovery import recover_semantics
        source=self.root/'outlined.ai';source.write_text('not an editable source')
        semantic,report=recover_semantics(source,self.root,1,False,'synthetic-converter',
            run=lambda *args:(_ for _ in ()).throw(ValueError('private raw error')))
        self.assertEqual(semantic,'');self.assertEqual(report['semantic_status'],'FAILED')
        self.assertNotIn('private raw error',json.dumps(shareable_report(report)))

    def test_actual_pdf_compatible_ai_has_two_recovery_channels_and_fallback(self):
        source=self.root/'authored-pdf-compatible.ai'
        writer=QPdfWriter(str(source));writer.setPageSize(QPageSize(QSizeF(90,54),QPageSize.Millimeter))
        writer.setPageMargins(QMarginsF(0,0,0,0),QPageLayout.Millimeter);writer.setResolution(120)
        painter=QPainter(writer);font=QFont('DejaVu Sans');font.setPixelSize(28);painter.setFont(font)
        painter.drawText(20,80,'Authored PDF 123');painter.end();del writer
        before=source.read_bytes();result=import_file(source,self.root/'assets')
        self.assertTrue(result['semantic_svg']);self.assertEqual(result['recovery']['semantic_status'],'DERIVATIVE_TEXT')
        self.assertGreater(result['recovery']['counts']['text_nodes'],0)
        self.assertIn('visual_comparison',result['recovery'])
        with patch('template_ai.importer._run',side_effect=ValueError('authored converter failure')):
            fallback=import_file(source,self.root/'fallback-assets')
        self.assertIn('Qt PDF',fallback['engine'])
        self.assertIn('CONVERSION_FAILED',[row['code'] for row in fallback['recovery']['issues']])
        self.assertEqual(source.read_bytes(),before)


class VisualFontMatchingTests(unittest.TestCase):
    def faces(self):
        return [dict(path=str(FONTS/name),sha256=file_digest(FONTS/name),face_index=0)
                for name in ('DejaVuSans.ttf','DejaVuSansMono.ttf','DejaVuSerif.ttf')]

    def reference(self,text='MONO 1234 AV',family='DejaVu Sans Mono',pixel_size=54,hscale=.87):
        # Independent raster draw, not the matcher outline generation function.
        image=QImage(700,130,QImage.Format_RGB32);image.fill(QColor('white'))
        painter=QPainter(image)
        try:
            painter.setRenderHint(QPainter.TextAntialiasing)
            font=QFont(family);font.setPixelSize(pixel_size);font.setHintingPreference(QFont.PreferNoHinting)
            font.setStyleStrategy(QFont.NoFontMerging);painter.setFont(font)
            painter.scale(hscale,1);painter.setPen(QColor('black'));painter.drawText(20,90,text)
        finally:painter.end()
        return image

    def test_real_outline_matching_finds_known_font_with_scale_and_physical_size(self):
        report=match_fonts(self.reference(),[dict(text='MONO 1234 AV',origin='REVIEWED_TEXT')],self.faces(),
                           pixels_per_mm=6.,tracking_options=(0.,))
        self.assertEqual(report['status'],'CANDIDATE',report)
        first=report['candidates'][0]
        self.assertEqual(first['family'],'DejaVu Sans Mono')
        self.assertAlmostEqual(first['horizontal_scale'],.87,delta=.04)
        self.assertAlmostEqual(first['size_pt'],54/6*72/25.4,delta=.7)
        self.assertTrue(report['search_complete'])

    def test_duplicate_faces_are_ambiguous_and_incomplete_search_is_explicit(self):
        faces=self.faces();mono=faces[1]
        texts=[dict(text='MONO 1234 AV',origin='OCR')]
        report=match_fonts(self.reference(),texts,[mono,dict(mono)],tracking_options=(0.,))
        self.assertEqual(report['status'],'AMBIGUOUS')
        self.assertIsNone(report['candidates'][0]['size_pt'])
        self.assertIn('OCR_REVIEW_REQUIRED',[row['code'] for row in report['issues']])
        short=match_fonts(self.reference(),texts,faces,max_faces=1,tracking_options=(0.,))
        self.assertFalse(short['search_complete']);self.assertEqual(short['omitted_faces'],2)
        self.assertEqual(short['next_offset'],1)

    def test_wrong_text_missing_font_and_cancel_do_not_claim_identification(self):
        faces=self.faces()
        wrong=match_fonts(self.reference(),[dict(text='ZZZZZZZZZZ',origin='OCR')],faces,tracking_options=(0.,),maximum_error=.02)
        self.assertEqual(wrong['status'],'NO_MATCH')
        changed=dict(faces[0],sha256='0'*64)
        broken=match_fonts(self.reference(),[dict(text='MONO 1234 AV',origin='REVIEWED_TEXT')],[changed])
        self.assertFalse(broken['search_complete']);self.assertEqual(broken['status'],'NO_MATCH')
        cancelled=match_fonts(self.reference(),[dict(text='MONO',origin='OCR')],faces,cancelled=lambda:True)
        self.assertEqual(cancelled['checked_faces'],0);self.assertFalse(cancelled['search_complete'])

    def test_actual_local_tesseract_text_then_font_matching(self):
        from template_ai.quality_ocr import freeze
        from template_ai.visual_font_match import ocr_text_candidates
        with tempfile.TemporaryDirectory() as directory:
            record=freeze(Path(directory),dict(languages=['eng'],psm=6))
            crop=self.reference('MONO 1234',hscale=1.)
            rows=ocr_text_candidates(crop,record)
            self.assertEqual(len(rows),1,rows);self.assertEqual(rows[0]['text'],'MONO 1234')
            result=match_fonts(crop,rows,self.faces(),tracking_options=(0.,))
        self.assertEqual(result['candidates'][0]['family'],'DejaVu Sans Mono')
        self.assertIn('OCR_REVIEW_REQUIRED',[row['code'] for row in result['issues']])


class RecoveryDialogTests(unittest.TestCase):
    def test_local_diagnostic_dialog_crops_field_and_exports_only_public_projection(self):
        from template_ai.storage import Library
        from template_ai.recovery_dialog import RecoveryDialog
        from training_fixture import source_work
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);library=Library(root/'data')
            class Window(QDialog):pass
            window=Window();window.library=library
            source,work=source_work(library,root)
            dialog=RecoveryDialog(window,source,work=work,field=work['payload']['slots'][0])
            try:
                self.assertGreater(dialog.crop().width(),0)
                self.assertIn('NO_SOURCE_TEXT_PATH',dialog.public.toPlainText())
                self.assertNotIn(str(root),dialog.public.toPlainText())
                self.assertFalse(dialog.verified.isChecked())
            finally:dialog.close();window.close();library.close()
