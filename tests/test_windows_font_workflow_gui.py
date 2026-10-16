"""Actual default-No GUI with an explicitly fake OS handoff, no system install."""
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
import test_font_source_context_gui as fixture
from template_ai.windows_font_dialog import WindowsFontWorkflowDialog

class WindowsFontWorkflowGuiTests(unittest.TestCase):
    setUp=fixture.FontSourceContextGuiTests.setUp
    wait=fixture.FontSourceContextGuiTests.wait
    def make(self):
        r=WindowsFontWorkflowDialog(self.d);self.addCleanup(r.deleteLater);r.show();r.actor.setText('Synthetic author');r.basis.setText('Authored install workflow permission');return r
    def test_current_linux_action_stays_disabled_and_direct_call_does_not_launch(self):
        with patch('sys.platform','linux'),patch('template_ai.windows_font_workflow._launch_viewer') as launch:
            self.d.update_windows_action()
            self.assertFalse(self.d.windows_button.isEnabled());self.d.open_windows_workflow();launch.assert_not_called();self.assertIsNone(self.d.windows_receipt)
    def test_independent_default_no_and_final_decline_never_start_backend(self):
        r=self.make()
        with patch('template_ai.windows_font_workflow.open_windows_font_workflow') as launch,patch.object(QMessageBox,'question',return_value=QMessageBox.No) as question:
            self.assertFalse(r.consent.isChecked());r.begin();launch.assert_not_called();question.assert_not_called();r.consent.setChecked(True);r.begin();launch.assert_not_called();self.assertEqual(question.call_args.args[-1],QMessageBox.No);self.assertIsNone(r.receipt)
    def test_confirmed_mock_os_handoff_keeps_pending_state_and_restores_owned_controls(self):
        r=self.make();r.consent.setChecked(True);receipt=dict(state='VIEWER_OPENED_PENDING_OS_ACTION',system_installed=None,reason='Only original viewer opened, no installation result')
        with patch('template_ai.windows_font_workflow.open_windows_font_workflow',return_value=receipt) as launch,patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):r.begin();self.wait()
        import sys
        launch.assert_called_once();self.assertEqual(self.d.windows_receipt,receipt);self.assertIsNone(r.receipt['system_installed']);self.assertFalse(r.running);self.assertTrue(r.open_button.isEnabled());self.assertEqual(self.d.windows_button.isEnabled(),sys.platform=='win32')

if __name__=='__main__':unittest.main()
