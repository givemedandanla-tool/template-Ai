"""Small isolated source-distribution guards, not real OCR accuracy tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location('tesseract_sources_under_test', Path(__file__).resolve().parents[1] / 'tools/tesseract_sources.py')
sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sources)


class CorrespondingSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        notices = self.root / 'notices'
        notices.mkdir()
        license_bytes = b'An actual fixed notice\n'
        (notices / 'LICENSE.txt').write_bytes(license_bytes)
        version = self.root / 'template_ai/review_tool/__init__.py'
        version.parent.mkdir(parents=True)
        version.write_text("__version__ = '0.1.0-beta.2'\n")
        payload = b'Isolated synthetic source archive bytes\n'
        self.cache = self.root / 'cache'
        self.cache.joinpath('sources').mkdir(parents=True)
        self.payload = self.cache / 'sources/dependency.tar.gz'
        self.payload.write_bytes(payload)
        self.lock = self.root / 'source-lock.json'
        self.runtime = self.root / 'runtime-lock.json'
        self.runtime.write_text(json.dumps(dict(installer=dict(sha256='a' * 64), runtime_files=[dict(path='tesseract.exe')])))
        self.document = dict(schema_version=1, legal_status='REVIEWED', installer_sha256='a' * 64,
            archive_count=1, archives=[dict(asset_name='dependency.tar.gz', bytes=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(), url='https://example.invalid/pinned-source',
                runtime_files=['tesseract.exe'])], notice_files=[dict(path='LICENSE.txt', bytes=len(license_bytes),
                sha256=hashlib.sha256(license_bytes).hexdigest())])
        self._save()
        for name, value in [('ROOT', self.root), ('LOCK', self.lock), ('NOTICES', notices), ('RUNTIME_LOCK', self.runtime)]:
            hook = patch.object(sources, name, value)
            hook.start()
            self.addCleanup(hook.stop)
        request = patch.object(sources.urllib.request, 'urlopen', side_effect=AssertionError('Synthetic verification must stay offline'))
        request.start()
        self.addCleanup(request.stop)

    def _save(self):
        self.lock.write_text(json.dumps(self.document))

    def _prepare(self):
        return sources.prepare(self.cache, self.root / 'output')

    def test_complete_sources_and_notices_are_verified_offline_and_repeatable(self):
        first = self._prepare()
        second = self._prepare()
        self.assertEqual(first['status'], 'PASS')
        self.assertEqual(first['archives_verified'], 1)
        self.assertEqual(first['notices_verified'], 1)
        self.assertEqual(first['archive']['sha256'], second['archive']['sha256'])
        self.assertEqual(first['cache_inputs'][0]['origin'], 'VERIFIED_CACHE_HIT')
        self.assertEqual(sources.verify(first['archive']['path'])['archives_verified'], 1)

    def test_changed_cached_source_is_rejected_without_download_or_baseline_refresh(self):
        self.payload.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            self._prepare()
        self.assertEqual(json.loads(self.lock.read_text()), self.document)

    def test_changed_notice_is_rejected(self):
        (sources.NOTICES / 'LICENSE.txt').write_bytes(b'altered notice')
        with self.assertRaisesRegex(ValueError, 'notice differs'):
            self._prepare()

    def test_source_zip_tampering_and_unlisted_members_are_rejected(self):
        original = Path(self._prepare()['archive']['path'])
        with zipfile.ZipFile(original) as stream:
            members = {name: stream.read(name) for name in stream.namelist()}
        for label, edits in [('tampered', {'archives/dependency.tar.gz': b'bad'}), ('unlisted', {'../unexpected': b'bad'})]:
            path = self.root / (label + '.zip')
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as stream:
                for name, data in {**members, **edits}.items():
                    stream.writestr(name, data)
            with self.assertRaises(ValueError):
                sources.verify(path)

    def test_duplicate_source_member_is_rejected(self):
        original = Path(self._prepare()['archive']['path'])
        duplicate = self.root / 'duplicate.zip'
        with zipfile.ZipFile(original) as stream, zipfile.ZipFile(duplicate, 'w') as target:
            for name in stream.namelist():
                target.writestr(name, stream.read(name))
            with self.assertWarns(UserWarning):
                target.writestr('archives/dependency.tar.gz', b'duplicate')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            sources.verify(duplicate)

    def test_symlink_entry_cannot_impersonate_a_pinned_source(self):
        original = Path(self._prepare()['archive']['path'])
        changed = self.root / 'symlink.zip'
        with zipfile.ZipFile(original) as stream, zipfile.ZipFile(changed, 'w') as target:
            for name in stream.namelist():
                info = zipfile.ZipInfo(name)
                info.external_attr = (0o120777 if name.startswith('archives/') else 0o100644) << 16
                target.writestr(info, stream.read(name))
        with self.assertRaisesRegex(ValueError, 'non-regular'):
            sources.verify(changed)

    def test_unsafe_paths_empty_scan_and_pending_legal_review_fail_closed(self):
        for change in ('unsafe', 'empty', 'pending'):
            original = json.loads(json.dumps(self.document))
            if change == 'unsafe':
                self.document['archives'][0]['asset_name'] = '../escape.tar.gz'
            elif change == 'empty':
                self.document['archives'] = []
                self.document['archive_count'] = 0
            else:
                self.document['legal_status'] = 'PENDING'
            self._save()
            with self.assertRaises(ValueError):
                self._prepare()
            self.document = original
            self._save()

    def test_source_map_cannot_omit_a_runtime_dependency_or_target_another_installer(self):
        self.runtime.write_text(json.dumps(dict(installer=dict(sha256='a' * 64), runtime_files=[dict(path='tesseract.exe'), dict(path='missing.dll')])))
        with self.assertRaisesRegex(ValueError, 'cover'):
            self._prepare()
        self.runtime.write_text(json.dumps(dict(installer=dict(sha256='b' * 64), runtime_files=[dict(path='tesseract.exe')])))
        with self.assertRaisesRegex(ValueError, 'another runtime'):
            self._prepare()


if __name__ == '__main__':
    unittest.main()
