"""Actual original-worker multi-size editing, source-version and retention guards."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QCoreApplication,QEvent
import test_multi_size as fixture
from template_ai.gui import MainWindow
from template_ai.multi_size_dialog import MultiSizeDialog
from template_ai.multi_size_edit import SizeEditAdapter,SizeEditController
from template_ai.candidate_edit import plan_candidate
from gui_wait import wait_for_gui
from runtime_fixture import controlled_resources
APP=fixture.APP


class MultiSizeEditGuiTests(unittest.TestCase):
    def setUp(self):
        fixture.MultiSizeTests.setUp(self);self.w=MainWindow(self.library.root);controlled_resources(self.w);self.w.adopt_input_graph(self.graph.data);self.d=MultiSizeDialog(self.w);self.d.show()
        for row in range(self.d.table.rowCount()):self.d.table.item(row,0).setCheckState(Qt.Checked)
        self.d.start();self.wait();self.assertIsNotNone(self.d.service)
    def tearDown(self):
        self.d.stop.set();self.w.input_timer.stop();self.w.execution_queue.cancel_event.set();self.w.pool.waitForDone(5000);APP.processEvents();self.d.deleteLater();self.w.font_manager.close();self.w.library.close();self.w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);fixture.MultiSizeTests.tearDown(self)
    def wait(self):self.assertTrue(wait_for_gui(lambda:not self.d.running and not self.w.busy,10),'Owned matrix worker did not complete')
    def change_source(self,value='Alex Updated'):
        graph=self.w.active_input_graph.clone();field=next(f for f in graph.data['fields'] if f['kind']=='name' and f['owner_id']==graph.data['people'][0]['id']);graph.apply(graph.preview('edit_field',field_id=field['id'],value=value),True);self.w.adopt_input_graph(graph.data,history=graph)
    def test_failed_source_recalculation_never_makes_old_service_current(self):
        previous=self.d.service;self.change_source();self.assertFalse(self.d.is_current())
        with patch('template_ai.multi_size_dialog.MultiSizeWorkflow.calculate_preserving',side_effect=ValueError('Synthetic owned calculation failure')):self.d.sync_source();self.wait()
        self.assertIs(self.d.service,previous);self.assertFalse(self.d.is_current());self.assertFalse(self.d.export_button.isEnabled())
    def test_source_sync_preserves_previously_unchecked_manual_size(self):
        entry=next(e for e in self.d.service.entries if e['size_mm']==[100,60]);adapter=SizeEditAdapter(self.d,entry,0);controller=SizeEditController(adapter);identity=adapter.candidates[0].template.slots[0].id;controller.submit(plan_candidate(adapter,0,[identity],1,0));self.wait();manual=copy.deepcopy(adapter.candidates[0].template.to_dict());self.assertIn('manual_edit_receipt',adapter.candidates[0].risk_context)
        row=next(i for i,s in enumerate(self.d.sizes) if s==[100,60]);self.d.table.item(row,0).setCheckState(Qt.Unchecked);self.change_source();self.d.sync_source();self.wait();self.assertEqual(len(self.d.service.entries),2);updated=next(e for e in self.d.service.entries if e['size_mm']==[100,60]);current=self.d.service.selected(updated);self.assertEqual(current.template.to_dict(),manual);self.assertIn('Alex Updated',[item.text for item in current.items]);self.assertFalse(current.formal_eligible)

    def local(self):
        from template_ai.candidate_edit import CandidateEditDialog
        entry=next(e for e in self.d.service.entries if e['size_mm']==[90,54]);adapter=SizeEditAdapter(self.d,entry,0);controller=SizeEditController(adapter);dialog=CandidateEditDialog(adapter,controller=controller);dialog.show();dialog.objects.item(0).setSelected(True);return entry,adapter,controller,dialog
    def test_actual_reused_dialog_move_and_undo_use_same_pool_and_no_dispatch_queue(self):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtTest import QTest
        entry,adapter,controller,dialog=self.local();before=copy.deepcopy(adapter.candidates[0].template.to_dict());pool=self.w.pool;dialog.dx.setValue(1);QTest.mouseClick(dialog.preview_button,Qt.LeftButton)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(dialog.apply_button,Qt.LeftButton)
        self.assertFalse(adapter.candidates[0].formal_eligible);self.wait();self.assertTrue(adapter.candidates[0].formal_eligible);self.assertIs(self.w.pool,pool);self.assertEqual(pool.maxThreadCount(),1);self.assertFalse(hasattr(adapter,'candidate_edit_dispatcher'));QTest.mouseClick(dialog.undo_button,Qt.LeftButton)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(dialog.apply_button,Qt.LeftButton)
        self.wait();self.assertEqual(adapter.candidates[0].template.to_dict(),before);self.assertEqual(adapter.candidates[0].risk_context['manual_revision'],2)
    def blocked(self):
        import threading
        from template_ai.multi_size_edit import calculate_edit
        started=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def work(envelope,library):
            started.set()
            if not release.wait(5):raise AssertionError('Owned local edit worker not released')
            return calculate_edit(envelope,library)
        return started,release,patch('template_ai.multi_size_edit.calculate_edit',side_effect=work)
    def test_source_change_during_local_worker_keeps_manual_pending_until_current_sync(self):
        entry,adapter,controller,dialog=self.local();started,release,guard=self.blocked();identity=adapter.candidates[0].template.slots[0].id
        with guard:
            controller.submit(plan_candidate(adapter,0,[identity],1,0));self.assertTrue(wait_for_gui(started.is_set,2));manual=copy.deepcopy(adapter.candidates[0].template.to_dict());self.change_source();release.set();self.wait()
        self.assertFalse(adapter.candidates[0].formal_eligible);self.assertEqual(adapter.candidates[0].template.to_dict(),manual);self.assertFalse(self.d.is_current());self.d.sync_source();self.wait();fresh=self.d.service.selected(next(e for e in self.d.service.entries if e['key']==entry['key']));self.assertEqual(fresh.template.to_dict(),manual);self.assertIn('Alex Updated',[item.text for item in fresh.items]);self.assertTrue(fresh.formal_eligible)
    def test_actual_local_comparison_does_not_apply_until_explicit_current_gate_adoption(self):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtTest import QTest
        entry,adapter,controller,dialog=self.local();original=copy.deepcopy(adapter.candidates[0]);dialog.dx.setValue(1);dialog.preview();QTest.mouseClick(dialog.compare_button,Qt.LeftButton);self.wait();self.assertEqual(adapter.candidates[0],original);self.assertFalse(dialog.compared[1].formal_eligible);self.assertTrue(dialog.adopt_button.isEnabled())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(dialog.adopt_button,Qt.LeftButton)
        self.assertTrue(adapter.candidates[0].formal_eligible);self.assertEqual(adapter.candidates[0].template.slots[0].rect.x,original.template.slots[0].rect.x+1)
    def test_cancel_resource_wait_starts_no_calculation_and_keeps_manual_unknown(self):
        from types import SimpleNamespace
        entry,adapter,controller,dialog=self.local();identity=adapter.candidates[0].template.slots[0].id
        with patch.object(self.w.runtime,'admit',return_value=SimpleNamespace(allowed=False,reasons=['SYNTHETIC_HIGH_LOAD'])),patch('template_ai.multi_size_edit.calculate_edit') as calculation:
            controller.submit(plan_candidate(adapter,0,[identity],1,0));self.assertTrue(wait_for_gui(lambda:bool(self.w._waiting_launches),2));controller.cancel(0);self.wait();self.assertFalse(calculation.called)
        self.assertFalse(adapter.candidates[0].formal_eligible);self.assertEqual(adapter.candidates[0].risk_context['edit_state'],'PENDING_MANUAL_RECHECK')
    def test_destroyed_local_dialog_does_not_receive_worker_callback(self):
        entry,adapter,controller,dialog=self.local();started,release,guard=self.blocked();identity=adapter.candidates[0].template.slots[0].id
        with guard:
            controller.submit(plan_candidate(adapter,0,[identity],1,0));self.assertTrue(wait_for_gui(started.is_set,2));dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);release.set();self.wait()
        self.assertTrue(entry['candidates'][0].formal_eligible)
