"""Actual async background review must preserve a changed draft/asset decision."""
from copy import deepcopy
from pathlib import Path
import tempfile,time,unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox
from template_ai.gui import MainWindow
from template_ai.demo import demo_template
from template_ai.importer import import_file
from template_ai.background import make_background
from gui_wait import dispose_main_window
from runtime_fixture import controlled_resources
APP=QApplication.instance() or QApplication([])

class BackgroundContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.w=MainWindow(self.root/'data');controlled_resources(self.w);self.addCleanup(self.cleanup)
        self.template=demo_template();self.w.library.save_template(self.template);self.w.open_catalog_editor(self.template.id);self.w.show();APP.processEvents()
        self.notices=[];self.errors=[];self.w.inform=self.notices.append;self.w.error=self.errors.append
        self.path=self.svg('first.svg','#ff0000');self.original=self.w.library.object_snapshot('TEMPLATE',self.template.id)

    def cleanup(self):
        end=time.monotonic()+30
        while self.w.busy and time.monotonic()<end:APP.processEvents();QTest.qWait(10)
        dispose_main_window(self.w)

    def svg(self,name,color):
        path=self.root/name;path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect width="90" height="54" fill="{color}"/></svg>');return path

    def test_missing_draft_after_file_picker_is_plain_rejection(self):
        def choose(*args):self.w.template=None;return str(self.path),''
        with patch('template_ai.gui.QFileDialog.getOpenFileName',side_effect=choose):self.w.import_background()
        self.assertIsNone(self.w.template);self.assertFalse(self.w.busy);self.assertTrue(self.notices);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.template.id),self.original)

    def approval_race(self,replace):
        if replace:
            replacement=deepcopy(self.template);replacement.id='authored-background-replacement';replacement.family_id='authored-background-family';replacement.name='Authored replacement';self.w.library.save_template(replacement)
        else:
            second=import_file(self.svg('second.svg','#00ff00'),self.w.library.assets);replacement=make_background(second,90,54);replacement['approved']=True
        seen=[];expected=[];transition_errors=[];timer=QTimer()
        def inspect():
            modal=APP.activeModalWidget()
            if not isinstance(modal,QDialog) or modal.windowTitle()!='核對固定背景':return
            timer.stop();seen.append(True)
            try:
                if replace:
                    self.w.open_catalog_editor(replacement.id)
                    self.assertEqual(self.w.template.id,replacement.id)
                else:self.w.template.background=replacement
                expected.append(deepcopy(self.w.template.to_dict()))
                buttons=modal.findChild(QDialogButtonBox);self.assertIsNotNone(buttons);QTest.mouseClick(buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
            except BaseException as error:
                transition_errors.append(type(error).__name__);modal.reject()
        timer.timeout.connect(inspect);timer.start(10)
        try:
            with patch('template_ai.gui.QFileDialog.getOpenFileName',return_value=(str(self.path),'')):self.w.import_background()
            end=time.monotonic()+30
            while (self.w.busy or not seen) and time.monotonic()<end:APP.processEvents();QTest.qWait(10)
            APP.processEvents();self.assertEqual(transition_errors,[]);self.assertEqual(seen,[True],'The actual product review dialog must be reached once');self.assertEqual(self.w.template.to_dict(),expected[0]);self.assertTrue(self.notices)
            self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.template.id),self.original)
            if replace:self.assertEqual(self.w.library.template(replacement.id).to_dict(),expected[0])
        finally:timer.stop()

    def test_registered_draft_switch_during_review_is_not_overwritten(self):self.approval_race(True)
    def test_changed_background_choice_during_review_is_not_overwritten(self):self.approval_race(False)
