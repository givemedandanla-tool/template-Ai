"""Actual original canvas/property panel and per-row format QA; authored data."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]

def capture(folder):
    from unittest.mock import patch
    from PySide6.QtCore import Qt,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QMessageBox
    from test_digital_preflight_gui import DigitalPreflightGuiTests
    from test_batch_format_review_gui import BatchFormatReviewGuiTests
    from template_ai.digital_output_proof import pdf_evidence
    from gui_wait import wait_for_gui
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);screens=[];errors=[]
    previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error))
    main=DigitalPreflightGuiTests('runTest');batch=None
    def shot(widget,name):
        QApplication.processEvents();path=folder/('digital-preflight-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    try:
        main.setUp();w=main.w;p=main.p;w.dpi.setValue(300);w.resize(1420,1060);shot(w,'01-original-canvas-unchecked-guides')
        p.format.setCurrentText('PDF');main.inspect();assert not p.review_consent.isChecked();assert not w.export_button.isEnabled();shot(w,'02-actual-pdf-checklist-no-consent')
        index=next(i for i in range(p.objects.count()) if 'logo' in p.objects.itemText(i).lower());p.objects.setCurrentIndex(index);p.open_detail();main.wait();assert p.detail;shot(p.detail,'03-logo-source-vector-and-actual-pdf');p.detail.close()
        index=next(i for i in range(p.objects.count()) if 'name' in p.objects.itemText(i).lower());p.objects.setCurrentIndex(index);p.open_detail();main.wait();shot(p.detail,'04-text-source-and-actual-pdf');p.detail.close()
        p.review_actor.setText('SYNTHETIC_SOURCE_AUTHOR');p.review_evidence.setText('Authored people/company, full Logo, text, same-format original-size PDF inspected');p.confirm_review();assert p.review_receipt is None;shot(w,'05-default-no-formal-still-blocked')
        p.review_consent.setChecked(True);p.confirm_review();main.wait();assert p.review_receipt and w.export_button.isEnabled();shot(w,'06-explicit-current-format-review')
        target=folder/'digital-preflight-authored-FINAL.pdf';failures=[]
        with patch('template_ai.gui.QFileDialog.getSaveFileName',return_value=(str(target),'PDF (*.pdf)')),patch.object(w,'error',side_effect=failures.append):w.export_current(False)
        assert not failures and target.is_file(),failures;pdf=pdf_evidence(target);assert pdf['all_fonts_embedded'] and pdf['vector_operator_count']>0;shot(w,'07-original-final-export-readback')
        w.dpi.setValue(150);assert p.proof is None and p.review_receipt is None and not w.export_button.isEnabled();shot(w,'08-new-dpi-clears-old-review')
        p.format.setCurrentText('PNG');main.inspect();shot(w,'09-lossless-png-proof-current-size')
        row=next(i for i in range(p.table.rowCount()) if p.table.item(i,0).data(Qt.UserRole)['code']=='LOGO_SOURCE');p.table.selectRow(row);p.locate();shot(w,'10-exact-logo-locator')
        batch=BatchFormatReviewGuiTests('runTest');batch.setUp();r=batch.make();shot(r,'11-original-batch-target-default-no');batch.inspect();shot(r,'12-batch-same-format-proof')
        r.open_detail();batch.wait();assert r.detail;shot(r.detail,'13-batch-source-and-actual-format');r.detail.close()
        r.actor.setText('SYNTHETIC_SOURCE_AUTHOR');r.evidence.setText('Selected batch row actual96DPI PDF/Logo source inspected');r.consent.setChecked(True);r.confirm();batch.wait();assert len(batch.workflow.format_reviews)==1;shot(r,'14-exact-batch-row-review')
        batch.d.dpi.setValue(150);r.confirm();assert '具名證據' in r.status.text();shot(r,'15-batch-new-dpi-rejects-old-snapshot')
        assert not errors,errors
        result=dict(status='PASS',screens=screens,actual_gui=True,qt_errors=errors,final_pdf=dict(fonts_embedded=pdf['all_fonts_embedded'],vector_operator_count=pdf['vector_operator_count']),scope='Authored Linux Qt original canvas/right pane/batch row only. Screen detail is not physical printing or Windows hardware qualification.',paid_services=False)
        (folder/'digital-preflight-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        sys.excepthook=previous
        if batch:
            if getattr(batch,'r',None) and batch.r.detail:batch.r.detail.close()
            batch.tearDown();batch.doCleanups()
        if hasattr(main,'w'):main.w.navigation.confirm_close=lambda:True
        main.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=capture(args.folder);print(json.dumps({k:v for k,v in r.items() if k!='screens'},ensure_ascii=False))
