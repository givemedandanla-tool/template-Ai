"""Actual Qt/SQLite capture for UI051, with current-host metrics and synthetic sources."""
import json,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture_runtime(folder):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    import test_automatic_training as fixture
    from template_ai.gui import MainWindow
    from template_ai.runtime_panel import RuntimePanel
    from template_ai.review_ledger_dialog import ReviewLedgerDialog
    case=fixture.AutomaticTrainingTests('runTest');case.setUp();window=panel=ledger=None;folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    def wait(predicate,timeout=20):
        deadline=time.monotonic()+timeout
        while not predicate():
            QApplication.processEvents();QTest.qWait(20)
            if time.monotonic()>deadline:raise RuntimeError('UI051 capture condition timed out')
    def shot(widget,name):
        widget.show();QApplication.processEvents()
        if not widget.grab().save(str(folder/name)):raise RuntimeError('UI051 Qt screenshot failed')
    try:
        alias=case.path.with_name('B0002.svg');alias.write_bytes(case.path.read_bytes());job=case.job([case.path,alias]);window=MainWindow(case.library.root);window.show();panel=RuntimePanel(window);panel.resize(1280,860);panel.show()
        wait(lambda:window.runtime.monitor.snapshot() is not None and window.runtime.monitor.snapshot().sequence>=2)
        panel.change(True);request=window.execution_queue.submit('AUTO_JOB',job,'SYNTHETIC_CAPTURE');QApplication.processEvents();panel.refresh()
        if window.execution_queue.queue.get(request['id'])['state']!='WAITING' or case.service.get(job['id'])['phase']!='READY':raise RuntimeError('paused scope was incorrectly started')
        shot(panel,'remaining28-runtime-paused-queue.png');measurement=window.runtime.state()
        panel.change(False);wait(lambda:window.execution_queue.queue.get(request['id'])['state']=='DONE');panel.refresh();shot(panel,'remaining28-runtime-fifo-results.png')
        sources=case.library.list_sources();units=case.service.store.records('AUTO_UNIT')
        if len(sources)!=2 or len({s['id'] for s in sources})!=2 or len(units)!=4 or any(case.service.store.facts(u['work_id'])['confirmation'] is not None for u in units):raise RuntimeError('actual aliases or review independence failed')
        before=window.library.db.total_changes;ledger=ReviewLedgerDialog(window);ledger.show();wait(lambda:ledger.snapshot is not None);shot(ledger,'remaining28-runtime-source-ledger.png')
        ledger.table.selectRow(0);ledger.open_works();wait(lambda:ledger.snapshot['mode']=='WORK');ledger.table.selectRow(0)
        if ledger.snapshot['total']!=2 or ledger.snapshot['page_reviewed']!=0:raise RuntimeError('analysis incorrectly counted as human review')
        shot(ledger,'remaining28-runtime-human-review.png')
        if window.library.db.total_changes!=before:raise RuntimeError('read-only ledger changed source/model/ownership data')
        report=dict(status='PASS',kind='ACTUAL_QT_SQLITE_AND_CURRENT_HOST_PROBE_WITH_SYNTHETIC_SOURCES',parent='UI-051',queue_request=window.execution_queue.queue.get(request['id']),source_ids=[s['id'] for s in sources],unit_ids=[u['id'] for u in units],actual_current_host_measurement=measurement,source_pages=2,recorded_work_units=4,human_reviewed=0,ledger_read_only=True,reference_hardware_verified=False,windows_verified=False,independent_review=False)
        (folder/'remaining28-runtime-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
    finally:
        if ledger:
            ledger.close()
            if ledger.process:ledger.process.waitForFinished(2000)
        if panel:panel.close()
        if window:window.source=None;window.work=None;window.template=None;window.close()
        case.tearDown();QApplication.processEvents()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',required=True);args=parser.parse_args();print(json.dumps(dict(status=capture_runtime(args.artifacts_dir)['status'])))
