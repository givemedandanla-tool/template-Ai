"""Administrative release guards use real ZIP bytes in isolated test folders."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

_PATH = Path(__file__).resolve().parents[1] / 'tools/review_release.py'
_SPEC = importlib.util.spec_from_file_location('review_release_under_test', _PATH)
release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release)


class ReviewReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='review-release-guard-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.build = self.root / 'build';self.build.mkdir()
        self.download = self.root / 'download';self.download.mkdir()
        self.stack = []
        for name, value in [('OUTPUT', self.build), ('commit', lambda:'a'*40), ('version', lambda:'0.1.0-beta.1'), ('tag', lambda:'review-v0.1.0-beta.1')]:
            guard = patch.object(release, name, value);guard.start();self.addCleanup(guard.stop)

    def fixture(self, *, member='TemplateAIReview/TemplateAIReview.exe', duplicate=False):
        archive = self.download / 'review.zip'
        payload = b'MZ-authored-test-not-an-executable'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr(member, payload)
            if duplicate:z.writestr(member, payload)
        import hashlib
        manifest = dict(source_commit='a'*40, version='0.1.0-beta.1', tag='review-v0.1.0-beta.1',
            archive=dict(name='review.zip',bytes=archive.stat().st_size,sha256=release.sha(archive)),
            package_files=[dict(path='TemplateAIReview.exe',bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())],
            package_file_count=1, corresponding_sources=dict(status='PASS',archives_verified=125))
        for folder in [self.build, self.download]:
            (folder/'release-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            for name in ['SOURCE_DOWNLOADS.json','validation-summary.json','SHA256SUMS.txt']:
                (folder/name).write_text('authored companion '+name,encoding='utf-8')
        return archive

    def test_complete_download_checks_real_member_bytes(self):
        self.fixture();release.verify_download(self.download)
        result=json.loads((self.download/'download-verification.json').read_text())
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['verified_files'],1)

    def test_corrupted_download_is_rejected(self):
        archive=self.fixture();archive.write_bytes(archive.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'archive hash/size'):release.verify_download(self.download)

    def test_replaced_manifest_is_rejected(self):
        self.fixture();p=self.download/'release-manifest.json';p.write_text(p.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'manifest differs'):release.verify_download(self.download)

    def test_duplicate_zip_members_are_rejected(self):
        self.fixture(duplicate=True)
        with self.assertRaisesRegex(ValueError,'inventory differs'):release.verify_download(self.download)

    def test_unlisted_traversal_member_is_rejected(self):
        self.fixture(member='../outside.exe')
        with self.assertRaisesRegex(ValueError,'inventory differs'):release.verify_download(self.download)

    def test_companion_file_change_is_rejected(self):
        self.fixture();(self.download/'SOURCE_DOWNLOADS.json').write_text('replaced')
        with self.assertRaisesRegex(ValueError,'companion file differs'):release.verify_download(self.download)

    def test_component_version_cannot_silently_drift(self):
        self.fixture()
        with patch.object(release,'version',lambda:'0.1.0-beta.2'):
            with self.assertRaisesRegex(ValueError,'version differs'):release.verify_download(self.download)

    def test_archive_paths_reject_aliases_and_escape(self):
        for name in ['../a','/a','a/../b','a//b','a/./b','a\\b','C:/a','']:
            with self.subTest(name=name),self.assertRaises(ValueError):release.safe_member(name)
        self.assertEqual(release.safe_member('engines/inkscape/bin/inkscape.exe'),'engines/inkscape/bin/inkscape.exe')

    def test_publish_requires_explicit_workflow_authorization(self):
        with patch.dict(release.os.environ,{'GITHUB_ACTIONS':'false','REVIEW_RELEASE_PUBLISH_ALLOWED':'false'}):
            with self.assertRaisesRegex(ValueError,'authorized'):release.publish()

    def test_precommit_authorization_allows_null_source_without_self_reference(self):
        request=dict(version='0.1.0-beta.1',tag='review-v0.1.0-beta.1',scope='PUBLISH_WINDOWS_INTERNAL_BETA',
                     user_request='使用者要求第一版發布GitHub',published=False,source_commit=None)
        release.validate_request(request,'0.1.0-beta.1','a'*40)
        request['source_commit']='a'*40
        release.validate_request(request,'0.1.0-beta.1','a'*40)

    def test_explicit_source_pin_cannot_target_different_commit(self):
        request=dict(version='0.1.0-beta.1',tag='review-v0.1.0-beta.1',scope='PUBLISH_WINDOWS_INTERNAL_BETA',
                     user_request='授權',published=False,source_commit='b'*40)
        with self.assertRaisesRegex(ValueError,'source pin'):release.validate_request(request,'0.1.0-beta.1','a'*40)

    def test_previously_published_request_is_not_reusable(self):
        request=dict(version='0.1.0-beta.1',tag='review-v0.1.0-beta.1',scope='PUBLISH_WINDOWS_INTERNAL_BETA',
                     user_request='舊授權',published=True,source_commit=None)
        with self.assertRaises(ValueError):release.validate_request(request,'0.1.0-beta.1','a'*40)

    def test_stage_failure_preserves_actual_failure(self):
        with self.assertRaisesRegex(RuntimeError,'authored failure'):
            with release.stage('authored-guard'):
                raise RuntimeError('authored failure')
        row=json.loads((self.build/'release-timings.json').read_text())['stages'][0]
        self.assertEqual(row['status'],'FAIL');self.assertGreaterEqual(row['seconds'],0)


if __name__=='__main__':unittest.main()
