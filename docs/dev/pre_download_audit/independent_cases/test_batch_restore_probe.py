"""Expose the real batch restore failure without blocking in its error dialog."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tests'))
from template_ai.gui import MainWindow
from test_batch_recovery import BatchRecoveryCandidateTests


class BatchRestoreProbeTests(unittest.TestCase):
    def test_existing_batch_restore_with_nonblocking_error_observation(self):
        errors = []
        case = BatchRecoveryCandidateTests(
            'test_actual_gui_restore_then_selected_inverse_keeps_same_stable_field_identity')
        result = unittest.TestResult()
        with patch.object(MainWindow, 'error', lambda window, text: errors.append(str(text))):
            case.run(result)
        self.assertEqual(errors, [], 'Actual error dialog contents: ' + repr(errors))
        self.assertTrue(result.wasSuccessful(), repr(result.errors + result.failures))
