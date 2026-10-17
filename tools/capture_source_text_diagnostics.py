"""Actual original annotation canvas and shared font centre; no native AI claims."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from unittest.mock import patch
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QDialog
    from test_source_text_diagnostics import SourceTextDiagnosticsGuiTests
    from template_ai.font_dialog import FontCenterDialog
    from gui_wait import wait_for_gui
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);screens=[];errors=[];old=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));case=SourceTextDiagnosticsGuiTests('runTest')
    def shot(widget,name):
        QApplication.processEvents();p=folder/('source-text-'+name+'.png');assert widget.grab().save(str(p));screens.append(p.name)
    try:
        case.setUp();case.path.write_text(case.path.read_text().replace('id="nameA"','id="nameA" font-family="DejaVu Sans" letter-spacing="0.1" style="paint-order:stroke;stroke-width:0.05"'))
        window,d=case.ready();d.resize(1660,1060);slot=next(s for s in d.session.payload['slots'] if s['kind']=='name');d.select([slot['id']]);d.details.setMinimumHeight(280);d.canvas.fit();shot(d,'01-original-object-source-literal-unknown-native')
        before=case.path.read_bytes();payload=json.dumps(d.session.payload,sort_keys=True);d.value.setText('UNSAVED LOCAL DRAFT')
        def visit(center):
            def check():
                try:
                    assert wait_for_gui(lambda:not center.busy and not window.busy,15);assert center.source_context['proof']['native_editability']=='UNKNOWN';assert center.visible_rows;assert center.query.text()=='DejaVu Sans';center.resize(1380,940);shot(center,'02-shared-centre-source-object-not-original-font-proof')
                except BaseException as e:errors.append(str(e))
                finally:center.reject()
            QTimer.singleShot(0,check);return QDialog.exec(center)
        with patch.object(FontCenterDialog,'exec',visit):d.source_font_diagnosis()
        assert d.value.text()=='UNSAVED LOCAL DRAFT';assert json.dumps(d.session.payload,sort_keys=True)==payload;assert case.path.read_bytes()==before;shot(d,'03-unsaved-local-draft-preserved-no-asset-change')
        logo=next(s for s in d.session.payload['slots'] if s['kind']=='logo');d.select([logo['id']]);d.source_font_diagnosis();assert 'Logo' in d.status.text();shot(d,'04-whole-logo-font-action-refused')
        assert not errors,errors
        result=dict(status='PASS',screens=screens,actual_gui=True,qt_errors=errors,source_and_payload_unchanged=True,scope='Authored SVG through actual Inkscape source-analysis and original annotation/font centre. Native Illustrator private editability/original font and actual Windows hardware remain NOT_VERIFIED.',paid_services=False)
        (folder/'source-text-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        sys.excepthook=old;case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',required=True);a=p.parse_args();print(json.dumps(capture(a.folder),ensure_ascii=False))
