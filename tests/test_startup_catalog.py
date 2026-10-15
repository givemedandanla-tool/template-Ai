import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.gui import MainWindow
from template_ai.model import Template,Slot,Rect,new_id
from template_ai.startup_catalog import editor_page,search
from training_fixture import source_work

APP=QApplication.instance() or QApplication([])


class StartupCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.library=Library(self.root/'data');TrainingStore(self.library);self.addCleanup(self.library.close);self.windows=[];self.addCleanup(self.close_windows)

    def close_windows(self):
        for window in self.windows:window.source=None;window.work=None;window.template=None;window.close()

    def templates(self,count):
        ids=[];rows=[]
        for index in range(count):
            template=Template('Style '+str(index),90,54,[Slot('name','p1',Rect(2,2,40,8))]);ids.append(template.id)
            if index==count-1:template.name='Straße special needle'
            rows.append((template.id,template.family_id,template.version,template.state,json.dumps(template.to_dict())))
        with self.library.db:self.library.db.executemany('INSERT INTO templates VALUES(?,?,?,?,?)',rows)
        return ids

    def window(self):
        window=MainWindow(self.library.root);self.windows.append(window);return window

    def test_thousand_template_startup_never_calls_unbounded_catalog_and_global_unicode_search_opens_exact_id(self):
        ids=self.templates(1003)
        with patch.object(Library,'templates',side_effect=AssertionError('unbounded startup read')):window=self.window()
        self.assertLessEqual(len(window.templates),48);self.assertLessEqual(len(window.template_catalog.entries),48)
        self.assertEqual(window.template_catalog.matching_count,1003);window.template_catalog.query.setText('STRASSE special');self.assertEqual(window.template_catalog.matching_count,1)
        self.assertEqual(window.template_catalog.visible[0]['template_id'],ids[-1]);window.open_catalog_editor(ids[1]);self.assertEqual(window.template.id,ids[1]);self.assertLessEqual(len(window.templates),48)

    def test_source_page_denominator_and_selected_id_work_across_pages_without_unbounded_read(self):
        source,work=source_work(self.library,self.root);raw=json.dumps(source);rows=[];ids=[]
        for index in range(122):
            identity=new_id();value=dict(source,id=identity,original_path=str(self.root/('synthetic-'+str(index)+'.svg')));rows.append((identity,source['hash'],value['original_path'],json.dumps(value)));ids.append(identity)
        with self.library.db:self.library.db.executemany('INSERT INTO sources VALUES(?,?,?,?)',rows)
        with patch.object(Library,'list_sources',side_effect=AssertionError('unbounded startup read')):window=self.window()
        window.refresh_sources(select=source['id']);self.assertEqual(window.source['id'],source['id']);self.assertEqual(window.source_offset,96);self.assertEqual(len(window.sources),27);self.assertIn('全部123',window.source_count.text())
        window.source_page(-48);self.assertEqual(window.source_offset,48);self.assertEqual(len(window.sources),48);self.assertNotEqual(window.source['id'],source['id']);self.assertEqual(self.library.artwork(work['id']),work)

    def test_lazy_fonts_and_models_are_not_loaded_or_parsed_at_normal_startup(self):
        with self.library.db:
            self.library.db.executemany('INSERT INTO font_assets VALUES(?,?)',[(str(index),json.dumps(dict(hash=str(index),path='UNREADABLE_SYNTHETIC',families=['SYNTHETIC']))) for index in range(1000)])
        with patch.object(Library,'fonts',side_effect=AssertionError('all font assets loaded')),patch('template_ai.gui.import_file',side_effect=AssertionError('original parsed at startup')),patch('template_ai.semantic_learning.SemanticLearning.active',side_effect=AssertionError('model loaded at startup')):window=self.window()
        self.assertEqual(window.font_manager.loaded,{});self.assertTrue(hasattr(window,'runtime'));self.assertTrue(hasattr(window,'execution_queue'));self.assertFalse(window.busy)

    def test_oversized_single_payload_is_explicitly_blocked_without_hiding_denominator_or_loading_it(self):
        ids=self.templates(2);value=Template('X'*1_100_000,90,54,[]).to_dict();value.update(id=ids[-1])
        with self.library.db:self.library.db.execute('UPDATE templates SET payload=? WHERE id=?',(json.dumps(value),ids[-1]))
        page=editor_page(self.library,'templates');self.assertEqual(page['total'],2);self.assertEqual(len(page['items']),1);self.assertIn('1MiB',page['issues'][0]);window=self.window();self.assertIn('1MiB',window.template_count.toolTip());self.assertTrue(window.isEnabled())

    def test_sql_filter_count_and_page_are_global_and_query_bounds_fail_before_expansion(self):
        self.templates(203);first=search(self.library,page=0);last=search(self.library,page=4)
        self.assertEqual(first['total'],203);self.assertEqual(len(first['ids']),48);self.assertEqual(len(last['ids']),11);self.assertFalse(set(first['ids'])&set(last['ids']))
        with self.assertRaises(ValueError):search(self.library,'a'*501)
        with self.assertRaises(ValueError):editor_page(self.library,'templates',limit=101)

    def test_invalid_resource_policy_still_opens_gui_and_diagnostic_entry_with_background_fail_closed(self):
        with self.library.db:self.library.db.execute('INSERT INTO preferences VALUES(?,?)',('runtime_execution_policy','{"version":99}'))
        window=self.window();self.assertIsNotNone(window.runtime.policy_error);self.assertTrue(window.runtime.pause_event.is_set());self.assertFalse(window.runtime.admit().allowed);self.assertTrue(window.isEnabled());self.assertTrue(hasattr(window,'execution_queue'))

    def test_explicit_source_preflight_and_registration_lookup_never_expand_all_other_source_records(self):
        from template_ai.automatic_training import AutomaticTraining
        source,work=source_work(self.library,self.root)
        with patch.object(Library,'list_sources',side_effect=AssertionError('unbounded analysis source lookup')):
            report=AutomaticTraining(self.library).preflight([source['original_path']],compare=False);job=AutomaticTraining(self.library).create(report,'SYNTHETIC',True)
        self.assertEqual(job['items'][0]['source_id'],source['id']);self.assertEqual(report['items'][0]['existing_source_id'],source['id'])
