"""Admin-tool regressions using tiny authored fixtures, not product qualification."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).parent))
import release_cache as cache
import release_impact as impact
import release_pipeline as pipeline
from release_actions_support import budget


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.body=b'authored immutable binary fixture'
        self.row=dict(filename='fixture.whl',url='https://example.invalid/not-actually-fetched',
                      bytes=len(self.body),sha256=hashlib.sha256(self.body).hexdigest())
    def opener(self,*args,**kwargs):return io.BytesIO(self.body)
    def test_cold_then_warm_verifies_bytes_and_does_not_fetch_warm(self):
        path,first=cache.fetch_verified(self.row,self.root,opener=self.opener)
        with patch.object(cache,'sha',wraps=cache.sha) as verify:
            _,second=cache.fetch_verified(self.row,self.root,opener=lambda *a,**k:self.fail('network on warm hit'))
        self.assertTrue(verify.called);self.assertEqual(path.read_bytes(),self.body)
        self.assertEqual(first['downloaded_bytes'],len(self.body));self.assertEqual(second['state'],'HIT_VALIDATED')
        self.assertEqual(second['downloaded_bytes'],0)
    def test_same_size_corruption_is_replaced(self):
        (self.root/self.row['filename']).write_bytes(b'x'*len(self.body))
        path,result=cache.fetch_verified(self.row,self.root,opener=self.opener)
        self.assertEqual(result['state'],'INVALID_REPLACED');self.assertEqual(path.read_bytes(),self.body)
    def test_invalid_download_is_bounded_and_never_promoted(self):
        calls=[]
        def corrupt(*args,**kwargs):calls.append(1);return io.BytesIO(b'x'*len(self.body))
        with self.assertRaises(ValueError):cache.fetch_verified(self.row,self.root,opener=corrupt)
        self.assertEqual(len(calls),3);self.assertFalse((self.root/self.row['filename']).exists())
        self.assertFalse(list(self.root.glob('*.partial')))
    def test_oversize_download_rejected(self):
        with self.assertRaises(ValueError):cache.fetch_verified(self.row,self.root,opener=lambda *a,**k:io.BytesIO(self.body+b'X'))
    def test_path_traversal_and_absolute_cache_members_rejected(self):
        for name in ('../fixture.whl','/fixture.whl','a\\b','C:evil','a/./b'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                cache.fetch_verified(dict(self.row,filename=name),self.root,opener=self.opener)
    def test_cache_symlink_rejected_without_following(self):
        target=self.root/'real';target.write_bytes(self.body)
        link=self.root/self.row['filename']
        try:link.symlink_to(target)
        except OSError:
            # Exercise the guard without claiming Windows symlink privileges.
            original=Path.is_symlink
            with patch.object(Path,'is_symlink',lambda p:p==link or original(p)),self.assertRaises(ValueError):
                cache.fetch_verified(self.row,self.root,opener=self.opener)
            return
        with self.assertRaises(ValueError):cache.fetch_verified(self.row,self.root,opener=self.opener)
    def test_changed_requirement_invalidates_lock(self):
        with patch.object(cache,'sha',return_value='0'*64),self.assertRaises(ValueError):cache.load_locks()
    def test_cache_key_binds_platform_python_and_pins(self):
        first=cache.cache_key()
        with patch.object(cache.sys,'version','3.11.999 synthetic'):
            self.assertNotEqual(first,cache.cache_key())
    def test_offline_install_uses_hashes_no_index_and_no_resolution(self):
        folder=self.root/'wheels';folder.mkdir();(folder/self.row['filename']).write_bytes(self.body)
        wheels=dict(wheels=[dict(self.row,name='fixture',version='1')])
        with patch.object(cache,'load_locks',return_value=(wheels,{})),patch.object(cache.sys,'platform','win32'),\
             patch.object(cache.sys,'version_info',(3,11,9)),patch.object(cache.subprocess,'run') as run:
            cache.install_dependencies(self.root,root=self.root)
        command=run.call_args_list[0].args[0]
        for option in ('--no-index','--require-hashes','--no-deps','--only-binary=:all:'):
            self.assertIn(option,command)
        self.assertEqual(run.call_args_list[1].args[0][-1],'check')
    def test_changed_wheel_never_executed_by_pip(self):
        with patch.object(cache,'load_locks',return_value=(dict(wheels=[dict(self.row,name='fixture',version='1')]),{})),\
             patch.object(cache.sys,'platform','win32'),patch.object(cache.sys,'version_info',(3,11,9)),\
             patch.object(cache.subprocess,'run') as run,self.assertRaises(ValueError):
            cache.install_dependencies(self.root,root=self.root)
        run.assert_not_called()


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'tools').mkdir();(self.root/'docs/dev/releases').mkdir(parents=True)
        (self.root/'tools/inkscape_distribution_lock.json').write_bytes(b'{"source": "authored"}\n')
        (self.root/'docs/dev/releases/INKSCAPE_REDISTRIBUTION.md').write_bytes(b'authored-notice')
        self.files={'bin/inkscape.exe':b'MZ_SYNTHETIC_NOT_EXECUTABLE',
                    'TEMPLATE_AI_SOURCE_MAP.json':b'{"source": "authored"}\n',
                    'TEMPLATE_AI_REDISTRIBUTION.md':b'authored-notice'}
        value=dict(version='1.4.2',executable='bin/inkscape.exe',files=[
            dict(path=n,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in self.files.items()])
        self.files['manifest.json']=(json.dumps(value)+'\n').encode()
        self.pin=dict(version='1.4.2',files=3,manifest_sha256=hashlib.sha256(self.files['manifest.json']).hexdigest())
        self.archive=self.root/'cached-release.zip'
        with zipfile.ZipFile(self.archive,'w') as z:
            for n,b in self.files.items():z.writestr('TemplateAI/engines/inkscape/'+n,b)
            z.writestr('TemplateAI/TemplateAI.exe',b'OLD_APP_MUST_NOT_BE_REUSED')
    def extract(self):
        dest=self.root/'stage';cache.extract_engine(self.archive,dest,self.pin,root=self.root);return dest
    def test_reuses_engine_only_not_old_product_executable(self):
        dest=self.extract();self.assertEqual((dest/'bin/inkscape.exe').read_bytes(),self.files['bin/inkscape.exe'])
        self.assertFalse((dest/'TemplateAI.exe').exists());self.assertEqual(len(list(p for p in dest.rglob('*') if p.is_file())),4)
    def test_changed_dependency_rejected(self):
        dest=self.extract();(dest/'bin/inkscape.exe').write_bytes(b'X'*len(self.files['bin/inkscape.exe']))
        with self.assertRaises(ValueError):cache.validate_engine(dest,self.pin,root=self.root)
    def test_extra_payload_rejected(self):
        dest=self.extract();(dest/'private.db').write_bytes(b'not-allowed')
        with self.assertRaises(ValueError):cache.validate_engine(dest,self.pin,root=self.root)
    def test_manifest_substitution_rejected(self):
        dest=self.extract();(dest/'manifest.json').write_text('{}')
        with self.assertRaises(ValueError):cache.validate_engine(dest,self.pin,root=self.root)
    def test_source_map_mismatch_rejected(self):
        dest=self.extract();(self.root/'tools/inkscape_distribution_lock.json').write_bytes(b'new-map')
        with self.assertRaises(ValueError):cache.validate_engine(dest,self.pin,root=self.root)
    def test_pinned_windows_crlf_source_map_matches_git_lf_semantics(self):
        dest=self.extract();path=dest/'TEMPLATE_AI_SOURCE_MAP.json'
        path.write_bytes(self.files['TEMPLATE_AI_SOURCE_MAP.json'].replace(b'\n',b'\r\n'))
        manifest=json.loads((dest/'manifest.json').read_bytes())
        row=next(r for r in manifest['files'] if r['path']=='TEMPLATE_AI_SOURCE_MAP.json')
        row.update(bytes=path.stat().st_size,sha256=cache.sha(path))
        (dest/'manifest.json').write_text(json.dumps(manifest))
        pin=dict(self.pin,manifest_sha256=cache.sha(dest/'manifest.json'))
        self.assertEqual(cache.validate_engine(dest,pin,root=self.root)['files'],3)
        path.write_bytes(path.read_bytes().replace(b'authored',b'changed'))
        with self.assertRaises(ValueError):cache.validate_engine(dest,pin,root=self.root)
    def test_zip_slip_rejected_before_any_write(self):
        with zipfile.ZipFile(self.archive,'w') as z:
            for n,b in self.files.items():
                z.writestr('TemplateAI/engines/inkscape/'+('../outside' if n=='manifest.json' else n),b)
        with self.assertRaises(ValueError):self.extract()
        self.assertFalse((self.root/'stage').exists());self.assertFalse((self.root/'outside').exists())
    def test_existing_stage_not_overwritten_by_extractor(self):
        self.extract()
        with self.assertRaises(FileExistsError):self.extract()


class ImpactTests(unittest.TestCase):
    def setUp(self):
        self.windows=sorted(impact.FLOOR|{'test_panel','test_other'})
        self.files={'template_ai/panel.py':'VALUE=1\n','tests/test_panel.py':'from template_ai import panel\n'}
    def plan(self,changed,base=None,head=None,**kw):
        return impact.plan_changes(changed,base or self.files,head or self.files,self.windows,**kw)
    def test_docs_only_no_exe_unless_explicitly_requested(self):
        self.assertEqual(self.plan(['docs/guide.md'])['tier'],'DOCUMENTATION_NO_EXE')
        self.assertEqual(self.plan(['docs/guide.md'],force_build=True)['tier'],'FULL_WINDOWS')
    def test_isolated_panel_selects_callers_and_mandatory_floor(self):
        p=self.plan(['template_ai/panel.py']);self.assertEqual(p['tier'],'IMPACTED_PLUS_FLOOR')
        self.assertEqual(set(p['selected_windows_modules']),impact.FLOOR|{'test_panel'})
        self.assertEqual(p['required_actual_exe_checks'],21);self.assertEqual(p['required_engine_scenarios'],5)
    def test_removed_import_still_reachable_through_base(self):
        head=dict(self.files);head['tests/test_panel.py']='VALUE=2\n'
        self.assertIn('test_panel',self.plan(['template_ai/panel.py'],head=head)['selected_windows_modules'])
    def test_unknown_dynamic_import_widens(self):
        files=dict(self.files);files['template_ai/dynamic.py']='import importlib\nimportlib.import_module(name)\n'
        self.assertEqual(self.plan(['template_ai/panel.py'],base=files,head=files)['tier'],'FULL_WINDOWS')
    def test_reviewed_dynamic_contract_is_hash_bound(self):
        files=dict(self.files);text='import importlib\nimportlib.import_module(name)\n';files['template_ai/dynamic.py']=text
        contracts={'template_ai/dynamic.py':dict(sha256=hashlib.sha256(text.encode()).hexdigest(),imports=['template_ai.panel'])}
        self.assertEqual(self.plan(['template_ai/panel.py'],base=files,head=files,contracts=contracts)['tier'],'IMPACTED_PLUS_FLOOR')
        head=dict(files);head['template_ai/dynamic.py']+='X=1\n'
        self.assertEqual(self.plan(['template_ai/panel.py'],base=files,head=head,contracts=contracts)['tier'],'FULL_WINDOWS')
    def test_critical_data_or_build_change_full(self):
        for path in ('template_ai/storage.py','template_ai/design_session.py','.github/workflows/build.yml',
                     'requirements-lock.txt','docs/dev/releases/release_cache.py','unknown/config.json'):
            with self.subTest(path=path):self.assertEqual(self.plan([path])['tier'],'FULL_WINDOWS')
    def test_new_or_deleted_product_module_full(self):
        self.assertEqual(self.plan(['template_ai/missing.py'])['tier'],'FULL_WINDOWS')
    def test_unmapped_product_never_empty_pass(self):
        files={'template_ai/panel.py':'VALUE=1\n'}
        self.assertEqual(self.plan(['template_ai/panel.py'],base=files,head=files)['tier'],'FULL_WINDOWS')
    def test_missing_floor_contract_is_error(self):
        with self.assertRaises(ValueError):impact.plan_changes([],{}, {}, [])
    def test_syntax_error_widens(self):
        files=dict(self.files);files['template_ai/panel.py']='def broken('
        self.assertEqual(self.plan(['template_ai/panel.py'],head=files)['tier'],'FULL_WINDOWS')
    def test_previous_release_logs_do_not_falsely_expand_unrelated_panel_change(self):
        p=self.plan(['template_ai/panel.py','docs/dev/releases/v0.2.0-beta.2/windows/native.log'])
        self.assertEqual(p['tier'],'IMPACTED_PLUS_FLOOR');self.assertEqual(len(p['report_only_paths']),1)
    def test_report_metadata_alone_needs_no_exe_but_executable_in_report_folder_is_not_exempt(self):
        self.assertEqual(self.plan(['docs/dev/releases/release-speed-validation/demo/report.json'])['tier'],'DOCUMENTATION_NO_EXE')
        self.assertEqual(self.plan(['docs/dev/releases/release-speed-validation/demo/run.py'])['tier'],'FULL_WINDOWS')
    def test_git_batch_snapshot_preserves_exact_selected_source(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            expected={'template_ai/panel.py':'# 中文\nVALUE=1\n','tests/test_panel.py':'from template_ai import panel\n'}
            for name,body in expected.items():
                path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(body.encode())
            (root/'unrelated.bin').write_bytes(b'not-source')
            for command in (['git','init'],['git','add','.'],['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','authored snapshot']):
                subprocess.run(command,cwd=root,check=True,capture_output=True)
            self.assertEqual(impact.snapshot(root,'HEAD'),expected)


class GuardTests(unittest.TestCase):
    def test_budget_unknown_private_or_over_limit_no_remote_save(self):
        for usage,size,public in ((None,1,True),(0,1,False),(9*1024**3,1,True),(0,3*1024**3,True)):
            self.assertFalse(budget(usage,size,public))
        self.assertTrue(budget(0,1508883223,True))
    def test_old_tag_is_rejected_before_any_remote_mutation(self):
        with patch.dict(pipeline.os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REF':pipeline.BUILDER_REF,'RELEASE_SPEED_PUBLISH_ALLOWED':'true'}),\
             patch.object(pipeline.subprocess,'check_output',return_value=b'existing-tag\n') as read,\
             patch.object(pipeline.subprocess,'run') as mutate,self.assertRaises(FileExistsError):
            pipeline.publication_preflight('0.2.0-beta.2','publish')
        self.assertEqual(read.call_args.args[0][1:3],['ls-remote','--tags']);mutate.assert_not_called()
    def test_validation_mode_never_checks_or_creates_release(self):
        with patch.object(pipeline.subprocess,'run') as mutate,patch.object(pipeline.subprocess,'check_output') as read:
            pipeline.publication_preflight('0.2.0-beta.2','validate')
        mutate.assert_not_called();read.assert_not_called()
    def test_wrong_publication_branch_rejected(self):
        with patch.dict(pipeline.os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REF':'refs/heads/dev/x','RELEASE_SPEED_PUBLISH_ALLOWED':'true'}),self.assertRaises(ValueError):
            pipeline.publication_preflight('0.2.0-beta.3','publish')
    def test_old_beta_authorization_cannot_authorize_new_version(self):
        with patch.dict(pipeline.os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REF':pipeline.BUILDER_REF,'RELEASE_SPEED_PUBLISH_ALLOWED':'true'}),\
             patch.object(pipeline.subprocess,'check_output',return_value=''),\
             patch.object(pipeline.subprocess,'run') as mutate,self.assertRaises(ValueError):
            pipeline.publication_preflight('0.2.0-beta.3','publish')
        mutate.assert_not_called()
    def test_future_publication_requires_exact_source_request_ref(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);(root/'docs/dev').mkdir(parents=True)
            state=dict(release_speed_optimization=dict(release_request=dict(version='0.2.0-beta.3',published=False,
                authorization=dict(scope='PUBLISH_WINDOWS_INTERNAL_BETA',user_request='authored version-specific authorization fixture'))))
            (root/'docs/dev/STATE.json').write_text(json.dumps(state))
            for ref,allowed in (('f'*40,True),('0'*40,False)):
                reads=['',ref+'\trefs/heads/release-request/v0.2.0-beta.3\n','f'*40+'\n']
                absent=subprocess.CompletedProcess([],1,b'',b'release not found')
                readable=subprocess.CompletedProcess([],0,b'false',b'')
                with patch.object(pipeline,'ROOT',root),patch.dict(pipeline.os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REF':pipeline.BUILDER_REF,'RELEASE_SPEED_PUBLISH_ALLOWED':'true'}),\
                     patch.object(pipeline.subprocess,'check_output',side_effect=reads),\
                     patch.object(pipeline.subprocess,'run',side_effect=[absent,readable]) as run:
                    if allowed:pipeline.publication_preflight('0.2.0-beta.3','publish')
                    else:
                        with self.assertRaises(ValueError):pipeline.publication_preflight('0.2.0-beta.3','publish')
                        run.assert_not_called()
    def test_workflow_uses_stable_builder_for_cross_version_cache_scope(self):
        text=(cache.ROOT/'.github/workflows/optimized-release.yml').read_text()
        self.assertIn("- '"+pipeline.BUILDER_REF.removeprefix('refs/heads/')+"'",text)
        self.assertNotIn("- 'release-request/**'",text)
        self.assertNotIn('pull_request:',text)
    def test_failed_stage_preserves_status_and_time(self):
        with tempfile.TemporaryDirectory() as raw:
            r=pipeline.Stages(Path(raw)/'timing.json','synthetic')
            with self.assertRaises(RuntimeError),r.stage('controlled-failure'):
                raise RuntimeError('authored failure')
            saved=json.loads((Path(raw)/'timing.json').read_text());row=saved['stages'][0]
            self.assertEqual(row['status'],'FAIL');self.assertGreaterEqual(row['seconds'],0)
    def test_build_continuation_requires_current_source_and_verified_inputs(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/'timing.json';r=pipeline.Stages(path,'synthetic')
            r.data['status']='INPUTS_VERIFIED_NOT_PRODUCT_VALIDATED';r.save()
            self.assertEqual(pipeline.Stages(path,'synthetic',resume=True).data['status'],'INPUTS_VERIFIED_NOT_PRODUCT_VALIDATED')
            data=json.loads(path.read_text());data['source_commit']='0'*40;path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):pipeline.Stages(path,'synthetic',resume=True)
            data['source_commit']=r.data['source_commit'];data['status']='FAILED_NOT_VERIFIED';path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):pipeline.Stages(path,'synthetic',resume=True)
    def test_real_published_source_map_matches_windows_serializer(self):
        root=cache.ROOT
        value=json.loads((root/'tools/inkscape_distribution_lock.json').read_bytes())
        generated=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').replace('\n','\r\n').encode()
        manifest=json.loads((root/'docs/dev/releases/v0.2.0-beta.2/windows-native-004/release-manifest.json').read_bytes())
        row=next(r for r in manifest['package_files'] if r['path']=='engines/inkscape/TEMPLATE_AI_SOURCE_MAP.json')
        self.assertEqual(hashlib.sha256(generated).hexdigest(),row['sha256'])
        self.assertEqual(len(generated),row['bytes'])
    def test_sha_locked_engine_and_all_dependencies_current(self):
        wheels,assets=cache.load_locks();self.assertEqual(len(wheels['wheels']),27)
        self.assertEqual(assets['engine']['files'],11837)


if __name__=='__main__':unittest.main()
