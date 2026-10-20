"""Actual existing GUI navigation, exact return fences and honest unsaved choices."""
import copy,time,unittest,json
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer,QPointF
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from template_ai.gui import Box
from template_ai.candidate_edit import apply_candidate,plan_candidate
from template_ai.workbench_navigation import work_token
from gui_wait import wait_layout
import test_seventy_ui as fixture

APP=fixture.APP


def click_message(text):
    box=next(w for w in QApplication.topLevelWidgets() if isinstance(w,QMessageBox) and w.isVisible())
    button=next(b for b in box.buttons() if b.text()==text);QTest.mouseClick(button,Qt.LeftButton)


class WorkbenchNavigationTests(unittest.TestCase):
    setUp=fixture.SeventyUiTests.setUp
    close_window=fixture.SeventyUiTests.close_window
    def ready(self):
        self.w.tabs.setCurrentIndex(2);self.w.show();self.w.generate();wait_layout(self.w);APP.processEvents()
        self.w.navigation.locations.clear();self.w.navigation.update()
        return self.w.candidates[0]
    def test_actual_logo_modal_cancel_returns_exact_candidate_size_view_and_problem_selection(self):
        c=self.ready();w=self.w;before=c.template.to_dict();changes=w.library.db.total_changes
        box=Box(copy.deepcopy(c.template.slots[0]),lambda *args:None);w.output_canvas.scene().addItem(box);box.setSelected(True)
        w.output_canvas.set_zoom(16);w.output_canvas.centerOn(QPointF(35,20));QTest.qWait(30);transform=w.output_canvas.transform();centre=w.output_canvas.mapToScene(w.output_canvas.viewport().rect().center())
        from template_ai.logo_library_dialog import LogoLibraryDialog
        def cancel():
            dialog=next(d for d in w.findChildren(LogoLibraryDialog) if d.isVisible());dialog.reject()
        QTimer.singleShot(0,cancel);w.logo_center();self.assertTrue(w.return_work_button.isEnabled())
        w.tabs.setCurrentIndex(1);QTest.mouseClick(w.return_work_button,Qt.LeftButton);QTest.qWait(30)
        self.assertEqual(w.tabs.currentIndex(),2);self.assertEqual(w.candidates[0].template.to_dict(),before)
        self.assertEqual(w.output_canvas.transform(),transform);self.assertLess((w.output_canvas.mapToScene(w.output_canvas.viewport().rect().center())-centre).manhattanLength(),.2)
        self.assertEqual([b.slot.id for b in w.output_canvas.scene().selectedItems() if isinstance(b,Box)],[c.template.slots[0].id])
        self.assertEqual(w.library.db.total_changes,changes);self.assertFalse(w.return_work_button.isEnabled())

    def test_new_input_return_is_explicit_fallback_without_restoring_old_manual_or_safe_label(self):
        c=self.ready();w=self.w;nav=w.navigation;nav.begin('字型管理');nav.finish()
        apply_candidate(w,plan_candidate(w,0,[c.template.slots[0].id],1,0),True);manual=w.candidates[0].template.to_dict()
        w.people.item(0,2).setText('1234567890'*30);w.tabs.setCurrentIndex(1)
        self.assertFalse(nav.return_to_work());self.assertEqual(w.candidates[0].template.to_dict(),manual)
        self.assertIn('需重新驗證',w.work_context.text());self.assertIn('無法還原',nav.notice);self.assertFalse(w.export_button.isEnabled())

    def test_changed_published_template_and_removed_candidate_do_not_restore_old_position(self):
        self.ready();w=self.w;nav=w.navigation;nav.begin('來源修正');nav.finish()
        # Inject an external registry replacement; the supported API correctly
        # refuses overwriting an immutable published template.
        payload=w.library.object_snapshot('TEMPLATE',w.candidates[0].template.id)['payload'];payload['name']='Injected external registry replacement'
        w.library.db.execute('UPDATE templates SET payload=? WHERE id=?',(json.dumps(payload),payload['id']));w.library.db.commit()
        self.assertFalse(nav.return_to_work());self.assertIn('版本已變更',nav.notice)
        nav.begin('字型管理');nav.finish();w.candidates=[];w.candidate_list.clear()
        self.assertFalse(nav.return_to_work());self.assertIn('原候選已移除',nav.notice);self.assertFalse(w.export_button.isEnabled())

    def test_return_never_overwrites_new_same_geometry_human_review(self):
        self.ready();w=self.w;nav=w.navigation;nav.begin('來源修正');nav.finish()
        w.candidates[0].risk_context['conditions'].append(dict(id='NEW_REVIEW',status='UNKNOWN',reason='Authored later required review'))
        self.assertFalse(nav.return_to_work());self.assertTrue(any(c['id']=='NEW_REVIEW' for c in w.candidates[0].risk_context['conditions']))

    def test_navigation_history_is_bounded_deduplicated_consumed_and_contains_no_business_copy(self):
        self.ready();w=self.w;nav=w.navigation
        nav.begin('Logo');nav.finish();nav.begin('Logo');nav.finish();self.assertEqual(len(nav.locations),1)
        for n in range(12):w.candidates[0].risk_context['manual_revision']=n+1;nav.begin('字型');nav.finish()
        self.assertEqual(len(nav.locations),8);self.assertFalse(any(key in nav.locations[-1] for key in ('people','companies','candidate','payload','template')))
        self.assertTrue(nav.return_to_work());self.assertEqual(len(nav.locations),7)
        self.assertFalse(nav.return_to_work());self.assertEqual(len(nav.locations),6)

    def test_unsaved_property_form_survives_tab_switch_and_close_stay_without_implicit_apply(self):
        from training_fixture import source_work
        from template_ai.model import Slot,Rect
        source,work=source_work(self.w.library,self.root,'navigation-source.svg');w=self.w;w.work=work
        w.slots=[Slot(**{**row,'rect':Rect(**row['rect'])}) for row in work['payload']['slots']]
        w.tabs.setCurrentIndex(0);w.select_slot(w.slots[0]);before=copy.deepcopy(w.slots[0]);w.coords[0].setValue(before.rect.x+1)
        self.assertTrue(w.navigation.pending_form());w.tabs.setCurrentIndex(1);self.assertTrue(any('其他功能頁' in s for s in w.navigation.close_impacts()))
        w.tabs.setCurrentIndex(0);self.assertEqual(w.coords[0].value(),before.rect.x+1);self.assertEqual(w.slots[0],before)
        w.show();QTimer.singleShot(0,lambda:click_message('返回繼續編輯'));self.assertFalse(w.close())
        self.assertFalse(w.library.closed);self.assertEqual(w.slots[0],before);self.assertEqual(w.coords[0].value(),before.rect.x+1)
        QTimer.singleShot(0,lambda:click_message('明確放棄當次操作並關閉'));self.assertTrue(w.navigation.confirm_close());self.assertEqual(w.slots[0],before)

    def test_close_recovery_choice_opens_existing_session_and_never_claims_written(self):
        self.ready();w=self.w;QTimer.singleShot(0,lambda:click_message('開啟安全恢復'))
        with patch.object(w,'layout_session') as existing:self.assertFalse(w.navigation.confirm_close());existing.assert_called_once_with()
        self.assertIsNone(w.navigation.recovery);self.assertIn('尚未保存',w.work_context.text())

    def test_fake_failed_expired_or_changed_recovery_receipt_never_clears_current_unsaved(self):
        self.ready();w=self.w;nav=w.navigation;token=work_token(w)
        nav.recovery_saved(dict(saved=False,encrypted=True,authenticated=True),token)
        self.assertIn('保存失敗',w.work_context.text());self.assertFalse(nav.recovery_current())
        nav.recovery_saved(dict(saved=True,encrypted=True,authenticated=True,expires=time.time()-1),token)
        self.assertFalse(nav.recovery_current());self.assertIn('尚未保存',w.work_context.text())
        nav.recovery_saved(dict(saved=True,encrypted=True,authenticated=True,expires=time.time()+100),token)
        self.assertFalse(nav.recovery_current());self.assertIn('保存失敗',w.work_context.text());self.assertTrue(nav.close_impacts())

    def test_context_minimizes_personal_details_and_navigation_does_not_schedule_calculation(self):
        self.ready();w=self.w;before=[c.template.to_dict() for c in w.candidates];count=w.library.db.total_changes
        with patch.object(w,'run_job') as jobs:
            for index in (0,1,2):w.tabs.setCurrentIndex(index);w.navigation.update()
            jobs.assert_not_called()
        for value in ('Alex','alex@example.test','+12025550100'):self.assertNotIn(value,w.work_context.text())
        self.assertEqual(w.library.db.total_changes,count);self.assertEqual([c.template.to_dict() for c in w.candidates],before)

    def test_actual_encrypted_save_failure_success_later_edit_and_clear_are_distinct(self):
        from PySide6.QtWidgets import QInputDialog
        from gui_wait import wait_for_gui
        self.ready();w=self.w;session=w.foreground_layout_session;session.report_state='CANCELLED';session.controls()
        with patch.object(QInputDialog,'getText',return_value=('synthetic-navigation-password',True)),patch.object(session.recovery,'save',side_effect=OSError('Injected disk full')):
            session.save_recovery();self.assertTrue(wait_for_gui(lambda:not w.busy,10))
        self.assertFalse(session.recovery.pending());self.assertIn('保存失敗',w.work_context.text());self.assertFalse(w.navigation.recovery_current())
        self.assertNotIn('背景執行中',w.statusBar().currentMessage())
        with patch.object(QInputDialog,'getText',return_value=('synthetic-navigation-password',True)):
            session.save_recovery();self.assertTrue(wait_for_gui(lambda:not w.busy,10))
        self.assertTrue(session.recovery.pending());self.assertTrue(w.navigation.recovery_current());self.assertIn('短期恢復已加密落盤',w.work_context.text())
        payload=session.recovery.load('synthetic-navigation-password');self.assertEqual(payload['state'],'CANCELLED')
        c=w.candidates[0];apply_candidate(w,plan_candidate(w,0,[c.template.slots[0].id],1,0),True)
        self.assertFalse(w.navigation.recovery_current());self.assertTrue(w.navigation.close_impacts())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):session.clear_recovery()
        self.assertFalse(session.recovery.pending());self.assertIsNone(w.navigation.recovery);self.assertIn('尚未保存',w.work_context.text())

    def test_mode_back_consumes_history_and_preserves_unstarted_input_without_recalculation(self):
        w=self.w;w.show();w.navigation.locations.clear();before=w.input_data();changes=w.library.db.total_changes
        with patch.object(w,'run_job') as jobs:
            w.tabs.setCurrentIndex(1);w.tabs.setCurrentIndex(2)
            self.assertIn('尚未產生候選',w.work_context.text());self.assertTrue(w.navigation.close_impacts())
            self.assertTrue(w.navigation.return_to_work());self.assertEqual(w.tabs.currentIndex(),1)
            self.assertTrue(w.navigation.return_to_work());self.assertEqual(w.tabs.currentIndex(),0)
            self.assertFalse(w.navigation.locations);jobs.assert_not_called()
        self.assertEqual(w.input_data(),before);self.assertEqual(w.library.db.total_changes,changes)

    def test_actual_official_save_failure_does_not_close_or_claim_safe_saved(self):
        w=self.w;w.tabs.setCurrentIndex(1);w.add_demo();w.show();before=w.template.to_dict()
        QTimer.singleShot(0,lambda:click_message('明確放棄當次操作並關閉'))
        with patch.object(w,'save_current_template',side_effect=OSError('Injected official save failure')),patch.object(w,'error') as error:
            self.assertFalse(w.close());error.assert_called_once()
        self.assertFalse(w.library.closed);self.assertEqual(w.template.to_dict(),before);self.assertIn('正式資料保存失敗',w.work_context.text())

    def test_real_active_worker_is_not_restarted_cancelled_or_duplicated_by_mode_back(self):
        import threading
        from gui_wait import wait_for_gui
        w=self.w;entered=threading.Event();release=threading.Event();calls=[];done=[]
        def work():calls.append(1);entered.set();release.wait(3);return 'actual worker result'
        w.run_job('Synthetic bounded foreground worker',work,done.append);self.assertTrue(entered.wait(1))
        for mode in (1,2,0):w.tabs.setCurrentIndex(mode);self.assertIn('背景工作進行中',w.work_context.text())
        self.assertTrue(w.navigation.return_to_work());self.assertTrue(w.busy);self.assertEqual(len(w._background_jobs),1)
        release.set();self.assertTrue(wait_for_gui(lambda:not w.busy,5));self.assertEqual(calls,[1]);self.assertEqual(done,['actual worker result'])

    def test_actual_back_with_selected_frame_keeps_unapplied_property_value(self):
        from training_fixture import source_work
        from template_ai.model import Slot,Rect
        source,work=source_work(self.w.library,self.root,'navigation-selected-frame.svg');w=self.w;w.work=work
        w.slots=[Slot(**{**row,'rect':Rect(**row['rect'])}) for row in work['payload']['slots']]
        w.train_canvas.set_content(90,54,slots=w.slots);w.train_canvas.set_mode('edit');w.train_canvas.select_id(w.slots[0].id)
        original=w.slots[0].rect.x;w.coords[0].setValue(original+1);w.tabs.setCurrentIndex(1)
        self.assertTrue(w.navigation.return_to_work());self.assertEqual(w.coords[0].value(),original+1)
        self.assertEqual(w.slots[0].rect.x,original);self.assertTrue(w.navigation.pending_form())

    def test_removed_actual_encrypted_file_revokes_current_recovery_before_close(self):
        from PySide6.QtWidgets import QInputDialog
        from gui_wait import wait_for_gui
        self.ready();w=self.w;session=w.foreground_layout_session;session.report_state='CANCELLED';session.controls()
        with patch.object(QInputDialog,'getText',return_value=('synthetic-navigation-password',True)):
            session.save_recovery();self.assertTrue(wait_for_gui(lambda:not w.busy,10))
        self.assertTrue(w.navigation.recovery_current());session.recovery.path.unlink()
        self.assertFalse(w.navigation.recovery_current());self.assertTrue(w.navigation.close_impacts())

    def test_small_window_keeps_visible_canvas_and_reachable_existing_controls(self):
        from PySide6.QtWidgets import QPushButton
        from gui_wait import wait_for_gui
        self.ready();w=self.w;w.foreground_layout_session.hide();w.resize(960,640);w.property_panel.hide();APP.processEvents()
        QTest.mouseClick(next(b for b in w.function_rail.findChildren(QPushButton) if b.text()=='排版與輸出'),Qt.LeftButton)
        self.assertTrue(wait_for_gui(lambda:w.output_canvas.visibleRegion().boundingRect().height()>=180,2))
        visible=w.output_canvas.visibleRegion().boundingRect()
        self.assertGreaterEqual(visible.height(),180);self.assertGreaterEqual(visible.width(),240)
        self.assertGreaterEqual(w.output_canvas.viewport().visibleRegion().boundingRect().height(),180)
        self.assertTrue(w.rect().contains(w.return_work_button.mapTo(w,w.return_work_button.rect().center())))
        if hasattr(w,'output_page_scroll'):
            w.output_page_scroll.ensureWidgetVisible(w.preview_button);APP.processEvents();self.assertFalse(w.preview_button.visibleRegion().isEmpty())
