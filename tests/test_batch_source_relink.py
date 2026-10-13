"""匿名原稿批次候選／全批交易／復原；不讀使用者實際資料夾。"""
import copy
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.source_dialog import SourceRelinkDialog
from template_ai.source_discovery import discover_sources
from template_ai.source_links import hash_source, verify_source
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])


class BatchSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = Library(self.root / "data")
        self.addCleanup(self.library.close)
        self.search = self.root / "search"
        self.search.mkdir()
        image = QImage(900, 540, QImage.Format_ARGB32)
        image.fill(0xffffffff)
        first = self.root / "A001.png"
        image.save(str(first))
        second = self.root / "B002.png"
        shutil.copyfile(first, second)
        self.originals = [first, second]
        self.sources = [self.library.add_source(p, import_file(p, self.library.assets)) for p in self.originals]
        self.sources = self.library.list_sources()
        self.candidate = self.search / "new-name.png"
        shutil.copyfile(first, self.candidate)

    def requests(self, path=None):
        path = path or self.candidate
        return [dict(source_id=s["id"], expected_revision=s["link_revision"], proof=verify_source(path, s["hash"])) for s in self.sources]

    def test_one_candidate_hashed_once_for_independent_same_content_registrations(self):
        with patch("template_ai.source_discovery.hash_source", wraps=hash_source) as hasher:
            report = discover_sources(self.sources, self.search)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(hasher.call_count, 1)
        self.assertEqual(report["hashed_files"], 1)
        self.assertEqual([len(r["candidates"]) for r in report["rows"]], [1, 1])
        self.assertNotEqual(report["rows"][0]["source"]["id"], report["rows"][1]["source"]["id"])

    def test_size_prefilter_same_name_different_bytes_and_ambiguous_copies(self):
        wrong = self.search / "A001.png"
        data = self.candidate.read_bytes()
        wrong.write_bytes(b"x" * len(data))
        copy_path = self.search / "another-copy.png"
        shutil.copyfile(self.candidate, copy_path)
        (self.search / "too-small.png").write_bytes(b"tiny")
        report = discover_sources(self.sources, self.search)
        self.assertEqual(report["hashed_files"], 3)
        self.assertTrue(all(len(r["candidates"]) == 2 for r in report["rows"]))
        a = next(r for r in report["rows"] if Path(r["source"]["original_path"]).name == "A001.png")
        self.assertEqual(a["same_name_different"], [str(wrong)])

    def test_limits_cancel_unreadable_and_missing_fingerprint_are_explicit(self):
        for kwargs in (dict(max_bytes=1), dict(max_entries=1)):
            extra = self.search / "extra.png"; shutil.copyfile(self.candidate, extra)
            self.assertEqual(discover_sources(self.sources, self.search, **kwargs)["status"], "PARTIAL")
        cancelled = threading.Event(); cancelled.set()
        self.assertEqual(discover_sources(self.sources, self.search, cancelled)["status"], "CANCELLED")
        with patch("template_ai.source_discovery.hash_source", side_effect=PermissionError("no access")):
            report = discover_sources(self.sources, self.search)
        self.assertEqual(report["status"], "PARTIAL")
        self.assertTrue(report["errors"])
        unknown = copy.deepcopy(self.sources); unknown[0].pop("byte_size")
        report = discover_sources(unknown, self.search)
        self.assertEqual(report["rows"][0]["candidates"], [])
        self.assertIn("資料不足", report["rows"][0]["availability"])

    @unittest.skipIf(os.name == "nt", "Windows symlink 建立需另驗收")
    def test_search_does_not_follow_symlink_outside_selected_root(self):
        external = self.root / "outside"; external.mkdir()
        shutil.copyfile(self.candidate, external / "outside.png")
        self.candidate.unlink()
        (self.search / "linked").symlink_to(external, target_is_directory=True)
        report = discover_sources(self.sources, self.search)
        self.assertEqual(report["hashed_files"], 0)
        self.assertEqual(report["status"], "PARTIAL")
        self.assertTrue(all(not r["candidates"] for r in report["rows"]))

    def test_candidate_count_is_bounded_and_partial_not_all_found(self):
        for i in range(34): shutil.copyfile(self.candidate, self.search / f"copy-{i}.png")
        report = discover_sources(self.sources, self.search)
        self.assertEqual(report["status"], "PARTIAL")
        self.assertTrue(all(len(r["candidates"]) == 32 and r["candidate_limit"] for r in report["rows"]))

    @unittest.skipIf(os.name == "nt", "模擬目錄接點用 symlink 建立測試映射；Windows 真實接點另驗收")
    def test_resolved_directory_outside_root_not_entered_even_without_symlink_flag(self):
        outside = self.root / "outside"; outside.mkdir()
        shutil.copyfile(self.candidate, outside / "other.png")
        junction = self.search / "junction"; junction.symlink_to(outside, target_is_directory=True)
        entry = Mock(path=str(junction))
        entry.is_symlink.return_value = False
        entry.stat.return_value = junction.stat()
        entry.is_dir.return_value = True
        class Entries:
            def __init__(self): self.items = iter([entry])
            def __next__(self): return next(self.items)
            def close(self): pass
        with patch("template_ai.source_discovery.os.scandir", return_value=Entries()) as listing:
            report = discover_sources(self.sources, self.search)
        self.assertEqual(listing.call_count, 1)
        self.assertEqual(report["hashed_files"], 0)
        self.assertEqual(report["status"], "PARTIAL")
        self.assertIn("範圍之外", report["errors"][0]["reason"])

    def test_batch_requires_approval_and_preserves_source_payload_and_ids(self):
        payloads = self.library.db.execute("SELECT id,payload FROM sources ORDER BY id").fetchall()
        with self.assertRaisesRegex(ValueError, "勾選"):
            self.library.relink_sources(self.requests())
        batch = self.library.relink_sources(self.requests(), approved=True)
        self.assertEqual(len(batch["items"]), 2)
        self.assertEqual(self.library.db.execute("SELECT id,payload FROM sources ORDER BY id").fetchall(), payloads)
        self.assertTrue(all(self.library.source(s["id"])["current_path"] == str(self.candidate) for s in self.sources))
        self.assertEqual(len(self.library.list_sources()), 2)
        reopened = Library(self.library.root)
        try:
            self.assertEqual(reopened.relink_batch(batch["id"]), batch)
            self.assertEqual(len(reopened.source_link_history(self.sources[0]["id"])), 1)
        finally: reopened.close()

    def test_late_revision_conflict_and_event_failure_roll_back_entire_batch(self):
        requests = self.requests()
        self.library.relink_source(self.sources[1]["id"], requests[1]["proof"], 0)
        before = self.library.list_sources()
        with self.assertRaisesRegex(ValueError, "另一工作階段"):
            self.library.relink_sources(requests, approved=True)
        self.assertEqual(self.library.list_sources(), before)
        self.assertEqual(self.library.source_link_history(self.sources[0]["id"]), [])
        self.assertEqual(self.library.relink_batches(), [])
        requests[1]["expected_revision"] = 1
        with patch.object(self.library, "event", side_effect=sqlite3.OperationalError("audit fail")):
            with self.assertRaises(sqlite3.OperationalError): self.library.relink_sources(requests, approved=True)
        self.assertEqual(self.library.list_sources(), before)
        self.assertEqual(self.library.relink_batches(), [])

    def test_candidate_changed_after_background_verify_does_not_partially_commit(self):
        requests = self.requests()
        alternate = self.search / "altered.png"; shutil.copyfile(self.candidate, alternate)
        requests[1]["proof"] = verify_source(alternate, self.sources[1]["hash"])
        alternate.write_bytes(b"changed after verification")
        before = self.library.list_sources()
        with self.assertRaisesRegex(ValueError, "驗證後變更"):
            self.library.relink_sources(requests, approved=True)
        self.assertEqual(self.library.list_sources(), before)
        self.assertEqual(self.library.relink_batches(), [])

    def test_undo_verifies_old_paths_creates_new_revisions_and_keeps_history(self):
        batch = self.library.relink_sources(self.requests(), approved=True)
        requests = [dict(source_id=i["source_id"], expected_revision=i["after_revision"], proof=verify_source(i["previous_path"], i["hash"])) for i in batch["items"]]
        restored = self.library.relink_sources(requests, approved=True, undo_of=batch["id"])
        self.assertEqual(restored["kind"], "UNDO")
        self.assertEqual(restored["undo_of"], batch["id"])
        self.assertEqual(len(self.library.relink_batches()), 2)
        for s in self.sources:
            self.assertEqual(self.library.source(s["id"])["current_path"], s["original_path"])
            self.assertEqual(self.library.source(s["id"])["link_revision"], 2)
            self.assertEqual(len(self.library.source_link_history(s["id"])), 2)

    def test_undo_missing_original_wrong_position_or_later_revision_rejected(self):
        batch = self.library.relink_sources(self.requests(), approved=True)
        requests = [dict(source_id=i["source_id"], expected_revision=i["after_revision"], proof=verify_source(i["previous_path"], i["hash"])) for i in batch["items"]]
        self.originals[0].unlink()
        with self.assertRaises(FileNotFoundError): verify_source(self.originals[0], self.sources[0]["hash"])
        before = self.library.list_sources()
        with self.assertRaises(FileNotFoundError): self.library.relink_sources(requests, approved=True, undo_of=batch["id"])
        self.assertEqual(self.library.list_sources(), before)
        requests[0]["proof"] = verify_source(self.candidate, self.sources[0]["hash"])
        with self.assertRaisesRegex(ValueError, "位置或版次"):
            self.library.relink_sources(requests, approved=True, undo_of=batch["id"])
        with self.assertRaisesRegex(ValueError, "全體來源"):
            self.library.relink_sources(requests[:1], approved=True, undo_of=batch["id"])

    def test_empty_duplicate_and_same_current_location_are_not_fake_updates(self):
        with self.assertRaises(ValueError): self.library.relink_sources([], approved=True)
        requests = self.requests()
        with self.assertRaisesRegex(ValueError, "重複"):
            self.library.relink_sources([requests[0], requests[0]], approved=True)
        self.library.relink_sources(requests, approved=True)
        count = len(self.library.relink_batches())
        requests = self.requests()
        for r in requests: r["expected_revision"] = 1
        record = self.library.relink_sources(requests, approved=True)
        self.assertEqual(record["items"], [])
        self.assertIsNone(record["id"])
        self.assertEqual(len(self.library.relink_batches()), count)

    def test_later_relink_revision_is_not_overwritten_by_old_batch_undo(self):
        batch = self.library.relink_sources(self.requests(), approved=True)
        later = self.search / "later.png"; shutil.copyfile(self.candidate, later)
        self.library.relink_source(self.sources[0]["id"], verify_source(later, self.sources[0]["hash"]), 1)
        before = self.library.list_sources()
        requests = [dict(source_id=i["source_id"], expected_revision=i["after_revision"], proof=verify_source(i["previous_path"], i["hash"])) for i in batch["items"]]
        with self.assertRaisesRegex(ValueError, "另一工作階段"):
            self.library.relink_sources(requests, approved=True, undo_of=batch["id"])
        self.assertEqual(self.library.list_sources(), before)
        self.assertEqual(len(self.library.relink_batches()), 1)

    def test_final_batch_audit_failure_rolls_back_links_histories_and_reviews(self):
        original_event = self.library.event
        called = []
        def fail_at_batch_event(entity, action):
            called.append(action)
            if len(called) == 3: raise sqlite3.OperationalError("final batch audit failed")
            original_event(entity, action)
        before = self.library.list_sources()
        with patch.object(self.library, "event", side_effect=fail_at_batch_event):
            with self.assertRaisesRegex(sqlite3.OperationalError, "final batch"):
                self.library.relink_sources(self.requests(), approved=True)
        self.assertEqual(len(called), 3)
        self.assertEqual(self.library.list_sources(), before)
        self.assertEqual(self.library.db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 0)
        self.assertEqual(self.library.db.execute("SELECT COUNT(*) FROM source_relinks").fetchone()[0], 0)
        self.assertEqual(self.library.relink_batches(), [])


class BatchSourceGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.window = MainWindow(self.root / "gui"); self.addCleanup(self.window.close)
        path = self.root / "source.png"
        image = QImage(900, 540, QImage.Format_ARGB32); image.fill(0xffffffff); image.save(str(path))
        source = self.window.library.add_source(path, import_file(path, self.window.library.assets))
        self.window.refresh_sources(source["id"])
        self.search = self.root / "search"; self.search.mkdir()
        shutil.copyfile(path, self.search / "moved.png")
        self.dialog = SourceRelinkDialog(self.window); self.addCleanup(self.dialog.close)
        self.dialog.root = str(self.search)

    def test_background_preview_is_unselected_and_cancel_confirmation_writes_nothing(self):
        jobs = []
        with patch.object(self.window, "run_job", side_effect=lambda message, fn, callback: jobs.append((fn, callback))):
            self.dialog.search()
        self.assertTrue(self.dialog.busy)
        jobs[0][1](jobs[0][0]())
        self.assertFalse(self.dialog.busy)
        self.assertFalse(self.dialog.table.cellWidget(0, 0).isChecked())
        self.assertIsNone(self.dialog.table.cellWidget(0, 3).currentData())
        self.dialog.apply_selection()
        self.assertEqual(self.window.library.relink_batches(), [])
        self.dialog.table.cellWidget(0, 0).setChecked(True)
        self.dialog.table.cellWidget(0, 3).setCurrentIndex(1)
        with patch("template_ai.source_dialog.QMessageBox.question", return_value=QMessageBox.No): self.dialog.apply_selection()
        self.assertEqual(self.window.library.relink_batches(), [])

    def test_selected_batch_apply_and_gui_undo_preserve_work(self):
        work_id = self.window.work["id"]
        with patch.object(self.window, "run_job", side_effect=lambda message, fn, callback: callback(fn())):
            self.dialog.search()
            self.dialog.table.cellWidget(0, 0).setChecked(True)
            self.dialog.table.cellWidget(0, 3).setCurrentIndex(1)
            with patch("template_ai.source_dialog.QMessageBox.question", return_value=QMessageBox.Yes):
                self.dialog.apply_selection()
                self.assertEqual(self.window.source["link_revision"], 1)
                self.dialog.undo_batch()
        self.assertEqual(self.window.source["link_revision"], 2)
        self.assertEqual(self.window.work["id"], work_id)
        self.assertEqual(len(self.window.library.relink_batches()), 2)

    def test_cancelled_scan_or_worker_error_never_enables_commit(self):
        jobs = []
        with patch.object(self.window, "run_job", side_effect=lambda message, fn, callback: jobs.append((fn, callback))): self.dialog.search()
        self.dialog.cancel_event.set()
        jobs[0][1](jobs[0][0]())
        self.assertEqual(self.dialog.report["status"], "CANCELLED")
        self.assertFalse(self.dialog.apply_button.isEnabled())
        with patch("template_ai.source_dialog.discover_sources", side_effect=OSError("failed scan")), \
             patch.object(self.window, "run_job", side_effect=lambda message, fn, callback: callback(fn())): self.dialog.search()
        self.assertFalse(self.dialog.busy)
        self.assertIn("failed scan", self.dialog.status.text())
        self.assertEqual(self.window.library.relink_batches(), [])
