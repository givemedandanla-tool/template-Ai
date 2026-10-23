"""Public vendor exceptions and source assets cannot hide unrelated private files."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import bundled_inkscape_build as build
from dev_governance import verify_exe_authorization


class BundledReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_vendor_inventory_allows_only_exact_pinned_files(self):
        engine = self.root/'engines/inkscape'
        engine.mkdir(parents=True)
        file = engine/'public.db'
        file.write_bytes(b'PUBLIC_UPSTREAM_FIXTURE_NOT_CUSTOMER_DB')
        manifest = engine/'manifest.json'
        build.write(manifest, dict(files=[dict(path=file.name,bytes=file.stat().st_size,sha256=build.digest(file))]))
        build.write(self.root/'_internal/release-info.json', dict(inkscape_runtime=dict(manifest_sha256=build.digest(manifest))))
        self.assertEqual(build.vendor_inventory(self.root), {'engines/inkscape/public.db','engines/inkscape/manifest.json'})
        (engine/'unlisted-private.db').write_bytes(b'UNLISTED')
        with self.assertRaises(RuntimeError):
            build.vendor_inventory(self.root)

    def test_vendor_bytes_changed_after_acceptance_are_rejected(self):
        engine = self.root/'engines/inkscape'
        engine.mkdir(parents=True)
        file = engine/'runtime.dll'
        file.write_bytes(b'ORIGINAL')
        manifest = engine/'manifest.json'
        build.write(manifest, dict(files=[dict(path=file.name,bytes=8,sha256=build.digest(file))]))
        build.write(self.root/'_internal/release-info.json', dict(inkscape_runtime=dict(manifest_sha256=build.digest(manifest))))
        file.write_bytes(b'REPLACED')
        with self.assertRaises(RuntimeError):
            build.vendor_inventory(self.root)

    def test_source_archive_verifies_every_locked_object_and_rejects_new_members(self):
        lock = self.root/'lock.json'
        content = b'AUTHORED_CORRESPONDING_SOURCE_EXAMPLE'
        build.write(lock, dict(corresponding_sources=[dict(asset_name='example.tar.gz',bytes=len(content),sha256=hashlib.sha256(content).hexdigest())]))
        archive = self.root/'source.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name, data in [('SOURCE_MAP.json',lock.read_bytes()),('README.md',b'readme'),('INKSCAPE-GPL-3.0.txt',b'fixture license'),('sources/example.tar.gz',content)]:
                z.writestr(name,data)
        with patch.object(build,'LOCK',lock):
            build.verify_source_archive(archive)
            with zipfile.ZipFile(archive,'a') as z:
                z.writestr('unlisted.file',b'EXTRA')
            with self.assertRaises(RuntimeError):
                build.verify_source_archive(archive)

    def test_beta2_authorization_is_exact_and_does_not_allow_general_push(self):
        file = self.root/'.github/workflows/first-version.yml'
        file.parent.mkdir(parents=True)
        text = "name: fixture\non:\n  workflow_dispatch:\n  push:\n    branches: ['release-request/v0.2.0-beta.2']\npermissions:\n  contents: read\n"
        file.write_text(text)
        state = dict(exe_policy='EXPLICIT_V0_2_0_BETA_2_RELEASE_AUTHORIZED_NO_GENERAL_PUSH_BUILD',
                     pending_release=dict(version='0.2.0-beta.2',authorization=dict(scope='PUBLISH_WINDOWS_INTERNAL_BETA',user_request='參用隨包附帶方案，完善代碼後，打包成exe發佈到release')))
        verify_exe_authorization(self.root,state)
        file.write_text(text.replace("['release-request/v0.2.0-beta.2']", "['**']"))
        with self.assertRaises(ValueError):
            verify_exe_authorization(self.root,state)


if __name__ == '__main__':
    unittest.main()
