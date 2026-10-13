"""使用環境既有字型；不將字型 bytes、隔離副本或 SQLite 上傳 GitHub。"""
import copy
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox
from template_ai.background import file_digest
from template_ai.demo import demo_template
from template_ai.fonts import FontManager, font_errors
from template_ai.gui import MainWindow
from template_ai.layout import generate
from template_ai.render import export
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])
FONT = next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                        Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),
                        Path(r'C:\Windows\Fonts\arial.ttf')) if p.is_file()), None)


@unittest.skipUnless(FONT, "無可用環境字型，實際修復驗證跳過")
class FontRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = Library(self.root / "data")
        self.addCleanup(self.library.close)
        self.manager = FontManager(self.library)
        self.addCleanup(self.manager.close)
        self.asset = self.manager.import_font(FONT, approved=True)
        self.target = Path(self.asset["path"])

    def test_missing_copy_restored_and_reopened_without_changing_published_pin(self):
        template = demo_template()
        for slot in template.slots:
            slot.font = self.asset["families"][0]
            slot.font_asset = copy.deepcopy(self.asset)
        self.library.save_template(template)
        self.library.publish(template)
        published = self.library.templates(True)[0].to_dict()
        self.target.unlink()
        before = generate(template, [{"name": "Alex Example", "title": "Consultant", "phone": "0900-123-456", "email": "hello@example.test"}], [], {})
        self.assertFalse(before.valid)
        self.assertEqual(self.manager.repair_font(self.asset["hash"], FONT, approved=True), self.asset)
        self.assertEqual(file_digest(self.target), self.asset["hash"])
        self.assertEqual(self.library.fonts(), [self.asset])
        self.assertEqual(self.library.templates(True)[0].to_dict(), published)
        candidate = generate(template, [{"name": "Alex Example", "title": "Consultant", "phone": "0900-123-456", "email": "hello@example.test"}], [], {})
        self.assertTrue(candidate.valid, candidate.issues)
        exported = self.root / "restored.pdf"
        export(candidate, exported)
        self.assertTrue(exported.read_bytes().startswith(b"%PDF-"))
        self.manager.close()
        reopened = FontManager(self.library)
        try:
            self.assertIn(self.asset["hash"], reopened.loaded)
            self.assertEqual(reopened.issues, [])
        finally:
            reopened.close()
        self.assertEqual(self.library.font_repairs()[0]["phase"], "COMPLETED")

    def test_corrupted_copy_retained_in_quarantine_and_reference_unchanged(self):
        broken = b"corrupt local font"
        self.target.write_bytes(broken)
        self.manager.repair_font(self.asset["hash"], FONT, approved=True)
        repair = self.library.font_repairs()[0]
        self.assertEqual(Path(repair["backup"]).read_bytes(), broken)
        self.assertEqual(file_digest(Path(repair["backup"])), repair["previous_hash"])
        self.assertEqual(repair["phase"], "COMPLETED")
        self.assertEqual(font_errors(self.asset, self.asset["families"][0]), [])
        self.assertEqual(self.library.fonts(), [self.asset])

    def test_unapproved_or_different_content_rejected_without_writes(self):
        self.target.unlink()
        with self.assertRaisesRegex(ValueError, "確認有權"):
            self.manager.repair_font(self.asset["hash"], FONT)
        alternative = self.root / "same-family.ttf"
        alternative.write_bytes(FONT.read_bytes() + b"different version")
        with self.assertRaisesRegex(ValueError, "內容不符"):
            self.manager.repair_font(self.asset["hash"], alternative, approved=True)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.library.font_repairs(), [])

    def test_completion_event_failure_restores_corrupt_copy_and_pending_intent(self):
        broken = b"original corrupt bytes"
        self.target.write_bytes(broken)
        with patch.object(self.library, "event", side_effect=sqlite3.OperationalError("simulated audit failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.manager.repair_font(self.asset["hash"], FONT, approved=True)
        self.assertEqual(self.target.read_bytes(), broken)
        self.assertEqual(self.library.fonts(), [self.asset])
        self.assertEqual(self.library.font_repairs()[0]["phase"], "PREPARED")
        self.assertEqual(Path(self.library.font_repairs()[0]["backup"]).read_bytes(), broken)
        self.manager.close()
        reopened = FontManager(self.library)
        try:
            self.assertNotIn(self.asset["hash"], reopened.loaded)
            self.assertEqual(self.library.font_repairs()[0]["phase"], "FAILED")
        finally:
            reopened.close()

    def test_missing_copy_event_failure_stays_missing(self):
        self.target.unlink()
        with patch.object(self.library, "event", side_effect=sqlite3.OperationalError("audit failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.manager.repair_font(self.asset["hash"], FONT, approved=True)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.library.font_repairs()[0]["phase"], "PREPARED")

    def test_prepared_repair_recovery_requires_actual_expected_bytes(self):
        self.library.prepare_font_repair({"id": "simulated-interruption", "hash": self.asset["hash"], "path": str(self.target), "approved": True})
        self.manager.close()
        reopened = FontManager(self.library)
        try:
            self.assertEqual(self.library.font_repairs()[0]["phase"], "COMPLETED")
            self.assertIn(self.asset["hash"], reopened.loaded)
            events = [r[0] for r in self.library.db.execute("SELECT action FROM reviews")]
            self.assertIn("font_repair_recovered_same_content", events)
        finally:
            reopened.close()

    def test_qt_parse_failure_does_not_replace_or_create_repair_intent(self):
        self.target.write_bytes(b"broken")
        with patch.object(QFontDatabase, "addApplicationFont", return_value=-1):
            with self.assertRaisesRegex(ValueError, "Qt 解析"):
                self.manager.repair_font(self.asset["hash"], FONT, approved=True)
        self.assertEqual(self.target.read_bytes(), b"broken")
        self.assertEqual(self.library.font_repairs(), [])
        self.assertEqual(list(self.target.parent.glob('.repair-*')), [])

    def test_healthy_copy_repair_is_idempotent(self):
        stamp = self.target.stat().st_mtime_ns
        self.assertEqual(self.manager.repair_font(self.asset["hash"], FONT, approved=True), self.asset)
        self.assertEqual(self.target.stat().st_mtime_ns, stamp)
        self.assertEqual(self.library.font_repairs(), [])

    def test_external_catalog_path_not_modified(self):
        outside = self.root / (self.asset["hash"] + ".ttf")
        outside.write_bytes(b"outside must remain")
        changed = {**self.asset, "path": str(outside)}
        import json
        with self.library.db:
            self.library.db.execute("UPDATE font_assets SET payload=? WHERE hash=?", (json.dumps(changed), self.asset["hash"]))
        with self.assertRaisesRegex(ValueError, "不是程式擁有"):
            self.manager.repair_font(self.asset["hash"], FONT, approved=True)
        self.assertEqual(outside.read_bytes(), b"outside must remain")

    @unittest.skipIf(os.name == "nt", "Windows symlink 建立需獨立權限驗收")
    def test_symlink_target_never_overwrites_original_font(self):
        protected = self.root / "protected.ttf"
        protected.write_bytes(b"protected source")
        self.target.unlink()
        self.target.symlink_to(protected)
        with self.assertRaisesRegex(ValueError, "不是程式擁有"):
            self.manager.repair_font(self.asset["hash"], FONT, approved=True)
        self.assertEqual(protected.read_bytes(), b"protected source")
        self.assertTrue(self.target.is_symlink())

    def test_gui_repair_preserves_asset_and_invalidates_previous_candidate(self):
        window = MainWindow(self.root / "gui")
        self.addCleanup(window.close)
        asset = window.font_manager.import_font(FONT, approved=True)
        Path(asset["path"]).unlink()
        generation = window.generation
        with patch("template_ai.gui.QInputDialog.getItem", return_value=(" / ".join(asset["families"]) + " · " + asset["original_name"] + " · " + asset["hash"][:12], True)), \
             patch("template_ai.gui.QFileDialog.getOpenFileName", return_value=(str(FONT), "")), \
             patch("template_ai.gui.QMessageBox.question", return_value=QMessageBox.Yes), \
             patch.object(window, "inform"), patch.object(window, "error", side_effect=AssertionError):
            window.repair_font()
        self.assertEqual(file_digest(Path(asset["path"])), asset["hash"])
        self.assertEqual(window.library.fonts(), [asset])
        self.assertGreater(window.generation, generation)
        self.assertFalse(window.export_button.isEnabled())
