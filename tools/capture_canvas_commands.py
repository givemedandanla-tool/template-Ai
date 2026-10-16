"""Real Qt keyboard/focus/dialog workflow with authored data, no device qualification."""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from PySide6.QtCore import Qt,QTimer,QPoint,QCoreApplication,QEvent
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QApplication,QMessageBox,QDialog
    from PySide6.QtTest import QTest
    from test_canvas_named_commands import CanvasNamedCommandTests
    from template_ai.object_dialog import ObjectToolsDialog
    from template_ai.editor_settings import EditorSettingsDialog,load_commands
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);case=CanvasNamedCommandTests('runTest');case.setUp();w=case.w;app=QApplication.instance();screens=[];errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error))
    def shot(widget,name):
        app.processEvents();path=folder/('canvas-command-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    def modal(action,call):
        case.focus(w.edit_canvas)
        def respond():
            dialog=QApplication.activeModalWidget()
            try:action(dialog)
            except BaseException as error:errors.append(str(error))
            finally:
                if dialog and dialog.isVisible():dialog.reject()
        QTimer.singleShot(0,respond);call();assert not errors,errors
    try:
        w.resize(1360,940);app.processEvents();case.move();assert w.template.slots[0].rect.x==8.1 and w.template.slots[0].size_pt==18;shot(w,'01-focused-mm-nudge-current-id')
        case.key(Qt.Key_Z,Qt.ControlModifier);assert w.template.slots[0].rect.x==8;case.key(Qt.Key_Y,Qt.ControlModifier);assert w.template.slots[0].rect.x==8.1;shot(w,'02-existing-work-undo-redo')
        case.focus(w.text_color);w.text_color.selectAll();QTest.keyClicks(w.text_color,'#abcdef');QTest.keyClick(w.text_color,Qt.Key_Z,Qt.ControlModifier);assert len(w.undo_stack)==1 and w.text_color.text()=='#111827';shot(w,'03-text-focus-undo-keeps-work')
        w.coords[0].setValue(12);case.key(Qt.Key_Right);assert w.template.slots[0].rect.x==8.1 and w.coords[0].value()==12;shot(w,'04-unapplied-field-blocks-nudge')
        def discard(box):
            assert isinstance(box,QMessageBox);shot(box,'05-real-pending-discard-scope');next(b for b in box.buttons() if '放棄未套用輸入並切換' in b.text()).click()
        modal(discard,lambda:w.editor_selection([case.ids[1]]));assert w.current_slot.id==case.ids[1] and w.template.slots[0].rect.x==8.1
        def cancel_undo(box):
            assert isinstance(box,QMessageBox) and case.ids[0] in box.text();shot(box,'06-real-history-scope-confirmation');box.button(QMessageBox.No).click()
        modal(cancel_undo,lambda:QTest.keyClick(w.edit_canvas,Qt.Key_Z,Qt.ControlModifier));assert len(w.undo_stack)==1
        def help_view(dialog):
            assert isinstance(dialog,QDialog) and dialog.windowTitle()=='畫布快捷鍵與目前模式';shot(dialog,'07-actual-f1-overview-and-mouse-routes')
        modal(help_view,lambda:QTest.keyClick(w.edit_canvas,Qt.Key_F1))
        w.editor_selection([case.ids[0]]);case.key(Qt.Key_Z,Qt.ControlModifier);assert w.template.slots[0].rect.x==8
        before=w.library.object_snapshot('TEMPLATE',case.draft.id)
        def delete_preview(dialog):
            assert isinstance(dialog,ObjectToolsDialog) and dialog.request['operation']=='DELETE' and dialog.request['ids']==[case.ids[0]];shot(dialog,'08-real-delete-preview-no-write')
        modal(delete_preview,lambda:QTest.keyClick(w.edit_canvas,Qt.Key_Delete));assert w.library.object_snapshot('TEMPLATE',case.draft.id)==before
        # Explicit existing UI transaction/save authors the locked test scenario.
        w.editor_canvas_apply(dict(operation='LOCK',ids=[case.ids[0]],locked=True));w.save_draft();assert w.library.object_snapshot('TEMPLATE',case.draft.id)['payload']['slots'][0]['locked']
        def locked_preview(dialog):
            assert isinstance(dialog,ObjectToolsDialog) and dialog.plan is None and '鎖定' in dialog.status.text();shot(dialog,'09-locked-delete-remains-blocked')
        modal(locked_preview,lambda:QTest.keyClick(w.edit_canvas,Qt.Key_Delete))
        w.editor_selection([case.ids[1]]);old=w.template.to_dict();changed=copy.deepcopy(w.template);changed.name+=' authored external source';w.library.save_template(changed,expected_revision=w.template_revision)
        history_before=copy.deepcopy(w.undo_stack);case.key(Qt.Key_Right);assert w.template.to_dict()==old and w.undo_stack==history_before;assert '版本已變更' in w.statusBar().currentMessage();shot(w,'10-stale-source-no-old-key-transaction')
        dialog=EditorSettingsDialog(w);dialog.show();app.processEvents();writes=w.library.db.total_changes;dialog.command_keys['REDO'].setKeySequence(QKeySequence('Ctrl+Z'));dialog.save();assert '衝突' in dialog.status.text() and writes==w.library.db.total_changes;shot(dialog,'11-real-key-conflict-no-save');dialog.reject()
        dialog=EditorSettingsDialog(w)
        for name,key in [('UNDO','F7'),('REDO','F8'),('DELETE','F9')]:dialog.command_keys[name].setKeySequence(QKeySequence(key))
        dialog.save();assert load_commands(w.library)==dict(UNDO='F7',REDO='F8',DELETE='F9');reopen=EditorSettingsDialog(w);reopen.show();app.processEvents();shot(reopen,'12-explicit-remap-reopens-from-preferences');reopen.reject()
        w.template=None;w.refresh_templates(case.draft.id);w.editor_selection([case.ids[0]]);case.focus(w.edit_canvas);before=w.template.to_dict();QTest.keyPress(w.edit_canvas,Qt.Key_Space);assert w.edit_canvas.mode=='pan' and '視角平移' in w.statusBar().currentMessage();shot(w,'13-space-visible-view-only-mode')
        QTest.keyRelease(w.edit_canvas,Qt.Key_Space);assert w.edit_canvas.mode=='edit' and w.template.to_dict()==before and w.template.slots[0].size_pt==18;shot(w,'14-release-restores-exact-tool-and-data')
        assert not errors,errors
        result=dict(status='PASS',screens=screens,actual_gui=True,qt_errors=errors,scope='Authored controlled Linux actual Qt key/focus/modal/draft-save/preference operations, no Windows IME/device or private Illustrator qualification',fixture_preparation=['Authored demo template only','Locked scene uses original Main LOCK transaction and explicit save_draft','Supported draft CAS authors external revision; stale keystroke does not write','Keymap preference changes are explicit settings saves'],paid_services=False,automatic_training=False)
        (folder/'canvas-command-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        sys.excepthook=previous;case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=capture(args.folder);print(json.dumps({k:v for k,v in r.items() if k!='screens'},ensure_ascii=False))
