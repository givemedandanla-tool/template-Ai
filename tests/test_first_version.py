"""驗證最容易造成錯誤成品的限制，以及來源→標記→模板→輸出的實際閉環。"""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication

from template_ai.demo import default_font, demo_template
from template_ai.gui import MainWindow
from template_ai.importer import import_file, inkscape_path
from template_ai.layout import generate, match
from template_ai.model import Rect, Slot, Template, learn_from_labels, new_id, template_errors
from template_ai.render import export
from template_ai.storage import Library
from template_ai.validation import compare_images

APP = QApplication.instance() or QApplication([])
DATA = [{"name": "林小明", "title": "設計顧問", "phone": "0900-123-456", "email": "hello@example.test"}]


class FirstVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = Library(self.root / "data")
        self.template = demo_template()
        self.template.state = "published"

    def tearDown(self):
        self.library.close()
        self.temp.cleanup()

    def candidate(self):
        return generate(self.template, DATA, [], {}, 7)

    def test_fixed_size_long_text_is_blocked_without_mutation(self):
        before = self.template.to_dict()
        data = copy.deepcopy(DATA)
        data[0]["name"] = "非常長且不能被截斷的姓名" * 20
        c = generate(self.template, data, [], {})
        self.assertFalse(c.valid)
        self.assertIn("字寬", "；".join(c.issues))
        self.assertEqual(before, self.template.to_dict())
        with self.assertRaises(ValueError):
            export(c, self.root / "FINAL.png")
        self.assertFalse((self.root / "FINAL.png").exists())

    def test_unused_contact_and_wrong_capacity_block(self):
        data = copy.deepcopy(DATA)
        data[0]["phone"] = ["0900-123-456", "0800-000-000"]
        self.assertIn("第 2 筆沒有", "；".join(generate(self.template, data, [], {}).issues))
        self.assertFalse(generate(self.template, DATA * 2, [], {}).valid)

    def test_missing_font_does_not_use_silent_fallback(self):
        self.template.slots[0].font = "Nonexistent-Font-For-Validation"
        c = self.candidate()
        self.assertIn("未安裝", "；".join(c.issues))
        self.assertFalse(c.valid)

    def test_geometric_overlap_and_outside_block_publication(self):
        self.template.slots[1].rect = Rect(8, 6, 70, 11)
        self.assertIn("重疊", "；".join(template_errors(self.template)))
        self.template.slots[1].rect.x = -1
        self.assertIn("邊界", "；".join(template_errors(self.template)))

    def test_missing_logo_and_wrong_size_or_company_do_not_pass(self):
        self.template.slots.append(Slot("logo", "c1", Rect(79, 7, 8, 10), font=default_font()))
        self.template.company_bindings = {"p1": "c1"}
        data = [{**DATA[0], "company": "c1"}]
        companies = [{"name": "合成公司"}]
        missing = generate(self.template, data, companies, {})
        self.assertFalse(missing.valid)
        self.assertIn("占位", "；".join(missing.issues))
        export(missing, self.root / "PREVIEW.png", preview=True)
        self.assertGreater(QImage(str(self.root / "PREVIEW.png")).height(), round(54 * 300 / 25.4))
        asset = {"approved": True, "company": "合成公司", "width_mm": 91, "height_mm": 54}
        self.assertIn("尺寸不符", "；".join(generate(self.template, data, companies, {"c1": asset}).issues))
        asset.update(width_mm=90, company="另一公司")
        self.assertFalse(generate(self.template, data, companies, {"c1": asset}).valid)

    def test_person_company_binding_is_not_inferred_from_strings(self):
        self.template.slots.append(Slot("company", "c1", Rect(79, 7, 8, 10), font=default_font()))
        self.template.company_bindings = {"p1": "c1"}
        bad = generate(self.template, [{**DATA[0], "company": "c2"}], [{"name": "同名"}, {"name": "同名"}], {})
        self.assertIn("不能混配", "；".join(bad.issues))

    def test_export_all_formats_real_pdf_dimensions_and_no_overwrite(self):
        c = self.candidate()
        self.assertTrue(c.valid, c.issues)
        for extension in ["png", "jpg", "pdf"]:
            path = self.root / ("FINAL." + extension)
            export(c, path, expected_generation=7)
            digest = path.read_bytes()
            with self.assertRaises(FileExistsError):
                export(c, path)
            self.assertEqual(digest, path.read_bytes())
        doc = QPdfDocument()
        self.assertEqual(doc.load(str(self.root / "FINAL.pdf")), QPdfDocument.Error.None_)
        size = doc.pagePointSize(0)
        self.assertAlmostEqual(size.width()*25.4/72, 90, delta=0.05)
        self.assertAlmostEqual(size.height()*25.4/72, 54, delta=0.05)
        self.assertFalse(doc.render(0, QSize(900, 540)).isNull())
        doc.close()
        self.assertFalse(QImage(str(self.root / "FINAL.png")).isNull())
        self.assertFalse(QImage(str(self.root / "FINAL.jpg")).isNull())

    def test_stale_generation_and_unmarked_preview_block(self):
        with self.assertRaises(ValueError):
            export(self.candidate(), self.root / "FINAL.png", expected_generation=8)
        with self.assertRaises(ValueError):
            export(self.candidate(), self.root / "unmarked.png", preview=True)

    def test_atomic_publish_failure_preserves_existing_file_and_cleans_temp(self):
        target = self.root / "FINAL.png"
        with patch("template_ai.render.os.link", side_effect=OSError("simulated filesystem failure")):
            with self.assertRaises(OSError):
                export(self.candidate(), target)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".template-ai-*")), [])

    def test_published_templates_are_immutable_and_family_versions_safe(self):
        t = demo_template()
        self.library.save_template(t)
        self.library.publish(t)
        changed = copy.deepcopy(t)
        changed.name = "不允許改正式版本"
        with self.assertRaises(ValueError):
            self.library.save_template(changed)
        changed.id, changed.state = new_id(), "draft"
        with self.assertRaises(ValueError):
            self.library.save_template(changed)
        changed.version = self.library.next_version(t.family_id)
        self.library.save_template(changed)
        self.assertEqual(len(self.library.templates()), 2)
        self.assertEqual(self.library.templates(True)[0].name, t.name)

    def test_source_dedupe_preserves_independent_registrations_and_reopen(self):
        original = self.root / "A001.png"
        image = QImage(400, 240, QImage.Format_ARGB32)
        image.fill(0xffffffff)
        self.assertTrue(image.save(str(original)))
        other = self.root / "B002.png"
        shutil.copyfile(original, other)
        a = self.library.add_source(original, import_file(original, self.library.assets))
        result_b = import_file(other, self.library.assets)
        b = self.library.add_source(other, result_b)
        self.assertTrue(result_b["reused"])
        self.assertEqual(a["hash"], b["hash"])
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(len(self.library.list_sources()), 2)
        self.library.save_labels(a["id"], {"review": "人工確認"})
        self.library.close()
        self.library = Library(self.root / "data")
        self.assertEqual(self.library.get_labels(a["id"]), {"review": "人工確認"})
        self.assertIsNone(self.library.get_labels(b["id"]))

    def test_source_labels_to_learned_template_to_output(self):
        path = self.root / "training-reference.png"
        export(self.candidate(), path)
        source = self.library.add_source(path, import_file(path, self.library.assets))
        learned = learn_from_labels("確認標記學習", 90, 54, self.template.slots, source["id"], Rect(0, 0, 90, 54))
        self.library.save_template(learned)
        self.library.publish(learned)
        results = match(self.library.templates(True), 90, 54, DATA, [], {})
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].valid)
        self.assertIn("標記", "；".join(learned.reasons))
        export(results[0], self.root / "learned.pdf")
        self.assertEqual(match(self.library.templates(True), 91, 54, DATA, [], {}), [])

    def test_pixel_comparison_reports_unknown_alignment(self):
        a = QImage(40, 20, QImage.Format_ARGB32)
        a.fill(0xffffffff)
        b = a.copy()
        self.assertEqual(compare_images(a, b)["status"], "像素完全一致")
        b.setPixel(5, 5, 0xff000000)
        self.assertGreater(compare_images(a, b)["mean_difference"], 0)
        self.assertIn("尺寸不同", compare_images(a, b.scaled(20, 10))["status"])

    @unittest.skipUnless(inkscape_path(), "環境未安裝 Inkscape，真實轉換測試跳過並明示")
    def test_actual_inkscape_svg_and_pdf_compatible_ai(self):
        path = Path(__file__).parents[1] / "examples" / "synthetic-source.svg"
        imported = import_file(path, self.library.assets)
        self.assertIn("Inkscape", imported["engine"])
        self.assertTrue(Path(imported["svg"]).is_file())
        self.assertFalse(QImage(imported["image"]).isNull())
        export(self.candidate(), self.root / "fixture.pdf")
        shutil.copyfile(self.root / "fixture.pdf", self.root / "fixture.ai")
        compatible = import_file(self.root / "fixture.ai", self.library.assets)
        self.assertIn("Inkscape", compatible["engine"])
        self.assertAlmostEqual(compatible["width_mm"], 90, delta=0.05)
        # 此案例是合成 PDF 相容 AI，不能當作真實 Illustrator 私有檔驗收。

    def test_gui_real_demo_flow_and_readonly_published_canvas(self):
        window = MainWindow(self.root / "gui")
        window.tabs.setCurrentIndex(1)
        window.add_demo()
        self.assertEqual(window.template.state, "draft")
        window.library.publish(window.template)
        window.refresh_templates(window.template.id)
        window.edit_canvas.set_mode("edit")
        self.assertEqual(window.edit_canvas.mode, "pan")
        window.tabs.setCurrentIndex(2)
        window.demo_input()
        window.generate()
        self.assertTrue(window.candidates[0].valid, window.candidates[0].issues)
        self.assertTrue(window.export_button.isEnabled())
        window.people.item(0, 0).setText("姓名已修改")
        self.assertFalse(window.export_button.isEnabled())
        window.close()


if __name__ == "__main__":
    unittest.main()
