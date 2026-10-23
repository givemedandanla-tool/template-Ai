"""Real font validation plus fake OS launcher; no Windows qualification claim."""
import unittest
from pathlib import Path
from unittest.mock import patch
import test_font_center as fixture
from template_ai.font_evidence import inspect_font
from template_ai.windows_font_workflow import open_windows_font_workflow

class WindowsFontWorkflowTests(unittest.TestCase):
    setUp=fixture.FontCatalogTests.setUp
    def test_import_approval_never_supplies_nonliteral_or_missing_windows_consent(self):
        with patch('template_ai.windows_font_workflow._launch_viewer') as launch:
            for consent in (False,0,1,None,'yes'):
                with self.assertRaises(ValueError):open_windows_font_workflow(self.asset,'Synthetic author','Authored install permission',consent)
            launch.assert_not_called()
    def test_nonwindows_refuses_even_with_explicit_consent(self):
        with patch('template_ai.windows_font_workflow.sys.platform','linux'),patch('template_ai.windows_font_workflow._launch_viewer') as launch:
            with self.assertRaisesRegex(ValueError,'不是Windows'):open_windows_font_workflow(self.asset,'Synthetic author','Authored install permission',True)
            launch.assert_not_called()
    def test_confirmed_exact_current_font_opens_only_viewer_and_never_claims_installation(self):
        before=self.library.fonts()
        with patch('template_ai.windows_font_workflow.sys.platform','win32'),patch('template_ai.windows_font_workflow._launch_viewer',return_value=12345) as launch:
            result=open_windows_font_workflow(self.asset,'Synthetic author','Authored install permission',True)
        launch.assert_called_once_with(Path(self.asset['path']).resolve());self.assertIsNone(result['system_installed']);self.assertEqual(result['state'],'VIEWER_OPENED_PENDING_OS_ACTION');self.assertEqual(result['asset_sha256'],self.asset['hash']);self.assertEqual(self.library.fonts(),before)
    def test_changed_source_is_not_opened_under_old_authorization(self):
        Path(self.asset['path']).write_bytes(b'changed local fixture')
        with patch('template_ai.windows_font_workflow.sys.platform','win32'),patch('template_ai.windows_font_workflow._launch_viewer') as launch:
            with self.assertRaises(ValueError):open_windows_font_workflow(self.asset,'Synthetic author','Authored install permission',True)
            launch.assert_not_called()
    def test_mutation_after_inspection_is_rejected_before_os_action(self):
        def changed(path):
            proof=inspect_font(path);Path(path).write_bytes(b'late changed local fixture');return proof
        with patch('template_ai.windows_font_workflow.sys.platform','win32'),patch('template_ai.windows_font_workflow.inspect_font',side_effect=changed),patch('template_ai.windows_font_workflow._launch_viewer') as launch:
            with self.assertRaises(ValueError):open_windows_font_workflow(self.asset,'Synthetic author','Authored install permission',True)
            launch.assert_not_called()
    def test_blank_or_control_character_actor_and_permission_are_rejected(self):
        with patch('template_ai.windows_font_workflow._launch_viewer') as launch:
            for actor,basis in (('','yes'),('Actor',''),('Actor\nOther','Legal'),('Actor','x'*2001)):
                with self.assertRaises(ValueError):open_windows_font_workflow(self.asset,actor,basis,True)
            launch.assert_not_called()

if __name__=='__main__':unittest.main()
