from copy import deepcopy
from pathlib import Path
import unittest
import os
from unittest.mock import patch

from PySide6.QtCore import Qt,QTimer,QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget,QDialog,QDialogButtonBox,QTableWidgetItem,QMessageBox

from template_ai.storage import Library
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.design_learning_dialog import DesignLearningDialog
from template_ai.design_session import DesignSessions
from template_ai.design_synthesis import input_facts
from template_ai.production_bridge import attach,current_graph,publish_preview,uses_learning,export_current
from gui_wait import wait_for_gui,dispose_main_window
from runtime_fixture import controlled_resources
import test_design_session as fixtures

APP=QApplication.instance() or QApplication([])


class InputLearningIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=fixtures.DesignSessionTests;cls.fixture.setUpClass();cls.root=cls.fixture.root;cls.model=cls.fixture.model
    @classmethod
    def tearDownClass(cls):cls.fixture.tearDownClass()
    def setUp(self):
        self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        self.parent=QWidget();self.parent.library=self.library;self.addCleanup(self.parent.deleteLater)
        self.sessions=DesignSessions(self.library)
        self.graph=InputGraph.from_legacy([dict(name='Alex Example',title='Designer',phone='+1 202 555 0100',email='alex@example.test')],[])
        self.row=self.sessions.create(self.graph,90,54,'Author',self.model['id'],dict(version='input-integration-test-1',approved=True,production=False))
        from template_ai.design_learning import CrossWorkLearning
        learning=CrossWorkLearning(self.library);active=learning.store.get('DESIGN_ACTIVE','local-layout')
        learning.activate(self.model['id'],active['revision'] if active else 0,'Author',dict(version='integration-fixture-1',basis='Authored local GUI integration tests',approved=True,production=False),True)
        self.dialog=DesignLearningDialog(self.parent);self.dialog.session_id=self.row['id'];self.dialog.tabs.setCurrentIndex(2)
        self.addCleanup(self.dialog.close);self.dialog.show();APP.processEvents()

    def modal_input(self,action,kind,value):
        observations=[];errors=[]
        def edit():
            try:
                modal=APP.activeModalWidget()
                self.assertIsInstance(modal,InputGraphDialog)
                field=next(f for f in modal.graph.data['fields'] if f['kind']==kind)
                editor=modal.field_editors[field['id']];editor.selectAll();QTest.keyClicks(editor,value)
                observations.append(field['id'])
                modal.refresh_warnings()
                self.capture(modal,'input-integration-real-data-entry.png')
                QTest.mouseClick(modal.adopt_button,Qt.LeftButton)
            except BaseException as error:
                errors.append(error)
                if APP.activeModalWidget():APP.activeModalWidget().reject()
        guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:APP.activeModalWidget().reject() if APP.activeModalWidget() else None);guard.start(5000)
        QTimer.singleShot(0,self.dialog,edit)
        try:action()
        finally:guard.stop()
        if errors:raise errors[0]
        self.assertTrue(observations,'Actual input dialog never opened')
        return observations[0]

    def capture(self,widget,name):
        folder=os.environ.get('TEMPLATE_AI_INPUT_CAPTURE_DIR')
        if folder:
            path=Path(folder);path.mkdir(parents=True,exist_ok=True);self.assertTrue(widget.grab().save(str(path/name)))

    def test_real_new_input_modal_keeps_data_and_does_not_require_main_candidates(self):
        learning=self.dialog.learning;active=learning.store.get('DESIGN_ACTIVE','local-layout')
        learning.activate(self.model['id'],active['revision'] if active else 0,'Author',dict(version='new-input-modal-1',basis='Authored GUI integration policy',approved=True,production=False),True)
        self.modal_input(self.dialog.new_session,'name','New Person')
        current=self.sessions.current(self.dialog.session_id)
        self.assertEqual(current['input_graph']['fields'][0]['value'],'New Person')
        self.assertNotEqual(current['id'],self.row['id'])

    def test_real_edit_modal_return_undo_redo_preserve_new_phone_and_exact_owner(self):
        d=self.dialog;d.solve();facts={f['kind']:f for f in input_facts(self.graph)}
        d.set_relation(facts['phone']['render_id'],'BELOW',facts['email']['render_id'])
        fid=self.modal_input(d.edit_data,'phone','+1 202 555 0199')
        current=self.sessions.current(d.session_id);self.assertEqual(current['result_state'],'STALE');self.assertIsNone(current['confirmation'])
        d.solve();d.undo_layout();d.redo_layout()
        current=self.sessions.current(d.session_id);field=next(f for f in current['input_graph']['fields'] if f['id']==fid)
        self.assertEqual(field['value'],'+1 202 555 0199');self.assertEqual(field['owner_id'],self.graph.data['people'][0]['id'])
        self.assertEqual(current['intents'][0]['relation'],'BELOW')
        reopened=DesignSessions(self.library).current(current['id']);self.assertEqual(reopened['intents'],current['intents'])

    def test_real_clipboard_over_limit_keeps_all_text_and_blocks_adoption_without_loss(self):
        modal=InputGraphDialog(self.dialog,self.graph.data);self.addCleanup(modal.close);self.addCleanup(modal.warning_timer.stop)
        fid=next(f['id'] for f in self.graph.data['fields'] if f['kind']=='phone');editor=modal.field_editors[fid]
        original=deepcopy(modal.graph.data);modal.show();editor.setFocus();editor.selectAll();APP.clipboard().setText('X'*2050);editor.paste()
        self.assertTrue(wait_for_gui(lambda:not modal.adopt_button.isEnabled(),2))
        self.assertEqual(editor.text(),'X'*2050);self.assertEqual(modal.graph.data,original)
        self.capture(modal,'input-integration-long-paste-retained.png')
        modal.accept();self.assertNotEqual(modal.result(),QDialog.Accepted);self.assertEqual(editor.text(),'X'*2050)
        editor.selectAll();QTest.keyClicks(editor,'+1 202 555 0199')
        self.assertTrue(wait_for_gui(lambda:modal.adopt_button.isEnabled(),2));QTest.mouseClick(modal.adopt_button,Qt.LeftButton)
        self.assertEqual(modal.graph.field(fid)['value'],'+1 202 555 0199')

    def test_actual_pointer_drag_creates_relation_and_preserves_unaffected_structure(self):
        d=self.dialog;d.solve();APP.processEvents();facts={f['kind']:f for f in input_facts(self.graph)}
        boxes={box.identity:box for box in d.canvas.boxes};phone=boxes[facts['phone']['render_id']];email=boxes[facts['email']['render_id']]
        start=d.canvas.mapFromScene(phone.sceneBoundingRect().center())
        destination=d.canvas.mapFromScene(email.sceneBoundingRect().center()+QPointF(0,email.sceneBoundingRect().height()*.7))
        viewport=d.canvas.viewport();QTest.mousePress(viewport,Qt.LeftButton,Qt.NoModifier,start)
        movement=QMouseEvent(QEvent.MouseMove,QPointF(destination),QPointF(viewport.mapToGlobal(destination)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
        QApplication.sendEvent(viewport,movement);QTest.mouseRelease(viewport,Qt.LeftButton,Qt.NoModifier,destination)
        self.assertTrue(wait_for_gui(lambda:bool(self.sessions.current(d.session_id)['intents']) and d.solve_worker is not None and not d.solve_worker.isRunning(),15))
        row,result,candidate=d.sessions.checked_result(d.session_id)
        self.assertEqual(row['intents'][0],dict(subject=facts['phone']['render_id'],relation='BELOW',object=facts['email']['render_id']))
        from template_ai.design_evaluation import check_layout
        self.assertEqual(check_layout(candidate,InputGraph(row['input_graph']),row['intents'])['status'],'PASS')
        positions={item.slot.kind:item.slot.rect for item in candidate.items}
        self.assertLess(positions['name'].y,positions['title'].y)
        self.capture(d,'input-integration-dragged-preview.png')

    def test_background_cancel_retains_new_data_and_cannot_install_old_confirmation(self):
        d=self.dialog;d.solve();d.confirm_preview();row=self.sessions.current(d.session_id)
        graph=InputGraph(row['input_graph']);phone=next(f for f in graph.data['fields'] if f['kind']=='phone');phone['value']='+1 202 555 0199'
        self.sessions.replace_input(row['id'],row['revision'],'cancel-new-phone',graph)
        d.solve_async();d.cancel_solve()
        self.assertTrue(wait_for_gui(lambda:not d.solve_worker.isRunning(),15));APP.processEvents()
        current=self.sessions.current(d.session_id);self.assertIsNone(current['confirmation'])
        self.assertEqual(next(f for f in current['input_graph']['fields'] if f['kind']=='phone')['value'],'+1 202 555 0199')
        self.assertEqual(current['result_state'],'STALE');self.assertFalse(d.confirm_button.isEnabled())

    def test_existing_confirmed_artifact_auto_discovered_and_choice_invalidates_confirmation(self):
        d=self.dialog;d.solve();d.confirm_preview();target=self.root/('PREVIEW-input-reprint-'+self.row['id']+'.png')
        artifact=self.sessions.export(self.row['id'],target,preview=True)
        d.refresh_draft();self.assertEqual(d.artifacts.currentData(),artifact['id'])
        row=self.sessions.current(d.session_id);d.sessions.select_candidate(row['id'],row['revision'],0)
        self.assertIsNone(self.sessions.current(d.session_id)['confirmation'])
        self.assertEqual(self.sessions.find_accepted(self.graph,90,54,production=False)['sha256'],artifact['sha256'])
        _,result,_=self.sessions.checked_result(d.session_id)
        self.assertNotIn('serialized',result['choices'][0])
        reference=result['choices'][0]['serialized_ref']
        stored=self.sessions.store.get('DESIGN_CHOICE',reference)
        self.assertEqual(stored['serialized']['items'],result['selected']['serialized']['items'])
        with self.sessions.store.transaction():
            payload=dict(stored);payload['serialized']=dict(stored['serialized'],items=[])
            self.sessions.store._write('DESIGN_CHOICE',reference,payload,stored['revision'],'test_candidate_corruption')
        before=self.sessions.current(d.session_id)
        with self.assertRaisesRegex(ValueError,'missing or changed'):
            self.sessions.select_candidate(d.session_id,before['revision'],0)
        self.assertEqual(self.sessions.current(d.session_id),before)

    def test_new_model_activation_keeps_exact_accepted_session_for_reorder(self):
        d=self.dialog;d.solve();d.confirm_preview()
        artifact=self.sessions.export(d.session_id,self.root/('PREVIEW-repeat-'+d.session_id+'.png'),preview=True)
        newer=d.learning.train(self.model['dataset_id'],'Author',approved=True)
        active=d.learning.store.get('DESIGN_ACTIVE','local-layout')
        d.learning.activate(newer['id'],active['revision'],'Author',dict(version='newer-policy-1',basis='Authored newer model test',approved=True,production=False),True)
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w));w.adopt_input_graph(self.graph.data)
        reopened=DesignLearningDialog(w);self.addCleanup(reopened.close);row=attach(reopened)
        self.assertEqual(row['id'],d.session_id);self.assertEqual(row['model_id'],self.model['id'])
        self.assertEqual(reopened.matching_accepted_id,artifact['id'])
        self.assertEqual(reopened.sessions.replay_artifact(artifact['id'])['sha256'],artifact['sha256'])

    def test_resume_other_saved_draft_updates_main_input_size_and_export_reference(self):
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w));w.adopt_input_graph(self.graph.data)
        d=DesignLearningDialog(w);self.addCleanup(d.close);attach(d)
        graph=InputGraph.from_legacy([dict(name='Second Person',title='Designer',phone='+1 202 555 0199',email='second@example.test')],[])
        other=self.sessions.create(graph,120,80,'Author',self.model['id'],dict(version='resume-size-test-1',approved=True,production=False))
        d.refresh();d.session_choices.setCurrentIndex(d.session_choices.findData(other['id']));d.resume_session()
        self.assertEqual(w.production_session_id,other['id']);self.assertEqual(w.active_input_graph.data,graph.data)
        self.assertEqual((w.out_w.value(),w.out_h.value()),(120,80));self.assertEqual(d.session_choices.currentData(),other['id'])
        self.assertIsNone(w.reorder_customer_snapshot)

    def test_shared_learning_preview_preserves_original_pdf_png_jpg_formats(self):
        self.dialog.solve();self.dialog.confirm_preview()
        for suffix in ('png','pdf','jpg'):
            target=self.root/('PREVIEW-formats-'+self.row['id']+'.'+suffix)
            artifact=self.sessions.export(self.row['id'],target,preview=True)
            self.assertGreater(target.stat().st_size,100);self.assertEqual(self.sessions.replay_artifact(artifact['id'])['sha256'],artifact['sha256'])

    def test_legacy_edit_progress_and_stale_preview_buttons_use_same_learning_draft(self):
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w));w.adopt_input_graph(self.graph.data)
        d=DesignLearningDialog(w);self.addCleanup(d.close);row=attach(d);d.solve()
        from template_ai.source_change_impact import consumers
        self.assertTrue(any(scope=='目前學習稿件' for scope,_ in consumers(w)))
        with patch.object(w,'shared_design_learning') as open_draft:
            w.candidate_editor();w.layout_session();w.invalidate();w.export_current(True)
        self.assertEqual(open_draft.call_count,3)
        self.assertTrue(all(call.kwargs.get('use_current_input') is True for call in open_draft.call_args_list))
        self.assertEqual(w.production_session_id,row['id']);self.assertEqual(w.active_input_graph.data,self.graph.data)

    def test_real_learned_input_logo_library_keeps_size_and_uses_main_background_services(self):
        from template_ai.gui import MainWindow
        from template_ai.logo_library_dialog import LogoLibraryDialog
        from template_ai.logo_choice_dialog import LogoChoiceDialog
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w))
        d=DesignLearningDialog(w);self.addCleanup(d.close);d.session_id=None;d.out_w.setValue(120);d.out_h.setValue(80)
        graph=InputGraph(self.graph.data);pid=graph.data['people'][0]['id']
        graph.apply(graph.make_plan('add_company',person_id=pid,name='Authored Company'),approved=True)
        cid=graph.data['companies'][0]['id'];entry=InputGraphDialog(d,graph.data);self.addCleanup(entry.close);self.addCleanup(entry.warning_timer.stop)
        seen=[];errors=[]
        def inspect_library():
            modal=APP.activeModalWidget()
            try:
                self.assertIsInstance(modal,LogoLibraryDialog);self.assertIs(modal.window,w);self.assertIs(modal.size_owner,d)
                self.assertEqual(modal.selected_size(),[120.,80.]);self.assertEqual((modal.target_w.value(),modal.target_h.value()),(120,80))
                modal.background('核對自製測試圖片庫',lambda store:dict(companies=len(store.companies())))
                self.assertTrue(wait_for_gui(lambda:not modal.running and not w.busy,10))
                self.assertNotIn('未完成',modal.status.text());seen.append(True)
                self.capture(modal,'input-integration-logo-library.png')
            except BaseException as error:errors.append(error)
            finally:
                if modal:modal.reject()
        for action in (lambda:entry.open_logo_library(cid,False),lambda:LogoChoiceDialog(d,graph,cid,entry).library()):
            guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:APP.activeModalWidget().reject() if APP.activeModalWidget() else None);guard.start(15000)
            QTimer.singleShot(0,d,inspect_library)
            try:action()
            finally:guard.stop()
        if errors:raise errors[0]
        self.assertEqual(len(seen),2);self.assertEqual(entry.graph.data,graph.data)

    def test_resize_keeps_position_intent_but_new_person_roots_start_independent_draft(self):
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w));w.adopt_input_graph(self.graph.data)
        d=DesignLearningDialog(w);self.addCleanup(d.close);row=attach(d);d.solve()
        facts={f['kind']:f for f in input_facts(self.graph)};d.set_relation(facts['phone']['render_id'],'BELOW',facts['email']['render_id'])
        before=d.sessions.current(d.session_id);w.out_w.setValue(95);resized=attach(d)
        self.assertEqual(resized['id'],before['id']);self.assertEqual(resized['width_mm'],95)
        self.assertEqual(resized['intents'],before['intents']);self.assertIsNone(resized['confirmation']);self.assertEqual(resized['result_state'],'STALE')
        new_graph=InputGraph.from_legacy([dict(name='Alex Example',title='Designer',phone='+1 202 555 0100',email='alex@example.test')],[])
        w.adopt_input_graph(new_graph.data);new=attach(d)
        self.assertNotEqual(new['id'],before['id']);self.assertEqual(new['intents'],[]);self.assertEqual(new['input_graph'],new_graph.data)
        self.assertEqual(d.sessions.current(before['id'])['intents'],before['intents'])

    def test_real_clear_and_demo_actions_remove_previous_production_and_customer_context(self):
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w));w.adopt_input_graph(self.graph.data)
        d=DesignLearningDialog(w);self.addCleanup(d.close);row=attach(d)
        def confirm(action):
            seen=[]
            def click_yes():
                box=APP.activeModalWidget()
                if isinstance(box,QMessageBox):seen.append(True);QTest.mouseClick(box.button(QMessageBox.Yes),Qt.LeftButton)
            guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:APP.activeModalWidget().reject() if APP.activeModalWidget() else None);guard.start(3000)
            QTimer.singleShot(0,w,click_yes)
            try:action()
            finally:guard.stop()
            self.assertTrue(seen)
        confirm(w.clear_input_graph)
        self.assertIsNone(w.production_session_id);self.assertIsNone(w.active_input_graph);self.assertIsNone(w.reorder_customer_snapshot)
        self.assertEqual(self.sessions.current(row['id'])['input_graph'],self.graph.data)
        w.adopt_input_graph(self.graph.data);attach(d);w.reorder_customer_snapshot=dict(id='authored-demo-context',code='0001',revision=1)
        confirm(w.demo_input)
        self.assertIsNone(w.production_session_id);self.assertIsNone(w.reorder_customer_snapshot);self.assertIsNone(w.reorder_template_id)
        self.assertNotEqual(w.active_input_graph.data['people'],self.graph.data['people'])

    def test_explicit_fixed_preview_remains_edit_export_target_after_model_activation(self):
        from template_ai.gui import MainWindow
        from template_ai.demo import demo_template
        from template_ai.layout import generate
        from authored_font_fixture import bind_authored_fonts
        from template_ai.production_bridge import routes_to_learning
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w));w.adopt_input_graph(self.graph.data)
        w.tabs.setCurrentIndex(2)
        d=DesignLearningDialog(w);self.addCleanup(d.close);attach(d);d.solve()
        facts={f['kind']:f for f in input_facts(self.graph)};d.set_relation(facts['phone']['render_id'],'BELOW',facts['email']['render_id'])
        saved_intents=d.sessions.current(d.session_id)['intents'];self.assertFalse(w.property_panel.isEnabled())
        template=bind_authored_fonts(demo_template(),w.font_manager);w.library.publish(template)
        candidate=generate(template,*w.input_data(),w.generation);w.candidates=[candidate]
        w.candidate_list.addItem('已保存的原款式');w.candidate_list.setCurrentRow(0);w.choose_candidate(0)
        saved_session=w.production_session_id;self.assertEqual(w.production_view,'FIXED');self.assertFalse(routes_to_learning(w))
        self.assertTrue(w.property_panel.isEnabled())
        target=self.root/('PREVIEW-explicit-fixed-'+self.row['id']+'.png')
        with patch.object(w,'shared_design_learning') as learning,patch('template_ai.gui.QFileDialog.getSaveFileName',return_value=(str(target),'PNG')):
            w.export_current(True)
        learning.assert_not_called();self.assertTrue(target.is_file())
        restored=attach(d);self.assertEqual(restored['id'],saved_session);self.assertEqual(w.production_view,'LEARNED')
        self.assertEqual(restored['intents'],saved_intents)

    def test_main_legacy_table_enters_real_learned_preview_and_exports_exact_confirmed_data(self):
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);self.addCleanup(lambda:dispose_main_window(w));controlled_resources(w)
        w.tabs.setCurrentIndex(2);w.show();APP.processEvents()
        for col,value in enumerate(['Alex Example','Designer','+1 202 555 0100','alex@example.test']):w.people.setItem(0,col,QTableWidgetItem(value))
        w.companies.setRowCount(0)
        learning=self.dialog.learning;active=learning.store.get('DESIGN_ACTIVE','local-layout')
        learning.activate(self.model['id'],active['revision'] if active else 0,'Author',dict(version='legacy-main-learning-1',basis='Authored legacy GUI integration policy',approved=True,production=False),True)
        name=w.people.item(0,0);saved_name=name.text();name.setText('');w.refresh_input_problems()
        self.assertGreater(w.input_problems.count(),0);self.assertIn('請先處理',w.input_state.text())
        name.setText(saved_name);w.refresh_input_problems()
        observations=[];errors=[];timer=QTimer();timer.setInterval(20)
        def inspect():
            try:
                modal=APP.activeModalWidget()
                if not isinstance(modal,DesignLearningDialog):return
                if not observations:observations.append(modal.session_id)
                row=modal.sessions.current(modal.session_id)
                if row['result_state']!='CURRENT' or modal.solve_worker and modal.solve_worker.isRunning():return
                self.capture(modal,'input-integration-legacy-to-learned-preview.png')
                modal.confirm_preview();modal.close();timer.stop()
            except BaseException as error:
                errors.append(error);timer.stop()
                if APP.activeModalWidget():APP.activeModalWidget().close()
        timer.timeout.connect(inspect);timer.start();guard=QTimer();guard.setSingleShot(True);guard.timeout.connect(lambda:APP.activeModalWidget().close() if APP.activeModalWidget() else None);guard.start(20000)
        try:w.generate()
        finally:timer.stop();guard.stop()
        if errors:raise errors[0]
        self.assertTrue(observations);self.assertEqual(w.production_session_id,observations[0]);self.assertTrue(w.preview_button.isEnabled())
        current=DesignSessions(w.library).current(w.production_session_id)
        self.assertEqual(current['input_graph'],w.active_input_graph.data);self.assertEqual(current['result_state'],'CURRENT')
        target=self.root/('PREVIEW-main-input-'+current['id']+'.png')
        with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName',return_value=(str(target),'PNG')):artifact=export_current(w,True)
        self.assertTrue(target.is_file());self.assertEqual(artifact['session_id'],current['id'])
        w.statusBar().showMessage('Status refresh must preserve the displayed learned case')
        w.refresh_input_problems();w.navigation.update();APP.processEvents()
        self.assertIn('學習稿已保存',w.work_context.text());self.assertNotIn('尚未產生候選',w.work_context.text())
        self.assertIn('學習稿已保存',w.input_state.text());self.assertEqual(w.input_problems.count(),0)
        self.capture(w,'input-integration-main-preview.png')
        w.reorder_template_id='explicit-historical-style';self.assertFalse(uses_learning(w))

    def test_shared_company_graph_and_dimensions_are_not_flattened_by_legacy_adapter(self):
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);self.addCleanup(lambda:dispose_main_window(w));controlled_resources(w)
        graph=InputGraph.from_legacy([dict(name='Person A',phone=['020-000-0100','020-000-0100'],company='c1'),dict(name='Person B',company='c1')],[dict(name='Shared Company')])
        w.adopt_input_graph(graph.data);w.out_w.setValue(120);w.out_h.setValue(80)
        d=DesignLearningDialog(w);self.addCleanup(d.close);attach(d)
        row=d.sessions.current(d.session_id)
        self.assertEqual(row['input_graph'],graph.data);self.assertEqual((row['width_mm'],row['height_mm']),(120,80))
        self.assertEqual(len(row['input_graph']['links']),2)
        phone_ids=[f['id'] for f in row['input_graph']['fields'] if f['kind']=='phone'];self.assertEqual(len(set(phone_ids)),2)
        before=w.generation;w.invalidate();publish_preview(d);self.assertGreater(w.generation,before);self.assertFalse(w.preview_button.isEnabled())

    def test_font_style_enumeration_order_does_not_invalidate_same_face(self):
        self.dialog.solve();_,_,candidate=self.sessions.checked_result(self.row['id'])
        from template_ai.layout import layout_dependency
        with patch('PySide6.QtGui.QFontDatabase.styles',return_value=['Regular','Bold']):a=layout_dependency(candidate.template,{})
        with patch('PySide6.QtGui.QFontDatabase.styles',return_value=['Bold','Regular']):b=layout_dependency(candidate.template,{})
        self.assertEqual(a,b)

    def test_input_advice_and_failure_explanations_keep_unknown_and_plain_summary(self):
        from template_ai.production_report import input_advice,explain_error,result_report
        advice=input_advice(self.library,self.graph,90,54,self.model['id']);self.assertIsNone(advice['hard_limit'])
        self.assertEqual(advice['model_id'],self.model['id']);self.assertTrue(advice['actual_layout_required'])
        self.dialog.solve();row,result,candidate=self.sessions.checked_result(self.row['id'])
        report=result_report(self.library,row,result,candidate);self.assertIn('尚未核實',report['capacity_summary'])
        error=explain_error(ValueError('Font/asset/engine dependencies changed'))
        self.assertTrue(error['summary']);self.assertTrue(error['next_step']);self.assertIn('dependencies',error['details'])
        from template_ai.diagnostic_bundle import plain_overview,report_html
        from template_ai.diagnostic_snapshot import make_snapshot
        from template_ai.gui import MainWindow
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w))
        data=make_snapshot(w,'input').data;self.assertIn('接下來怎麼做',plain_overview(data));self.assertIn('白話摘要',report_html(data).decode())


    def test_learned_reports_preflight_and_comparison_use_current_session_and_safe_summary(self):
        from template_ai.gui import MainWindow
        from template_ai.production_report import save_report
        import json
        w=MainWindow(self.library.root);controlled_resources(w);self.addCleanup(lambda:dispose_main_window(w));w.adopt_input_graph(self.graph.data);w.tabs.setCurrentIndex(2)
        d=DesignLearningDialog(w);self.addCleanup(d.close);attach(d);d.solve()
        with patch.object(w,'shared_design_learning') as route:
            w.diagnostic_report('input');w.diagnostic_report('candidate');w.digital_preflight();w.compare_candidate_results();w.recheck_candidate();w.open_diagnostic('candidate');w.custom_layout()
        self.assertEqual(route.call_count,7);self.assertTrue(all(c.kwargs['use_current_input'] for c in route.call_args_list))
        row=d.sessions.current(d.session_id);target=self.root/('safe-layout-report-'+row['id']+'.json')
        report=save_report(d.sessions,row['id'],row['revision'],target);self.assertEqual(json.loads(target.read_text()),report)
        self.assertEqual(set(report['plain_summary']),{'summary','impact','next_step'});self.assertTrue(report['technical']['result_valid_for_current_input'])
        self.assertFalse(report['technical']['formal_output_allowed']);self.assertEqual(report['technical']['physical_size_mm'],[90.,54.])
        raw=target.read_text();self.assertNotIn('Alex Example',raw);self.assertNotIn('+1 202 555',raw);self.assertNotIn(str(self.root),raw)
        prior=target.read_bytes()
        with self.assertRaises(FileExistsError):save_report(d.sessions,row['id'],row['revision'],target)
        self.assertEqual(target.read_bytes(),prior)


if __name__=='__main__':unittest.main()
