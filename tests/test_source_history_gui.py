"""Actual undo/redo confirmation shows every live multi-size consumer first."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog,QPlainTextEdit,QDialogButtonBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
import test_multi_size_edit_gui as fixture
from template_ai.input_graph_dialog import InputGraphDialog
APP=fixture.APP


class SourceHistoryGuiTests(unittest.TestCase):
    setUp=fixture.MultiSizeEditGuiTests.setUp
    tearDown=fixture.MultiSizeEditGuiTests.tearDown
    wait=fixture.MultiSizeEditGuiTests.wait
    change_source=fixture.MultiSizeEditGuiTests.change_source
    def inspect_confirmation(self,approved,seen):
        real_exec=QDialog.exec
        def actual(dialog):
            def click():
                seen.append(dialog.findChild(QPlainTextEdit).toPlainText());buttons=dialog.findChild(QDialogButtonBox);QTest.mouseClick(buttons.button(QDialogButtonBox.Yes if approved else QDialogButtonBox.No),Qt.LeftButton)
            QTimer.singleShot(30,dialog,click);return real_exec(dialog)
        return patch.object(QDialog,'exec',actual)
    def test_actual_undo_cancel_displays_both_size_consumers_without_source_change(self):
        self.change_source();editor=InputGraphDialog(self.w);editor.show();before=copy.deepcopy(editor.graph.data);seen=[]
        with self.inspect_confirmation(False,seen):editor.undo()
        self.assertEqual(editor.graph.data,before);self.assertEqual(len(seen),1);self.assertIn('90',seen[0]);self.assertIn('100',seen[0]);self.assertIn('涉及框位',seen[0]);self.assertEqual(self.w.active_input_graph.data,before)
    def test_actual_undo_then_redo_require_impact_confirmation_and_stay_unadopted(self):
        self.change_source();global_before=copy.deepcopy(self.w.active_input_graph.data);editor=InputGraphDialog(self.w);editor.show();seen=[]
        with self.inspect_confirmation(True,seen):editor.undo()
        self.assertTrue(any(f['value']=='Alex' for f in editor.graph.data['fields']));self.assertEqual(self.w.active_input_graph.data,global_before);self.assertIn('多尺寸',editor.source_impacts.toPlainText())
        with self.inspect_confirmation(True,seen):editor.redo()
        self.assertTrue(any(f['value']=='Alex Updated' for f in editor.graph.data['fields']));self.assertEqual(len(seen),2);self.assertEqual(self.w.active_input_graph.data,global_before);self.assertFalse(self.d.is_current())
