"""衍生快取是可重建資料；損壞不能被当作原稿成功匯入。"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from template_ai.importer import import_file, inkscape_path

APP = QApplication.instance() or QApplication([])


class SourceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / "original.png"
        image = QImage(400, 240, QImage.Format_ARGB32)
        image.fill(0xffffffff)
        image.save(str(self.original))
        self.original_bytes = self.original.read_bytes()
        self.original_mtime = self.original.stat().st_mtime_ns
        self.assets = self.root / "assets"

    def test_valid_cache_reused_without_rewriting(self):
        first = import_file(self.original, self.assets)
        path = Path(first["image"])
        before = path.stat().st_mtime_ns
        second = import_file(self.original, self.assets)
        self.assertTrue(second["reused"])
        self.assertEqual(path.stat().st_mtime_ns, before)

    def test_changed_preview_regenerated_original_unchanged(self):
        first = import_file(self.original, self.assets)
        path = Path(first["image"])
        original_preview = path.read_bytes()
        changed = QImage(400, 240, QImage.Format_ARGB32)
        changed.fill(0xffff0000)
        changed.save(str(path))
        second = import_file(self.original, self.assets)
        self.assertFalse(second["reused"])
        self.assertEqual(path.read_bytes(), original_preview)
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        self.assertEqual(self.original.stat().st_mtime_ns, self.original_mtime)

    def test_invalid_metadata_and_foreign_paths_are_not_reused(self):
        first = import_file(self.original, self.assets)
        metadata = Path(first["image"]).parent / "metadata.json"
        metadata.write_text("{ broken JSON", encoding="utf-8")
        recovered = import_file(self.original, self.assets)
        self.assertFalse(recovered["reused"])
        payload = json.loads(metadata.read_text(encoding="utf-8"))
        payload["image"] = str(self.original)
        if "metadata_sha256" in payload:
            check = {k: v for k, v in payload.items() if k != "metadata_sha256"}
            payload["metadata_sha256"] = hashlib.sha256(json.dumps(check, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        metadata.write_text(json.dumps(payload), encoding="utf-8")
        second = import_file(self.original, self.assets)
        self.assertFalse(second["reused"])
        self.assertEqual(Path(second["image"]), Path(first["image"]))
        self.assertEqual(self.original.read_bytes(), self.original_bytes)

    @unittest.skipIf(os.name == "nt", "Windows 建立符號連結需額外系統權限；本案例只證明本次 Linux")
    def test_symlink_cache_does_not_overwrite_original(self):
        first = import_file(self.original, self.assets)
        path = Path(first["image"])
        path.unlink()
        path.symlink_to(self.original)
        with self.assertRaisesRegex(ValueError, "符號連結"):
            import_file(self.original, self.assets)
        self.assertEqual(self.original.read_bytes(), self.original_bytes)

    @unittest.skipUnless(inkscape_path(), "需要實際 Inkscape 驗證向量快取恢復")
    def test_changed_vector_asset_regenerated(self):
        original = Path(__file__).parents[1] / "examples/synthetic-source.svg"
        first = import_file(original, self.assets)
        path = Path(first["svg"])
        expected = path.read_bytes()
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        second = import_file(original, self.assets)
        self.assertFalse(second["reused"])
        self.assertEqual(path.read_bytes(), expected)

    @unittest.skipUnless(inkscape_path(), "需要實際 Inkscape 快取及轉換失敗驗證")
    def test_failed_regeneration_does_not_restore_corrupt_cache_as_success(self):
        original = Path(__file__).parents[1] / "examples/synthetic-source.svg"
        first = import_file(original, self.assets)
        Path(first["svg"]).write_text("corrupted cached SVG", encoding="utf-8")
        with patch("template_ai.importer._run", side_effect=ValueError("模擬轉換器失敗")):
            with self.assertRaisesRegex(ValueError, "轉換器失敗"):
                import_file(original, self.assets)
