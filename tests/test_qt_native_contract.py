"""Framework APIs must remain usable on the real product windows."""
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QStyle, QVBoxLayout

from template_ai.font_candidate_dialog import FontCandidateDialog
from template_ai.font_dialog import FontCenterDialog
from template_ai.gui import MainWindow
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.logo_compare import LogoCompareWidget


class QtNativeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.window = MainWindow(Path(self.temp.name) / 'library')
        self.addCleanup(self.window.close)

    def test_main_window_keeps_native_font_and_geometry_methods(self):
        self.assertIsInstance(self.window.font(), QFont)
        self.assertGreater(self.window.width(), 0)
        self.assertGreater(self.window.height(), 0)

    def test_input_editor_keeps_native_owner_and_scroll_methods(self):
        graph = InputGraph.from_legacy([{'name': 'Alex Example'}], {}, [])
        dialog = InputGraphDialog(self.window, graph.data)
        self.addCleanup(dialog.close)
        self.assertIs(dialog.parentWidget(), self.window)
        self.assertIs(dialog.window(), dialog)
        dialog.scroll(0, 0)

    def test_font_windows_keep_native_geometry_style_and_result_methods(self):
        center = FontCenterDialog(self.window)
        self.addCleanup(center.close)
        candidate = FontCandidateDialog(center)
        self.addCleanup(candidate.close)
        for dialog in (center, candidate):
            with self.subTest(dialog=type(dialog).__name__):
                self.assertIs(dialog.window(), dialog)
                self.assertGreater(dialog.size().width(), 0)
                self.assertGreater(dialog.width(), 0)
                self.assertIsInstance(dialog.style(), QStyle)
                self.assertEqual(dialog.result(), 0)

    def test_logo_comparison_keeps_native_layout_access(self):
        comparison = LogoCompareWidget(self.window)
        self.addCleanup(comparison.close)
        self.assertIsInstance(comparison.layout(), QVBoxLayout)
        self.assertIs(comparison.body.parentWidget(), comparison)

    def test_safe_main_close_stops_catalog_preview_controller(self):
        controller = self.window.template_catalog.controller
        self.assertFalse(controller.closed)
        self.assertTrue(self.window.close())
        self.assertTrue(self.window.library.closed)
        self.assertTrue(controller.closed)

    def test_rejected_main_close_keeps_catalog_preview_available(self):
        notices = []
        original_inform = self.window.inform
        self.window.inform = notices.append
        self.window.busy = True
        try:
            self.assertFalse(self.window.close())
            self.assertFalse(self.window.library.closed)
            self.assertFalse(self.window.template_catalog.controller.closed)
            self.assertTrue(notices)
        finally:
            self.window.busy = False
            self.window.inform = original_inform


if __name__ == '__main__':
    unittest.main()
