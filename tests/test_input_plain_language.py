from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGroupBox

from template_ai.gui import MainWindow
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog


APP = QApplication.instance() or QApplication([])


class InputPlainLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.window = MainWindow(Path(self.temporary.name) / 'data')
        self.window.show(); self.editor = None; self.addCleanup(self.dispose)

    def dispose(self):
        if self.editor is not None:
            self.editor.close(); self.editor.deleteLater()
        self.window.close(); self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def open_graph(self, graph):
        self.editor = InputGraphDialog(self.window, graph.data)
        self.editor.show(); APP.processEvents()
        return self.editor

    def test_plain_normal_labels_preserve_full_ids_in_expandable_details(self):
        graph = InputGraph.from_legacy([dict(name='Alex', company='c1'), dict(name='Casey', company='c1')], [dict(name='Example Company', phone=['020-000-0100'])])
        original = deepcopy(graph.data); dialog = self.open_graph(graph)
        for term in ['ROOT', 'p1/c1', 'ID']:
            self.assertNotIn(term, dialog.status.text())
        self.assertFalse(dialog.technical_body.isVisible())
        for entity in [*graph.data['people'], *graph.data['companies']]:
            self.assertFalse(any(entity['id'] in box.title() for box in dialog.findChildren(QGroupBox)))
            self.assertIn(entity['id'], dialog.identity_details.toPlainText())
        first = dialog.tree.topLevelItem(0)
        self.assertEqual(first.data(0, Qt.UserRole), graph.data['people'][0]['id'])
        self.assertNotIn('ROOT', first.text(0))
        dialog.technical_group.setFocus(); QTest.keyClick(dialog.technical_group, Qt.Key_Space); APP.processEvents()
        self.assertTrue(dialog.technical_group.isChecked())
        self.assertTrue(dialog.technical_body.isVisible())
        self.assertIn('p1/c1', dialog.identity_details.toPlainText())
        self.assertIn('IDENTITY_REVIEW_REQUIRED', dialog.identity_details.toPlainText())
        for field in graph.data['fields']:
            self.assertIn(field['id'], dialog.identity_details.toPlainText())
        self.assertEqual(dialog.graph.data, original)
        self.assertIsNone(self.window.active_input_graph)

    def test_plain_problem_list_keeps_exact_field_navigation_and_private_data(self):
        graph = InputGraph.from_legacy([dict(name='')], [])
        dialog = self.open_graph(graph)
        issue = next(dialog.problems.item(i) for i in range(dialog.problems.count()) if dialog.problems.item(i).data(Qt.UserRole)['code'] == 'MISSING_NAME')
        field_id = issue.data(Qt.UserRole)['field_id']
        self.assertNotIn(field_id, issue.text())
        self.assertIn('姓名', issue.text())
        dialog.locate_warning(issue); APP.processEvents()
        self.assertTrue(dialog.field_editors[field_id].hasFocus())
        self.assertEqual(dialog.selected_id, field_id)
        self.assertEqual(dialog.graph.field(field_id)['value'], '')
        self.assertIsNone(self.window.active_input_graph)
