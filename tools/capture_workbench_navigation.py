"""Actual navigation/return/unsaved/recovery GUI; authored fixtures, no private corpus."""
import argparse,json,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from unittest.mock import patch
    from PySide6.QtCore import Qt,QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog,QPushButton
    from PySide6.QtTest import QTest
    from template_ai.gui import Box
    from template_ai.logo_library_dialog import LogoLibraryDialog
    from template_ai.candidate_edit import apply_candidate,plan_candidate
    from test_workbench_navigation import WorkbenchNavigationTests,click_message
    from sync_workflow_fixture import SyncWorkflowFixture
    from gui_wait import wait_for_gui
    case=WorkbenchNavigationTests('runTest');case.setUp();w=case.w;app=QApplication.instance();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));screens=[];multi=None
    def shot(widget,name):
        app.processEvents();path=folder/('workbench-navigation-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    try:
        case.ready();w.resize(1360,940);w.foreground_layout_session.hide();app.processEvents();c=w.candidates[0]
        box=Box(copy.deepcopy(c.template.slots[0]),lambda *args:None);w.output_canvas.scene().addItem(box);box.setSelected(True);w.output_canvas.set_zoom(12);view=w.output_canvas.transform()
        original=c.template.to_dict();shot(w,'01-current-candidate-context')
        def logo_cancel():
            dialog=next(d for d in w.findChildren(LogoLibraryDialog) if d.isVisible());shot(dialog,'02-existing-logo-correction');QTest.keyClick(dialog,Qt.Key_Escape)
        QTimer.singleShot(0,logo_cancel);w.logo_center();w.tabs.setCurrentIndex(1);assert w.navigation.return_to_work();assert w.output_canvas.transform()==view;assert w.candidates[0].template.to_dict()==original
        shot(w,'03-exact-candidate-view-return')
        def close_stay():
            dialog=next(d for d in QApplication.topLevelWidgets() if isinstance(d,QMessageBox) and d.isVisible());shot(dialog,'04-real-unsaved-close-choices');click_message('返回繼續編輯')
        QTimer.singleShot(0,close_stay);assert not w.close();assert not w.library.closed
        session=w.foreground_layout_session;session.report_state='CANCELLED';session.controls()
        with patch.object(QInputDialog,'getText',return_value=('synthetic-navigation-password',True)),patch.object(session.recovery,'save',side_effect=OSError('Injected disk full')):
            session.save_recovery();assert wait_for_gui(lambda:not w.busy,10)
        assert not session.recovery.pending();assert '保存失敗' in w.work_context.text();shot(w,'05-actual-save-failure-not-saved')
        with patch.object(QInputDialog,'getText',return_value=('synthetic-navigation-password',True)):
            session.save_recovery();assert wait_for_gui(lambda:not w.busy,10)
        assert session.recovery.pending() and w.navigation.recovery_current();shot(w,'06-actual-encrypted-short-recovery')
        w.navigation.begin('字型管理');w.navigation.finish();apply_candidate(w,plan_candidate(w,0,[c.template.slots[0].id],1,0),True);manual=w.candidates[0].template.to_dict()
        assert not w.navigation.return_to_work();assert not w.navigation.recovery_current();assert w.candidates[0].template.to_dict()==manual;shot(w,'07-new-manual-version-safe-fallback')
        w.resize(960,640);app.processEvents();w.function_rail.setVisible(True);w.property_panel.setVisible(False);w.navigation.update();app.processEvents()
        QTest.mouseClick(next(b for b in w.function_rail.findChildren(QPushButton) if b.text()=='排版與輸出'),Qt.LeftButton)
        assert wait_for_gui(lambda:w.output_canvas.visibleRegion().boundingRect().height()>=180,2)
        assert w.rect().contains(w.return_work_button.mapTo(w,w.return_work_button.rect().center()));assert w.output_canvas.viewport().width()>=240
        shot(w,'08-small-window-current-work-return-visible')
        multi=SyncWorkflowFixture();multi.d.resize(1250,850);multi.select('C100');before=multi.candidate('C100').template.to_dict()
        def multi_logo_cancel():
            dialog=next(d for d in multi.w.findChildren(LogoLibraryDialog) if d.isVisible());assert dialog.selected_size()==[100,60];shot(dialog,'09-size100-existing-logo-correction');QTest.keyClick(dialog,Qt.Key_Escape)
        QTimer.singleShot(0,multi_logo_cancel);multi.w.logo_center(return_origin=multi.d);multi.select('A90');assert multi.w.navigation.return_to_work();assert multi.d.entry()['selected']==multi.templates['C100'].id;assert not multi.candidate('C100').formal_eligible
        shot(multi.d,'10-return-original100-blocked-candidate')
        multi.w.navigation.begin('人物與公司資料',origin=multi.d);multi.w.navigation.finish();multi.change_phone('+12025550999');assert not multi.w.navigation.return_to_work();assert multi.candidate('C100').template.to_dict()==before
        shot(multi.d,'11-changed-shared-source-size-pending')
        from training_fixture import source_work
        from template_ai.model import Slot,Rect
        source,work=source_work(w.library,case.root,'navigation-native-pending.svg');w.work=work;w.slots=[Slot(**{**row,'rect':Rect(**row['rect'])}) for row in work['payload']['slots']]
        w.resize(1360,940);w.property_panel.setVisible(True);w.tabs.setCurrentIndex(0);w.train_canvas.set_content(90,54,slots=w.slots);w.train_canvas.set_mode('edit');w.train_canvas.select_id(w.slots[0].id);old_x=w.slots[0].rect.x;w.coords[0].setValue(old_x+1);w.tabs.setCurrentIndex(1)
        assert w.navigation.return_to_work();assert w.coords[0].value()==old_x+1 and w.slots[0].rect.x==old_x and w.navigation.pending_form();shot(w,'12-return-preserves-unapplied-property')
        assert not errors,errors
        result=dict(status='PASS',screens=screens,qt_errors=errors,actual_gui=True,scope='Authored controlled Linux, existing GUI/worker and actual encrypted disk writes; no reference Windows/private Illustrator qualification',actual_cases=['Exact Main candidate/size/view/problem selection after real Logo modal cancel','Actual unsaved close Stay','Actual disk failure then encrypted readback/stat receipt success; newer manual revision safe fallback','Small 960x640 requested window with current/back visible, collapsed existing property pane','Actual 100mm origin not Main90; missing dedicated Logo stays blocked','Changed shared source invalidates return and preserves original instances','Selected-frame return keeps unapplied X without changing stored geometry'],automatic_training=False,paid_services=False)
        (folder/'workbench-navigation-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        if multi:multi.close()
        w.pool.waitForDone(5000);app.processEvents();sys.excepthook=previous;case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=capture(args.folder);print(json.dumps({k:v for k,v in r.items() if k!='screens'},ensure_ascii=False))
