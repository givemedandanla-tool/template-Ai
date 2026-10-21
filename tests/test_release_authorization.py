import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dev_governance import verify_exe_authorization


class ReleaseAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workflow = self.root / '.github/workflows/first-version.yml'
        self.workflow.parent.mkdir(parents=True)
        self.text = "name: release\non:\n  workflow_dispatch:\n  push:\n    branches: ['release-request/v0.2.0-beta.1']\npermissions:\n  contents: read\n"
        self.workflow.write_text(self.text, encoding='utf-8')
        self.state = dict(exe_policy='EXPLICIT_V0_2_0_BETA_1_RELEASE_AUTHORIZED_NO_GENERAL_PUSH_BUILD',
            windows_release=dict(version='0.2.0-beta.1', authorization=dict(scope='PUBLISH_WINDOWS_INTERNAL_BETA',
                user_request='好，現在我要你在github發佈程式本體exe，讓我投入實機測試')))

    def test_exact_authorized_request_branch_and_manual_dispatch_are_allowed(self):
        verify_exe_authorization(self.root, self.state)

    def test_normal_push_and_pr_cannot_be_enabled_by_beta_authorization(self):
        for value in [self.text.replace("['release-request/v0.2.0-beta.1']", "['**']"),
                      self.text.replace('  push:', '  pull_request:'),
                      self.text.replace('  workflow_dispatch:', '  workflow_dispatch:\n  pull_request:')]:
            self.workflow.write_text(value, encoding='utf-8')
            with self.assertRaises(ValueError): verify_exe_authorization(self.root, self.state)

    def test_wrong_version_or_missing_explicit_scope_is_rejected(self):
        for key, value in [('version', '0.2.0'), ('authorization', {})]:
            state = copy.deepcopy(self.state)
            state['windows_release'][key] = value
            with self.assertRaises(ValueError): verify_exe_authorization(self.root, state)

    def test_historical_deferred_policy_still_rejects_automatic_trigger(self):
        with self.assertRaises(ValueError):
            verify_exe_authorization(self.root, dict(exe_policy='DEFERRED_NO_AUTOMATIC_BUILD'))
        self.workflow.write_text('name: old\non:\n  workflow_dispatch:\n', encoding='utf-8')
        verify_exe_authorization(self.root, dict(exe_policy='DEFERRED_NO_AUTOMATIC_BUILD'))
