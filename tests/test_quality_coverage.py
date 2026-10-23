from gui_wait import dispose_main_window
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work
from test_noise_authoring import confirmed
from test_trusted_samples import admitted
from test_dataset_learning import frozen
APP=QApplication.instance() or QApplication([])


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close);self.store=TrainingStore(self.library)
    def seed(self):
        source,work=source_work(self.library,self.root);confirmed(self.store,work);sample=admitted(self.store,work);return source,work,sample
    def test_empty_inventory_neutral_no_quality_or_supplementation(self):
        report=self.store.coverage_report();self.assertEqual(report['totals']['sources'],0);self.assertEqual(report['totals']['artworks'],0);self.assertFalse(report['quality_pass_claim']);self.assertFalse(report['supplementation']);self.assertTrue(report['scan']['complete_inventory']);self.assertEqual(report['facets'],{})
    def test_source_without_artwork_aliases_denominators_and_overlapping_facets(self):
        source,work,sample=self.seed();source2,work2=source_work(self.library,self.root,'alias.svg');extra=self.library.add_source(Path(source['original_path']),{k:v for k,v in source.items() if k not in ('id','original_path')});report=self.store.coverage_report();self.assertEqual(report['totals']['sources'],3);self.assertEqual(report['totals']['artworks'],2);self.assertEqual(report['totals']['sources_without_artworks'],1);self.assertEqual(len(report['facets']['content_group'][source['hash']]),2);self.assertEqual(report['facets']['people']['1'],sorted([work['id'],work2['id']]));self.assertEqual(report['facets']['companies']['0'],sorted([work['id'],work2['id']]));self.assertEqual(report['sample_states'],{'APPROVED':1});self.assertTrue(all(r['native_effects']=='UNKNOWN' for r in report['artworks']));self.assertTrue(any(s['source_id']==extra['id'] and s['health']=='CURRENT_HEALTH_UNKNOWN' for s in report['sources']))
    def test_holdout_pending_roles_and_revocation_update_current_counts_keep_saved_history(self):
        source,work,sample=self.seed();ds=frozen(self.store,[sample],'HOLDOUT');before=self.store.coverage_report();self.assertEqual(before['saved_dataset_role_occurrences'],{'HOLDOUT':1});self.assertEqual(before['current_role_occurrences_in_scanned_scope'],{'HOLDOUT':1});self.store.transition_sample(self.store.sample_transition_plan(sample['id'],'REVOKE'),'Reviewer','withdraw',True);after=self.store.coverage_report();self.assertEqual(after['sample_states'],{'REVOKED':1});self.assertEqual(after['current_role_occurrences_in_scanned_scope'],{});self.assertEqual(after['saved_dataset_role_occurrences'],{'HOLDOUT':1});self.assertEqual(after['unvalidated_role_occurrences_in_scanned_datasets'],1);self.assertNotEqual(after['snapshot_digest'],before['snapshot_digest']);self.assertEqual(before['sample_states'],{'APPROVED':1});self.assertEqual(self.store.get('DATASET',ds['id']),ds)
    def test_bounded_scan_no_images_readonly_reproducible_and_bad_limit(self):
        self.seed();source2,work2=source_work(self.library,self.root,'other.svg');epoch=self.store.epoch;reviews=self.library.db.execute('SELECT count(*) FROM reviews').fetchone()[0]
        with patch('template_ai.trusted_samples.healthy_source',side_effect=AssertionError('inventory must not load/rasterize image')):a=self.store.coverage_report(limit=1);b=self.store.coverage_report(limit=1)
        self.assertEqual(a,b);self.assertFalse(a['scan']['complete_inventory']);self.assertEqual(a['totals']['sources'],2);self.assertEqual(a['scan']['sources'],1);self.assertEqual(a['scan']['artworks'],1);self.assertFalse(a['images_loaded']);self.assertEqual(self.store.epoch,epoch);self.assertEqual(self.library.db.execute('SELECT count(*) FROM reviews').fetchone()[0],reviews)
        with self.assertRaises(ValueError):self.store.coverage_report(limit=201)
        with self.assertRaises(ValueError):self.store.coverage_report(offset=-1)
    def test_file_missing_and_native_logo_unknown_are_not_false_quality_pass(self):
        source,work,sample=self.seed();Path(source['original_path']).unlink();report=self.store.coverage_report();self.assertEqual(report['sources'][0]['health'],'SOURCE_MISSING');self.assertEqual(report['sample_states'],{'STALE':1});self.assertFalse(report['quality_pass_claim']);self.assertIn('SOURCE_CONTENT_UNKNOWN',report['artworks'][0]['logo_class'])


class CoverageGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close);self.source,self.work=source_work(self.window.library,self.root);self.store=TrainingStore(self.window.library);confirmed(self.store,self.work);self.sample=admitted(self.store,self.work);self.d=TrainingQualityDialog(self.window);self.addCleanup(self.d.close);self.p=self.d.inventory_panel;self.d.show();self.d.tabs.setCurrentWidget(self.p);APP.processEvents()
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;dispose_main_window(self.window)
    def select_work(self):
        axis=self.p.tree.topLevelItem(0);group=axis.child(0);item=group.child(0);axis.setExpanded(True);group.setExpanded(True);self.p.tree.setCurrentItem(item);APP.processEvents()
    def test_actual_drilldown_source_locate_readonly_and_stale_guard(self):
        before=self.window.library.artwork(self.work['id']);epoch=self.store.epoch;self.select_work();QTest.mouseClick(self.p.locate_button,Qt.LeftButton);self.assertEqual(self.window.work['id'],self.work['id']);self.assertEqual(self.window.library.artwork(self.work['id']),before);self.assertEqual(self.store.epoch,epoch)
        payload=copy.deepcopy(before['payload']);payload['slots'][0]['rect']['x']+=1;self.window.library.save_artwork(self.work['id'],payload,1);QTest.mouseClick(self.p.locate_button,Qt.LeftButton);self.assertIn('已變更',self.p.status.text());self.p.reload();self.assertEqual(self.p.report['sample_states'],{'STALE':1})
    def test_actual_failed_statistics_recovery_and_neutral_unknown_detail(self):
        with patch.object(self.p.store,'coverage_report',side_effect=RuntimeError('synthetic failure')):self.p.reload()
        self.assertIsNone(self.p.report);self.assertIn('未完成',self.p.status.text());self.assertTrue(self.p.reload_button.isEnabled());self.p.reload();self.assertEqual(self.p.report['totals']['stored_samples'],1);self.assertFalse(self.p.report['quality_pass_claim']);self.assertIn('UNKNOWN',self.p.details.toPlainText())
