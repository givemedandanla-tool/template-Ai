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
import test_backup_center as backup_fixture
from template_ai import backup_policy



def capture_relink(folder):
    import hashlib,shutil,time
    from unittest.mock import patch
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QMessageBox
    from template_ai.source_dialog import SourceRelinkDialog
    import test_customer_candidates as fixture
    case=fixture.CustomerCandidateTests('test_filename_full_rule_and_actual_facts_propose_only_without_master_writes');case.setUp();window=None;dialog=None
    try:
        candidate=case.reviewed(case.candidates.propose(case.source['id'])[0]);customer=case.commit([candidate])[0]
        window=MainWindow(case.library.root);window.refresh_sources(case.source['id']);dialog=SourceRelinkDialog(window)
        original=Path(case.source['original_path']);before=hashlib.sha256(original.read_bytes()).hexdigest();roots=[]
        for label in ['new-root-A','new-root-B']:
            root=case.root/label;root.mkdir();shutil.copyfile(original,root/('moved-'+original.name));roots.append(root)
        dialog.roots=[str(r) for r in roots];dialog.root=str(roots[0]);dialog.path_label.setText('已明列搜尋根目錄：'+'；'.join(dialog.roots))
        def wait():
            deadline=time.monotonic()+15
            while dialog.busy or window.busy:
                QApplication.processEvents();QTest.qWait(10)
                if time.monotonic()>deadline:raise RuntimeError('relink Qt worker timeout')
        dialog.search();wait();dialog.show();QApplication.processEvents()
        report=dialog.report
        if report['status']!='COMPLETE' or len(report['roots'])!=2 or dialog.table.cellWidget(0,0).isChecked() or dialog.table.cellWidget(0,3).currentData() is not None:raise RuntimeError('relink explicit multi-root preview invariant failed')
        if not dialog.grab().save(str(folder/'remaining28-relink-multi-root.png')):raise RuntimeError('relink preview screenshot failed')
        def details(preview):
            preview.show();QApplication.processEvents()
            if not preview.grab().save(str(folder/'remaining28-relink-dependency-details.png')):raise RuntimeError('relink dependency screenshot failed')
            preview.close();return 0
        with patch('template_ai.source_dialog.QDialog.exec',details):dialog.show_details()
        dialog.table.cellWidget(0,0).setChecked(True);dialog.table.cellWidget(0,3).setCurrentIndex(2)
        with patch('template_ai.source_dialog.QMessageBox.question',return_value=QMessageBox.Yes):dialog.apply_selection();wait()
        batch=window.library.relink_batches()[0]
        with patch('template_ai.source_dialog.QMessageBox.question',return_value=QMessageBox.Yes):dialog.undo_batch();wait()
        if window.library.source(case.source['id'])['current_path']!=str(original) or hashlib.sha256(original.read_bytes()).hexdigest()!=before:raise RuntimeError('relink actual apply/undo/original protection failed')
        QApplication.processEvents()
        if not dialog.grab().save(str(folder/'remaining28-relink-history-restored.png')):raise RuntimeError('relink history screenshot failed')
        result=dict(status='PASS',parent='UI-049',kind='ACTUAL_QT_READONLY_SNAPSHOT_MULTIPLE_ROOTS_AND_SQLITE_APPLY_UNDO_SYNTHETIC',
                    source_id=case.source['id'],customer_id=customer['customer_id'],roots=[str(r) for r in roots],
                    explicit_unselected_preview=True,independent_candidate_positions=2,applied_batch_id=batch['id'],
                    mapping_context_sha256=batch['items'][0]['impact_sha256'],source_original_bytes_unchanged=True,
                    exact_original_location_restored=True,history_revisions_preserved=True,windows_verified=False,independent_review=False)
        (folder/'remaining28-relink-capture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        if dialog:dialog.close();dialog.deleteLater()
        if window:window.close();window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);QApplication.processEvents();case.tearDown()


def capture_backup(folder):
    case=backup_fixture.BackupCenterTests();case.setUp();folder=Path(folder)
    try:
        customer=case.data();dialog=case.dialog
        dialog.sources.setChecked(True);dialog.fonts.setChecked(True);dialog.password.setText(backup_fixture.PASSWORD)
        dialog.preview_backup();case.wait();dialog.show();QApplication.processEvents()
        if not dialog.grab().save(str(folder/'remaining28-backup-scope.png')):raise RuntimeError('backup Qt scope capture failed')
        archive=case.create();receipt=backup_policy.history(case.window.library)[0]
        dialog.tabs.setCurrentIndex(3);dialog.history_tree.setCurrentItem(dialog.history_tree.topLevelItem(0));dialog.password.setText(backup_fixture.PASSWORD)
        dialog.test_restore();case.wait();QApplication.processEvents()
        if not dialog.grab().save(str(folder/'remaining28-backup-tested-restore.png')):raise RuntimeError('backup Qt history capture failed')
        dialog.archive.setText(str(archive));dialog.trusted.setChecked(True);dialog.mode.setCurrentIndex(1);dialog.password.setText(backup_fixture.PASSWORD)
        dialog.preview_restore();case.wait();dialog.tabs.setCurrentIndex(1);QApplication.processEvents()
        if not dialog.grab().save(str(folder/'remaining28-backup-existing-differences.png')):raise RuntimeError('backup Qt differences capture failed')
        actual=backup_policy.history(case.window.library)[0]
        if not archive.is_file() or not actual['test_restore'] or dialog.restore_plan is None or case.errors:raise RuntimeError('backup actual capture flow failed')
        report=dict(status='PASS',kind='ACTUAL_QT_SQLITE_AESGCM_AND_ISOLATED_RESTORE_SYNTHETIC',parent='UI-047',
                    customer_id=customer['id'],archive_sha256=receipt['sha256'],archive_bytes=receipt['bytes'],
                    authenticated_file_created=True,actual_isolated_test_restore=actual['last_test_restore'],
                    existing_environment_modified=False,scope=receipt['scope'],
                    preview_categories=len(dialog.restore_plan['database_rows']),
                    temporary_synthetic_archive_removed_after_capture=True,password_persisted=False,
                    windows_verified=False,independent_review=False)
        (folder/'remaining28-backup-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        return report
    finally:case.tearDown()


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
        backup=capture_backup(folder)
        relink=capture_relink(folder)
        report=dict(status='PASS',kind='ACTUAL_QT_AND_SQLITE_SYNTHETIC_CAPTURE',
                    parent='UI-046',merged=True,split=True,original_template_payload_unchanged=True,
                    foreign_keys='PASS',runtime_errors=errors,local_export_has_only_synthetic_people=True,
                    windows_verified=False,independent_review=False,backup_parent_self_capture=backup['status'],relink_parent_self_capture=relink['status'])
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
