"""Remote assets must match locally tested bytes, not self-declared new hashes."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import windows_release as release


class ReleaseDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.download = self.root / 'download'
        self.download.mkdir()
        self.archive = self.download / 'fixture.zip'
        with zipfile.ZipFile(self.archive, 'w') as bundle:
            bundle.writestr('TemplateAI/fixture.txt', b'authored-fixture')
        self.manifest = dict(version=release.__version__, source_commit='a' * 40,
            archive=dict(name='fixture.zip', sha256=release.sha(self.archive)),
            package_files=[dict(path='fixture.txt', sha256=hashlib.sha256(b'authored-fixture').hexdigest())])
        self.expected = self.root / 'locally-tested-manifest.json'
        release.write(self.expected, self.manifest)
        self.write_download()
        self.pinned = patch.object(release, 'source_commit', return_value='a' * 40)
        self.pinned.start()
        self.addCleanup(self.pinned.stop)

    def write_download(self):
        release.write(self.download / 'release-manifest.json', self.manifest)
        (self.download / 'SHA256SUMS.txt').write_text(''.join(release.sha(p) + '  ' + p.name + '\n'
            for p in [self.archive, self.download / 'release-manifest.json']), encoding='utf-8')

    def test_exact_downloaded_fixture_verifies_inventory_and_local_identity(self):
        release.verify_download(self.download, self.expected)
        proof = json.loads((self.download / 'download-verification.json').read_text())
        self.assertEqual(proof['status'], 'PASS')
        self.assertEqual(proof['checked_files'], 1)

    def test_replaced_archive_with_recomputed_remote_checksums_is_rejected(self):
        self.archive.write_bytes(b'replacement')
        self.manifest['archive']['sha256'] = release.sha(self.archive)
        self.write_download()
        with self.assertRaisesRegex(RuntimeError, 'locally tested'):
            release.verify_download(self.download, self.expected)

    def test_changed_bytes_cannot_pass_unchanged_manifest(self):
        with self.archive.open('ab') as stream: stream.write(b'changed')
        self.write_download()
        with self.assertRaisesRegex(RuntimeError, 'archive mismatch'):
            release.verify_download(self.download, self.expected)
