"""Administrative release guards use real ZIP bytes in isolated test folders."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import types
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

    def test_prepare_cli_passes_isolated_ocr_cache_without_installing(self):
        with patch.object(release, 'prepare') as prepare:
            self.assertEqual(release.main(['prepare', '--cache', str(self.root/'fixed'),
                '--ocr-cache', str(self.root/'ocr')]), 0)
            prepare.assert_called_once_with(self.root/'fixed', self.root/'ocr')

    def ocr_proof(self):
        pin = dict(version='5.4.0.20240606', executable_sha256='c'*64, manifest_sha256='d'*64)
        detail = dict(status='PASS', required=True, runtime_origin='BUNDLED',
            image_transport='STDIN_BINARY_IMAGE', english_positive=True,
            traditional_chinese_positive=True, missing_corrupt_fallback_verified=True,
            models=['eng', 'chi_tra'], version=pin['version'], executable_sha256='c'*64,
            runtime_manifest_sha256='d'*64)
        return dict(bundled_ocr=detail), pin

    def test_bundled_positive_bilingual_ocr_and_fallback_are_required(self):
        report, pin = self.ocr_proof();release.validate_bundled_ocr_acceptance(report, pin)
        for key in ['required', 'english_positive', 'traditional_chinese_positive', 'missing_corrupt_fallback_verified']:
            with self.subTest(key=key):
                changed, _ = self.ocr_proof();changed['bundled_ocr'][key] = False
                with self.assertRaisesRegex(ValueError, 'positively verify'):
                    release.validate_bundled_ocr_acceptance(changed, pin)

    def test_legacy_optional_or_host_ocr_cannot_qualify_new_bundle(self):
        report, pin = self.ocr_proof()
        for change in [{}, {'runtime_origin':'HOST'}, {'models':['eng']}, {'required':'true'}, {'image_transport':'LEGACY_FILENAME'}]:
            detail = {} if not change else dict(report['bundled_ocr'], **change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'positively verify'):
                release.validate_bundled_ocr_acceptance(dict(bundled_ocr=detail), pin)

    def test_ocr_proof_is_bound_to_exact_runtime_version_and_bytes(self):
        for key in ['version', 'executable_sha256', 'runtime_manifest_sha256']:
            report, pin = self.ocr_proof();report['bundled_ocr'][key] = 'other'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'exact runtime pin'):
                release.validate_bundled_ocr_acceptance(report, pin)

    def test_ocr_cache_budget_includes_executable_and_all_source_archives(self):
        from release_actions_support import ocr_input_bytes
        tools = self.root/'tools';tools.mkdir()
        (tools/'tesseract_distribution_lock.json').write_text(json.dumps(dict(installer=dict(bytes=50))))
        (tools/'tesseract_sources_lock.json').write_text(json.dumps(dict(archives=[dict(bytes=100),dict(bytes=5)])))
        self.assertEqual(ocr_input_bytes(self.root),155)
        (tools/'tesseract_sources_lock.json').write_text(json.dumps(dict(archives=[dict(bytes=True)])))
        with self.assertRaisesRegex(ValueError,'positive exact download sizes'):ocr_input_bytes(self.root)

    def fixture_with_ocr_source(self):
        self.fixture()
        source = self.download/'ocr-source.zip'
        with zipfile.ZipFile(source,'w') as archive:
            archive.writestr('SYNTHETIC_SOURCE.txt','Authored routing test, not genuine upstream source')
        manifest = json.loads((self.build/'release-manifest.json').read_text())
        manifest['ocr_corresponding_sources'] = dict(status='PASS',archive=dict(
            name=source.name,bytes=source.stat().st_size,sha256=release.sha(source)))
        for directory in [self.build,self.download]:
            (directory/'release-manifest.json').write_text(json.dumps(manifest))
        return source

    def test_download_revalidates_ocr_source_through_same_source_guard(self):
        source = self.fixture_with_ocr_source();calls=[]
        module=types.ModuleType('tesseract_sources');module.verify=lambda path:calls.append(path)
        with patch.dict(sys.modules,{'tesseract_sources':module}):release.verify_download(self.download)
        self.assertEqual(calls,[source])
        self.assertIn('ocr_corresponding_sources',json.loads((self.download/'download-verification.json').read_text()))

    def test_changed_ocr_source_download_is_rejected_before_verifier(self):
        source = self.fixture_with_ocr_source();source.write_bytes(source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'OCR corresponding source hash/size'):
            release.verify_download(self.download)

    def test_ocr_source_verifier_failure_cannot_be_treated_as_pass(self):
        self.fixture_with_ocr_source();module=types.ModuleType('tesseract_sources')
        def reject(path):raise ValueError('Actual upstream member differs')
        module.verify=reject
        with patch.dict(sys.modules,{'tesseract_sources':module}),self.assertRaisesRegex(ValueError,'Actual upstream'):
            release.verify_download(self.download)
        self.assertFalse((self.download/'download-verification.json').exists())

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

    def installed_sklearn_fixture(self):
        package=self.root/'authored site-packages/sklearn'
        testfile=package/'datasets/tests/data/openml/id_1/api-v1-jd-1.json.gz'
        runtime=package/'datasets/data/iris.csv'
        for path,content in [(package/'__init__.py',b'# authored installed package fixture'),
                (testfile,b'AUTHORED_PUBLIC_TEST_FIXTURE'),(runtime,b'AUTHORED_RUNTIME_DATA')]:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        lock=self.root/'.github/windows-wheels-lock.json';lock.parent.mkdir()
        lock.write_text(json.dumps(dict(wheels=[dict(name='scikit-learn',version='1.7.2',sha256='a'*64)])))
        distribution=types.SimpleNamespace(version='1.7.2',locate_file=lambda name:package.parent/name)
        original_find=importlib.util.find_spec
        for guard in [patch.object(release,'ROOT',self.root),
                patch('importlib.metadata.distribution',return_value=distribution),
                patch('importlib.util.find_spec',side_effect=lambda name:types.SimpleNamespace(origin=str(package/'__init__.py')) if name=='sklearn' else original_find(name))]:
            guard.start();self.addCleanup(guard.stop)
        rows=[('sklearn/datasets/tests/data/openml/id_1/api-v1-jd-1.json.gz',str(testfile),'DATA'),
              ('sklearn/datasets/data/iris.csv',str(runtime),'DATA')]
        return package,testfile,runtime,rows,distribution

    def test_build_filter_only_excludes_verified_installed_upstream_test_data(self):
        package,testfile,runtime,rows,_=self.installed_sklearn_fixture()
        rows[0]=(rows[0][0].replace('/','\\'),rows[0][1],rows[0][2])
        kept=[('sklearn_extra/datasets/tests/example.json',str(testfile),'DATA'),
              ('sklearn/datasets/testsupport/example.json',str(testfile),'DATA'),
              ('template_ai/tests/example.json',str(testfile),'DATA'),
              ('other/tests/example.json',str(testfile),'DATA'),
              ('licenses/scikit-learn/LICENSE',str(package/'__init__.py'),'DATA')]
        report=self.build/'upstream-build-exclusions.json'
        self.assertEqual(release.filter_upstream_test_data(rows+kept,report),rows[1:]+kept)
        value=json.loads(report.read_text())
        self.assertEqual(value['removed_entries'],1);self.assertEqual(value['distribution']['version'],'1.7.2')
        self.assertTrue(value['distribution']['import_origin_matches_installed_distribution'])
        self.assertEqual(value['removed'][0]['sha256'],release.sha(testfile))
        self.assertEqual(value['removed'][0]['bytes'],testfile.stat().st_size)
        self.assertEqual(value['removed'][0]['source_relative'],'sklearn/datasets/tests/data/openml/id_1/api-v1-jd-1.json.gz')
        self.assertEqual(runtime.read_bytes(),b'AUTHORED_RUNTIME_DATA')

    def test_build_filter_rejects_private_or_mismatched_source_instead_of_hiding_it(self):
        package,_,_,rows,_=self.installed_sklearn_fixture()
        outside=self.root/'PRIVATE_AUTHORED_NOT_CUSTOMER_DATA.json.gz';outside.write_bytes(b'authored private decoy')
        different=package/'datasets/tests/data/different.json.gz';different.write_bytes(b'other test fixture')
        for source in [outside,different]:
            report=self.build/'rejected-filter.json'
            with self.subTest(source=source.name),self.assertRaisesRegex(ValueError,'source differs'):
                release.filter_upstream_test_data([(rows[0][0],str(source),'DATA')],report)
            self.assertFalse(report.exists())

    def test_build_filter_rejects_changed_installed_distribution_version(self):
        _,_,_,rows,distribution=self.installed_sklearn_fixture();distribution.version='9.9.9'
        with self.assertRaisesRegex(ValueError,'fixed build dependency version'):
            release.filter_upstream_test_data(rows,self.build/'changed-filter.json')

    def test_generated_spec_executes_real_filter_before_collect(self):
        _,_,_,rows,_=self.installed_sklearn_fixture()
        pin=self.root/'build/release/inkscape-runtime-pin.json';pin.parent.mkdir(parents=True)
        pin.write_text(json.dumps(dict(version='1.4.2',manifest_sha256='b'*64)))
        specdir=self.root/'build/review-release';specdir.mkdir(parents=True)
        (specdir/'tesseract-runtime-pin.json').write_text(json.dumps(dict(version='5.4.0.20240606',manifest_sha256='c'*64)))
        with patch.object(release,'BUILD',specdir):release.make_spec()
        class AuthoredAnalysis:
            def __init__(self,*args,**kwargs):
                self.datas=list(rows);self.pure=[];self.scripts=[];self.binaries=[]
        hooks=types.ModuleType('PyInstaller.utils.hooks')
        hooks.collect_submodules=lambda *args,**kwargs:[]
        hooks.copy_metadata=lambda *args,**kwargs:[]
        hooks.collect_data_files=lambda *args,**kwargs:[]
        modules={'PyInstaller':types.ModuleType('PyInstaller'),'PyInstaller.utils':types.ModuleType('PyInstaller.utils'),
                 'PyInstaller.utils.hooks':hooks,'review_release':release}
        namespace=dict(SPECPATH=str(specdir),Analysis=AuthoredAnalysis,PYZ=lambda *a,**k:object(),
                       EXE=lambda *a,**k:object(),COLLECT=lambda *a,**k:object())
        previous=list(sys.path)
        try:
            with patch.dict(sys.modules,modules):exec(compile((specdir/'TemplateAIReview.spec').read_text(),'<authored-spec-wire-test>','exec'),namespace)
        finally:sys.path[:]=previous
        self.assertEqual(namespace['a'].datas,rows[1:])
        report=json.loads((self.root/'artifacts/review-release/upstream-build-exclusions.json').read_text())
        self.assertEqual(report['removed_entries'],1);self.assertEqual(report['kept_entries'],1)


if __name__=='__main__':unittest.main()
