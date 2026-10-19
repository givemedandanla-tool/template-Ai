"""Authored, locally rendered source fixture; no real customer corpus."""
import unittest
import tempfile
import shutil
from pathlib import Path
import test_design_session as source_fixture

from template_ai.storage import Library
from template_ai.family_workspace import FamilyWorkspace, reference
from template_ai.family_rules import FamilyRuleDrafts
from template_ai.training_store import digest


class FamilyFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_fixture.DesignSessionTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        local=tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(local.cleanup)
        target=Path(local.name)/'data'
        shutil.copytree(self.root/'data',target)
        self.library = Library(target)
        self.addCleanup(self.library.close)
        self.workspace = FamilyWorkspace(self.library)
        self.rules = FamilyRuleDrafts(self.library)
        self.current_model, _ = self.workspace.learning.checked_model(self.model['id'])
        self.profile = self.current_model['artifact']['profile_model']['families'][0]
        self.ref = reference(self.current_model, self.profile)

    def draft(self):
        return self.rules.create(self.ref, 'Authored synthetic reviewer')

    def reorder(self):
        return dict(kind='DEFAULT_ORDER', order=list(reversed([r['key'] for r in self.profile['roles']])))

    def apply(self, draft, operation, request='request'):
        return self.rules.command(draft['id'], draft['revision'], request, 'APPLY', 'Reviewer', operation)
