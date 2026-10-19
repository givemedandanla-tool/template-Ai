from copy import deepcopy
from pathlib import Path
import os
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget,QDialog
from template_ai.storage import Library
from template_ai.design_learning_dialog import DesignLearningDialog
from template_ai.design_session import DesignSessions
from template_ai.input_graph import InputGraph
import test_design_session as session_fixture

APP=QApplication.instance() or QApplication([])


class DesktopSharedLearningWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=session_fixture.DesignSessionTests;cls.fixture.setUpClass()
        cls.root=cls.fixture.root;cls.model=cls.fixture.model
    @classmethod
    def tearDownClass(cls):cls.fixture.tearDownClass()
    def setUp(self):
        self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        self.parent=QWidget();self.parent.library=self.library;self.addCleanup(self.parent.deleteLater)
        self.sessions=DesignSessions(self.library)
        graph=InputGraph.from_legacy([dict(name='Alex Example',title='Designer',phone='+1 202 555 0100',email='alex@example.test')],[])
        self.session=self.sessions.create(graph,90,54,'Author',self.model['id'],
            dict(version='authored-gui-1',approved=True,production=False))
        self.dialog=DesignLearningDialog(self.parent);self.addCleanup(self.dialog.close)
        self.dialog.session_id=self.session['id'];self.dialog.save_workspace();self.dialog.tabs.setCurrentIndex(2)
        self.dialog.show();APP.processEvents()
    def test_actual_desktop_solve_confirm_export_and_reopen_keeps_same_artifact(self):
        self.dialog.solve();APP.processEvents()
        self.assertTrue(self.dialog.confirm_button.isEnabled());self.assertTrue(self.dialog.canvas.boxes)
        QTest.mouseClick(self.dialog.confirm_button,Qt.LeftButton);APP.processEvents()
        self.assertTrue(self.dialog.export_button.isEnabled())
        target=self.root/('PREVIEW-gui-'+self.session['id']+'.png')
        with patch('template_ai.design_learning_dialog.QFileDialog.getSaveFileName',return_value=(str(target),'PNG')):
            QTest.mouseClick(self.dialog.export_button,Qt.LeftButton);APP.processEvents()
        self.assertTrue(target.is_file(),self.dialog.status.text());identity=self.dialog.artifacts.currentData()
        self.assertTrue(identity);first=self.sessions.replay_artifact(identity)
        capture=os.environ.get('TEMPLATE_AI_DESIGN_GUI_CAPTURE')
        if capture:self.dialog.grab().save(capture)
        self.dialog.close();reopened=DesignLearningDialog(self.parent)
        try:
            self.assertEqual(reopened.session_id,self.session['id'])
            self.assertEqual(reopened.sessions.replay_artifact(identity)['sha256'],first['sha256'])
        finally:reopened.close()
    def test_relative_dropdown_edit_data_return_and_undo_do_not_restore_old_phone(self):
        self.dialog.solve();fields={row['kind']:row for row in __import__('template_ai.design_synthesis',fromlist=['input_facts']).input_facts(InputGraph(self.session['input_graph']))}
        self.dialog.set_relation(fields['phone']['render_id'],'BELOW',fields['email']['render_id'])
        current=self.sessions.current(self.session['id']);graph=InputGraph(deepcopy(current['input_graph']))
        next(field for field in graph.data['fields'] if field['kind']=='phone')['value']='+1 202 555 0199'
        class AcceptedInput:
            def __init__(self,*args,**kwargs):self.graph=graph
            def exec(self):return QDialog.Accepted
        with patch('template_ai.input_graph_dialog.InputGraphDialog',AcceptedInput):self.dialog.edit_data()
        self.assertFalse(self.dialog.confirm_button.isEnabled());self.assertTrue(self.sessions.current(current['id'])['intents'])
        self.dialog.solve();self.dialog.undo_layout()
        after=self.sessions.current(current['id'])
        self.assertEqual(next(field for field in after['input_graph']['fields'] if field['kind']=='phone')['value'],'+1 202 555 0199')
        self.assertEqual(after['intents'],[]);self.assertTrue(self.dialog.confirm_button.isEnabled())
    def test_source_correspondence_is_never_automatically_confirmed_and_draft_has_no_fine_controls(self):
        self.assertFalse(self.dialog.source_confirm.isChecked())
        before=self.dialog.jobs.store.count('DESIGN_SOURCE_BINDING')
        self.dialog.attempt(self.dialog.bind_source)
        self.assertEqual(before,self.dialog.jobs.store.count('DESIGN_SOURCE_BINDING'))
        draft=self.dialog.tabs.widget(2)
        self.assertEqual(len(draft.findChildren(__import__('PySide6.QtWidgets',fromlist=['QDoubleSpinBox']).QDoubleSpinBox)),2)
