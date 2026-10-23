"""Actual reused right panel/worker/canvas and source-vs-encoded detail views."""
import copy,threading,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from sync_workflow_fixture import SyncWorkflowFixture,APP
from gui_wait import wait_for_gui
from template_ai.preflight_detail import SourcePictureItem


class DigitalPreflightGuiTests(unittest.TestCase):
    def setUp(self):
        self.f=SyncWorkflowFixture(compound_marks=True);self.addCleanup(self.f.close);self.w=self.f.w;self.w.candidates=[copy.deepcopy(self.f.candidate('A90'))];self.w.candidate_list.clear();self.w.candidate_list.addItem('Authored exact A90');self.w.candidate_list.setCurrentRow(0);self.w.tabs.setCurrentIndex(2);self.w.resize(1360,940);self.w.show();self.w.dpi.setValue(96);self.p=self.w.digital_preflight();self.addCleanup(self.cleanup)
    def cleanup(self):
        self.p.cancel_event.set();self.w.pool.waitForDone(5000);APP.processEvents()
        if self.p.detail:self.p.detail.close();self.p.detail.deleteLater()
        self.p.temporary.cleanup()
    def wait(self):self.assertTrue(wait_for_gui(lambda:not self.p.running and not self.w.busy,15),self.p.status.text())
    def inspect(self):self.p.inspect();self.wait();self.assertIsNotNone(self.p.proof,self.p.status.text())
    def test_initial_panel_is_same_existing_right_container_without_running_or_approval(self):
        self.assertIs(self.p.parentWidget(),self.w.property_panel.widget());self.assertEqual(self.p.table.rowCount(),0);self.assertIsNone(self.p.proof);self.assertFalse(self.w.busy);self.assertTrue(self.p.guides);self.assertTrue(all(not item.flags()&item.GraphicsItemFlag.ItemIsMovable for item in self.p.guides))
    def test_actual_original_worker_populates_named_checks_and_marked_format_readback(self):
        self.inspect();self.assertGreater(self.p.table.rowCount(),10);rows=[self.p.table.item(i,0).data(Qt.UserRole) for i in range(self.p.table.rowCount())];self.assertTrue(any(r['code']=='ENCODED_FORMAT' and r['status']=='PASS' for r in rows));self.assertFalse(self.p.proof['formal_output_allowed']);self.assertIn('尚非正式',self.p.status.text())
    def test_dpi_format_and_input_changes_clear_proof_without_mutating_geometry(self):
        self.inspect();before=self.w.candidates[0].template.to_dict();self.p.format.setCurrentText('PDF');self.assertIsNone(self.p.proof);self.assertEqual(self.p.table.rowCount(),0);self.assertEqual(self.w.candidates[0].template.to_dict(),before);self.inspect();self.w.dpi.setValue(150);self.assertIsNone(self.p.proof);self.w.invalidate();self.assertFalse(self.p.detail_button.isEnabled())
    def test_actual_logo_detail_keeps_vector_picture_and_encoded_pixels_with_original_pan_zoom(self):
        self.inspect();self.p.open_detail();self.wait();detail=self.p.detail;self.assertIsNotNone(detail,self.p.status.text());self.assertTrue(any(isinstance(item,SourcePictureItem) for item in detail.views[0].scene().items()));self.assertEqual(len(detail.views),2);before=self.w.candidates[0].template.to_dict();detail.views[0].set_zoom(200);detail.views[1].set_zoom(400);self.assertEqual(self.w.candidates[0].template.to_dict(),before);self.w.dpi.setValue(150);self.assertIn('歷史比較',detail.status.text())
    def test_late_format_result_is_not_adopted_as_current(self):
        from template_ai.digital_preflight_panel import build_proof
        started=threading.Event();release=threading.Event()
        def slow(*args):started.set();release.wait(8);return build_proof(*args)
        with patch('template_ai.digital_preflight_panel.build_proof',side_effect=slow):
            self.p.inspect();self.assertTrue(wait_for_gui(started.is_set,3));self.p.format.setCurrentText('PDF');release.set();self.wait()
        self.assertIsNone(self.p.proof);self.assertEqual(self.p.table.rowCount(),0);self.assertIn('舊比較未採用',self.p.status.text())
    def test_actual_cancel_never_claims_saved_comparison_or_formal_output(self):
        from template_ai.digital_preflight_panel import build_proof
        started=threading.Event();release=threading.Event()
        def slow(*args):started.set();release.wait(8);return build_proof(*args)
        with patch('template_ai.digital_preflight_panel.build_proof',side_effect=slow):
            self.p.inspect();self.assertTrue(wait_for_gui(started.is_set,3));self.p.cancel();release.set();self.wait()
        self.assertIsNone(self.p.proof);self.assertIn('取消',self.p.status.text());self.assertEqual(self.p.table.rowCount(),0)
    def test_overlay_toggles_and_mode_return_do_not_edit_or_revalidate_candidate(self):
        before=self.w.candidates[0].template.to_dict();self.p.overlay['trim'].setChecked(False);self.p.overlay['safe'].setChecked(False);self.assertEqual(len(self.p.guides),0);self.p.overlay['page'].setChecked(True);self.assertEqual(len(self.p.guides),1);self.w.tabs.setCurrentIndex(1);APP.processEvents();self.assertFalse(self.p.isVisible());self.w.tabs.setCurrentIndex(2);APP.processEvents();self.assertTrue(self.p.isVisible());self.assertEqual(self.w.candidates[0].template.to_dict(),before);self.assertIsNone(self.p.proof)

    def test_same_candidate_rerender_preserves_current_proof_but_new_geometry_invalidates_it(self):
        self.inspect();proof=self.p.proof;self.w.choose_candidate(0);self.assertIs(self.p.proof,proof);self.assertTrue(self.p.guides);self.w.candidates[0].template.slots[0].rect.x+=.1;self.w.choose_candidate(0);self.assertIsNone(self.p.proof);self.assertEqual(self.p.table.rowCount(),0)
    def test_cancelled_actual_detail_work_does_not_open_a_view(self):
        from template_ai.digital_preflight_panel import region_images
        self.inspect();started=threading.Event();release=threading.Event()
        def slow(*args):started.set();release.wait(8);return region_images(*args)
        with patch('template_ai.digital_preflight_panel.region_images',side_effect=slow):
            self.p.open_detail();self.assertTrue(wait_for_gui(started.is_set,3));self.p.cancel();release.set();self.wait()
        self.assertIsNone(self.p.detail);self.assertIn('取消',self.p.status.text())
    def test_problem_row_routes_exact_slot_to_existing_canvas_without_moving_it(self):
        from template_ai.gui import Box
        c=self.w.candidates[0];c.template.slots[0].rect.x=-1;self.w.choose_candidate(0);self.inspect();row=next(i for i in range(self.p.table.rowCount()) if self.p.table.item(i,0).data(Qt.UserRole)['code']=='TRIM_BOUNDS');self.p.table.selectRow(row);before=c.template.to_dict();self.p.locate();self.assertTrue(any(isinstance(item,Box) and item.slot.id==c.items[0].slot.id for item in self.w.output_canvas.scene().items()));self.assertEqual(c.template.to_dict(),before);self.assertTrue(self.p.guides)

    def test_text_detail_keeps_verified_font_drawing_and_selected_scope_without_layout_edits(self):
        self.inspect();before=self.w.candidates[0].template.to_dict();self.p.objects.setCurrentIndex(next(i for i in range(self.p.objects.count()) if 'name' in self.p.objects.itemText(i)));self.p.open_detail();self.wait();detail=self.p.detail
        self.assertTrue(any(isinstance(item,SourcePictureItem) for item in detail.views[0].scene().items()));self.assertEqual(self.w.candidates[0].template.to_dict(),before);self.assertFalse(self.p.proof['output_written']);self.assertTrue(detail.views[0].readonly)

if __name__=='__main__':unittest.main()
