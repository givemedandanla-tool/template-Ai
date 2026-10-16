"""Actual original shared font centre; Linux does not qualify Windows install."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]

def capture(folder):
    from unittest.mock import patch
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog
    from test_font_source_context_gui import FontSourceContextGuiTests
    from gui_wait import wait_for_gui
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);screens=[];errors=[];old=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));case=FontSourceContextGuiTests('runTest')
    def shot(widget,name):
        QApplication.processEvents();path=folder/('font-source-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    def rights_responses(responses):
        queue=list(responses)
        def answer():
            box=QApplication.activeModalWidget()
            try:
                name,value=queue.pop(0);assert isinstance(box,QMessageBox);assert box.defaultButton()==box.button(QMessageBox.No);shot(box,name);box.button(value).click()
                if queue:QTimer.singleShot(0,answer)
            except BaseException as error:
                errors.append(str(error))
                if box:box.reject()
        QTimer.singleShot(0,answer)
    try:
        case.setUp();d=case.d;d.resize(1320,900);before=[t.to_dict() for t in case.window.library.templates()];shot(d,'01-original-centre-unknown-source-use')
        case.reference();d.verify_source_identity();case.wait();assert d.identity_report['state']=='PROVEN_SAME_BYTES';assert d.identity_report['original_ai_font_relation']=='UNVERIFIED';shot(d,'02-actual-reference-file-and-face-not-native-origin')
        d.text.setText('A1');d.analyze();case.wait();d.glyph.setCurrentIndex(d.glyph.findData('COVERED'));assert len(d.visible_rows)==1;shot(d,'03-measured-current-glyph-covered')
        d.text.setText('\U0010ffff');assert not d.measurements and not d.visible_rows;d.glyph.setCurrentIndex(d.glyph.findData(None));d.table.selectRow(0);d.analyze();case.wait();d.glyph.setCurrentIndex(d.glyph.findData('MISSING'));assert len(d.visible_rows)==1;shot(d,'04-real-missing-glyph-no-old-coverage')
        d.glyph.setCurrentIndex(d.glyph.findData(None));d.table.selectRow(0)
        rights_responses([('05-pdf-rights-default-no',QMessageBox.No),('06-final-rights-default-no',QMessageBox.No)])
        with patch.object(QInputDialog,'getText',side_effect=[('SYNTHETIC_SOURCE_AUTHOR',True),('Authored font source/use record for this synthetic workflow',True)]):d.attest_rights()
        assert not case.window.library.fonts()[0].get('usage_rights')
        rights_responses([('07-pdf-rights-explicit-yes',QMessageBox.Yes),('08-final-rights-explicit-yes',QMessageBox.Yes)])
        with patch.object(QInputDialog,'getText',side_effect=[('SYNTHETIC_SOURCE_AUTHOR',True),('Authored font source/use record for this synthetic workflow',True)]):d.attest_rights()
        case.wait();d.rights.setCurrentIndex(d.rights.findData('PDF_RECORDED'));assert len(d.visible_rows)==1;d.table.selectRow(0);shot(d,'09-recorded-rights-filter-original-template-unchanged')
        assert [t.to_dict() for t in case.window.library.templates()]==before;assert not d.windows_button.isEnabled();d.open_windows_workflow();assert d.windows_receipt is None;shot(d,'10-linux-windows-action-unavailable-no-install')
        assert not errors,errors
        result=dict(status='PASS',screens=screens,qt_errors=errors,actual_gui=True,original_templates_unchanged=True,actual_windows_system_install_verified=False,scope='Actual Linux original shared font centre, real source/face, current glyph filters and real defaultNo No/Yes rights dialogs. No native AI identity or Windows installation outcome qualified.',paid_services=False)
        (folder/'font-source-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        sys.excepthook=old
        if hasattr(case,'window'):case.window.navigation.confirm_close=lambda:True
        case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=capture(args.folder);print(json.dumps({k:v for k,v in r.items() if k!='screens'},ensure_ascii=False))
