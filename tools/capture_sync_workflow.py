"""Native UI061 original scope, with authored marks and exact source identity."""
import argparse,json,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from unittest.mock import patch
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QPlainTextEdit,QPushButton,QMessageBox
    from PySide6.QtTest import QTest
    from sync_workflow_fixture import SyncWorkflowFixture,REVIEW
    from template_ai.candidate_edit import CandidateEditDialog
    from template_ai.input_graph_dialog import InputGraphDialog
    from template_ai.candidate_sync_dialog import CrossPropertyDialog
    from template_ai.importer import import_file
    f=SyncWorkflowFixture();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);app=QApplication.instance();errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));screens=[];dialogs=[];official={name:f.w.library.object_snapshot('TEMPLATE',t.id)['payload'] for name,t in f.templates.items()}
    def shot(widget,name):
        app.processEvents();path=folder/('sync-workflow-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    def approve(button):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(button,Qt.LeftButton)
    def editor(name):
        adapter,index,controller=f.controller(name);dialog=CandidateEditDialog(adapter,controller=controller);dialogs.append(dialog);dialog.show();dialog.objects.item(0).setSelected(True);return dialog
    def adopt(source):
        QTest.mouseClick(source.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton);f.w.adopt_input_graph(source.graph.data,history=source.graph)
    def preview(name,tag):
        f.select(name);real_exec=QDialog.exec
        def inspect(dialog):
            QTimer.singleShot(30,dialog,lambda:(shot(dialog,tag),dialog.reject()));return real_exec(dialog)
        with patch.object(QDialog,'exec',inspect):f.d.preview()
    try:
        f.w.resize(1360,940);f.w.show();f.w.tabs.setCurrentIndex(2);assert f.candidate('A90').formal_eligible and f.candidate('B90').formal_eligible;assert not f.candidate('C100').formal_eligible;shot(f.d,'01-two-people-companies-three-candidates-two-sizes')
        local=editor('A90');local.dx.setValue(1);QTest.mouseClick(local.preview_button,Qt.LeftButton);shot(local,'02-manual-a-only-actual-difference');approve(local.apply_button);f.wait();manual_x=f.candidate('A90').template.slots[0].rect.x;assert manual_x==4;assert f.candidate('B90').template.slots[0].rect.x==5;local.hide()
        source=InputGraphDialog(f.w);dialogs.append(source);source.show();entity=source.graph.data['people'][0]['id'];phone=next(field for field in source.graph.data['fields'] if field['owner_id']==entity and field['kind']=='phone');source.execute('edit_field',field_id=phone['id'],value='+12025550999');source.focus_field(phone['id'],entity);assert all(name in source.source_impacts.toPlainText() for name in ('A90','B90','C100'));shot(source,'03-exact-person-a-phone-consumers-before-adoption');adopt(source);assert not f.d.is_current();shot(f.d,'04-shared-source-stale-no-new-pass');f.sync()
        for name in f.templates:
            phones={item.slot.owner:item.text for item in f.candidate(name).items if item.slot.kind=='phone'};assert phones==dict(p1='+12025550999',p2='+12025550100')
        assert f.candidate('A90').template.slots[0].rect.x==manual_x;preview('A90','05-synced-phones-preserved-manual-a-and-logos');preview('C100','06-missing-beta-size-logo-stays-marked-preview')
        local=editor('A90');local.operation.setCurrentIndex(4);local.align.setCurrentText('center');QTest.mouseClick(local.preview_button,Qt.LeftButton);approve(local.apply_button);f.wait();local.hide();f.select('A90');cross=CrossPropertyDialog(f.d);dialogs.append(cross);cross.show()
        for row in range(cross.table.rowCount()):cross.table.item(row,0).setCheckState(Qt.Checked)
        QTest.mouseClick(cross.preview_button,Qt.LeftButton);shot(cross,'07-explicit-cross-target-differences-and-current-risks');before_c=copy.deepcopy(f.candidate('C100').template.to_dict());approve(cross.apply_button);f.wait();assert [r['state'] for r in cross.results]==['APPLIED_VERIFIED','VALIDATION_FAILED'];assert f.candidate('B90').template.slots[0].rect.x==5;assert f.candidate('B90').template.slots[0].align=='center';assert f.candidate('C100').template.to_dict()==before_c;shot(cross,'08-safe-b90-only-failed100-keeps-old-version');cross.hide()
        # Additional authored mark is fixture preparation, never inferred use.
        path=f.root/'authored-alpha-green.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm"><rect width="20" height="10" fill="#20a050"/></svg>');image=import_file(path,f.w.library.assets);payload=dict(image=image['image'],svg=image['svg'],source_width_mm=image['width_mm'],source_height_mm=image['height_mm'],crop=None);plan=f.store.propose(payload,90,54,company_id=f.registry[0]['id']);new=f.store.approve(plan['id'],plan['revision'],f.registry[0]['id'],REVIEW,True);graph=f.w.active_input_graph.clone();company=graph.data['companies'][0]['id'];graph.apply(graph.preview('edit_logo',company_id=company,logo_id=new['id']),True);f.w.adopt_input_graph(graph.data,history=graph);f.sync()
        for name in ('A90','B90'):
            logos={item.slot.owner:item.logo['id'] for item in f.candidate(name).items if item.logo};assert logos==dict(c1=new['id'],c2=f.assets[1,90]['id'])
        assert next(item.logo['id'] for item in f.candidate('C100').items if item.slot.owner=='c1')==f.assets[0,100]['id'];assert not f.candidate('C100').formal_eligible;preview('A90','09-explicit-alpha90-logo-beta90-unchanged-alpha100-independent')
        f.change_phone('+12025550777');f.sync();source=InputGraphDialog(f.w);dialogs.append(source);source.show();global_phone=f.w.active_input_graph.compile()[0][0]['phone'][0];real_exec=QDialog.exec
        def undo_inspect(dialog):
            def accept():
                assert all(name in dialog.findChild(QPlainTextEdit).toPlainText() for name in ('A90','B90','C100'));shot(dialog,'10-source-undo-all-true-consumers-confirmation');QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Yes),Qt.LeftButton)
            QTimer.singleShot(30,dialog,accept);return real_exec(dialog)
        with patch.object(QDialog,'exec',undo_inspect):QTest.mouseClick(source.undo_button,Qt.LeftButton)
        assert f.w.active_input_graph.compile()[0][0]['phone'][0]==global_phone;assert source.graph.compile()[0][0]['phone'][0]=='+12025550999';shot(source,'11-source-undo-remains-draft-until-adopted');adopt(source);f.sync();local=editor('B90');QTest.mouseClick(local.undo_button,Qt.LeftButton);approve(local.apply_button);f.wait();assert f.candidate('B90').template.slots[0].align=='left';assert f.candidate('A90').template.slots[0].align=='center';assert f.candidate('A90').template.slots[0].rect.x==manual_x;assert f.w.active_input_graph.compile()[0][0]['phone'][0]=='+12025550999';shot(local,'12-single-target-undo-keeps-source-and-other-manual');local.hide()
        output=f.root/'output';output.mkdir();requests=[dict(key=entry['key'],mode='FINAL' if entry['size_mm']==[90,54] else 'PREVIEW',formats=['png']) for entry in f.d.service.entries];plan=f.d.service.plan(output,requests);results=f.d.service.execute(plan,True,acknowledge_partial=True,current_check=f.d.is_current,dpi=96);assert [row['status'] for row in results]==['SUCCESS','SUCCESS'];assert {Path(row['path']).parent.name for row in results}=={'FINAL','PREVIEW'};f.d.details.setPlainText('\n'.join(row['mode']+'／'+Path(row['path']).name+'／'+row['status'] for row in results));shot(f.d,'13-actual-qualified90-final-and-failed100-separate-preview')
        assert all(f.w.library.object_snapshot('TEMPLATE',template.id)['payload']==official[name] for name,template in f.templates.items());assert not errors,errors
        report=dict(status='PASS',screens=screens,qt_uncaught=errors,scope='AUTHORED_SYNTHETIC_TWO_PEOPLE_TWO_COMPANIES_THREE_CANDIDATES_TWO_PHYSICAL_SIZES',reference_hardware_qualified=False,native_private_illustrator_qualified=False,source_preparation_excluded=True,original_templates_unchanged=True,source_identity='Stable entity and field IDs; same initial phone strings remain distinct',logo_update='Explicit approved Alpha90 changes only actual90 assets; Beta90/Alpha100 preserved; Beta100 stillmissing',single_existing_worker=True,automatic_training=False,paid_services=False)
        (folder/'sync-workflow-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
    finally:
        f.d.stop.set();f.w.pool.waitForDone(5000);app.processEvents();sys.excepthook=previous;f.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();result=capture(args.folder);print(json.dumps({k:v for k,v in result.items() if k!='screens'},ensure_ascii=False))
