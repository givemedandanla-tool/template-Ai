import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

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
