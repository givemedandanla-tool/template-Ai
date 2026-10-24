"""Synthetic failures must remain selectable and show safe recovery guidance."""
import json
from pathlib import Path
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from template_ai.review_tool.jobs import AnalysisJobs
from template_ai.review_tool.window import ReviewWindow

APP = QApplication.instance() or QApplication([])


class ReviewFailedSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.window = ReviewWindow(self.root / 'session')
        source = self.root / 'synthetic.svg'
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm"/>', encoding='utf-8')
        self.source = self.window.store.add_files([source])[0]

    def tearDown(self):
        self.window.store.save()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def test_added_source_with_null_analysis_can_be_selected(self):
        self.assertIsNone(self.source['analysis'])
        self.window.select_source(self.source['id'])
        self.assertIsNone(self.window._page(self.source))
        self.assertIn('尚未判讀', self.window.notice.text())

    def test_failed_source_selection_preserves_recovery_message(self):
        message = '合成測試：本機快取無法建立，請改用較短路徑。'
        self.window._analysis_failure(self.source['id'], message)
        self.window.select_source(self.source['id'])
        self.assertEqual(self.source['status'], 'FAILED')
        self.assertIn(message, self.window.notice.text())
        self.assertIn('更多', self.window.notice.text())
        self.assertEqual(self.window.store.works(self.source['id']), [])

    def test_missing_local_file_error_has_fixed_recovery_without_child_payload(self):
        jobs = AnalysisJobs(self.root / 'protocol')
        private = 'SYNTHETIC_PRIVATE_FILENAME_MUST_NOT_LEAVE_CHILD'
        jobs._consume(json.dumps({'type':'error','code':'FileNotFoundError','message':private}).encode())
        self.assertNotIn(private, jobs._failure_message)
        self.assertIn('較短', jobs._failure_message)
        self.assertIn('快取', jobs._failure_message)
        jobs._consume(json.dumps({'type':'error','code':'UNKNOWN_CODE','message':private}).encode())
        self.assertNotIn(private, jobs._failure_message)
        self.assertNotIn('較短', jobs._failure_message)


if __name__ == '__main__':
    unittest.main()
