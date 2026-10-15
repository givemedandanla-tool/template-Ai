"""Actual Qt identity workbench and local synthetic audit export."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.customer_dialog import CustomerDialog
from test_customer_identity import CustomerIdentityTests


def capture(folder):
    app=QApplication.instance() or QApplication([]);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    errors=[];old=sys.excepthook
    sys.excepthook=lambda kind,value,tb:errors.append(str(value))
    case=CustomerIdentityTests();case.setUp();window=None;dialog=None
    try:
        before=case.library.template_snapshots();window=MainWindow(case.temp.name);dialog=CustomerDialog(window)
        plan=dialog.identity_service().plan_merge(case.a['id'],case.b['id'])
        dialog.identity_plan=plan
        dialog.status.setText('合併前完整影響預覽：2個獨立人物／公司、全部欄位、來源、版型與舊碼別名；尚未合併')
        dialog.show_identity_preview();app.processEvents()
        if not dialog.identity_preview.grab().save(str(folder/'remaining28-identity-merge-preview.png')):raise RuntimeError('Qt screenshot failed')
        dialog.identity_preview.close()
        result=dialog.identity_service().merge(plan,True,'SYNTHETIC_CAPTURE','Synthetic confirmed identity fixture')
        local=folder/'remaining28-identity-local-export.json'
        dialog.identity_service().export_event(result['id'],local,True)
        split=dialog.identity_service().plan_split(result['id']);dialog.identity_plan=split
        dialog.show_identity_preview();dialog.status.setText('拆分前目前值與原歸屬預覽：保留後續合法新值，歧義會阻擋')
        app.processEvents()
        if not dialog.identity_preview.grab().save(str(folder/'remaining28-identity-split-preview.png')):raise RuntimeError('Qt screenshot failed')
        dialog.identity_preview.close()
        final=dialog.identity_service().split(split,True,'SYNTHETIC_CAPTURE','Synthetic explicit split')
        if len(final['customers'])!=2 or case.library.template_snapshots()!=before or case.library.db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Capture actual identity invariants failed')
        dialog.close();dialog.deleteLater();dialog=None;window.close();window.deleteLater();window=None
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
        if errors:raise RuntimeError('Unhandled Qt capture error: '+str(errors))
        report=dict(status='PASS',kind='ACTUAL_QT_AND_SQLITE_SYNTHETIC_CAPTURE',
                    parent='UI-046',merged=True,split=True,original_template_payload_unchanged=True,
                    foreign_keys='PASS',runtime_errors=errors,local_export_has_only_synthetic_people=True,
                    windows_verified=False,independent_review=False)
        (folder/'remaining28-identity-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        return report
    finally:
        if dialog:dialog.close();dialog.deleteLater()
        if window:window.close();window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
        case.doCleanups();sys.excepthook=old


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',required=True)
    print(json.dumps(capture(parser.parse_args().artifacts_dir)))
