"""多作品、歷史恢復與競爭寫入驗證；測試既有 SQLite 的真實遷移。"""
import copy
from dataclasses import asdict
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from template_ai.demo import demo_template
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.model import Rect, learn_from_labels, new_id
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])


class ArtworkRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        image = QImage(900, 540, QImage.Format_ARGB32)
        image.fill(0xffffffff)
        self.path = self.root / "source.png"
        image.save(str(self.path))
        self.library = Library(self.root / "data")
        self.addCleanup(self.library.close)
        self.source = self.library.add_source(self.path, import_file(self.path, self.library.assets))
        self.payload = {"crop": asdict(Rect(0, 0, 100, 60)), "work_width": 90, "work_height": 54,
                        "slots": [asdict(slot) for slot in demo_template().slots], "visual_confirmed": True}

    def test_two_works_reopen_active_selection_and_marks(self):
        first = self.library.create_artwork(self.source["id"], "正面", self.payload)
        back = copy.deepcopy(self.payload)
        back["slots"] = []
        back["visual_confirmed"] = False
        second = self.library.create_artwork(self.source["id"], "背面", back)
        self.library.select_artwork(self.source["id"], first["id"])
        other = Library(self.root / "data")
        try:
            self.assertEqual(other.active_artwork(self.source["id"])["id"], first["id"])
            self.assertEqual(other.artwork(first["id"])["payload"], self.payload)
            self.assertEqual(other.artwork(second["id"])["payload"], back)
        finally:
            other.close()

    def test_history_restore_adds_revision_and_stale_update_blocks(self):
        work = self.library.create_artwork(self.source["id"], "正面", self.payload)
        newer = copy.deepcopy(self.payload)
        newer["slots"][0]["rect"]["x"] = 9
        saved = self.library.save_artwork(work["id"], newer, 1)
        self.assertEqual(saved["revision"], 2)
        with self.assertRaisesRegex(ValueError, "另一工作階段"):
            self.library.save_artwork(work["id"], self.payload, 1)
        restored = self.library.restore_artwork(work["id"], 1, 2)
        self.assertEqual(restored["revision"], 3)
        self.assertEqual(restored["payload"], self.payload)
        self.assertEqual([item["revision"] for item in self.library.artwork_history(work["id"])], [3, 2, 1])
        self.assertEqual(self.library.save_artwork(work["id"], self.payload, 3)["revision"], 3)

    def test_old_labels_migrate_once_without_deleting_legacy(self):
        self.library.save_labels(self.source["id"], self.payload)
        migrated = self.library.initialize_artwork(self.source["id"], {})
        self.assertEqual(migrated["payload"], self.payload)
        self.assertIn("舊標記", migrated["name"])
        self.assertEqual(self.library.initialize_artwork(self.source["id"], {})["id"], migrated["id"])
        self.assertEqual(self.library.get_labels(self.source["id"]), self.payload)
        self.assertEqual(len(self.library.artworks(self.source["id"])), 1)

    def test_cross_source_selection_and_invalid_geometry_do_not_mutate(self):
        first = self.library.create_artwork(self.source["id"], "正面", self.payload)
        second_source = self.library.add_source(self.path, import_file(self.path, self.library.assets))
        with self.assertRaisesRegex(ValueError, "不屬於"):
            self.library.select_artwork(second_source["id"], first["id"])
        invalid = copy.deepcopy(self.payload)
        invalid["work_width"] = 0
        with self.assertRaisesRegex(ValueError, "不合法"):
            self.library.save_artwork(first["id"], invalid, 1)
        self.assertEqual(self.library.artwork(first["id"]), first)
        self.assertIsNone(self.library.active_artwork(second_source["id"]))

    def test_publish_event_failure_rolls_back_database_and_memory(self):
        template = demo_template()
        self.library.save_template(template)
        with patch.object(self.library, "event", side_effect=sqlite3.OperationalError("simulated disk failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.library.publish(template)
        self.assertEqual(template.state, "draft")
        self.assertEqual(self.library.templates()[0].state, "draft")
        self.assertEqual(self.library.templates(True), [])

    def test_learned_template_pins_work_revision_and_rejects_wrong_source(self):
        work = self.library.create_artwork(self.source["id"], "學習作品", self.payload)
        template = learn_from_labels("可追溯模板", 90, 54, demo_template().slots, self.source["id"], Rect(0, 0, 100, 60),
                                     source_work_id=work["id"], source_work_revision=1)
        self.library.save_template(template)
        self.library.publish(template)
        changed = copy.deepcopy(self.payload)
        changed["slots"] = []
        self.library.save_artwork(work["id"], changed, 1)
        persisted = self.library.templates(True)[0]
        self.assertEqual((persisted.source_work_id, persisted.source_work_revision), (work["id"], 1))
        wrong = copy.deepcopy(persisted)
        wrong.id, wrong.family_id, wrong.state = new_id(), new_id(), "draft"
        wrong.source_id = "a-different-source"
        with self.assertRaisesRegex(ValueError, "來源作品"):
            self.library.save_template(wrong)

    def test_gui_new_crop_keeps_previous_work_and_reopens_latest(self):
        window = MainWindow(self.root / "gui")
        source = window.library.add_source(self.path, import_file(self.path, window.library.assets))
        window.refresh_sources(source["id"])
        window.slots = demo_template().slots
        window.visual.setChecked(True)
        window.save_labels(silent=True)
        first_id = window.work["id"]
        first_payload = window.work["payload"]
        window.train_canvas.set_mode("crop")
        with patch("template_ai.gui.QInputDialog.getDouble", side_effect=[(45, True), (54, True)]):
            window.add_rectangle(Rect(50, 0, 50, 60))
        second_id = window.work["id"]
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(len(window.works), 2)
        window.work_combo.setCurrentIndex(window.work_combo.findData(first_id))
        self.assertEqual(window.work["payload"], first_payload)
        window.work_combo.setCurrentIndex(window.work_combo.findData(second_id))
        window.close()
        reopened = MainWindow(self.root / "gui")
        try:
            self.assertEqual(reopened.work["id"], second_id)
            self.assertEqual(reopened.work_width, 45)
            self.assertEqual(len(reopened.works), 2)
            reopened.work_combo.setCurrentIndex(reopened.work_combo.findData(first_id))
            self.assertEqual(len(reopened.slots), 4)
            self.assertTrue(reopened.visual.isChecked())
        finally:
            reopened.close()

    def test_gui_restore_history_preserves_published_template(self):
        window = MainWindow(self.root / "restore-gui")
        self.addCleanup(window.close)
        source = window.library.add_source(self.path, import_file(self.path, window.library.assets))
        window.refresh_sources(source["id"])
        window.slots = demo_template().slots
        window.save_labels(silent=True)
        marked_revision = window.work["revision"]
        template = demo_template()
        window.library.save_template(template)
        window.library.publish(template)
        published = template.to_dict()
        window.slots[0].rect.x = 9
        window.save_labels(silent=True)
        with patch("template_ai.gui.QInputDialog.getItem", side_effect=lambda *args: (next(item for item in args[3] if item.startswith(f"r{marked_revision} ·")), True)), \
             patch("template_ai.gui.QMessageBox.question", return_value=QMessageBox.Yes):
            window.restore_work()
        self.assertEqual(window.slots[0].rect.x, 8)
        self.assertEqual(len(window.library.artwork_history(window.work["id"])), 4)
        self.assertEqual(window.library.templates(True)[0].to_dict(), published)

    def test_gui_learning_saves_exact_current_mark_revision(self):
        window = MainWindow(self.root / "learn-gui")
        self.addCleanup(window.close)
        source = window.library.add_source(self.path, import_file(self.path, window.library.assets))
        window.refresh_sources(source["id"])
        window.work_width, window.work_height = 90, 54
        window.slots = demo_template().slots
        window.visual.setChecked(True)
        with patch("template_ai.gui.QInputDialog.getText", return_value=("來源版次模板", True)):
            window.learn_template()
        self.assertEqual(window.template.source_work_id, window.work["id"])
        self.assertEqual(window.template.source_work_revision, window.work["revision"])

    def test_gui_reopens_last_selected_source_not_latest_import(self):
        window = MainWindow(self.root / "source-context-gui")
        sources = [window.library.add_source(self.path, import_file(self.path, window.library.assets)) for _ in range(2)]
        window.refresh_sources(sources[0]["id"])
        work_id = window.work["id"]
        window.close()
        reopened = MainWindow(self.root / "source-context-gui")
        try:
            self.assertEqual(reopened.source["id"], sources[0]["id"])
            self.assertEqual(reopened.work["id"], work_id)
        finally:
            reopened.close()
