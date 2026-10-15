"""Logo 原條款的實際 Qt 互動、背景失敗與同來源邊界校正。"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog, QLabel, QPushButton

from template_ai.customers import digest
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.logo_choice_dialog import LogoChoiceDialog
from template_ai.logo_library_dialog import LogoLibraryDialog
from template_ai.logo_review_dialog import LogoReviewDialog
from template_ai.logo_store import LogoStore

APP=QApplication.instance() or QApplication([])
REVIEW=dict(identity_confirmed=True,whole_mark_confirmed=True,usage_authorized=True,
    digital_quality_confirmed=True,actor='SYNTHETIC_TEST',note='Synthetic full source and target size checked')


class LogoWorkflowGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.window=MainWindow(self.root/'library');self.store=LogoStore(self.window.library)
        self.company=self.store.create_company('Synthetic Brand','Synthetic explicit identity',True)
        self.path=self.root/'synthetic-logo.svg'
        self.path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10"><g id="whole"><rect id="symbol" x="1" y="1" width="5" height="5" fill="red"/><text id="brand" x="8" y="6" font-size="2">Example</text></g></svg>')
        result=import_file(self.path,self.window.library.assets)
        self.payload=dict(image=result['image'],svg=result['svg'],source_width_mm=result['width_mm'],source_height_mm=result['height_mm'],source_hash=result['hash'],crop=None)

    def tearDown(self):
        self.window.input_timer.stop();self.window.font_manager.close();self.window.library.close();self.window.deleteLater();APP.processEvents();self.temp.cleanup()

    def proposal(self,width=90,height=54):
        return self.store.propose(self.payload,width,height,company_id=self.company['id'])

    def approve(self,row=None):
        row=row or self.proposal();return self.store.approve(row['id'],row['revision'],self.company['id'],REVIEW,True)

    def wait(self,condition):
        for _ in range(1000):
            APP.processEvents()
            if condition():return
            QTest.qWait(10)
        self.fail('bounded Qt background operation did not finish')

    def graph(self):
        return InputGraph.from_legacy([dict(name=['Alex'],company='c1')],[dict(name=self.company['name'])])

    def test_actual_review_default_unchecked_cancel_then_explicit_approval(self):
        row=self.proposal();dialog=LogoReviewDialog(self.store,row,self.window);self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.compare.available)
        self.assertTrue(all(not x.isChecked() for x in dialog.flags.values()))
        dialog.approve();self.assertEqual(self.window.library.logos(),[])
        for check in dialog.flags.values():check.setChecked(True)
        dialog.note.setText('Synthetic original, complete graphic/text and target size reviewed')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):dialog.approve()
        self.assertEqual(self.window.library.logos(),[])
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.approve()
        self.assertEqual(dialog.result(),QDialog.Accepted)
        self.assertEqual(len(self.window.library.logos()),1)
        self.assertEqual(dialog.approved_asset['company_id'],self.company['id'])

    def test_changed_geometry_or_company_invalidates_preview_and_all_approval_flags(self):
        row=self.proposal();dialog=LogoReviewDialog(self.store,row,self.window);self.addCleanup(dialog.deleteLater)
        for check in dialog.flags.values():check.setChecked(True)
        dialog.note.setText('Synthetic corrected complete region')
        dialog.coords[0].setValue(1);dialog.coords[2].setValue(19)
        self.assertTrue(all(not check.isChecked() for check in dialog.flags.values()))
        self.assertIsNone(dialog.preview_signature)
        dialog.preview()
        for check in dialog.flags.values():check.setChecked(True)
        dialog.approve();self.assertIn('邊界尚未保存',dialog.status.text())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.correct()
        self.assertEqual(dialog.proposal['revision'],row['revision']+1)
        self.assertTrue(all(not check.isChecked() for check in dialog.flags.values()))
        self.assertEqual(self.window.library.logos(),[])

    def test_library_three_views_and_reference_return_keep_physical_size_isolation(self):
        a=self.approve();b=self.approve(self.proposal(100,60));pending=self.proposal()
        dialog=LogoLibraryDialog(self.window);self.addCleanup(dialog.deleteLater)
        self.assertEqual(len(dialog.rows),1);self.assertEqual(dialog.rows[0]['id'],a['id'])
        dialog.views.setCurrentIndex(2);self.assertTrue(any(r['id']==pending['id'] for r in dialog.rows))
        dialog.views.setCurrentIndex(1);self.assertEqual(dialog.rows,[])
        dialog.views.setCurrentIndex(0);dialog.reference.setChecked(True)
        self.assertEqual({r['id'] for r in dialog.rows},{a['id'],b['id']})
        self.assertIn('目標未核准',dialog.table.item(0,3).text())
        self.assertFalse(dialog.import_button.isEnabled())
        dialog.reference.setChecked(False)
        self.assertEqual([r['id'] for r in dialog.rows],[a['id']])
        self.assertEqual(len(self.window.library.logos()),2)

    def test_actual_manual_import_background_is_pending_and_does_not_publish(self):
        dialog=LogoLibraryDialog(self.window);self.addCleanup(dialog.deleteLater)
        dialog.company.setCurrentIndex(dialog.company.findData(self.company['id']))
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(self.path),'')):
            dialog.manual_import()
        self.wait(lambda:not dialog.running)
        self.assertEqual(self.window.library.logos(),[])
        dialog.views.setCurrentIndex(2)
        self.assertEqual(len(dialog.rows),1);self.assertEqual(dialog.rows[0]['state'],'PENDING')
        self.assertFalse(self.window.busy)

    def test_worker_database_init_failure_releases_busy_and_dialog_can_close(self):
        dialog=LogoLibraryDialog(self.window);self.addCleanup(dialog.deleteLater)
        with patch('template_ai.storage.Library',side_effect=OSError('synthetic database unavailable')):
            dialog.background('Synthetic worker',lambda store:[])
            self.wait(lambda:not dialog.running)
        self.assertFalse(self.window.busy)
        self.assertIn('synthetic database unavailable',dialog.status.text())
        self.assertTrue(dialog.close())

    def test_generic_worker_start_failure_restores_controls_and_does_not_leave_job(self):
        with patch.object(self.window.pool,'start',side_effect=RuntimeError('synthetic start failure')):
            with self.assertRaises(RuntimeError):self.window.run_job('Synthetic',lambda:None,lambda _:None)
        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.import_button.isEnabled())
        self.assertEqual(self.window._background_jobs,{})

    def test_company_card_exposes_status_and_three_actions_without_auto_modifying_graph(self):
        asset=self.approve();graph=self.graph();before=deepcopy(graph.data)
        dialog=InputGraphDialog(self.window,graph.data);self.addCleanup(dialog.deleteLater)
        labels=[x.text() for x in dialog.findChildren(QLabel)]
        self.assertTrue(any('IDENTITY_REVIEW_REQUIRED' in text for text in labels))
        buttons=[b.text() for b in dialog.findChildren(QPushButton)]
        for label in ('選擇 Logo','匯入新 Logo','查看審核狀態'):self.assertIn(label,buttons)
        cid=graph.data['companies'][0]['id'];self.store.bind(cid,self.company['id'],self.company['name'],True)
        dialog.rebuild()
        self.assertTrue(any('SINGLE_PREVIEW' in x.text() for x in dialog.findChildren(QLabel)))
        self.assertEqual(dialog.graph.data,before)
        self.assertEqual(dialog.graph.entity(cid)['logo_id'],'')

    def test_actual_exact_logo_choice_then_graph_undo_only_changes_local_company_reference(self):
        asset=self.approve();graph=self.graph();cid=graph.data['companies'][0]['id']
        self.store.bind(cid,self.company['id'],self.company['name'],True)
        dialog=InputGraphDialog(self.window,graph.data);self.addCleanup(dialog.deleteLater)
        def choose():
            modal=APP.activeModalWidget()
            self.assertIsInstance(modal,LogoChoiceDialog)
            modal.choose()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            QTimer.singleShot(0,choose);dialog.choose_logo(cid)
        self.assertEqual(dialog.graph.entity(cid)['logo_id'],asset['id'])
        dialog.undo()
        self.assertEqual(dialog.graph.entity(cid)['logo_id'],'')
        self.assertEqual(self.window.active_input_graph,None)

    def test_revoked_during_confirmation_never_adopts_stale_logo(self):
        asset=self.approve();graph=self.graph();cid=graph.data['companies'][0]['id']
        self.store.bind(cid,self.company['id'],self.company['name'],True)
        dialog=LogoChoiceDialog(self.window,graph,cid);self.addCleanup(dialog.deleteLater)
        def withdraw(*_):
            self.store.revoke(asset['id'],digest(asset),'Synthetic concurrent revocation',True)
            return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=withdraw):dialog.choose()
        self.assertIsNone(dialog.selected_asset)
        self.assertNotEqual(dialog.result(),QDialog.Accepted)
        self.assertIn('未選用',dialog.status.text())

    def test_main_import_entry_enqueues_candidate_and_never_directly_approves(self):
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(self.path),'')), \
             patch.object(self.window,'open_logo_proposal') as opened:
            self.window.import_logo();self.wait(lambda:not self.window.busy)
        self.assertEqual(self.window.library.logos(),[])
        self.assertEqual(opened.call_count,1)
        row=self.store.proposal(opened.call_args.args[0]);self.assertEqual(row['state'],'PENDING')

    def test_merge_split_source_candidates_are_new_pending_and_do_not_modify_original(self):
        source=self.window.library.add_source(self.path,import_file(self.path,self.window.library.assets))
        work=self.window.library.create_artwork(source['id'],'Synthetic work',dict(crop=dict(x=0,y=0,w=20,h=10),work_width=90,work_height=54,slots=[],visual_confirmed=True))
        left=self.store.propose_source(source['id'],work['id'],dict(x=0,y=0,w=10,h=10),object_ids=['symbol'])
        right=self.store.propose_source(source['id'],work['id'],dict(x=10,y=0,w=10,h=10),object_ids=['brand'])
        selections=[dict(id=r['id'],revision=r['revision']) for r in (left,right)]
        original=self.path.read_bytes();merged=self.store.regions(selections,None,'Synthetic complete mark union')[0]
        self.assertEqual(merged['asset']['crop'],dict(x=0,y=0,w=20,h=10))
        self.assertEqual(merged['state'],'PENDING');self.assertEqual(self.store.proposal(left['id'])['state'],'PENDING')
        split=self.store.regions([dict(id=merged['id'],revision=merged['revision'])],
            [dict(x=0,y=0,w=10,h=10),dict(x=10,y=0,w=10,h=10)],'Synthetic two distinct complete marks require re-review')
        self.assertEqual(len(split),2);self.assertTrue(all(r['state']=='PENDING' for r in split))
        count=self.store.db.execute('SELECT count(*) FROM logo_proposals').fetchone()[0]
        with self.assertRaises(ValueError):self.store.regions(selections,[dict(x=0,y=0,w=50,h=10)],'Out of artwork')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM logo_proposals').fetchone()[0],count)
        self.assertEqual(self.path.read_bytes(),original);self.assertEqual(self.window.library.logos(),[])

    def test_focus_proposal_selects_correct_size_view_and_stable_id_without_approval(self):
        proposal=self.proposal(100,60);dialog=LogoLibraryDialog(self.window);self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.focus_proposal(proposal['id']))
        self.assertEqual(dialog.selected_size(),[100,60]);self.assertEqual(dialog.views.currentIndex(),2)
        self.assertEqual(dialog.current()['id'],proposal['id']);self.assertEqual(self.window.library.logos(),[])

    def test_actual_new_size_prediction_button_only_creates_pending_target_candidates(self):
        asset=self.approve();dialog=LogoLibraryDialog(self.window);self.addCleanup(dialog.deleteLater)
        dialog.reference.setChecked(True);dialog.company.setCurrentIndex(dialog.company.findData(self.company['id']))
        dialog.target_w.setValue(100);dialog.target_h.setValue(60);dialog.predict()
        self.wait(lambda:not dialog.running)
        proposed=self.store.proposals(100,60)
        self.assertEqual(len(proposed),1);self.assertEqual(proposed[0]['state'],'PENDING')
        self.assertEqual(self.window.library.logos(),[asset])
        dialog.focus_proposal(proposed[0]['id'])
        self.assertFalse(dialog.reference.isChecked());self.assertEqual(dialog.selected_size(),[100,60])
        self.assertEqual(dialog.current()['id'],proposed[0]['id'])

    def test_frame_adjustment_uses_existing_versioned_draft_and_never_mutates_published(self):
        from template_ai.model import Template,Slot,Rect
        template=Template('Synthetic protected logo frame',90,54,
            [Slot('name','p1',Rect(3,3,60,8)),Slot('logo','c1',Rect(3,20,30,15))],
            company_bindings={'p1':'c1'})
        self.window.library.publish(template);before=deepcopy(template.to_dict())
        self.window.refresh_templates(template.id);self.window.open_catalog_editor(template.id)
        dialog=LogoLibraryDialog(self.window);self.addCleanup(dialog.deleteLater)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes), \
             patch.object(self.window,'object_tools') as tools:
            dialog.edit_frame()
        self.assertEqual(tools.call_count,1)
        self.assertEqual(self.window.template.state,'draft');self.assertNotEqual(self.window.template.id,template.id)
        self.assertEqual(self.window.template.family_id,template.family_id)
        self.assertEqual(next(t for t in self.window.library.templates() if t.id==template.id).to_dict(),before)

    def test_actual_qt_source_drag_selects_full_crop_then_requires_saved_review(self):
        from PySide6.QtCore import QPointF
        proposal=self.proposal();dialog=LogoReviewDialog(self.store,proposal);self.addCleanup(dialog.deleteLater)
        canvas=dialog.crop_canvas();canvas.rectangle.connect(dialog.adopt_crop);canvas.resize(800,500);canvas.show();canvas.fit();APP.processEvents()
        start=canvas.mapFromScene(QPointF(1,1));end=canvas.mapFromScene(QPointF(17,8))
        QTest.mousePress(canvas.viewport(),Qt.LeftButton,pos=start)
        QTest.mouseMove(canvas.viewport(),end);QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,pos=end)
        self.assertAlmostEqual(dialog.crop()['x'],1,delta=.1);self.assertAlmostEqual(dialog.crop()['w'],16,delta=.1)
        self.assertTrue(all(not c.isChecked() for c in dialog.flags.values()))
        self.assertEqual(self.store.proposal(proposal['id'])['asset']['crop'],proposal['asset']['crop'])
        canvas.close();canvas.deleteLater()

    def test_exception_view_only_routes_uncertain_conflicted_or_repair_not_normal_high_confidence(self):
        ordinary=self.proposal();uncertain=self.store.propose(self.payload,90,54,company_id=self.company['id'],evidence={'uncertainty':'Synthetic boundary conflict'})
        repair=self.proposal();self.store.reject(repair['id'],repair['revision'],'Synthetic source repair',True,True)
        dialog=LogoLibraryDialog(self.window,exceptions_only=True);self.addCleanup(dialog.deleteLater);dialog.views.setCurrentIndex(1)
        self.assertEqual({r['id'] for r in dialog.rows},{uncertain['id'],repair['id']})
        self.assertNotIn(ordinary['id'],{r['id'] for r in dialog.rows});self.assertFalse(self.window.library.logos())
