"""Actual explicit source alignment, multi-target confirmation and late source guards."""
import copy,unittest,threading
from unittest.mock import patch
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QMessageBox
from PySide6.QtTest import QTest
import test_candidate_sync_batch as fixture
from template_ai.gui import MainWindow
from template_ai.multi_size_dialog import MultiSizeDialog
from template_ai.multi_size_edit import SizeEditAdapter,SizeEditController
from template_ai.candidate_edit import CandidateEditDialog,plan_candidate
from template_ai.candidate_sync_dialog import CrossPropertyDialog
from gui_wait import wait_for_gui
from runtime_fixture import controlled_resources
APP=fixture.fixture.APP


class CandidateSyncGuiTests(unittest.TestCase):
    adapter=fixture.CandidateSyncBatchTests.adapter
    def setUp(self):
        fixture.CandidateSyncBatchTests.setUp(self);self.w=MainWindow(self.library.root);controlled_resources(self.w);self.w.adopt_input_graph(self.graph.data);self.d=MultiSizeDialog(self.w);self.d.show()
        for row in range(self.d.table.rowCount()):self.d.table.item(row,0).setCheckState(Qt.Checked)
        self.d.start();self.wait();entry=next(e for e in self.d.service.entries if e['size_mm']==[90,54]);row=next(i for i,s in enumerate(self.d.sizes) if s==[90,54]);self.d.table.setCurrentCell(row,1);self.d.select_candidate(entry['key'],self.templates[0].id);index=next(i for i,c in enumerate(entry['candidates']) if c.template.id==self.templates[0].id);self.source_adapter=SizeEditAdapter(self.d,entry,index);controller=SizeEditController(self.source_adapter);editor=CandidateEditDialog(self.source_adapter,controller=controller);editor.show();editor.objects.item(0).setSelected(True);editor.operation.setCurrentIndex(4);editor.align.setCurrentText('center');QTest.mouseClick(editor.preview_button,Qt.LeftButton)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(editor.apply_button,Qt.LeftButton)
        self.wait();self.assertEqual(self.source_adapter.candidates[index].template.slots[0].align,'center');self.assertTrue(self.source_adapter.candidates[index].formal_eligible);editor.hide();self.cross=CrossPropertyDialog(self.d);self.cross.show()
        for row in range(self.cross.table.rowCount()):self.cross.table.item(row,0).setCheckState(Qt.Checked)
    def tearDown(self):
        self.d.stop.set();self.w.input_timer.stop();self.w.execution_queue.cancel_event.set();self.w.pool.waitForDone(5000);APP.processEvents();self.d.deleteLater();self.w.font_manager.close();self.w.library.close();self.w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);fixture.CandidateSyncBatchTests.tearDown(self)
    def wait(self):self.assertTrue(wait_for_gui(lambda:not self.d.running and not self.w.busy,10))
    def target_templates(self):return [copy.deepcopy(entry['candidates'][index].template.to_dict()) for key,entry,index in self.cross.targets]
    def test_actual_confirmation_applies_safe90_only_and_failed100_keeps_original(self):
        before=self.target_templates();QTest.mouseClick(self.cross.preview_button,Qt.LeftButton);self.assertIsNotNone(self.cross.plan);self.assertIn('禁止正式輸出',self.cross.details.toPlainText())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.cross.apply_button,Qt.LeftButton)
        self.wait();self.assertEqual([r['state'] for r in self.cross.results],['APPLIED_VERIFIED','VALIDATION_FAILED']);after=self.target_templates();self.assertEqual(after[0]['slots'][0]['align'],'center');self.assertEqual(after[0]['slots'][0]['rect'],before[0]['slots'][0]['rect']);self.assertEqual(after[1],before[1]);self.assertEqual(self.cross.adapters,{})
    def test_controls_changed_after_preview_do_not_start_or_mutate_any_target(self):
        self.cross.preview();before=self.target_templates();self.cross.attributes['color'].setChecked(True);QTest.mouseClick(self.cross.apply_button,Qt.LeftButton);self.assertFalse(self.d.running);self.assertFalse(self.w.busy);self.assertEqual(self.target_templates(),before);self.assertIn('重新預覽',self.cross.status.text())
    def test_cancel_resource_wait_cross_keeps_all_old_targets(self):
        from types import SimpleNamespace
        self.cross.preview();before=self.target_templates()
        with patch.object(self.w.runtime,'admit',return_value=SimpleNamespace(allowed=False,reasons=['SYNTHETIC_HIGH_LOAD'])),patch('template_ai.candidate_sync_dialog.calculate_cross_batch') as work:
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.cross.apply_button,Qt.LeftButton)
            self.assertTrue(wait_for_gui(lambda:bool(self.w._waiting_launches),2));QTest.mouseClick(self.cross.cancel_button,Qt.LeftButton);self.wait();self.assertFalse(work.called)
        self.assertEqual(self.target_templates(),before);self.assertEqual(self.cross.adapters,{})
    def test_source_registry_changes_during_actual_worker_reject_both_target_results(self):
        import json
        from template_ai.candidate_sync import calculate_cross_batch
        started=threading.Event();release=threading.Event();self.addCleanup(release.set);before=self.target_templates();self.cross.preview()
        def work(batch,library,cancel):
            started.set()
            if not release.wait(5):raise AssertionError('Owned cross worker not released')
            return calculate_cross_batch(batch,library,cancel)
        with patch('template_ai.candidate_sync_dialog.calculate_cross_batch',side_effect=work):
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.cross.apply_button,Qt.LeftButton)
            self.assertTrue(wait_for_gui(started.is_set,2));source=self.cross.source();payload=self.w.library.object_snapshot('TEMPLATE',source.template.id)['payload'];payload['name']+=' externally replaced';self.w.library.db.execute('UPDATE templates SET payload=? WHERE id=?',(json.dumps(payload),source.template.id));self.w.library.db.commit();release.set();self.wait()
        self.assertTrue(all(r['state']=='STALE_IGNORED' for r in self.cross.results));self.assertEqual(self.target_templates(),before)
