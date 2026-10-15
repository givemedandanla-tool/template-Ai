import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from evidence_publication import waived_attachments


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'docs/dev').mkdir(parents=True)
        (self.root / 'docs/dev/TEN_PACKAGES_DESIGN.md').write_text('Synthetic policy contract')
        self.run = {'id': 'RUN-X', 'source_commit': 'a' * 40,
                    'attachments': {'gui.png': {'bytes': 12, 'sha256': 'b' * 64},
                                    'tests.json': {'bytes': 12, 'sha256': 'b' * 64}}}
        self.policy = {'policy': 'USER_AUTHORIZED_METADATA_FIRST_TEN_PACKAGES',
                       'user_instruction': '如果這只是證明文件就略過',
                       'contract': 'docs/dev/TEN_PACKAGES_DESIGN.md',
                       'runs': {'RUN-X': {'source_commit': 'a' * 40,
                                         'attachments': {'gui.png': {'bytes': 12, 'sha256': 'b' * 64}}}}}
    def save(self):
        (self.root / 'docs/dev/TEN_PACKAGES_PUBLICATION.json').write_text(json.dumps(self.policy))
    def test_exact_source_bound_named_media_only(self):
        self.save(); result, policies = waived_attachments(self.root, 'docs/evidence/runs/RUN-X/run.json', self.run)
        self.assertEqual(list(result), ['docs/evidence/runs/RUN-X/gui.png'])
        self.assertEqual(policies, ['docs/dev/TEN_PACKAGES_PUBLICATION.json'])
    def test_wrong_source_hash_size_and_metadata_cannot_be_waived(self):
        for key, value in [('source_commit', 'c' * 40), ('sha256', 'd' * 64), ('bytes', 13)]:
            original = json.loads(json.dumps(self.policy))
            if key == 'source_commit': self.policy['runs']['RUN-X'][key] = value
            else: self.policy['runs']['RUN-X']['attachments']['gui.png'][key] = value
            self.save()
            with self.assertRaises(ValueError): waived_attachments(self.root, 'docs/evidence/runs/RUN-X/run.json', self.run)
            self.policy = original
        self.policy['runs']['RUN-X']['attachments']['tests.json'] = {'bytes': 12, 'sha256': 'b' * 64}
        self.save()
        with self.assertRaises(ValueError): waived_attachments(self.root, 'docs/evidence/runs/RUN-X/run.json', self.run)
    def test_unlisted_run_no_blanket_waiver_and_untrusted_policy_refused(self):
        self.save(); run = self.run | {'id': 'RUN-Y'}
        self.assertEqual(waived_attachments(self.root, 'docs/evidence/runs/RUN-Y/run.json', run), ({}, []))
        self.policy['user_instruction'] = ''
        self.save()
        with self.assertRaises(ValueError): waived_attachments(self.root, 'docs/evidence/runs/RUN-X/run.json', self.run)
    def test_traversal_and_nonlocal_contract_refused(self):
        self.policy['runs']['RUN-X']['attachments'] = {'../gui.png': {'bytes': 12, 'sha256': 'b' * 64}}
        self.save()
        with self.assertRaises(ValueError): waived_attachments(self.root, 'docs/evidence/runs/RUN-X/run.json', self.run)
        self.policy['contract'] = '../outside.md'
        self.save()
        with self.assertRaises(ValueError): waived_attachments(self.root, 'docs/evidence/runs/RUN-X/run.json', self.run)

    def test_seventy_policy_keeps_exact_source_media_and_contract_boundary(self):
        self.policy['policy']='USER_AUTHORIZED_METADATA_FIRST_SEVENTY'
        self.policy['contract']='docs/dev/SEVENTY_PARENTS_CONTRACT.json'
        (self.root/self.policy['contract']).write_text('{}')
        path=self.root/'docs/dev/SEVENTY_PARENTS_PUBLICATION.json';path.write_text(json.dumps(self.policy))
        result,policies=waived_attachments(self.root,'docs/evidence/runs/RUN-X/run.json',self.run)
        self.assertEqual(list(result),['docs/evidence/runs/RUN-X/gui.png']);self.assertEqual(policies,['docs/dev/SEVENTY_PARENTS_PUBLICATION.json'])
        self.policy['runs']['RUN-X']['source_commit']='c'*40;path.write_text(json.dumps(self.policy))
        with self.assertRaises(ValueError):waived_attachments(self.root,'docs/evidence/runs/RUN-X/run.json',self.run)

    def test_diagnostic_policy_does_not_waive_json_or_unlisted_run(self):
        self.policy['policy']='USER_AUTHORIZED_METADATA_FIRST_DIAGNOSTICS'
        self.policy['contract']='docs/dev/DIAGNOSTIC_REPORTS_CONTRACT.json'
        (self.root/self.policy['contract']).write_text('{}')
        path=self.root/'docs/dev/DIAGNOSTIC_REPORTS_PUBLICATION.json';path.write_text(json.dumps(self.policy))
        result,policies=waived_attachments(self.root,'docs/evidence/runs/RUN-X/run.json',self.run)
        self.assertEqual(list(result),['docs/evidence/runs/RUN-X/gui.png']);self.assertEqual(policies,['docs/dev/DIAGNOSTIC_REPORTS_PUBLICATION.json'])
        self.assertEqual(waived_attachments(self.root,'docs/evidence/runs/RUN-Y/run.json',self.run|{'id':'RUN-Y'}),({},[]))
        self.policy['runs']['RUN-X']['attachments']['tests.json']={'bytes':12,'sha256':'b'*64};path.write_text(json.dumps(self.policy))
        with self.assertRaises(ValueError):waived_attachments(self.root,'docs/evidence/runs/RUN-X/run.json',self.run)
