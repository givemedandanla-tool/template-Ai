"""真實多頁 PDF 用不同色頁確認選頁，不以 metadata 的頁碼代替驗證。"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import QApplication

from template_ai.importer import import_file, svg_size

APP = QApplication.instance() or QApplication([])


class ImportPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "two-pages.pdf"
        writer = QPdfWriter(str(self.path))
        writer.setResolution(96)
        writer.setPageSize(QPageSize(QSizeF(90, 54), QPageSize.Millimeter))
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
        painter = QPainter(writer)
        for index, color in enumerate(("#173d75", "#cba46b")):
            if index:
                self.assertTrue(writer.newPage())
            painter.fillRect(QRectF(0, 0, writer.width(), writer.height()), QColor(color))
        painter.end()
        del writer

    def test_actual_second_page_and_cache_stay_distinct(self):
        first = import_file(self.path, self.root / "assets", 1)
        second = import_file(self.path, self.root / "assets", 2)
        self.assertEqual(second["page_count"], 2)
        self.assertNotEqual(first["image"], second["image"])
        blue = QImage(first["image"]).pixelColor(800, 300)
        gold = QImage(second["image"]).pixelColor(800, 300)
        self.assertLess(blue.red(), blue.blue())
        self.assertGreater(gold.red(), gold.blue())
        cached = import_file(self.path, self.root / "assets", 2)
        self.assertTrue(cached["reused"])
        self.assertEqual(cached["image"], second["image"])

    def test_bad_pdf_page_is_rejected_before_converter_runs(self):
        with patch("template_ai.importer._run") as converter:
            with self.assertRaisesRegex(ValueError, "只有 2 頁"):
                import_file(self.path, self.root / "assets", 3)
            converter.assert_not_called()
        for page in (0, -1, 1.5, True, 1000):
            with self.assertRaisesRegex(ValueError, "頁碼"):
                import_file(self.path, self.root / "assets", page)

    def test_qt_fallback_really_selects_second_page(self):
        with patch("template_ai.importer.inkscape_path", return_value=None):
            second = import_file(self.path, self.root / "qt-assets", 2)
        self.assertIn("Qt PDF", second["engine"])
        gold = QImage(second["image"]).pixelColor(800, 300)
        self.assertGreater(gold.red(), gold.blue())

    def test_non_pdf_page_is_explicitly_rejected(self):
        path = Path(__file__).parents[1] / "examples/synthetic-source.svg"
        with self.assertRaisesRegex(ValueError, "只支援第 1 頁"):
            import_file(path, self.root / "assets", 2)

    def test_extreme_svg_is_blocked_before_large_preview(self):
        path = self.root / "extreme.svg"
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1mm" height="100000mm"/>', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "像素預算"):
            svg_size(path)
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1e999mm" height="54mm"/>', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "尺寸不合法"):
            svg_size(path)

    def test_raster_budget_checks_header_before_decoding(self):
        path = self.root / "oversize.png"
        path.write_bytes(b"synthetic header supplied by test reader")
        reader = Mock()
        reader.size.return_value = QSize(100000, 100000)
        with patch("template_ai.importer.QImageReader", return_value=reader):
            with self.assertRaisesRegex(ValueError, "像素預算"):
                import_file(path, self.root / "assets")
        reader.read.assert_not_called()
