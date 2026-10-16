import copy,json,threading,time
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from template_ai.gui import MainWindow
from template_ai.demo import demo_template
from template_ai.input_diagnostics import diagnose
from template_ai.layout import generate
from template_ai.layout_session import LayoutSessionDialog
from template_ai.logo_library_dialog import LogoLibraryDialog
from template_ai.candidate_edit import plan_candidate,apply_candidate,CandidateEditDialog
from template_ai.object_dialog import ObjectToolsDialog
from template_ai.batch_objects import batch_plan,apply_batch,BatchObjectDialog
from template_ai.diagnostic_routes import open_diagnostic
from template_ai.model import Slot,Rect
from training_fixture import source_work
from runtime_fixture import controlled_resources
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gui_convergence import reconcile
APP=QApplication.instance() or QApplication([])

def pump_until(fn,seconds=5):
    end=time.monotonic()+seconds
    while not fn() and time.monotonic()<end:APP.processEvents();QTest.qWait(10)
    if not fn():raise AssertionError('bounded GUI wait exceeded')

class SeventyUiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.w=MainWindow(self.root/'data');controlled_resources(self.w);self.addCleanup(self.close_window);self.t=demo_template();self.w.library.publish(self.t);self.w.people.setRowCount(1)
        from PySide6.QtWidgets import QTableWidgetItem
        for j,v in enumerate(('Alex Example','Designer','+12025550100','alex@example.test','','','','')):self.w.people.setItem(0,j,QTableWidgetItem(v))

    def close_window(self):
        self.w.input_timer.stop();self.w.execution_queue.cancel_event.set();self.w.pool.waitForDone(5000);APP.processEvents()
        self.w.font_manager.close();self.w.library.close();self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    def test_input_width_is_measured_fixed_point_no_global_limit_and_exact_gui_location(self):
        people,companies,_=self.w.input_data();people[0]['name']=['X'*200];report=diagnose(people,companies,[self.t],90,54);self.assertFalse(report['global_unsolvable']);self.assertTrue(any(i['code']=='FIT_RISK' for i in report['issues']));self.assertIn('固定18pt',report['issues'][0]['reason'])
        self.w.people.item(0,0).setText('');self.w.refresh_input_problems();item=self.w.input_problems.item(0);self.w.locate_input_problem(item);self.assertEqual((self.w.people.currentRow(),self.w.people.currentColumn()),(0,0));self.assertIn('待版面驗證',self.w.input_state.text());self.assertFalse(self.w.export_button.isEnabled())
        self.w.people.item(0,7).setText('bad');self.w.refresh_input_problems();self.assertIn('整數',self.w.input_problems.item(0).text());self.assertFalse(self.w.export_button.isEnabled())
    def test_logo_tree_normal_size_isolation_and_reference_does_not_create_approval(self):
        a=self.w.library.add_logo('Example Company',90,54,{});b=self.w.library.add_logo('Example Company',100,60,{});d=LogoLibraryDialog(self.w);self.addCleanup(d.deleteLater);d.show();APP.processEvents();self.assertEqual(d.tree.topLevelItemCount(),2);self.assertEqual(len(d.rows),1);self.assertEqual({(r['width_mm'],r['height_mm']) for r in d.rows},{(90,54)})
        before=self.w.library.logos();d.reference.setChecked(True);self.assertEqual(len(d.rows),2);self.assertIn('未核准',d.table.item(1,3).text());self.assertEqual(self.w.library.logos(),before);d.reference.setChecked(False);self.assertEqual(len(d.rows),1);d.hide()
    def test_worker_actual_progress_complete_adoption_and_stale_input_refusal(self):
        d=LayoutSessionDialog(self.w);self.addCleanup(d.deleteLater);d.show();QTest.mouseClick(d.start_button,Qt.LeftButton);pump_until(lambda:not d.running);self.assertEqual(len(d.rows),1);self.assertIn('COMPLETED',d.status.text());self.assertFalse(self.w.busy)
        with patch('template_ai.layout_session.QMessageBox.question',return_value=QMessageBox.Yes):d.adopt()
        self.assertEqual(len(self.w.candidates),1);self.assertEqual(self.w.candidates[0].template.id,self.t.id);self.w.people.item(0,0).setText('Casey Example')
        d.adopt();self.assertIn('版本已改變',d.status.text());d.hide()
    def test_real_worker_boundary_pause_cancel_retains_partial_and_controls_recover(self):
        t2=demo_template();self.w.library.publish(t2);entered=threading.Event();release=threading.Event();real=generate
        def barrier(*args,**kwargs):entered.set();release.wait(3);return real(*args,**kwargs)
        d=LayoutSessionDialog(self.w);self.addCleanup(d.deleteLater)
        with patch('template_ai.layout_session.generate',side_effect=barrier):
            d.start();self.assertTrue(entered.wait(2));d.pause();self.assertTrue(d.pause_event.is_set());d.reject();self.assertTrue(d.running);release.set();pump_until(lambda:not d.running)
        self.assertEqual(len(d.rows),1);self.assertIn('CANCELLED',d.status.text());self.assertTrue(d.start_button.isEnabled());self.assertFalse(self.w.busy)
        d.start();pump_until(lambda:not d.running);self.assertEqual(len(d.rows),2);self.assertIn('COMPLETED',d.status.text())
    def test_worker_start_and_item_failure_recover_no_fabricated_candidate(self):
        d=LayoutSessionDialog(self.w);self.addCleanup(d.deleteLater)
        with patch.object(self.w.pool,'start',side_effect=RuntimeError('worker unavailable')):d.start()
        self.assertFalse(d.running);self.assertFalse(self.w.busy);self.assertIn('worker unavailable',d.status.text())
        with patch('template_ai.layout_session.generate',side_effect=ValueError('font failure')):d.start();pump_until(lambda:not d.running)
        self.assertEqual(d.rows[0]['state'],'FAILED');self.assertIsNone(d.rows[0]['candidate']);self.assertTrue(d.start_button.isEnabled())
    def test_candidate_exact_local_geometry_isolation_fixed_font_template_readonly_stale(self):
        self.w.generate();self.assertEqual(len(self.w.candidates),1);other=copy.deepcopy(self.w.candidates[0]);self.w.candidates.append(other);before=copy.deepcopy(other);dbbefore=self.w.library.templates()[0].to_dict();slot=self.w.candidates[0].template.slots[0];plan=plan_candidate(self.w,0,[slot.id],1,0);self.assertEqual(plan['unaffected_candidates'],1)
        result=apply_candidate(self.w,plan,True);self.assertEqual(result.template.slots[0].rect.x,slot.rect.x+1);self.assertEqual(result.template.slots[0].size_pt,slot.size_pt);self.assertEqual(self.w.candidates[1],before);self.assertEqual(self.w.library.templates()[0].to_dict(),dbbefore)
        with self.assertRaises(ValueError):apply_candidate(self.w,plan,True)
        self.w.invalidate()
        with self.assertRaises(ValueError):plan_candidate(self.w,0,[slot.id],1,0)
    def test_actual_candidate_dialog_preview_cancel_then_apply(self):
        self.w.generate();d=CandidateEditDialog(self.w);self.addCleanup(d.deleteLater);d.objects.item(0).setSelected(True);d.dx.setValue(1);d.preview();self.assertIsNotNone(d.plan);x=self.w.candidates[0].template.slots[0].rect.x
        with patch('template_ai.candidate_edit.QMessageBox.question',return_value=QMessageBox.No):d.apply()
        self.assertEqual(self.w.candidates[0].template.slots[0].rect.x,x)
        with patch('template_ai.candidate_edit.QMessageBox.question',return_value=QMessageBox.Yes):d.apply()
        self.assertEqual(self.w.candidates[0].template.slots[0].rect.x,x+1)
    def test_object_context_pinned_text_disabled_on_logo_and_empty_selection_clears_values(self):
        source,work=source_work(self.w.library,self.root);payload=copy.deepcopy(work['payload']);logo=Slot('logo','c1',Rect(65,2,15,8));payload['slots'].append(__import__('dataclasses').asdict(logo));work=self.w.library.save_artwork(work['id'],payload,work['revision']);d=ObjectToolsDialog(self.w,'ARTWORK',work['id']);self.addCleanup(d.deleteLater);d.show();d.select_ids([payload['slots'][0]['id']]);d.pin_text.setChecked(True);self.assertTrue(d.editors['size_pt'].isEnabled());d.select_ids([logo.id]);self.assertFalse(d.editors['size_pt'].isEnabled());self.assertFalse(d.editors['size_pt'].isHidden());self.assertIn('Logo',d.context_status.text());d.select_ids([]);self.assertFalse(d.editors['size_pt'].isEnabled());self.assertEqual(d.editors['owner'].currentIndex(),-1);self.assertEqual(d.ids,[]);d.hide()
    def test_batch_partial_failure_idempotency_old_history_undo_and_protected_owner(self):
        source,work=source_work(self.w.library,self.root);source2,work2=source_work(self.w.library,self.root,'second.svg',note_text='different');targets=[{'id':work['id'],'slot_ids':[work['payload']['slots'][0]['id']]},{'id':work2['id'],'slot_ids':[work2['payload']['slots'][0]['id']]}];plan=batch_plan(self.w.library,targets,'center');changed=copy.deepcopy(work2['payload']);changed['visual_confirmed']=False;self.w.library.save_artwork(work2['id'],changed,work2['revision']);results=apply_batch(self.w.library,plan,True);self.assertEqual([r['state'] for r in results],['APPLIED_PENDING_FULL_VALIDATION','FAILED_OR_STALE']);rev=self.w.library.artwork(work['id'])['revision'];again=apply_batch(self.w.library,plan,True);self.assertEqual(again[0]['state'],'ALREADY_APPLIED');self.assertEqual(self.w.library.artwork(work['id'])['revision'],rev);self.w.library.object_history_action(results[0]['history_id'],'UNDO',True);self.assertEqual(self.w.library.artwork(work['id'])['payload']['slots'][0]['align'],'left');self.assertEqual(apply_batch(self.w.library,plan,True)[0]['state'],'FAILED_OR_STALE')
    def test_batch_actual_gui_exact_selection_diff_cancel_apply_and_no_repeat(self):
        source,work=source_work(self.w.library,self.root);d=BatchObjectDialog(self.w);self.addCleanup(d.deleteLater);d.table.item(0,0).setCheckState(Qt.Checked);d.preview();self.assertIsNotNone(d.plan);revision=work['revision']
        with patch('template_ai.batch_objects.QMessageBox.question',return_value=QMessageBox.No):d.apply()
        self.assertEqual(self.w.library.artwork(work['id'])['revision'],revision)
        with patch('template_ai.batch_objects.QMessageBox.question',return_value=QMessageBox.Yes):d.apply();d.apply()
        self.assertIn('ALREADY_APPLIED',d.details.toPlainText());self.assertEqual(self.w.library.artwork(work['id'])['revision'],revision+1)
    def test_diagnostic_reuse_same_data_no_report_no_gate_mutation_and_convergence_75(self):
        generation=self.w.generation;self.assertEqual(open_diagnostic(self.w,'input'),'OUTPUT_INPUT_PROBLEMS');self.assertEqual(self.w.generation,generation)
        with self.assertRaises(ValueError):open_diagnostic(self.w,'pdf-report')
        registry=json.loads((Path(__file__).resolve().parents[1]/'docs/dev/REQUIREMENTS.json').read_text());audit=reconcile(registry);self.assertEqual(len(audit['rows']),75);self.assertEqual(audit['product_features_added'],0);self.assertEqual(audit['open'],[]);self.assertTrue(all('docs/decisions/2026-10-15-DIAGNOSTIC-REPORT-ADOPTED.md' in r['sources'] for r in registry['requirements'] if r['id'] in ('UI-066-R1','UI-066-R2')));self.assertNotIn('AI',audit['formal_output_formats']);self.assertFalse(self.w.export_button.isEnabled())
