"""Capture the real existing property widgets and safety dialogs, authored data only."""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from PySide6.QtCore import Qt,QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtTest import QTest
    from test_property_context import PropertyContextTests,CandidatePropertyGateTests
    from template_ai.object_dialog import ObjectToolsDialog
    from template_ai.candidate_results import problem_rows,locate_problem
    from gui_wait import close_property_dialog
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    case=PropertyContextTests('runTest');case.setUp();w=case.w;app=QApplication.instance()
    errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));screens=[];dialogs=[];output=None
    def shot(widget,name):
        app.processEvents();path=folder/('property-context-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    def answer(name,button):
        def callback():
            box=next(d for d in QApplication.topLevelWidgets() if isinstance(d,QMessageBox) and d.isVisible())
            try:
                shot(box,name)
                target=next(b for b in box.buttons() if button in b.text());target.click()
            except BaseException as error:errors.append(str(error));box.reject()
        QTimer.singleShot(0,callback)
    try:
        w.resize(1360,940);case.sync();original=w.template.to_dict();stored=w.library.object_snapshot('TEMPLATE',case.draft.id)
        assert w.pt.value()==18 and w.font_input.isEnabled();shot(w,'01-text-fixed-size')
        w.property_pin_checks['text'].setChecked(True);logo=case.logo();before=copy.deepcopy(logo)
        assert not w.scale.isEnabled() and not w.font_input.isEnabled();assert '尚未核實' in w.property_context_label.text();shot(w,'02-logo-pinned-text-inapplicable')
        w.all_property_tools.setChecked(True);case.sync();assert logo==before;shot(w,'03-all-original-properties')
        # Reset authored fixture geometry, not a user navigation or hidden save.
        w.template=None;w.refresh_templates(case.draft.id);w.editor_selection(case.ids[:2]);case.sync()
        assert not w.pt.isEnabled() and w.pt.cleanText()=='';shot(w,'04-mixed-exact-selection')
        w.editor_selection([case.ids[0]]);case.sync();w.coords[0].setValue(12);case.sync();assert w.template.slots[0].rect.x==8
        shot(w,'05-unapplied-original-object')
        answer('06-real-selection-stay','返回目前物件繼續編輯');w.editor_selection([case.ids[1]])
        assert w.current_slot.id==case.ids[0] and w.coords[0].value()==12 and w.template.slots[0].rect.x==8
        w.resize(960,640);w.workspace_splitter.setSizes([140,590,220]);case.sync();w.property_panel.ensureWidgetVisible(w.property_button);QTest.qWait(20)
        assert not w.property_button.visibleRegion().isEmpty();shot(w,'07-narrow-scroll-apply')
        w.resize(1360,940);w.tabs.setCurrentIndex(0);changed=copy.deepcopy(w.template);changed.slots[0].rect.x=11
        w.library.save_template(changed,expected_revision=w.template_revision);w.template=None;w.refresh_templates(changed.id);w.tabs.setCurrentIndex(1);case.sync()
        assert w.coords[0].value()==11 and w.pending_property_conflict['values']['coords'][0]==12;shot(w,'08-new-source-old-input-retained')
        answer('09-real-readonly-conflict','保留供核對');w.right_context.inspect_conflict();assert w.pending_property_conflict
        d=ObjectToolsDialog(w,'TEMPLATE',case.draft.id);dialogs.append(d);d.show();d.select_ids(case.ids[:2]);app.processEvents();shot(d,'10-existing-mixed-property-editor')
        d.select_ids([case.ids[0]]);d.editors['x'].setValue(14)
        answer('11-real-editor-close-stay','返回目前物件繼續編輯');assert not d.close();assert d.editors['x'].value()==14
        changed=copy.deepcopy(w.template);changed.name+=' authored external revision';w.library.save_template(changed)
        d.update_context();assert d.canvas.readonly and not d.apply_button.isEnabled() and d.retained_patch['patch']['x']==14;shot(d,'12-stale-editor-retained-patch')
        output=CandidatePropertyGateTests('runTest');output.setUp();output.ready();bad=output.another(width=.1);o=output.w;o.resize(1360,940)
        row=next(r for r in problem_rows(o,1) if r['kind']=='name' and r['slot_ids']);locate_problem(o,row,open_input=False);app.processEvents();o.right_context.sync()
        assert o.right_context.problem_row['slot_ids']==row['slot_ids'] and not o.export_button.isEnabled();shot(o,'13-exact-local-problem-blocked')
        selected=next(item for item in bad.items if item.slot.id in row['slot_ids']);assert str(selected.text) in o.selected_info.text();o.property_panel.ensureWidgetVisible(o.selected_info);app.processEvents();shot(o,'14-current-exact-text-readonly')
        digest=bad.risk['digest'];o.property_pin_checks['text'].setChecked(True);o.all_property_tools.setChecked(True)
        for group in o.property_groups.values():group.setChecked(False)
        o.property_panel.hide();app.processEvents();assert not o.export_button.isEnabled() and bad.risk['digest']==digest and not bad.formal_eligible;shot(o,'15-hidden-panel-keeps-formal-gate')
        assert stored['payload']==original and not errors,errors
        result=dict(status='PASS',screens=screens,qt_errors=errors,actual_gui=True,scope='Authored controlled Linux Qt widgets, actual focus/dialog/selection and draft-CAS scenarios; no Windows/device/private Illustrator qualification',fixture_preparation=['Synthetic Logo frame only; explicitly unverified asset','Reset synthetic model from existing stored draft before mixed scene','Supported draft CAS simulates external source revision, never a user navigation action'],paid_services=False,automatic_training=False)
        (folder/'property-context-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        for dialog in reversed(dialogs):close_property_dialog(dialog)
        if output:output.doCleanups()
        sys.excepthook=previous;case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=capture(args.folder);print(json.dumps({k:v for k,v in r.items() if k!='screens'},ensure_ascii=False))
