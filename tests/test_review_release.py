"""Administrative release guards use real ZIP bytes in isolated test folders."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
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

    def isolated_case(self, module, source, timeout=2):
        (self.root/(module+'.py')).write_text(textwrap.dedent(source),encoding='utf-8')
        output=self.build/(module+'.json');log=self.build/(module+'.log')
        env=os.environ.copy();env['PYTHONPATH']=str(self.root)+os.pathsep+env.get('PYTHONPATH','')
        row=release.run_isolated_test(module,[sys.executable,str(_PATH),'test-one','--module',module,
            '--output',str(output)],output,log,cwd=self.root,env=env,timeout=timeout)
        return row,log.read_text(encoding='utf-8'),output

    def test_failure_traceback_survives_hanging_cleanup(self):
        row,log,path=self.isolated_case('authored_failure', '''
            import time,unittest
            class AuthoredFailure(unittest.TestCase):
                def tearDown(self):time.sleep(60)
                def test_requirement(self):self.assertEqual('actual','EXPECTED_AUTHORED_FAILURE')
        ''')
        self.assertEqual(row['status'],'ERROR');self.assertEqual(row['termination'],'TIMEOUT')
        self.assertEqual(row['process_tree_cleanup']['status'],'STOPPED')
        self.assertIn('IMMEDIATE_FAILURE:',log);self.assertIn('Traceback (most recent call last)',log)
        self.assertIn('AssertionError',log);self.assertIn('EXPECTED_AUTHORED_FAILURE',log)
        self.assertEqual(json.loads(path.read_text())['status'],'ERROR')

    def test_error_traceback_survives_hanging_cleanup(self):
        row,log,_=self.isolated_case('authored_error', '''
            import time,unittest
            class AuthoredError(unittest.TestCase):
                def tearDown(self):time.sleep(60)
                def test_requirement(self):raise RuntimeError('EXPECTED_AUTHORED_ERROR')
        ''')
        self.assertEqual(row['status'],'ERROR');self.assertEqual(row['termination'],'TIMEOUT')
        self.assertIn('IMMEDIATE_ERROR:',log);self.assertIn('RuntimeError: EXPECTED_AUTHORED_ERROR',log)

    def test_timeout_stops_owned_child_then_next_real_module_can_pass(self):
        pidfile=self.root/'authored-child-pid.txt'
        source='''
            import pathlib,subprocess,sys,time,unittest
            class AuthoredChild(unittest.TestCase):
                def test_requirement(self):
                    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
                    pathlib.Path(PIDFILE).write_text(str(child.pid))
                    time.sleep(60)
        '''.replace('PIDFILE',repr(str(pidfile)))
        row,log,_=self.isolated_case('authored_child',source)
        self.assertEqual(row['termination'],'TIMEOUT');self.assertFalse(row['tests_run_complete'])
        self.assertEqual(row['process_tree_cleanup']['status'],'STOPPED')
        self.assertGreaterEqual(row['process_tree_cleanup']['observed_descendants'],1)
        self.assertIn('RELEASE_MODULE_TIMEOUT:',log)
        import psutil
        try:child=psutil.Process(int(pidfile.read_text()))
        except psutil.NoSuchProcess:child=None
        self.assertTrue(child is None or not child.is_running() or child.status()==psutil.STATUS_ZOMBIE)
        next_row,_,_=self.isolated_case('authored_following', '''
            import unittest
            class Following(unittest.TestCase):
                def test_still_runs(self):self.assertEqual(2+2,4)
        ''')
        self.assertEqual(next_row['status'],'PASS');self.assertEqual(next_row['tests_run'],1)

    def test_timeout_does_not_skip_later_modules_or_pass_release_gate(self):
        tests=self.root/'tests';tests.mkdir();(tests/'test_review_authored.py').write_text('# synthetic module')
        seen=[]
        def outcomes(module,command,out,log,**kwargs):
            seen.append(module)
            value=dict(module=module,status='ERROR' if module=='authored_timeout' else 'PASS',
                termination='TIMEOUT' if module=='authored_timeout' else 'COMPLETE',
                tests_run=0 if module=='authored_timeout' else 1,failures=0,
                errors=int(module=='authored_timeout'),skipped=[],exit_code=-9 if module=='authored_timeout' else 0)
            if module=='authored_timeout':value['process_tree_cleanup']={'status':'STOPPED'}
            release.write(out,value);return value
        (tests/'authored_timeout.py').write_text('# isolated timeout fixture')
        pin=dict(source_commit='a'*40,source_manifest_sha256='b'*64)
        with patch.object(release,'ROOT',self.root),patch.object(release,'REUSED_TESTS',('authored_timeout',)),\
                patch.object(release,'identity',return_value=pin),patch.object(release,'run_isolated_test',side_effect=outcomes):
            with self.assertRaisesRegex(RuntimeError,'Component tests failed'):release.source_tests()
        self.assertEqual(seen,['authored_timeout','test_review_authored'])
        summary=json.loads((self.build/'source-tests.json').read_text())
        self.assertEqual(summary['status'],'FAIL');self.assertEqual(summary['timeout_modules'],['authored_timeout'])
        self.assertEqual(summary['modules_not_run'],[]);self.assertEqual(summary['errors'],1)

    def test_actual_failing_command_saves_ci_trace_and_still_exits_nonzero(self):
        launcher=self.root/'authored-cli-launcher.py'
        launcher.write_text(textwrap.dedent(f'''
            import importlib.util,pathlib,sys
            spec=importlib.util.spec_from_file_location('authored_release', {_PATH.as_posix()!r})
            release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
            release.OUTPUT=pathlib.Path({str(self.build)!r})
            release.commit=lambda: {'a'*40!r}
            raise SystemExit(release.entrypoint())
        '''),encoding='utf-8')
        command=[sys.executable,str(launcher),'verify-download','--output',str(self.download)]
        env=os.environ.copy();env['GITHUB_ACTIONS']='true'
        result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=15)
        self.assertNotEqual(result.returncode,0);self.assertIn('FileNotFoundError',result.stderr)
        record=json.loads((self.build/'verify-download-command-error.json').read_text())
        trace=(self.build/record['traceback_log']).read_text()
        self.assertEqual(record['status'],'ERROR');self.assertEqual(record['command'],'verify-download')
        self.assertEqual(record['source_commit'],'a'*40);self.assertTrue(record['exception_preserved'])
        self.assertIn('Traceback (most recent call last)',trace);self.assertIn('FileNotFoundError',trace)
        self.assertIn('verify_download',trace)

    def test_local_command_failure_does_not_create_public_error_evidence(self):
        env=os.environ.copy();env['GITHUB_ACTIONS']='false'
        with patch.dict(os.environ,env,clear=True):
            with self.assertRaises(FileNotFoundError):
                release.entrypoint(['verify-download','--output',str(self.download)])
        self.assertFalse((self.build/'verify-download-command-error.json').exists())

    def test_public_failure_trace_redacts_queries_and_credential_patterns(self):
        value=('RuntimeError: public invariant failed\n'
            'https://official.example/public/log?sig=AUTHORED_SIGNED_VALUE&key=AUTHORED_KEY\n'
            'Authorization: Bearer AUTHORED_BEARER\n'
            'ghp_AUTHORED_NOT_A_REAL_GITHUB_TOKEN')
        safe=release.public_failure_text(value)
        self.assertIn('RuntimeError: public invariant failed',safe)
        self.assertIn('https://official.example/public/log?[REDACTED_QUERY]',safe)
        for secret in ['AUTHORED_SIGNED_VALUE','AUTHORED_KEY','AUTHORED_BEARER','AUTHORED_NOT_A_REAL_GITHUB_TOKEN']:
            self.assertNotIn(secret,safe)

    def test_package_missing_required_evidence_records_failed_preflight(self):
        with patch.object(release,'identity',return_value=dict(source_commit='a'*40)):
            with self.assertRaises(FileNotFoundError):release.package()
        row=json.loads((self.build/'release-timings.json').read_text())['stages'][0]
        self.assertEqual(row['name'],'package_preflight');self.assertEqual(row['status'],'FAIL')
        self.assertEqual(row['error_type'],'FileNotFoundError')
        self.assertEqual(list(self.build.glob('*.zip')),[])


if __name__=='__main__':unittest.main()
