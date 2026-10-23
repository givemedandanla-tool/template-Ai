from pathlib import Path
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
from PySide6.QtTest import QTest
from template_ai.gui import MainWindow
from template_ai.multi_size_dialog import MultiSizeDialog
from template_ai.output_batch_dialog import OutputBatchDialog
from template_ai.background import file_digest
import test_multi_size as fixture
APP=fixture.APP
from runtime_fixture import controlled_resources
from gui_wait import job_diagnostics,wait_for_gui

class OutputBatchGuiTests(unittest.TestCase):
    setUp=fixture.MultiSizeTests.setUp
    tearDown=fixture.MultiSizeTests.tearDown
    requests=fixture.MultiSizeTests.requests
    def dialog(self):
        window=MainWindow(self.library.root);controlled_resources(window);self.addCleanup(window.deleteLater);self.addCleanup(window.library.close);self.addCleanup(window.font_manager.close);self.addCleanup(window.input_timer.stop);parent=MultiSizeDialog(window);self.addCleanup(parent.deleteLater);parent.service=self.workflow;parent.inputs=self.inputs;parent.graph=self.graph;parent.generation=7;parent.is_current=lambda:True
        d=OutputBatchDialog(parent,self.workflow.plan(self.output,self.requests()));self.addCleanup(d.deleteLater);d.show();APP.processEvents();return d,parent
    def finish(self,d):
        if wait_for_gui(lambda:not d.running,5):return
        self.fail('output worker did not finish within bounded test wait: '+job_diagnostics(d.host_window,'EXPORT')+'; dialog='+d.status.text())
    def test_actual_dialog_cancel_rename_skip_then_real_delivery_and_format_defaults(self):
        d,parent=self.dialog();self.assertEqual([k for k,v in parent.preview_formats.items() if v.isChecked()],['png']);self.assertEqual([k for k,v in parent.formats.items() if v.isChecked()],['pdf'])
        for name,action in d.controls[1:]:action.setCurrentIndex(action.findData('SKIP'))
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):d.run(False)
        self.assertIsNone(d.engine.scope);self.assertEqual(list(self.output.iterdir()),[])
        d.controls[0][0].setText('renamed_FINAL.pdf');fixture.approve_formats(self.workflow,d.engine.plan,d.dpi.value())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.run(False)
        self.finish(d);self.assertEqual(d.engine.items[0]['status'],'SUCCESS');self.assertTrue((self.output/'FINAL'/'renamed_FINAL.pdf').exists());self.assertTrue(all(row['status']=='SKIPPED' for row in d.engine.items[1:]));self.assertIn('SKIPPED',d.status.text())
    def test_actual_exact_retry_does_not_rewrite_success_and_cleanup_requires_specific_stage(self):
        import template_ai.output_batch as module
        d,parent=self.dialog()
        for name,action in d.controls[2:]:action.setCurrentIndex(action.findData('SKIP'))
        fixture.approve_formats(self.workflow,d.engine.plan,d.dpi.value())
        real=module.export
        def fail(candidate,target,**kwargs):
            if str(target).endswith('.pdf'):raise PermissionError('synthetic permission denied')
            return real(candidate,target,**kwargs)
        with patch.object(module,'export',side_effect=fail),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.run(False);self.finish(d)
        self.assertEqual(d.engine.items[0]['status'],'FAILED');self.assertEqual(d.engine.items[1]['status'],'SUCCESS');sha=file_digest(d.engine.items[1]['path']);d.table.selectRow(0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.run(True);self.finish(d)
        self.assertEqual(d.engine.items[0]['status'],'SUCCESS');self.assertEqual(file_digest(d.engine.items[1]['path']),sha);self.assertEqual(d.engine.items[1]['attempts'],1)
