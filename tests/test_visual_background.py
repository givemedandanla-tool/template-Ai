"""確認裝飾真的進入成品；來源變更不能沿用既有核准或輸出半成品。"""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QMessageBox

from digital_review_fixture import authored_review
from authored_font_fixture import bind_authored_fonts
from template_ai.fonts import FontManager
from template_ai.background import ensure_embedded_svg, make_background
from template_ai.demo import demo_template
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.layout import generate
from template_ai.model import Template, new_id, template_errors
from template_ai.render import export, render_background, render_image
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])
DATA = [{"name": "林小明", "title": "設計顧問", "phone": "0900-123-456", "email": "hello@example.test"}]


class VisualBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = Library(self.root / "data")
        self.addCleanup(self.library.close)
        fixture = Path(__file__).parents[1] / "examples/synthetic-background.svg"
        self.source = import_file(fixture, self.library.assets)
        self.template = demo_template()
        self.source_font_manager=FontManager(self.library);self.addCleanup(self.source_font_manager.close);bind_authored_fonts(self.template,self.source_font_manager)
        self.template.background = make_background(self.source, 90, 54, approved=True)

    def candidate(self):
        self.template.state = "published"
        return generate(self.template, DATA, [], {})

    def assert_decoration(self, image):
        # 框外左側實際像素應為藍色，右上應為金色；不能只檢查檔案存在。
        blue = image.pixelColor(round(image.width() * .015), round(image.height() * .5))
        gold = image.pixelColor(round(image.width() * .96), round(image.height() * .05))
        self.assertLess(blue.red(), blue.blue())
        self.assertGreater(gold.red(), gold.blue())

    def test_decoration_in_preview_and_all_actual_exports(self):
        c = self.candidate()
        self.assertTrue(c.valid, c.issues)
        self.assert_decoration(render_image(c))
        for suffix in ("png", "jpg", "pdf"):
            target = self.root / ("decorated." + suffix)
            export(c, target,format_review=authored_review(c,suffix,self.root/"proofs"))
            if suffix == "pdf":
                doc = QPdfDocument()
                self.assertEqual(doc.load(str(target)), QPdfDocument.Error.None_)
                self.assert_decoration(doc.render(0, QSize(900, 540)))
                doc.close()
            else:
                self.assert_decoration(QImage(str(target)))

    def test_unapproved_and_wrong_size_background_block_publication(self):
        self.template.background["approved"] = False
        with self.assertRaisesRegex(ValueError, "尚未人工核准"):
            self.library.publish(self.template)
        self.template.background["approved"] = True
        self.template.background["width_mm"] = 91
        self.assertFalse(self.candidate().valid)
        with self.assertRaisesRegex(ValueError, "同一毫米尺寸"):
            make_background(self.source, 91, 54, approved=True)

    def test_changed_background_after_candidate_blocks_and_cleans_export(self):
        c = self.candidate()
        Path(self.template.background["svg"]).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        self.assertFalse(generate(self.template, DATA, [], {}).valid)
        for suffix in ("pdf", "png"):
            target = self.root / ("changed." + suffix)
            with self.assertRaisesRegex(ValueError, "內容已變更"):
                export(c, target)
            self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".template-ai-*")), [])

    def test_missing_background_is_not_silently_rendered_white(self):
        Path(self.template.background["image"]).unlink()
        self.assertFalse(self.candidate().valid)
        with self.assertRaisesRegex(ValueError, "來源失聯"):
            render_background(self.template)

    def test_reopen_version_and_old_schema_preserve_background(self):
        self.library.save_template(self.template)
        self.library.publish(self.template)
        newer = copy.deepcopy(self.template)
        newer.id, newer.version, newer.state = new_id(), 2, "draft"
        newer.background = None
        self.library.save_template(newer)
        reopened = Library(self.root / "data")
        try:
            published = reopened.templates(True)[0]
            self.assertEqual(published.background, self.template.background)
            self.assert_decoration(render_background(published))
        finally:
            reopened.close()
        legacy = self.template.to_dict()
        legacy.pop("background")
        for slot in legacy["slots"]:
            slot.pop("color")
        restored = Template.from_dict(legacy)
        self.assertIsNone(restored.background)
        self.assertEqual(restored.slots[0].color, "#111827")

    def test_raster_background_requires_matching_ratio(self):
        source = dict(self.source, calibrated=False, width_mm=100, height_mm=60, svg="")
        self.assertTrue(make_background(source, 90, 54, approved=True)["approved"])
        with self.assertRaisesRegex(ValueError, "比例"):
            make_background(source, 90, 60, approved=True)

    def test_raster_choice_uses_approved_imported_pixels(self):
        self.template.background["render_mode"] = "raster"
        c = self.candidate()
        self.assertTrue(c.valid)
        self.assert_decoration(render_image(c))
        export(c, self.root / "raster.pdf",format_review=authored_review(c,"PDF",self.root/"proofs"))
        document = QPdfDocument()
        self.assertEqual(document.load(str(self.root / "raster.pdf")), QPdfDocument.Error.None_)
        self.assert_decoration(document.render(0, QSize(900, 540)))
        document.close()

    def test_external_svg_resource_is_rejected_before_approval(self):
        path = self.root / "external.svg"
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="changed-later.png"/></svg>', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "外連"):
            ensure_embedded_svg(path)
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><style>@import "external.css";</style></svg>', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "外連"):
            ensure_embedded_svg(path)

    def test_text_color_is_real_rendered_and_invalid_color_blocks(self):
        self.template.background = None
        self.template.slots[0].color = "#ff0000"
        image = render_image(self.candidate())
        red_pixels = sum(image.pixelColor(x, y).red() > 180 and image.pixelColor(x, y).green() < 80
                         for y in range(round(image.height() * .1), round(image.height() * .33))
                         for x in range(round(image.width() * .08), round(image.width() * .9)))
        self.assertGreater(red_pixels, 20)
        self.template.slots[0].color = "not-a-color"
        self.assertIn("色彩", "；".join(template_errors(self.template)))
        self.assertFalse(self.candidate().valid)

    def test_gui_background_controls_respect_published_version(self):
        window = MainWindow(self.root / "gui")
        self.addCleanup(window.close)
        window.tabs.setCurrentIndex(1)
        window.library.save_template(self.template)
        window.refresh_templates(self.template.id)
        self.assertTrue(window.background_button.isEnabled())
        self.assertTrue(window.clear_background_button.isEnabled())
        window.library.publish(window.template)
        window.refresh_templates(window.template.id)
        self.assertFalse(window.background_button.isEnabled())
        self.assertFalse(window.clear_background_button.isEnabled())
        window.new_version()
        self.assertTrue(window.background_button.isEnabled())
        with patch("template_ai.gui.QMessageBox.question", return_value=QMessageBox.Yes):
            window.clear_background()
        self.assertIsNone(window.template.background)
        self.assertIsNotNone(window.library.templates(True)[0].background)

    def test_real_background_review_dialog_saves_chosen_mode(self):
        window = MainWindow(self.root / "review-gui")
        self.addCleanup(window.close)
        window.tabs.setCurrentIndex(1)
        window.add_demo()
        fixture = str(Path(__file__).parents[1] / "examples/synthetic-background.svg")
        original_exec = QDialog.exec
        def review_dialog(dialog):
            def accept_review():
                modes = dialog.findChildren(QComboBox)
                self.assertEqual(len(modes), 1)
                modes[0].setCurrentIndex(modes[0].findData("raster"))
                dialog.accept()
            QTimer.singleShot(0, accept_review)
            return original_exec(dialog)
        with patch("template_ai.gui.QFileDialog.getOpenFileName", return_value=(fixture, "")), \
             patch.object(window, "run_job", side_effect=lambda message, function, callback: callback(function())), \
             patch.object(QDialog, "exec", review_dialog):
            window.import_background()
        self.assertTrue(window.template.background["approved"])
        self.assertEqual(window.template.background["render_mode"], "raster")
        self.assertEqual(window.library.templates()[0].background, window.template.background)
