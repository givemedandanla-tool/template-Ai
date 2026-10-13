"""合成來源：內容身份、不可變原登錄、交易回滾及 GUI 背景重連。"""
from dataclasses import asdict
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from template_ai.demo import demo_template
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.model import Rect
from template_ai.source_links import source_status, verify_source
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])


class SourceRelinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / "original.png"
        image = QImage(900, 540, QImage.Format_ARGB32)
        image.fill(0xffffffff)
        image.save(str(self.original))
        self.library = Library(self.root / "data")
        self.addCleanup(self.library.close)
        self.source = self.library.add_source(self.original, import_file(self.original, self.library.assets))
        self.moved = self.root / "renamed.png"
        shutil.copyfile(self.original, self.moved)

    def test_moved_source_reopens_with_original_identity_and_history(self):
        payload = {"crop": asdict(Rect(0, 0, 100, 60)), "work_width": 90, "work_height": 54,
                   "slots": [], "visual_confirmed": True}
        work = self.library.create_artwork(self.source["id"], "正面", payload)
        template = demo_template()
        template.source_id = self.source["id"]
        template.source_work_id, template.source_work_revision = work["id"], 1
        self.library.save_template(template)
        self.library.publish(template)
        original_db_payload = self.library.db.execute("SELECT payload FROM sources").fetchone()[0]
        templates = [t.to_dict() for t in self.library.templates()]
        preview = Path(self.source["image"]).read_bytes()
        original_bytes = self.original.read_bytes()
        moved_stat = self.moved.stat().st_mtime_ns
        self.original.unlink()
        result = self.library.relink_source(self.source["id"], verify_source(self.moved, self.source["hash"]), 0)
        self.assertEqual(result["link_revision"], 1)
        self.assertEqual(result["original_path"], str(self.original))
        self.assertEqual(result["current_path"], str(self.moved))
        self.assertEqual(self.library.db.execute("SELECT payload FROM sources").fetchone()[0], original_db_payload)
        self.assertEqual(self.library.artwork(work["id"]), work)
        self.assertEqual([t.to_dict() for t in self.library.templates()], templates)
        self.assertEqual(Path(self.source["image"]).read_bytes(), preview)
        self.assertEqual(self.moved.read_bytes(), original_bytes)
        self.assertEqual(self.moved.stat().st_mtime_ns, moved_stat)
        reopened = Library(self.library.root)
        try:
            self.assertEqual(reopened.source(self.source["id"]), result)
            history = reopened.source_link_history(self.source["id"])
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["previous_path"], str(self.original))
            self.assertEqual(history[0]["hash"], self.source["hash"])
        finally:
            reopened.close()

    def test_same_name_different_bytes_and_missing_candidate_rejected(self):
        folder = self.root / "wrong"
        folder.mkdir()
        wrong = folder / self.original.name
        wrong.write_bytes(b"different original")
        with self.assertRaisesRegex(ValueError, "內容已變更"):
            verify_source(wrong, self.source["hash"])
        with self.assertRaises(FileNotFoundError):
            verify_source(self.root / "missing.ai", self.source["hash"])
        self.assertEqual(self.library.source(self.source["id"])["link_revision"], 0)
        self.assertEqual(self.library.source_link_history(self.source["id"]), [])

    def test_stale_revision_and_candidate_changed_after_verification_rejected(self):
        proof = verify_source(self.moved, self.source["hash"])
        self.library.relink_source(self.source["id"], proof, 0)
        with self.assertRaisesRegex(ValueError, "另一工作階段"):
            self.library.relink_source(self.source["id"], proof, 0)
        other = Library(self.library.root)
        try:
            with self.assertRaisesRegex(ValueError, "另一工作階段"):
                other.relink_source(self.source["id"], verify_source(self.original, self.source["hash"]), 0)
        finally:
            other.close()
        self.moved.write_bytes(b"edited after check")
        with self.assertRaisesRegex(ValueError, "驗證後變更"):
            self.library.relink_source(self.source["id"], proof, 1)
        self.assertEqual(len(self.library.source_link_history(self.source["id"])), 1)

    def test_event_failure_rolls_back_link_and_history(self):
        before = self.library.source(self.source["id"])
        with patch.object(self.library, "event", side_effect=sqlite3.OperationalError("disk failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.library.relink_source(self.source["id"], verify_source(self.moved, self.source["hash"]), 0)
        self.assertEqual(self.library.source(self.source["id"]), before)
        self.assertEqual(self.library.source_link_history(self.source["id"]), [])
        self.library.relink_source(self.source["id"], verify_source(self.moved, self.source["hash"]), 0)
        self.assertEqual(self.library.source(self.source["id"])["link_revision"], 1)

    def test_status_distinguishes_missing_changed_unreadable_and_ok(self):
        self.assertEqual(source_status(self.source)["status"], "OK")
        with patch("template_ai.source_links.verify_source", side_effect=PermissionError()):
            self.assertEqual(source_status(self.source)["status"], "UNREADABLE")
        self.original.write_bytes(b"changed")
        self.assertEqual(source_status(self.source)["status"], "CHANGED")
        self.original.unlink()
        self.assertEqual(source_status(self.source)["status"], "MISSING")

    def test_repeated_current_path_is_idempotent_and_wrong_source_proof_rejected(self):
        proof = verify_source(self.original, self.source["hash"])
        self.library.relink_source(self.source["id"], proof, 0)
        self.assertEqual(self.library.source_link_history(self.source["id"]), [])
        image = QImage(10, 10, QImage.Format_ARGB32)
        image.fill(0xff000000)
        black = self.root / "black.png"
        image.save(str(black))
        other = self.library.add_source(black, import_file(black, self.library.assets))
        with self.assertRaisesRegex(ValueError, "不屬於"):
            self.library.relink_source(other["id"], proof, 0)

    def test_gui_background_relink_keeps_selected_work_and_reopens(self):
        window = MainWindow(self.root / "gui")
        def cleanup():
            # 明確重開後窗口已關閉；不再次保存到已關閉 SQLite。
            window.source, window.template = None, None
            window.close()
        self.addCleanup(cleanup)
        error_patch = patch.object(window, "error", side_effect=AssertionError)
        error_patch.start()
        self.addCleanup(error_patch.stop)
        source = window.library.add_source(self.original, import_file(self.original, window.library.assets))
        window.refresh_sources(source["id"])
        work_id = window.work["id"]
        jobs = []
        with patch("template_ai.gui.QFileDialog.getOpenFileName", return_value=(str(self.moved), "")):
            with patch.object(window, "run_job", side_effect=lambda message, fn, callback: jobs.append((fn, callback))):
                window.relink_source()
        self.assertEqual(window.source["link_revision"], 0)
        self.assertEqual(len(jobs), 1)
        jobs[0][1](jobs[0][0]())
        self.assertEqual(window.source["current_path"], str(self.moved))
        self.assertEqual(window.work["id"], work_id)
        self.assertEqual(window.source_combo.currentText().split(" · ")[0], "renamed.png")
        self.assertIn(str(self.original), window.source_combo.itemData(0, 3))
        window.close()
        reopened = MainWindow(self.root / "gui")
        try:
            self.assertEqual(reopened.source["current_path"], str(self.moved))
            self.assertEqual(reopened.work["id"], work_id)
        finally:
            reopened.close()
