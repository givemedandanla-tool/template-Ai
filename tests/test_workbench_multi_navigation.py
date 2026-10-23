"""Return to actual existing multi-size instances without borrowing Main's size."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
from sync_workflow_fixture import SyncWorkflowFixture


class WorkbenchMultiNavigationTests(unittest.TestCase):
    def setUp(self):self.fx=SyncWorkflowFixture();self.addCleanup(self.fx.close)
    def test_actual_logo_cancel_returns_original100_candidate_and_preserves_missing_logo_block(self):
        from template_ai.logo_library_dialog import LogoLibraryDialog
        f=self.fx;f.select('C100');before=f.candidate('C100').template.to_dict()
        seen=[]
        def cancel():
            dialog=next(d for d in f.w.findChildren(LogoLibraryDialog) if d.isVisible());seen.append(dialog.selected_size());QTest.keyClick(dialog,Qt.Key_Escape)
        QTimer.singleShot(0,cancel);f.w.logo_center(return_origin=f.d);self.assertEqual(seen,[[100,60]]);f.select('A90')
        self.assertTrue(f.w.navigation.return_to_work());self.assertEqual(f.d.entry()['key'],f.entry('C100')['key'])
        self.assertEqual(f.d.entry()['selected'],f.templates['C100'].id);self.assertEqual(f.candidate('C100').template.to_dict(),before);self.assertFalse(f.candidate('C100').formal_eligible)
        self.assertFalse(f.d.table.cellWidget(f.d.table.currentRow(),5).model().item(1).isEnabled())

    def test_multi_source_change_returns_explicit_stale_without_erasing_manual_instance(self):
        f=self.fx;f.select('A90');nav=f.w.navigation;nav.begin('人物資料',origin=f.d);nav.finish();before=copy.deepcopy(f.candidate('A90').template.to_dict());f.change_phone('+12025550999')
        self.assertFalse(nav.return_to_work());self.assertIn('需同步重驗',f.d.status.text());self.assertEqual(f.candidate('A90').template.to_dict(),before);self.assertFalse(f.d.is_current())

    def test_multi_same_named_company_binding_removal_invalidates_return_without_global_generation_change(self):
        f=self.fx;nav=f.w.navigation;nav.begin('Logo',origin=f.d);nav.finish();generation=f.w.generation;entity=f.w.active_input_graph.data['companies'][0]['id']
        f.w.library.db.execute('DELETE FROM logo_entity_bindings WHERE entity_id=?',(entity,));f.w.library.db.commit()
        self.assertEqual(f.w.generation,generation);self.assertFalse(nav.return_to_work());self.assertIn('資產版本已變更',f.d.status.text())

    def test_actual_source_button_supplies_multi_origin_and_unmodified_cancel_keeps_source(self):
        from PySide6.QtWidgets import QPushButton
        from template_ai.input_graph_dialog import InputGraphDialog
        f=self.fx;f.select('C100');before=copy.deepcopy(f.w.active_input_graph.data)
        def cancel():QTest.keyClick(next(d for d in f.w.findChildren(InputGraphDialog) if d.isVisible()),Qt.Key_Escape)
        QTimer.singleShot(0,cancel);QTest.mouseClick(next(b for b in f.d.findChildren(QPushButton) if b.text()=='修改共用來源人物資料'),Qt.LeftButton)
        self.assertEqual(f.w.navigation.locations[-1]['kind'],'MULTI_SIZE');self.assertTrue(f.w.navigation.return_to_work());self.assertEqual(f.w.active_input_graph.data,before)

    def test_navigation_capture_reads_only_existing_metadata_without_rehashing_logo_corpus(self):
        f=self.fx
        with patch('template_ai.logo_assets.file_digest',side_effect=AssertionError('Navigation must not hash the Logo corpus')):
            f.w.navigation.begin('來源修正',origin=f.d);f.w.navigation.finish()
            self.assertTrue(f.w.navigation.return_to_work())
