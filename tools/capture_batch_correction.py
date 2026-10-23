"""Actual source batch workbench, typed scope and real shared worker; authored fixtures."""
import argparse,copy,json,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture_source(folder):
    from unittest.mock import patch
    from PySide6.QtCore import Qt,QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QMessageBox
    from template_ai.storage import Library
    from test_batch_correction_gui import BatchCorrectionGuiTests
    from gui_wait import wait_for_gui
    case=BatchCorrectionGuiTests('runTest');case.setUp();d=case.make(3);w=case.w;app=QApplication.instance();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);screens=[];errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error))
    def shot(widget,name):
        app.processEvents();path=folder/('batch-correction-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    def confirm(name,yes=True):
        def respond():
            box=QApplication.activeModalWidget()
            try:
                assert isinstance(box,QMessageBox);shot(box,name);box.button(QMessageBox.Yes if yes else QMessageBox.No).click()
            except BaseException as error:errors.append(str(error))
            finally:
                if box and box.isVisible():box.reject()
        QTimer.singleShot(0,respond)
    release=threading.Event()
    try:
        # Explicit authored locked scenario; no automatic unlock or source-file edit.
        work=case.works[1];payload=copy.deepcopy(work['payload']);payload['slots'][0]['locked']=True;w.library.save_artwork(work['id'],payload,work['revision']);d.reload();w.resize(1360,940);w.show();d.show();app.processEvents();shot(d,'01-loaded-coverage-no-global-claim')
        case.check(case.works[0],2);case.check(case.works[1]);case.check(case.works[2]);d.table.sortItems(2,Qt.DescendingOrder);d.search.setText('phone');assert len(d.selected_rows())==3;shot(d,'02-filtered-hidden-explicit-selection')
        d.preview();assert d.plan and sum(r['state']=='READY' for r in d.plan['rows'])==2;shot(d,'03-real-preflight-fixed-font-differences')
        key='ARTWORK:'+case.works[0]['id']+':'+case.works[0]['payload']['slots'][2]['id'];index=next(i for i in range(d.table.rowCount()) if d.table.item(i,0).data(Qt.UserRole)==key);d.table.setCurrentCell(index,1);graphic=d.make_graphic_preview();graphic.show();app.processEvents();shot(graphic,'03a-source-readonly-before-after');graphic.close();graphic.deleteLater()
        before={work['id']:w.library.object_snapshot('ARTWORK',work['id']) for work in case.works};confirm('04-real-cancel-scope-confirmation',False);d.apply();assert not d.running;assert all(w.library.object_snapshot('ARTWORK',key)==value for key,value in before.items())
        started=threading.Event();real=Library.apply_object_edit
        def hold(library,*args):
            started.set()
            if not release.wait(5):raise RuntimeError('Capture-owned write gate was not released')
            return real(library,*args)
        with patch.object(Library,'apply_object_edit',hold):
            confirm('05-real-approved-fixed-scope');d.apply();assert wait_for_gui(started.is_set,2);shot(d,'06-real-shared-worker-processing');release.set();assert wait_for_gui(lambda:not d.running,5)
        assert sum(r['outcome']=='APPLIED_PENDING_FULL_VALIDATION' for r in d.results)==2 and sum(r['outcome']=='NEEDS_MANUAL_REVIEW' for r in d.results)==1;shot(d,'07-partial-results-no-full-pass')
        after={work['id']:w.library.object_snapshot('ARTWORK',work['id']) for work in case.works};confirm('08-real-safe-retry-confirmation');d.apply();assert wait_for_gui(lambda:not d.running,5);assert all(w.library.object_snapshot('ARTWORK',key)==value for key,value in after.items());shot(d,'09-operation-readback-no-duplicate-write')
        case.check(case.works[1],checked=False);case.check(case.works[2],checked=False);confirm('10-real-single-transaction-inverse-scope');d.undo();assert wait_for_gui(lambda:not d.running,5);assert w.library.artwork(case.works[0]['id'])['payload']['slots'][2]['align']=='left';assert w.library.artwork(case.works[2]['id'])['payload']['slots'][0]['align']=='center';shot(d,'11-single-inverse-retains-other-success')
        key='ARTWORK:'+case.works[1]['id']+':'+case.works[1]['payload']['slots'][0]['id'];d.search.clear();index=next(i for i in range(d.table.rowCount()) if d.table.item(i,0).data(Qt.UserRole)==key);d.table.setCurrentCell(index,2);d.locate();assert w.current_slot.id==case.works[1]['payload']['slots'][0]['id'] and w.current_slot.locked
        controls=[w.font_input,w.pt,w.text_color,w.scale,w.align,w.property_policy_button];assert wait_for_gui(lambda:all(b.geometry().top()>a.geometry().bottom() for a,b in zip(controls,controls[1:])),3);shot(w,'12-exact-locked-source-existing-location')
        assert not errors,errors
        result=dict(status='PASS',screens=screens,actual_gui=True,qt_errors=errors,scope='UI065 source-stage only: authored controlled Linux actual Qt dialogs, existing shared worker/owned SQLite, source transactions and exact original history; no complete UI065/candidate/recovery/Windows/private Illustrator qualification',fixture_preparation=['Three authored SVG source works; one explicit locked metadata setup','Actual Library.apply_object_edit temporarily waits on owned Event to expose processing; original write executes after release, not a simulated outcome'],paid_services=False,automatic_training=False)
        (folder/'batch-correction-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        release.set();sys.excepthook=previous;case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def capture_candidate(folder):
    from PySide6.QtCore import Qt,QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog
    from test_batch_candidate_gui import BatchCandidateGuiTests
    from gui_wait import wait_for_gui
    from template_ai.batch_recovery import store
    case=BatchCandidateGuiTests('runTest');case.setUp();d=case.d;f=case.f;app=QApplication.instance();folder=Path(folder);screens=[];errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error))
    def shot(widget,name):
        app.processEvents();path=folder/('batch-correction-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    def confirm(name,yes=True):
        def respond():
            box=QApplication.activeModalWidget()
            try:
                assert isinstance(box,QMessageBox);shot(box,name);box.button(QMessageBox.Yes if yes else QMessageBox.No).click()
            except BaseException as error:errors.append(str(error))
            finally:
                if box and box.isVisible():box.reject()
        QTimer.singleShot(0,respond)
    def password(name):
        def respond():
            box=QApplication.activeModalWidget()
            try:
                assert isinstance(box,QInputDialog);box.setTextValue('synthetic-batch-password');shot(box,name);box.accept()
            except BaseException as error:errors.append(str(error));box.reject()
        QTimer.singleShot(0,respond)
    try:
        d.resize(1280,940);d.show();app.processEvents();shot(d,'13-candidate-exact-sizes-and-context')
        ids={name:case.check(name) for name in ('A90','B90','C100')};case.check('C100','logo','c2');d.search.setText('phone');assert len(d.selected_rows())==4;shot(d,'14-candidate-filter-retains-hidden-logo')
        case.preview();assert sum(r['state']=='READY' for r in d.plan['rows'])==2;d.search.clear();shot(d,'15-candidate-preflight-own-geometry-fixed-font')
        index=next(i for i in range(d.table.rowCount()) if d.by_key[d.table.item(i,0).data(Qt.UserRole)]['slot_ids']==[ids['A90']]);d.table.setCurrentCell(index,1);graphic=d.make_graphic_preview();graphic.show();app.processEvents();shot(graphic,'16-original-canvas-readonly-before-after');graphic.close();graphic.deleteLater()
        before={name:copy.deepcopy(f.candidate(name).template.to_dict()) for name in ('A90','B90','C100')};confirm('17-candidate-real-no-confirmation',False);d.apply();assert not d.running;assert all(f.candidate(name).template.to_dict()==value for name,value in before.items())
        confirm('18-candidate-real-yes-confirmation');d.apply();case.wait();assert sum(r['outcome']=='APPLIED_VALIDATED' for r in d.results)==2;assert not f.candidate('C100').formal_eligible;shot(d,'19-two-qualified-one-manual-no-batch-pass')
        histories={name:copy.deepcopy(f.candidate(name).risk_context.get('manual_history')) for name in ('A90','B90')};confirm('20-candidate-real-retry-confirmation');d.apply();case.wait();assert sum(r['outcome']=='ALREADY_APPLIED' for r in d.results)==2;assert all(f.candidate(name).risk_context.get('manual_history')==value for name,value in histories.items());shot(d,'21-exact-receipts-no-duplicate-geometry')
        password('22-real-encrypted-stop-password');d.recovery_controller.save();case.wait();assert store(f.w.library.root).pending();assert hasattr(d,'batch_recovery_receipt');shot(d,'23-actual-ciphertext-readback-receipt')
        password('24-real-recovery-password')
        def restore_confirm():
            box=QApplication.activeModalWidget()
            if isinstance(box,QMessageBox):shot(box,'25-real-recovery-scope-confirmation');box.button(QMessageBox.Yes).click()
            elif d.running:QTimer.singleShot(20,restore_confirm)
        QTimer.singleShot(20,restore_confirm);d.recovery_controller.restore();case.wait();assert sum(r['outcome']=='ALREADY_APPLIED' for r in d.results)==2;shot(d,'26-recovery-verified-receipts-unverified-others')
        b=copy.deepcopy(f.candidate('B90').template.to_dict())
        for i in range(d.table.rowCount()):
            item=d.table.item(i,0);row=d.by_key[item.data(Qt.UserRole)]
            if row['id']!=f.candidate('A90').template.id:item.setCheckState(Qt.Unchecked)
        confirm('27-selected-original-transaction-inverse');d.undo();case.wait();assert f.candidate('B90').template.to_dict()==b;assert next(s for s in f.candidate('A90').template.slots if s.id==ids['A90']).align=='left';shot(d,'28-partial-inverse-retains-other-candidate')
        assert not errors,errors
        result=dict(status='PASS',screens=screens,qt_errors=errors,actual_gui=True,actual_existing_shared_worker=True,paid_services=False,scope='UI065 candidate/size original engine, real Qt No/Yes/password/restore/inverse, authored synthetic Linux fixtures; no Windows/private Illustrator qualification')
        (folder/'batch-candidate-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        sys.excepthook=previous;case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def capture(folder):
    source=capture_source(folder);candidate=capture_candidate(folder);folder=Path(folder)
    (folder/'batch-source-metadata.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n')
    result=dict(status='PASS',screens=source['screens']+candidate['screens'],actual_gui=True,qt_errors=source['qt_errors']+candidate['qt_errors'],stages=['SOURCE','CANDIDATE_SIZE','STOPPED_ENCRYPTED_RECOVERY'],scope='UI065 actual authored Linux original workbench/worker/current per-target engine/read-only previews/real confirmations/receipt retry/partial inverse/typed encrypted stopped recovery; no Windows16GB RTX5050/VivoBook or private native Illustrator qualification',paid_services=False)
    (folder/'batch-correction-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=capture(args.folder);print(json.dumps({k:v for k,v in r.items() if k!='screens'},ensure_ascii=False))
