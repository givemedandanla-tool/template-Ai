import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os,io,zipfile,hashlib,sqlite3,stat

from template_ai import relational_backup as backup
from template_ai.storage import Library
from template_ai.customers import CustomerStore
from template_ai.fonts import FontManager
from template_ai.font_evidence import inspect_font
from PySide6.QtWidgets import QApplication

APP=QApplication.instance() or QApplication([])
PASSWORD='synthetic test password 2026'


class RelationalBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=Library(self.root/'library');self.addCleanup(self.library.close)
        self.target=self.root/'synthetic-backup.tabi'

    def create(self,**options):
        plan=backup.plan_backup(self.library,**options)
        return backup.create_backup(self.library,self.target,PASSWORD,plan,True),plan

    def fixture(self):
        import test_customer_candidates as module
        case=module.CustomerCandidateTests();case.library=self.library;case.root=self.root
        case.store=CustomerStore(self.library)
        from template_ai.customer_candidates import CustomerCandidates
        case.candidates=CustomerCandidates(case.store)
        source,work,template=case.make_source('00001.svg')
        candidate=case.reviewed(case.candidates.propose(source['id'])[0]);case.commit([candidate])
        customer=case.store.search('00001',field='CODE')[0]
        return source,work,template,customer

    def test_empty_library_authenticated_package_and_isolated_restore_never_claim_output_ready(self):
        result,plan=self.create()
        self.assertTrue(result['complete']);self.assertFalse(result['test_restore'])
        restored=backup.restore_bundle(self.target,self.root/'restore',PASSWORD,True)
        self.assertEqual(restored['database_integrity'],'PASS');self.assertFalse(restored['production_ready'])
        self.assertTrue(restored['test_restore']);self.assertTrue(Path(restored['library_root']).is_dir())
        self.assertTrue((self.root/'restore/RESTORE_COMPLETE.json').is_file())

    def test_real_source_customer_styles_facts_and_all_cache_bytes_restore_with_portable_paths(self):
        source,work,template,customer=self.fixture()
        result,plan=self.create(include_sources=True,include_fonts=True)
        self.assertTrue(result['complete'],plan['notes'])
        restored=backup.restore_bundle(self.target,self.root/'portable',PASSWORD,True)
        library=Library(restored['library_root']);self.addCleanup(library.close)
        actual=library.source(source['id'])
        self.assertEqual(actual['original_path'],source['original_path'])
        self.assertNotEqual(actual['current_path'],self.library.source(source['id'])['current_path'])
        self.assertTrue(Path(actual['current_path']).is_file());self.assertEqual(backup.file_digest(actual['current_path']),source['hash'])
        store=CustomerStore(library);current=store.get(customer['id'])
        self.assertEqual(current['fields'],customer['fields']);self.assertEqual(current['graph']['people'],customer['graph']['people'])
        prefill=store.reorder(customer['id'],customer['styles'][0]['id'],True)
        self.assertEqual(prefill['status'],'PREFILL_PENDING_VALIDATION')
        self.assertEqual(library.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_new_machine_restore_succeeds_when_original_library_and_raw_source_paths_are_completely_offline(self):
        source,_,_,customer=self.fixture();self.create(include_sources=True,include_fonts=True)
        original=Path(self.library.source(source['id'])['current_path'])
        self.library.close();self.library.root.rename(self.root/'old-machine-offline');original.rename(self.root/'raw-offline.svg')
        restored=backup.restore_bundle(self.target,self.root/'new-machine',PASSWORD,True)
        library=Library(restored['library_root']);self.addCleanup(library.close)
        actual=library.source(source['id'])
        self.assertTrue(Path(actual['current_path']).is_file());self.assertEqual(backup.file_digest(actual['current_path']),source['hash'])
        store=CustomerStore(library);prefill=store.reorder(customer['id'],customer['styles'][0]['id'],True)
        self.assertEqual(prefill['status'],'PREFILL_PENDING_VALIDATION')
        self.assertEqual(restored['unresolved_references'],[])

    def rewrap(self,mutate,filename):
        package,manifest=backup.read_bundle(self.target,PASSWORD)
        data={name:package.read(name) for name in package.namelist()};package.close()
        special=mutate(data,manifest) or {}
        data['manifest.json']=backup._json(manifest)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
            for name,value in data.items():
                info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_STORED
                if name in special:info.external_attr=special[name]
                archive.writestr(info,value)
        salt=os.urandom(16);nonce=os.urandom(12)
        blob=backup.MAGIC+salt+nonce+backup.AESGCM(backup.key(PASSWORD,salt)).encrypt(nonce,stream.getvalue(),backup.MAGIC)
        path=self.root/filename;path.write_bytes(blob);return path

    def test_authenticated_but_malformed_paths_windows_case_collisions_and_symlinks_are_rejected(self):
        (self.library.assets/'allowed.bin').write_bytes(b'synthetic asset');self.create()
        def traversal(data,manifest):
            entry=manifest['entries'][0];old=entry['member'];entry['member']='assets/../outside.bin';data[entry['member']]=data.pop(old)
        def collision(data,manifest):
            entry=dict(manifest['entries'][0]);entry['member']=entry['member'].upper();manifest['entries'].append(entry);data[entry['member']]=b'synthetic asset'
        def symlink(data,manifest):return {manifest['entries'][0]['member']:(stat.S_IFLNK|0o777)<<16}
        for i,mutate in enumerate((traversal,collision,symlink)):
            forged=self.rewrap(mutate,f'hostile{i}.tabi')
            with self.assertRaises(ValueError):backup.restore_bundle(forged,self.root/f'reject{i}',PASSWORD,True)
            self.assertFalse((self.root/f'reject{i}').exists())
        self.assertFalse((self.root/'outside.bin').exists())

    def test_authenticated_unknown_schema_is_blocked_and_incomplete_restore_cannot_open_as_library(self):
        self.create()
        def unsupported(data,manifest):
            probe=self.root/'alter.sqlite3';probe.write_bytes(data['library.sqlite3'])
            with sqlite3.connect(probe) as db:db.execute('CREATE VIEW future_view AS SELECT 1')
            db.close()  # Commit context does not close/checkpoint the WAL connection.
            data['library.sqlite3']=probe.read_bytes();manifest['database_bytes']=len(data['library.sqlite3']);manifest['database_sha256']=hashlib.sha256(data['library.sqlite3']).hexdigest()
        forged=self.rewrap(unsupported,'unsupported.tabi')
        with self.assertRaisesRegex(ValueError,'trigger/view'):backup.restore_bundle(forged,self.root/'unsupported',PASSWORD,True)
        self.assertFalse((self.root/'unsupported').exists())
        incomplete=self.root/'incomplete';incomplete.mkdir();(incomplete/'RESTORE_STAGING_NOT_ACTIVE').write_text('not active')
        with self.assertRaisesRegex(ValueError,'尚未完成'):Library(incomplete/'restored-library')
        self.assertFalse((incomplete/'restored-library/library.sqlite3').exists())

    def test_restore_interrupts_old_workers_preserves_completed_units_and_disables_watch_roots(self):
        from template_ai.training_store import TrainingStore
        from template_ai.source_scan import register_root
        self.fixture();store=TrainingStore(self.library);root=register_root(store,self.root)
        with store.transaction():
            store._write('WORKER','automatic-worker',dict(active=True,owner=dict(pid=123456,token='old')),0,'synthetic')
            store._write('AUTO_JOB','restore-job',dict(phase='RUNNING',owner=dict(pid=123456),items=[dict(state='RUNNING'),dict(state='COMPLETED')]),0,'synthetic')
        self.create(include_sources=True,include_fonts=True)
        restored=backup.restore_bundle(self.target,self.root/'workers',PASSWORD,True)
        library=Library(restored['library_root']);self.addCleanup(library.close);new=TrainingStore(library)
        self.assertFalse(new.get('WORKER','automatic-worker')['active'])
        job=new.get('AUTO_JOB','restore-job');self.assertEqual(job['phase'],'INTERRUPTED');self.assertIsNone(job['owner'])
        self.assertEqual([item['state'] for item in job['items']],['INTERRUPTED','COMPLETED'])
        self.assertFalse(new.get('SCAN_ROOT',root['id'])['enabled']);self.assertEqual(new.get('SCAN_ROOT',root['id'])['restore_state'],'RECONNECT_REQUIRED')
        self.assertTrue(store.get('WORKER','automatic-worker')['active'])

    def test_disk_preflight_and_write_failure_leave_no_success_or_damaged_existing_file(self):
        plan=backup.plan_backup(self.library)
        with patch.object(backup.shutil,'disk_usage',return_value=type('Usage',(),dict(free=0))()):
            with self.assertRaisesRegex(ValueError,'空間'):backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        with patch.object(backup,'publish_complete',side_effect=PermissionError('synthetic disk denial')):
            with self.assertRaises(PermissionError):backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        self.assertFalse(self.target.exists());self.assertFalse(list(self.root.glob('.backup-complete-*')))

    def test_cancelled_real_pack_and_isolated_extract_leave_current_data_and_no_completed_target(self):
        (self.library.assets/'small.bin').write_bytes(b'synthetic asset');plan=backup.plan_backup(self.library)
        cancelled=[False];events=[]
        def progress(event):
            events.append(event)
            if event['phase']=='PACK_ASSETS':cancelled[0]=True
        with self.assertRaisesRegex(ValueError,'取消'):
            backup.create_backup(self.library,self.target,PASSWORD,plan,True,cancel=lambda:cancelled[0],progress=progress)
        self.assertFalse(self.target.exists());self.assertTrue(any(e.get('completed')==1 for e in events))
        backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        cancelled[0]=False
        def stop_extract(event):
            if event['phase']=='RESTORE_EXTRACT':cancelled[0]=True
        with self.assertRaisesRegex(ValueError,'取消'):
            backup.restore_bundle(self.target,self.root/'cancelled-restore',PASSWORD,True,cancel=lambda:cancelled[0],progress=stop_extract)
        self.assertFalse((self.root/'cancelled-restore').exists());self.assertEqual((self.library.assets/'small.bin').read_bytes(),b'synthetic asset')

    def test_changed_published_archive_is_retained_unverified_instead_of_claiming_success(self):
        plan=backup.plan_backup(self.library);original=backup.publish_complete
        def change(staged,target,check):
            original(staged,target,check);Path(target).write_bytes(b'external concurrent modification')
        with patch.object(backup,'publish_complete',side_effect=change):
            with self.assertRaisesRegex(ValueError,'發布後檔案已變更'):backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        self.assertEqual(self.target.read_bytes(),b'external concurrent modification')

    def test_source_facts_survive_restoration_but_old_host_stat_confirmation_is_not_a_new_quality_pass(self):
        from template_ai.training_store import TrainingStore
        source,work,_,_=self.fixture();store=TrainingStore(self.library);facts=store.facts(work['id'])
        self.assertEqual(store.facts_state(work['id']),'CONFIRMED')
        self.create(include_sources=True,include_fonts=True)
        result=backup.restore_bundle(self.target,self.root/'facts',PASSWORD,True)
        library=Library(result['library_root']);self.addCleanup(library.close);new=TrainingStore(library)
        self.assertEqual(new.facts(work['id'])['observations'],facts['observations'])
        self.assertEqual(new.facts_state(work['id']),'STALE')
        self.assertTrue(result['old_host_source_stat_not_adopted'])
        self.assertEqual(store.facts_state(work['id']),'CONFIRMED')

    def test_existing_environment_preview_finds_newer_real_rows_without_writes_and_restores_to_separate_copy(self):
        source,work,template,customer=self.fixture();self.create(include_sources=True,include_fonts=True)
        store=CustomerStore(self.library);field=next(f for f in customer['fields'] if f['kind']=='name')['id']
        updated=store.writeback(customer,{field:'Newer legitimate customer name'},[field],True)
        preview=backup.inspect_restore(self.target,PASSWORD,True,self.library.root)
        self.assertFalse(preview['existing_environment_modified']);self.assertFalse(preview['automatic_merge'])
        table=next(r for r in preview['database_rows'] if r['category']=='customer_fields')
        self.assertGreaterEqual(table['different_rows'],1);self.assertEqual(store.get(customer['id']),updated)
        with self.assertRaisesRegex(ValueError,'預覽不同'):
            backup.restore_bundle(self.target,self.root/'wrong-pin',PASSWORD,True,expected_archive_sha256='0'*64)
        self.assertFalse((self.root/'wrong-pin').exists())
        result=backup.restore_bundle(self.target,self.root/'older-copy',PASSWORD,True,expected_archive_sha256=preview['archive_sha256'])
        separate=Library(result['library_root']);self.addCleanup(separate.close)
        old=CustomerStore(separate).get(customer['id'])
        self.assertNotEqual(old['fields'],updated['fields']);self.assertEqual(store.get(customer['id']),updated)

    def test_sources_and_fonts_require_separate_backup_rights_and_missing_references_are_partial(self):
        source,_,_,_=self.fixture()
        manager=FontManager(self.library);self.addCleanup(manager.close)
        asset=manager.import_font('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',True)
        plan=backup.plan_backup(self.library)
        self.assertFalse(plan['complete']);self.assertTrue(any('FONT' in n['state'] for n in plan['notes']))
        with self.assertRaisesRegex(ValueError,'部分備份'):backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        full=backup.plan_backup(self.library,True,True)
        self.assertTrue(full['complete'],full['notes'])
        Path(asset['path']).unlink()
        missing=backup.plan_backup(self.library,True,True)
        self.assertFalse(missing['complete']);self.assertTrue(any(n['state']=='REFERENCED_ASSET_MISSING' for n in missing['notes']))

    def test_preview_pins_database_and_assets_and_changed_bytes_never_publish_half_archive(self):
        source,_,_,_=self.fixture();plan=backup.plan_backup(self.library,True,True)
        with self.library.db:self.library.event('test','legitimate concurrent update')
        with self.assertRaisesRegex(ValueError,'變更'):backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        self.assertFalse(self.target.exists())
        plan=backup.plan_backup(self.library,True,True);Path(self.library.source(source['id'])['current_path']).write_text('changed source')
        with self.assertRaises(ValueError):backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        self.assertFalse(self.target.exists())

    def test_mid_snapshot_database_update_is_retained_but_backup_publish_is_blocked(self):
        plan=backup.plan_backup(self.library);original=backup._snapshot
        def change(library,path):
            value=original(library,path)
            with library.db:library.event('test','concurrent legitimate write')
            return value
        with patch.object(backup,'_snapshot',side_effect=change):
            with self.assertRaises(ValueError):backup.create_backup(self.library,self.target,PASSWORD,plan,True)
        self.assertFalse(self.target.exists())

    def test_wrong_password_corruption_existing_target_and_untrusted_source_never_touch_current_data(self):
        self.create();before=backup.file_digest(self.library.root/'library.sqlite3')
        for password,trusted in [('wrong password',True),(PASSWORD,False)]:
            with self.assertRaises(ValueError):backup.restore_bundle(self.target,self.root/'bad',password,trusted)
            self.assertFalse((self.root/'bad').exists())
        existing=self.root/'existing';existing.mkdir();(existing/'keep').write_text('keep')
        with self.assertRaises(FileExistsError):backup.restore_bundle(self.target,existing,PASSWORD,True)
        self.assertEqual((existing/'keep').read_text(),'keep')
        blob=bytearray(self.target.read_bytes());blob[-1]^=1;self.target.write_bytes(blob)
        with self.assertRaises(ValueError):backup.restore_bundle(self.target,self.root/'corrupt',PASSWORD,True)
        self.assertFalse((self.root/'corrupt').exists());self.assertEqual(backup.file_digest(self.library.root/'library.sqlite3'),before)

    def test_database_categories_cannot_be_silently_sliced_and_budget_failure_is_explicit(self):
        blocked=backup.plan_backup(self.library,customers=False)
        self.assertEqual(blocked['state'],'BLOCKED_DATABASE_CATEGORY_DEPENDENCY')
        with self.assertRaises(ValueError):backup.create_backup(self.library,self.target,PASSWORD,blocked,True)
        owned=self.library.assets/'large.bin';owned.write_bytes(b'X'*(2*1024*1024))
        with self.assertRaisesRegex(ValueError,'預算'):backup.plan_backup(self.library,limit_bytes=1_048_576)
        self.assertFalse(self.target.exists())

    def test_same_bytes_distinct_original_names_and_source_ids_survive_backup_and_restore(self):
        source,_,_,_=self.fixture()
        import test_customer_candidates as module
        from template_ai.customer_candidates import CustomerCandidates
        case=module.CustomerCandidateTests();case.library=self.library;case.root=self.root;case.candidates=CustomerCandidates(CustomerStore(self.library))
        second,_,_=case.make_source('00002.svg')
        self.assertEqual(second['hash'],source['hash'])
        result,plan=self.create(include_sources=True,include_fonts=True)
        originals=[e for e in plan['entries'] if e['member'].startswith('originals/')]
        self.assertEqual(len(originals),1)
        restored=backup.restore_bundle(self.target,self.root/'aliases',PASSWORD,True)
        library=Library(restored['library_root']);self.addCleanup(library.close)
        a,b=library.source(source['id']),library.source(second['id'])
        self.assertNotEqual(a['id'],b['id']);self.assertNotEqual(a['current_path'],b['current_path'])
        self.assertEqual(Path(a['original_path']).name,'00001.svg');self.assertEqual(Path(b['original_path']).name,'00002.svg')
        self.assertEqual(backup.file_digest(a['current_path']),backup.file_digest(b['current_path']))


if __name__=='__main__':unittest.main()
