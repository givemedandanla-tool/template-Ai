"""Synthetic boundary regression for offline source transfer and local launch."""
import importlib.util
import json
import os
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
USB = ROOT / 'tools/windows_review_dev/usb'
import sys
sys.path.insert(0, str(USB))
import offline_start as start
import prepare_usb as prepare


class UsbStartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='review-usb-test-')
        self.root = Path(self.tmp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.required = ['python/python.exe', 'python/pythonw.exe', 'inkscape/bin/inkscape.exe',
                         'source/review_app.py', 'source/requirements-lock.txt', 'offline-requirements.txt']
        for name in self.required:
            path = self.bundle / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic payload')
        self.manifest = {'schema_version': 1, 'branch': start.BRANCH, 'source_commit': 'a' * 40,
                         'files': [{'path': n, 'bytes': (self.bundle/n).stat().st_size,
                                    'sha256': start.digest(self.bundle/n)} for n in self.required]}
        self.save_manifest()

    def tearDown(self):
        self.tmp.cleanup()

    def save_manifest(self):
        (self.bundle / 'transfer-manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def summary(self, folder, **overrides):
        value = {'status': 'AUTOMATED_PASS', 'synthetic_only': True, 'real_illustrator_verified': True,
                 'source_unchanged': True, 'checks_passed': 6, 'checks_total': 6}
        value.update(overrides)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'summary.json').write_text(json.dumps(value), encoding='utf-8')

    def test_intact_transfer(self):
        manifest, identity = start.verify_bundle(self.bundle)
        self.assertEqual(len(manifest['files']), 6)
        self.assertEqual(len(identity), 64)

    def test_corruption_stops_before_any_setup(self):
        (self.bundle / self.required[0]).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            start.verify_bundle(self.bundle)

    def test_missing_file_rejected(self):
        (self.bundle / self.required[0]).unlink()
        with self.assertRaises(ValueError):
            start.verify_bundle(self.bundle)

    def test_wrong_branch_rejected(self):
        self.manifest['branch'] = 'main'
        self.save_manifest()
        with self.assertRaises(ValueError):
            start.verify_bundle(self.bundle)

    def test_duplicate_case_alias_rejected(self):
        self.manifest['files'].append(dict(self.manifest['files'][0], path='PYTHON/PYTHON.EXE'))
        self.save_manifest()
        with self.assertRaises(ValueError):
            start.verify_bundle(self.bundle)

    def test_unsafe_paths_rejected(self):
        for name in ['../secret', '/secret', 'C:/secret', 'a\\secret', 'a:stream', 'a/../secret', 'a/./b', 'a//b']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                start.safe_member(self.bundle, name)

    def test_extra_private_files_not_copied(self):
        (self.bundle/'private.ai').write_bytes(b'synthetic private sentinel')
        target = self.root/'new'
        target.mkdir()
        start.clone_transfer(self.bundle, target, self.manifest)
        self.assertFalse((target/'private.ai').exists())
        self.assertEqual(start.verify_bundle(target)[1], start.verify_bundle(self.bundle)[1])

    def test_copy_refuses_overwrite(self):
        target = self.root/'existing'
        (target/'python').mkdir(parents=True)
        (target/'python/python.exe').write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            start.clone_transfer(self.bundle, target, self.manifest)
        self.assertEqual((target/'python/python.exe').read_bytes(), b'preserve')

    def test_unique_install_keeps_existing(self):
        base = self.root/'local'
        # test path must fit production's deliberately short path requirement
        with patch.object(start.ctypes, 'windll', create=True) as dll:
            dll.kernel32.GetDriveTypeW.return_value = 3
            a, b = start.new_install(base), start.new_install(base)
        self.assertNotEqual(a, b)
        self.assertTrue(a.exists() and b.exists())

    def test_write_new_never_overwrites(self):
        path = self.root/'receipt.json'
        start.write_new(path, {'first': True})
        with self.assertRaises(FileExistsError):
            start.write_new(path, {'second': True})
        self.assertEqual(json.loads(path.read_text()), {'first': True})

    def test_environment_ignores_user_python_and_pip_config(self):
        with patch.dict(os.environ, {'PYTHONPATH': 'private', 'PIP_INDEX_URL': 'https://invalid', 'QT_PLUGIN_PATH': 'old',
                                     'TEMPLATE_AI_INKSCAPE': 'old'}):
            env = start.child_env(self.root)
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('PIP_INDEX_URL', env)
        self.assertNotIn('QT_PLUGIN_PATH', env)
        self.assertEqual(env['PIP_NO_INDEX'], '1')
        self.assertEqual(env['PIP_CONFIG_FILE'], os.devnull)
        self.assertEqual(env['TEMPLATE_AI_INKSCAPE'], str(self.root/'inkscape/bin/inkscape.exe'))

    def test_offline_install_flags_and_fail_stop(self):
        logs = self.root/'logs'
        logs.mkdir()
        with patch.object(start, 'run_logged', side_effect=[0, 1]) as runner:
            with self.assertRaises(RuntimeError):
                start.prepare_environment(self.root, logs)
        self.assertEqual(runner.call_count, 2)
        args = runner.call_args_list[1].args[0]
        for flag in ('--no-index', '--require-hashes', '--only-binary=:all:', '--no-cache-dir'):
            self.assertIn(flag, args)
        self.assertFalse((self.root/'environment-ready.json').exists())

    def test_zero_exit_without_receipt_is_failure(self):
        self.assertFalse(start.smoke_passed(self.root/'missing', 0))

    def test_real_smoke_assertions_all_required(self):
        folder = self.root/'smoke'
        self.summary(folder)
        self.assertTrue(start.smoke_passed(folder, 0))
        for key, value in [('real_illustrator_verified', False), ('synthetic_only', False),
                           ('source_unchanged', False), ('checks_passed', 5), ('status', 'NOT_RUN')]:
            self.summary(folder, **{key: value})
            self.assertFalse(start.smoke_passed(folder, 0), key)
        self.summary(folder)
        self.assertFalse(start.smoke_passed(folder, 3))

    def test_missing_illustrator_blocks_launch_and_records_failure(self):
        logs = self.root/'logs'
        logs.mkdir()
        with patch.object(start, 'run_logged', return_value=3), patch.object(start, 'launch') as gui:
            self.assertFalse(start.qualify_illustrator(self.root, logs))
        gui.assert_not_called()
        receipts = list((self.root/'qualifications').glob('*.json'))
        self.assertEqual(len(receipts), 1)
        self.assertFalse(json.loads(receipts[0].read_text())['passed'])

    def test_pass_reuse_failed_retest_and_retry(self):
        logs = self.root/'logs'
        logs.mkdir()
        def success(args, *rest, **kwargs):
            self.summary(Path(args[-1]))
            return 0
        with patch.object(start, 'run_logged', side_effect=success) as runner:
            self.assertTrue(start.qualify_illustrator(self.root, logs))
            self.assertTrue(start.qualify_illustrator(self.root, logs))
            self.assertEqual(runner.call_count, 1)
        with patch.object(start, 'run_logged', return_value=3) as runner:
            self.assertFalse(start.qualify_illustrator(self.root, logs, retest=True))
            self.assertFalse(start.qualify_illustrator(self.root, logs))
            self.assertEqual(runner.call_count, 2)
        self.assertEqual(len(list((self.root/'qualifications').glob('*.json'))), 3)

    @unittest.skipUnless(os.name == 'nt', 'Windows session locks')
    def test_lock_blocks_duplicate_and_releases(self):
        path = self.root/'gui.lock'
        with start.exclusive_lock(path):
            self.assertTrue(start.gui_running(self.root))
        self.assertFalse(start.gui_running(self.root))

    def test_gui_is_independent_pythonw_with_local_logs(self):
        logs = self.root/'logs'
        logs.mkdir()
        with patch.object(start.subprocess, 'Popen') as popen, patch.object(start.time, 'sleep'):
            popen.return_value.poll.return_value = None
            popen.return_value.pid = 12345
            start.launch(self.root, logs)
        args = popen.call_args.args[0]
        self.assertTrue(args[0].endswith('pythonw.exe'))
        self.assertEqual(popen.call_args.kwargs['stdin'], start.subprocess.DEVNULL)
        self.assertTrue(popen.call_args.kwargs['creationflags'] & 0x00000008)
        self.assertTrue((logs/'launch.json').exists())

    def test_source_export_rejects_private_document(self):
        listing = b'100644 blob ' + b'a'*40 + b'\ttemplate_ai/private.ai\0'
        with patch.object(prepare, 'git', return_value=listing), self.assertRaises(ValueError):
            prepare.export_source(self.root, self.root/'source', 'a'*40)

    def test_source_export_uses_local_commit_verified_bytes(self):
        raw = b'print(1)\n'
        sha = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        listing = ('100644 blob '+sha+'\treview_app.py\0').encode()
        (self.root/'review_app.py').write_bytes(raw.replace(b'\n', b'\r\n'))
        with patch.object(prepare, 'git', return_value=listing) as git:
            prepare.export_source(self.root, self.root/'source', 'a'*40)
        self.assertEqual((self.root/'source/review_app.py').read_bytes(), raw)
        self.assertEqual(git.call_args.args[1], 'ls-tree')

    def test_source_export_rejects_changed_local_source(self):
        listing = b'100644 blob ' + b'a'*40 + b'\treview_app.py\0'
        (self.root/'review_app.py').write_bytes(b'changed')
        with patch.object(prepare, 'git', return_value=listing), self.assertRaises(ValueError):
            prepare.export_source(self.root, self.root/'source', 'a'*40)

    def test_source_export_keeps_only_scoped_icons_and_notices(self):
        for name in ['template_ai/review_tool/icons/LICENSE', 'template_ai/review_tool/icons/file.svg']:
            raw = b'synthetic icon or license'
            sha = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            listing = ('100644 blob '+sha+'\t'+name+'\0').encode()
            with patch.object(prepare, 'git', return_value=listing):
                prepare.export_source(self.root, self.root/'source', 'a'*40)
            self.assertEqual((self.root/'source'/name).read_bytes(), raw)
        for name in ['template_ai/private.svg', 'template_ai/font.ttf', 'template_ai/private.pdf']:
            listing = ('100644 blob '+'a'*40+'\t'+name+'\0').encode()
            with self.subTest(name=name), patch.object(prepare, 'git', return_value=listing), self.assertRaises(ValueError):
                prepare.export_source(self.root, self.root/'source', 'a'*40)

    def test_python_wrong_archive_hash_rejected_without_extract(self):
        archive = self.root/'fake.zip'
        archive.write_bytes(b'synthetic')
        with self.assertRaises(ValueError):
            prepare.python_runtime(archive, self.root/'runtime', '0'*64)
        self.assertFalse((self.root/'runtime').exists())

    def test_removable_install_destination_rejected(self):
        with patch.object(start.ctypes, 'windll', create=True) as dll:
            dll.kernel32.GetDriveTypeW.return_value = 2
            with self.assertRaises(ValueError):
                start.new_install(self.root/'disk')

    def test_copy_failure_keeps_local_diagnostic(self):
        target = self.root/'partial'
        target.mkdir()
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.root/'state')}), \
                patch.object(start, 'new_install', return_value=target), \
                patch.object(start, 'clone_transfer', side_effect=OSError('synthetic disk full')):
            with self.assertRaises(OSError):
                start.main(['--bundle', str(self.bundle), '--local-root', str(self.root)])
        failures = list((target/'diagnostics').glob('*/failure.local.json'))
        self.assertEqual(len(failures), 1)
        self.assertIn('synthetic disk full', failures[0].read_text())
        self.assertFalse((target/'environment-ready.json').exists())


if __name__ == '__main__':
    unittest.main()
