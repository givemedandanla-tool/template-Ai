"""使用環境既有字型驗證本機複本與重開；字型檔不加入倉庫或交付包。"""
import copy
import os
from pathlib import Path
import shutil
import sqlite3
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox

from template_ai.demo import demo_template
from template_ai.fonts import FontManager
from template_ai.gui import MainWindow
from template_ai.layout import generate
from template_ai.render import export
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])
FONT = next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                        Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),
                        Path(r'C:\Windows\Fonts\arial.ttf')) if p.is_file()), None)
DATA = [{"name": "Alex Example", "title": "Consultant", "phone": "0900-123-456", "email": "hello@example.test"}]


@unittest.skipUnless(FONT, "沒有可用環境字型，持久字型實際載入驗證跳過")
class PersistentFontTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = Library(self.root / "data")
        self.addCleanup(self.library.close)
        self.manager = FontManager(self.library)
        self.addCleanup(self.manager.close)

    def test_copy_reopen_and_original_removal_do_not_lose_font(self):
        original = self.root / "original.ttf"
        shutil.copyfile(FONT, original)
        asset = self.manager.import_font(original, approved=True)
        original.unlink()
        self.assertTrue(Path(asset["path"]).is_file())
        self.manager.close()
        reopened = FontManager(self.library)
        try:
            self.assertIn(asset["hash"], reopened.loaded)
            self.assertEqual(reopened.issues, [])
            self.assertIn(asset["families"][0], QFontDatabase.families())
        finally:
            reopened.close()

    def test_new_python_process_loads_persisted_font(self):
        asset = self.manager.import_font(FONT, approved=True)
        script = "from PySide6.QtWidgets import QApplication; from template_ai.storage import Library; from template_ai.fonts import FontManager; import json,sys; app=QApplication([]); library=Library(sys.argv[1]); manager=FontManager(library); print(json.dumps({'loaded':list(manager.loaded),'issues':manager.issues})); manager.close(); library.close()"
        result = subprocess.run([sys.executable, "-c", script, str(self.library.root)],
                                cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"loaded": [asset["hash"]], "issues": []})

    def test_unapproved_invalid_and_duplicate_font_protect_catalog(self):
        with self.assertRaisesRegex(ValueError, "確認有權"):
            self.manager.import_font(FONT)
        bad = self.root / "not-a-font.ttf"
        bad.write_bytes(b"not a font")
        with self.assertRaisesRegex(ValueError, "無法解析OpenType"):
            self.manager.import_font(bad, approved=True)
        self.assertEqual(self.library.fonts(), [])
        folder=self.library.assets / 'fonts'
        self.assertEqual(list(folder.iterdir()) if folder.exists() else [], [])
        asset = self.manager.import_font(FONT, approved=True)
        self.assertEqual(self.manager.import_font(FONT, approved=True), asset)
        self.assertEqual(len(self.library.fonts()), 1)

    def test_changed_or_missing_asset_blocks_even_if_system_font_exists(self):
        asset = self.manager.import_font(FONT, approved=True)
        template = demo_template()
        for slot in template.slots:
            slot.font, slot.font_asset = asset["families"][0], copy.deepcopy(asset)
        template.state = "published"
        candidate = generate(template, DATA, [], {})
        self.assertTrue(candidate.valid, candidate.issues)
        self.manager.close()
        Path(asset["path"]).write_bytes(b"changed after candidate was generated")
        self.assertFalse(generate(template, DATA, [], {}).valid)
        with self.assertRaisesRegex(ValueError, "內容已變更"):
            export(candidate, self.root / "must-not-export.pdf")
        self.assertFalse((self.root / "must-not-export.pdf").exists())
        Path(asset["path"]).unlink()
        failed_loader = FontManager(self.library)
        try:
            self.assertEqual(failed_loader.loaded, {})
            self.assertIn("失聯", "；".join(failed_loader.issues))
        finally:
            failed_loader.close()

    def test_same_family_different_file_is_not_silently_replaced(self):
        first = self.manager.import_font(FONT, approved=True)
        alternative = self.root / "different-content.ttf"
        alternative.write_bytes(FONT.read_bytes() + b"\0\0\0\0")
        with self.assertRaisesRegex(ValueError, "不同檔案版本"):
            self.manager.import_font(alternative, approved=True)
        self.assertEqual(self.library.fonts(), [first])

    def test_catalog_failure_removes_only_new_asset(self):
        with patch.object(self.library, "event", side_effect=sqlite3.OperationalError("simulated database failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.manager.import_font(FONT, approved=True)
        self.assertEqual(self.library.fonts(), [])
        self.assertEqual(list((self.library.assets / "fonts").iterdir()), [])

    def test_gui_import_binds_file_and_reopens_without_dialog(self):
        window = MainWindow(self.root / "gui")
        window.tabs.setCurrentIndex(1)
        window.add_demo()
        window.select_slot(window.template.slots[0])
        with patch("template_ai.gui.QFileDialog.getOpenFileName", return_value=(str(FONT), "")), \
             patch("template_ai.gui.QMessageBox.question", return_value=QMessageBox.Yes), \
             patch.object(window, "inform"):
            window.import_font()
        window.apply_properties()
        asset = window.template.slots[0].font_asset
        self.assertIsNotNone(asset)
        window.close()
        reopened = MainWindow(self.root / "gui")
        try:
            self.assertIn(asset["hash"], reopened.font_manager.loaded)
            self.assertEqual(reopened.template.slots[0].font_asset, asset)
        finally:
            reopened.close()
