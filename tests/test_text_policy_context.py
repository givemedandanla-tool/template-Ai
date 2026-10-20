"""Real policy dialog must revalidate the draft after the confirmation event loop."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
import test_text_policy as text_policy_source
from template_ai.text_policy_dialog import TextPolicyDialog


class TextPolicyContextTests(unittest.TestCase):
    setUp=text_policy_source.TextPolicyTests.setUp
    # Reuse real MainWindow setup without adding parent test copies.
    def dialog(self):
        self.w.editor_selection([self.w.template.slots[1].id])
        d=TextPolicyDialog(self.w);self.addCleanup(d.close);d.values[0].setValue(.2)
        return d

    def test_missing_draft_is_plain_rejection(self):
        d=self.dialog();self.w.template=None
        d.apply()
        self.assertIn('未套用',d.status.text())
        self.assertIn('草稿已變更',d.status.text())
        self.assertIsNone(self.w.template)

    def test_replacement_draft_during_confirmation_is_not_overwritten(self):
        self.confirmation_race(replace=True)

    def test_changed_same_draft_during_confirmation_is_not_overwritten(self):
        self.confirmation_race(replace=False)

    def confirmation_race(self,replace):
        d=self.dialog();replacement=deepcopy(self.w.template)
        if replace:replacement.id='authored-replacement-draft'
        replacement.name='Authored changed draft';before=replacement.to_dict()
        def confirm(*args):
            self.w.template=replacement
            return QMessageBox.Yes
        with patch('template_ai.text_policy_dialog.QMessageBox.question',side_effect=confirm):d.apply()
        self.assertEqual(self.w.template.to_dict(),before)
        self.assertIn('未套用',d.status.text())
        self.assertIn('草稿已變更',d.status.text())
