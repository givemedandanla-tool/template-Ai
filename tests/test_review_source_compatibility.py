"""Synthetic visible-notice cases; no private AI or Illustrator installation."""
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
from xml.sax.saxutils import escape

from PySide6.QtCore import QSizeF, QEventLoop, QTimer
from PySide6.QtGui import QFont, QImage, QPainter, QPdfWriter, QPageSize
from PySide6.QtWidgets import QApplication

from template_ai.review_tool.analysis import analyse_file
from template_ai.review_tool.source_compatibility import (
    ISSUE_CODE, MAX_VISIBLE_CHARACTERS, SAFE_MESSAGE,
    ReviewSourceCompatibilityError, pdf_backed_source,
    placeholder_language, visible_pdf_page,
)


ENGLISH = ('This is an Adobe® Illustrator® File that was saved without PDF Content. '
           'To place or open this file in other applications, it should be re-saved '
           'from Adobe Illustrator with the "Create PDF Compatible File" option turned on. '
           'This option is in the Illustrator Native Format Options dialog box.')
TRADITIONAL = ('當儲存 Adobe® Illustrator® 檔案時，未開啟 PDF 內容。'
               '若要在其他應用程式中置入或開啟此檔案，請回到 Adobe Illustrator '
               '開啟「建立 PDF 相容檔案」選項之後，再重新儲存該檔案。')
SIMPLIFIED = ('此 Adobe Illustrator 文件未包含 PDF 内容。请在 Adobe Illustrator 中'
              '开启「创建 PDF 兼容文件」选项，然后重新保存文件。')


class ReviewSourceCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def pdf(self, pages, name='source.ai', raster=False, title=None):
        path = self.root / name
        writer = QPdfWriter(str(path))
        if title is not None:
            writer.setTitle(title)
        writer.setPageSize(QPageSize(QSizeF(160, 150), QPageSize.Unit.Millimeter))
        writer.setResolution(72)
        painter = QPainter(writer)
        painter.setFont(QFont('Noto Sans CJK TC', 9))
        for index, text in enumerate(pages):
            if index:
                writer.newPage()
            if raster:
                image = QImage(800, 400, QImage.Format.Format_RGB32)
                image.fill('white')
                image_painter = QPainter(image)
                image_painter.setPen('black')
                image_painter.drawText(10, 30, 'Authored raster-only fixture')
                image_painter.end()
                painter.drawImage(10, 10, image)
            else:
                # Authored paragraphs wrap at fixed lengths so their visible
                # characters stay inside the actual synthetic PDF page.
                for line, start in enumerate(range(0, len(text), 40)):
                    painter.drawText(12, 24 + line * 16, text[start:start + 40])
        painter.end()
        del painter, writer
        return path

    def test_signatures_require_multiple_visible_warning_clauses(self):
        for text, expected in ((ENGLISH, 'en'), (TRADITIONAL, 'zh-Hant'),
                               (SIMPLIFIED, 'zh-Hans')):
            with self.subTest(language=expected):
                self.assertEqual(placeholder_language(text), expected)
                self.assertEqual(placeholder_language(text.replace('PDF', 'ＰＤＦ')), expected)

    def test_normal_illustrator_references_and_partial_messages_are_not_blocked(self):
        for text in ('Adobe Illustrator designer alice@example.com',
                     'Adobe Illustrator Create PDF Compatible File user guide',
                     'Adobe Illustrator saved without PDF Content. Ask Alice.',
                     'Adobe Illustrator 建立 PDF 相容檔案 使用說明',
                     'PDF 內容未開啟，請重新儲存',
                     'Adobe Illustrator 檔案未開啟 PDF 內容，請聯絡設計師'):
            with self.subTest(text=text):
                self.assertIsNone(placeholder_language(text))

    def test_visible_text_classification_is_bounded(self):
        self.assertIsNone(placeholder_language('x' * MAX_VISIBLE_CHARACTERS + ENGLISH))

    def test_header_and_source_type_do_not_guess_private_ai_payload(self):
        path = self.root / 'private.ai'
        path.write_text('%!PS-Adobe-3.0\n' + ENGLISH)
        self.assertFalse(pdf_backed_source(path))
        svg = self.root / 'notice.svg'
        svg.write_text(ENGLISH)
        self.assertFalse(pdf_backed_source(svg))

    def test_actual_english_pdf_notice_is_rejected_before_import_or_ocr(self):
        path = self.pdf([ENGLISH])
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        with patch('template_ai.importer.import_file') as importer:
            with self.assertRaises(ReviewSourceCompatibilityError) as caught:
                analyse_file(path, self.root / 'cache')
        importer.assert_not_called()
        self.assertEqual(str(caught.exception), SAFE_MESSAGE)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertFalse(list((self.root / 'cache').rglob('review-packet*.json')))

    def test_actual_traditional_pdf_visible_text_is_detected(self):
        path = self.pdf([TRADITIONAL], name='traditional.pdf')
        self.assertEqual(visible_pdf_page(path, 1), {'page_count': 1, 'language': 'zh-Hant'})
        with self.assertRaises(ReviewSourceCompatibilityError):
            analyse_file(path, self.root / 'cache', ocr=False)

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_normal_pdf_mentioning_illustrator_keeps_real_artwork(self):
        path = self.pdf(['Adobe Illustrator designer alice@example.com'])
        result = analyse_file(path, self.root / 'cache', ocr=False)
        self.assertTrue(result['works'])
        self.assertFalse(any(i['code'] == ISSUE_CODE for i in result['issues']))
        self.assertNotIn('blocked_pages', result['source'])

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_notice_in_pdf_metadata_is_not_mistaken_for_visible_warning(self):
        path = self.pdf(['alice@example.com'], title=ENGLISH)
        self.assertIsNone(visible_pdf_page(path, 1)['language'])
        result = analyse_file(path, self.root / 'cache', ocr=False)
        self.assertTrue(result['works'])
        self.assertFalse(any(i['code'] == ISSUE_CODE for i in result['issues']))

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_svg_even_with_complete_warning_is_not_misclassified_as_native_ai(self):
        path = self.root / 'guide.svg'
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="30mm" '
                        'viewBox="0 0 180 30"><text x="3" y="10" font-size="1">'
                        + escape(ENGLISH) + '</text></svg>')
        result = analyse_file(path, self.root / 'cache', ocr=False)
        self.assertTrue(result['works'])
        self.assertFalse(any(i['code'] == ISSUE_CODE for i in result['issues']))

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_mixed_pages_preserve_only_normal_page_in_both_orders(self):
        for blocked in (1, 2):
            with self.subTest(blocked=blocked):
                texts = [ENGLISH, 'alice@example.com']
                if blocked == 2:
                    texts.reverse()
                path = self.pdf(texts, name=f'mixed-{blocked}.pdf')
                before = path.read_bytes()
                result = analyse_file(path, self.root / f'cache-{blocked}', ocr=False)
                self.assertEqual(result['status'], 'PARTIAL')
                self.assertEqual(result['source']['page_count'], 2)
                self.assertEqual(result['source']['blocked_pages'], [blocked])
                self.assertEqual(result['source']['analysis_complete_pages'], 1)
                self.assertEqual({p['page'] for p in result['pages']}, {3 - blocked})
                self.assertEqual({w['page'] for w in result['works']}, {3 - blocked})
                self.assertTrue(any(i['code'] == ISSUE_CODE and i['page'] == blocked
                                    for i in result['issues']))
                from template_ai.review_tool.session import SessionStore
                store = SessionStore(self.root / f'session-{blocked}')
                source = store.add_files([path])[0]
                store.apply_analysis(source['id'], result)
                saved = store.sources()[0]
                self.assertEqual(saved['status'], 'PARTIAL')
                self.assertIn('Illustrator 提示頁', saved['stage_message'])
                self.assertEqual({work['page'] for work in saved['works']}, {3 - blocked})
                self.assertEqual(path.read_bytes(), before)

    def test_real_worker_error_reaches_parent_with_actionable_safe_message(self):
        from template_ai.review_tool.jobs import AnalysisJobs
        path = self.pdf([ENGLISH], name='worker-notice.ai')
        jobs = AnalysisJobs(self.root / 'worker-cache')
        failures, results = [], []
        loop = QEventLoop()
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        jobs.failure.connect(lambda identity, message: failures.append((identity, message)))
        jobs.result.connect(lambda identity, packet: results.append(packet))
        jobs.finished.connect(loop.quit)
        jobs.start([{'id': 'notice-source', 'path': str(path)}], ocr=False)
        deadline.start(10000)
        loop.exec()
        deadline.stop()
        try:
            self.assertFalse(jobs.is_running(), 'Actual source worker did not finish within 10 seconds')
            self.assertEqual(failures, [('notice-source', SAFE_MESSAGE)])
            self.assertEqual(results, [])
        finally:
            if jobs.is_running():
                jobs.stop()

    def test_parent_maps_only_known_codes_and_never_relays_child_text(self):
        from template_ai.review_tool.jobs import AnalysisJobs
        jobs = AnalysisJobs(self.root / 'protocol-cache')
        private = 'PRIVATE_CUSTOMER_TEXT_AND_C_PATH_MUST_NOT_BE_FORWARDED'
        for code, expected in ((ISSUE_CODE, SAFE_MESSAGE), ('UNKNOWN_CODE', None)):
            jobs._consume(json.dumps({'type': 'error', 'code': code, 'message': private}).encode())
            self.assertNotIn(private, jobs._failure_message)
            if expected:
                self.assertEqual(jobs._failure_message, expected)
            else:
                self.assertNotIn('Illustrator', jobs._failure_message)

    @unittest.skipUnless(shutil.which('inkscape'), 'actual Inkscape is required')
    def test_raster_pdf_uses_late_strong_visible_ocr_check(self):
        path = self.pdf([''], name='raster.ai', raster=True)
        self.assertIsNone(visible_pdf_page(path, 1)['language'])
        # Inject explicit authored OCR observations to verify the late gate,
        # not OCR accuracy (actual bilingual OCR has separate regression tests).
        candidates = [dict(key='ocr-page', crop=dict(x=0, y=0, w=160, h=150), slots=[],
                           observations=[dict(id='ocr-notice', object_type='TEXT',
                                              text=ENGLISH, region=dict(x=2, y=2, w=150, h=120))])]
        with patch('template_ai.review_tool.analysis._ocr_capability', return_value={'available': True}), \
                patch('template_ai.review_tool.analysis._ocr_fallback',
                      return_value=(candidates, {'status': 'AUTHORED_TEST_OBSERVATIONS'})) as ocr:
            with self.assertRaises(ReviewSourceCompatibilityError):
                analyse_file(path, self.root / 'cache')
        ocr.assert_called_once()
        self.assertFalse(list((self.root / 'cache').rglob('review-packet*.json')))

    def test_worker_reports_specific_safe_recovery_and_no_result(self):
        path = self.pdf([ENGLISH])
        request = self.root / 'request.json'
        request.write_text(json.dumps({'path': str(path), 'cache_dir': str(self.root / 'cache')}))
        env = os.environ.copy()
        env['QT_QPA_PLATFORM'] = 'offscreen'
        process = subprocess.run([sys.executable, '-m', 'template_ai.review_tool.worker', str(request)],
                                 env=env, capture_output=True, text=True, timeout=45)
        events = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(process.returncode, 1, process.stderr[-500:])
        self.assertEqual(events[-1], dict(type='error', code=ISSUE_CODE, message=SAFE_MESSAGE))
        self.assertFalse(any(event['type'] == 'result' for event in events))
        self.assertNotIn(str(path), events[-1]['message'])
        self.assertNotIn(ENGLISH, events[-1]['message'])


if __name__ == '__main__':
    unittest.main()
