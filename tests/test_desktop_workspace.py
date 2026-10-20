"""Actual desktop composition, embedded sessions and stable data/preview flow."""
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer, QEvent, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QPushButton, QFileDialog

from template_ai.gui import MainWindow
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.design_learning import CrossWorkLearning
from template_ai.design_session import DesignSessions
from template_ai.design_synthesis import input_facts
from template_ai.model import new_id
from gui_wait import wait_for_gui, dispose_main_window
from runtime_fixture import controlled_resources
import test_design_session as fixtures

APP = QApplication.instance() or QApplication([])


def capture(widget, name):
    folder = os.environ.get("TEMPLATE_AI_DESKTOP_CAPTURE_DIR")
    if folder:
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        APP.processEvents()
        if not widget.grab().save(str(path / name)):
            raise AssertionError("Actual desktop capture failed")


class DesktopNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="desktop-navigation-")
        self.addCleanup(self.temp.cleanup)
        self.w = MainWindow(self.temp.name)
        controlled_resources(self.w)
        self.addCleanup(lambda: dispose_main_window(self.w))
        self.w.show()

    def test_real_navigation_keeps_three_modes_and_original_commands(self):
        w = self.w
        desk = w.desktop_workspace
        for index in (2, 1, 0):
            QTest.mouseClick(desk.nav_buttons[index], Qt.LeftButton)
            APP.processEvents()
            self.assertEqual(w.tabs.currentIndex(), index)
            self.assertEqual(desk.title.text(), desk.TITLES[index])
            capture(w, f"desktop-mode-{index}.png")
        actions = {action.text() for menu in desk.menu_groups.values() for action in menu.actions()}
        self.assertIn("本機完整關聯備份／還原", actions)
        self.assertIn("匯入合法本機字型", actions)
        self.assertIs(w.train_canvas.parentWidget().parentWidget(), desk.learning_page)
        self.assertFalse(w.property_panel.isVisible())

    def test_small_window_keeps_primary_and_canvas_visible_without_scrolling(self):
        w = self.w
        w.tabs.setCurrentIndex(2)
        w.resize(960, 640)
        APP.processEvents()
        desk = w.desktop_workspace
        visible = w.output_canvas.viewport().visibleRegion().boundingRect()
        self.assertGreaterEqual(visible.width(), 240)
        self.assertGreaterEqual(visible.height(), 180)
        self.assertEqual(desk.primary.visibleRegion().boundingRect(), desk.primary.rect())
        self.assertFalse(desk.other_fixed.isChecked())
        self.assertFalse(w.candidate_scroll.isVisible())
        desk.other_fixed.setChecked(True)
        desk.refresh()
        self.assertTrue(w.candidate_scroll.isVisible())
        self.assertTrue(w.preview_button.isVisible())
        capture(w, "desktop-small-window.png")

    def test_real_background_job_records_duration_without_private_message(self):
        received = []
        self.w.run_job("PRIVATE-LOCAL-JOB-TEXT", lambda: 42, received.append)
        self.assertTrue(wait_for_gui(lambda: not self.w.busy, 5))
        self.assertEqual(received, [42])
        report = self.w.offline_support.journal.report()
        events = report["events"]
        self.assertTrue(any(e["code"] == "ACTION_STARTED" for e in events))
        self.assertTrue(any(e["code"] == "ACTION_COMPLETED" and e["duration_ms"] >= 0 for e in events))
        self.assertNotIn("PRIVATE-LOCAL-JOB-TEXT", str(report))

    def test_real_guidance_navigation_opens_four_task_pages(self):
        from template_ai.guided_operations import GuidedOperationsDialog
        errors = []
        def inspect():
            dialog = APP.activeModalWidget()
            try:
                self.assertIsInstance(dialog, GuidedOperationsDialog)
                self.assertEqual(dialog.tabs.count(), 4)
                capture(dialog, "desktop-guidance.png")
            except BaseException as error:
                errors.append(error)
            finally:
                if dialog:
                    dialog.reject()
        QTimer.singleShot(0, self.w, inspect)
        QTest.mouseClick(self.w.desktop_workspace.guidance_button, Qt.LeftButton)
        if errors:
            raise errors[0]

    def test_real_support_navigation_exports_local_safe_report(self):
        from template_ai.offline_support_dialog import OfflineSupportPanel
        from template_ai.offline_support import read_support_bundle
        target = Path(self.temp.name) / "manual-support.zip"
        errors = []
        self.w.statusBar().showMessage("PRIVATE-CUSTOMER-LOCAL-TEXT")
        def export():
            dialog = APP.activeModalWidget()
            try:
                panel = dialog.findChild(OfflineSupportPanel)
                self.assertIsNotNone(panel)
                panel.stage.setCurrentIndex(panel.stage.findData("LAYOUT"))
                panel.missing.setCurrentIndex(panel.missing.findData("FONT"))
                QTest.mouseClick(panel.mark_button, Qt.LeftButton)
                with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "問題報告 (*.zip)")):
                    QTest.mouseClick(panel.export_button, Qt.LeftButton)
                self.assertTrue(target.is_file())
                report = read_support_bundle(target.read_bytes())
                self.assertTrue(any(e["missing"] == "FONT" for e in report["events"]))
                self.assertNotIn("PRIVATE-CUSTOMER-LOCAL-TEXT", str(report))
                capture(dialog, "desktop-offline-support.png")
            except BaseException as error:
                errors.append(error)
            finally:
                if dialog:
                    dialog.reject()
        QTimer.singleShot(0, self.w, export)
        QTest.mouseClick(self.w.desktop_workspace.support_button, Qt.LeftButton)
        if errors:
            raise errors[0]


class DesktopProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixtures.DesignSessionTests
        cls.fixture.setUpClass()
        cls.root = cls.fixture.root
        cls.model = cls.fixture.model

    @classmethod
    def tearDownClass(cls):
        cls.fixture.tearDownClass()

    def setUp(self):
        self.w = MainWindow(self.root / "data")
        controlled_resources(self.w)
        self.addCleanup(lambda: dispose_main_window(self.w))
        learning = CrossWorkLearning(self.w.library)
        active = learning.store.get("DESIGN_ACTIVE", "local-layout")
        learning.activate(self.model["id"], active["revision"] if active else 0, "Author",
                          dict(version="desktop-test", basis="Authored desktop test", approved=True, production=False), True)
        self.graph = InputGraph.from_legacy([dict(name="Alex Example", title="Designer", phone="+1 202 555 0100", email="alex@example.test")], [])
        self.w.adopt_input_graph(self.graph.data)
        self.w.tabs.setCurrentIndex(2)
        self.w.show()
        APP.processEvents()
        self.desk = self.w.desktop_workspace

    def solved(self):
        editor = self.desk.ensure_editor()
        editor.solve()
        self.desk.refresh()
        APP.processEvents()
        self.assertTrue(editor.canvas.boxes)
        self.assertIs(self.desk.preview_stack.currentWidget(), editor.canvas)
        capture(self.w, "desktop-learned-preview.png")
        return editor

    def modal(self, action, handler):
        errors = []
        observed = []
        def perform():
            modal = APP.activeModalWidget()
            try:
                self.assertIsInstance(modal, QDialog)
                handler(modal)
                observed.append(True)
            except BaseException as error:
                errors.append(error)
                if modal:
                    modal.reject()
        guard = QTimer()
        guard.setSingleShot(True)
        guard.timeout.connect(lambda: APP.activeModalWidget().reject() if APP.activeModalWidget() else None)
        guard.start(5000)
        QTimer.singleShot(0, self.w, perform)
        try:
            action()
        finally:
            guard.stop()
        if errors:
            raise errors[0]
        self.assertTrue(observed)

    def test_embedded_primary_confirms_and_exports_same_real_preview(self):
        editor = self.solved()
        self.assertEqual(self.desk.primary.text(), "確認這份預覽稿")
        QTest.mouseClick(self.desk.primary, Qt.LeftButton)
        row = editor.sessions.current(editor.session_id)
        self.assertTrue(row["confirmation"])
        self.assertEqual(self.desk.primary.text(), "儲存預覽稿")
        capture(self.w, "desktop-confirmed.png")
        self.desk.learned_more.setChecked(True)
        APP.processEvents()
        self.assertTrue(editor.candidate_choices.isVisible())
        self.assertTrue(editor.formal_button.isVisible())
        self.assertFalse(editor.formal_button.isEnabled())
        self.assertTrue(editor.artifacts.isVisible())
        path = self.root / (new_id() + "-desktop-preview.png")
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(path), "PNG (*.png)")):
            QTest.mouseClick(self.desk.primary, Qt.LeftButton)
        self.assertTrue(path.is_file())
        saved = editor.sessions.store.records("DESIGN_ACCEPTED_ARTIFACT")
        artifact = next(x for x in saved if x["session_id"] == row["id"] and x["path"] == str(path))
        self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(artifact["production"])

    def test_real_main_input_edit_invalidates_old_canvas_then_regenerates_latest_data(self):
        editor = self.solved()
        editor.confirm_preview()
        def edit(dialog):
            self.assertIsInstance(dialog, InputGraphDialog)
            field = next(f for f in dialog.graph.data["fields"] if f["kind"] == "phone")
            control = dialog.field_editors[field["id"]]
            control.selectAll()
            QTest.keyClicks(control, "+1 202 555 0199")
            dialog.refresh_warnings()
            QTest.mouseClick(dialog.adopt_button, Qt.LeftButton)
        self.modal(self.w.graph_button.click, edit)
        self.desk.refresh()
        self.assertIs(self.desk.preview_stack.currentWidget(), self.w.output_canvas)
        self.assertFalse(self.w.preview_button.isEnabled())
        capture(self.w, "desktop-stale-after-correction.png")
        self.assertTrue(any(f["value"] == "+1 202 555 0199" for f in self.w.active_input_graph.data["fields"]))
        self.desk.generate()
        self.assertTrue(wait_for_gui(lambda: editor.solve_worker is None or not editor.solve_worker.isRunning(), 15))
        APP.processEvents()
        self.desk.refresh()
        row, result, candidate = editor.sessions.checked_result(editor.session_id)
        self.assertIsNone(row.get("confirmation"))
        self.assertTrue(any(f["value"] == "+1 202 555 0199" for f in row["input_graph"]["fields"]))
        self.assertIs(self.desk.preview_stack.currentWidget(), editor.canvas)
        capture(self.w, "desktop-corrected-preview.png")

    def test_external_session_revision_clears_embedded_old_result_and_confirmation(self):
        editor = self.solved()
        editor.confirm_preview()
        row = editor.sessions.current(editor.session_id)
        facts = input_facts(InputGraph(row["input_graph"]))
        phone = next(f["render_id"] for f in facts if f["kind"] == "phone")
        email = next(f["render_id"] for f in facts if f["kind"] == "email")
        editor.sessions.set_relation(row["id"], row["revision"], new_id(), phone, "LEFT_OF", email)
        self.desk.refresh()
        self.assertFalse(editor.confirm_button.isEnabled())
        self.assertFalse(editor.export_button.isEnabled())
        self.assertEqual(editor.canvas.boxes, [])
        self.assertEqual(self.desk.primary.text(), "產生稿件")

    def test_resume_selector_updates_main_graph_dimensions_and_embedded_session(self):
        editor = self.solved()
        graph = InputGraph.from_legacy([dict(name="Second Person", phone="+1 202 555 0199", email="second@example.test")], [])
        other = editor.sessions.create(graph, 120, 80, "Author", self.model["id"],
                                       dict(version="desktop-resume", approved=True, production=False))
        def choose(dialog):
            choices = dialog.findChild(QComboBox, "resumeDraftChoice")
            self.assertIsNotNone(choices)
            self.assertGreaterEqual(choices.findData(other["id"]), 0)
            choices.setCurrentIndex(choices.findData(other["id"]))
            QTest.mouseClick(dialog.findChild(QPushButton, "resumeDraftAccept"), Qt.LeftButton)
        self.modal(self.desk.resume_saved, choose)
        self.assertEqual(self.w.production_session_id, other["id"])
        self.assertEqual(editor.session_id, other["id"])
        self.assertEqual(self.w.active_input_graph.data, graph.data)
        self.assertEqual((self.w.out_w.value(), self.w.out_h.value()), (120, 80))
        self.assertEqual(editor.canvas.boxes, [])
        self.assertFalse(self.w.preview_button.isEnabled())

    def test_real_background_cancel_stays_enabled_and_close_waits_for_worker(self):
        editor = self.desk.ensure_editor()
        entered, release = threading.Event(), threading.Event()
        original = DesignSessions.solve
        def gated(service, *args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("Test barrier timeout")
            return original(service, *args, **kwargs)
        with patch.object(DesignSessions, "solve", gated):
            try:
                self.desk.generate()
                self.assertTrue(wait_for_gui(entered.is_set, 2))
                self.desk.refresh()
                self.assertTrue(self.w.busy)
                self.assertTrue(self.desk.primary.isEnabled())
                self.assertEqual(self.desk.primary.text(), "停止這次排版")
                self.assertFalse(self.desk.can_close())
                QTest.mouseClick(self.desk.primary, Qt.LeftButton)
                self.assertTrue(editor.solve_worker.cancel.is_set())
            finally:
                release.set()
                self.assertTrue(wait_for_gui(lambda: not self.w.busy, 10))
        self.assertTrue(self.desk.can_close())

    def test_embedded_pointer_drag_keeps_same_core_intent_and_data(self):
        editor = self.solved()
        before = editor.sessions.current(editor.session_id)["input_graph"]
        box, target = editor.canvas.boxes[:2]
        start = editor.canvas.mapFromScene(box.sceneBoundingRect().center())
        end = editor.canvas.mapFromScene(target.sceneBoundingRect().center() + QPointF(0, 3))
        viewport = editor.canvas.viewport()
        QTest.mousePress(viewport, Qt.LeftButton, Qt.NoModifier, start)
        movement = QMouseEvent(QEvent.MouseMove, QPointF(end), QPointF(viewport.mapToGlobal(end)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        APP.sendEvent(viewport, movement)
        QTest.mouseRelease(viewport, Qt.LeftButton, Qt.NoModifier, end)
        self.assertTrue(wait_for_gui(lambda: bool(editor.sessions.current(editor.session_id)["intents"]), 5))
        self.assertTrue(wait_for_gui(lambda: not self.w.busy, 15))
        row = editor.sessions.current(editor.session_id)
        self.assertEqual(row["input_graph"], before)
        self.assertIsNone(row.get("confirmation"))
        self.assertTrue(row["intents"])
        capture(self.w, "desktop-after-drag.png")


if __name__ == "__main__":
    unittest.main()
