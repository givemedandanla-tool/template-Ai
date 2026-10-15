"""Exercise the shipped reader and safe writer with anonymous synthetic data, no raw locator export."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from template_ai.gui import MainWindow
from template_ai.demo import demo_template
from template_ai.diagnostic_dialog import DiagnosticReportDialog
from template_ai.diagnostic_bundle import read_bundle,encoded,sha
from template_ai.importer import import_file
from template_ai.model import Rect


def capture(root):
    app=QApplication.instance() or QApplication([]);root=Path(root);root.mkdir(parents=True,exist_ok=True)
    def wait(dialog):
        end=time.monotonic()+8
        while dialog.raw is None and not dialog.status.text().startswith(('未完成','未產生')) and time.monotonic()<end:
            app.processEvents();QTest.qWait(10)
        if dialog.raw is None:raise ValueError('actual report GUI did not produce payload: '+dialog.status.text())
    window=MainWindow(root/'diagnostic-local-data');template=demo_template();window.library.publish(template)
    for j,v in enumerate(('X'*200,'Designer','+12025550100','alex@example.test','','','','')):window.people.setItem(0,j,QTableWidgetItem(v))
    window.generate();before=window.library.templates()[0].to_dict();gate=window.export_button.isEnabled()
    d=DiagnosticReportDialog(window,'candidate');d.show();wait(d);app.processEvents()
    assert d.data['status']=='BLOCKED' and not gate
    assert d.grab().save(str(root/'diagnostic-preview.png'))
    (root/'diagnostic-safe-report.json').write_bytes(encoded(d.data))
    path=root/'diagnostic-safe-report.zip'
    with patch('template_ai.diagnostic_dialog.QFileDialog.getSaveFileName',return_value=(str(path),'')):QTest.mouseClick(d.save_button,Qt.LeftButton)
    assert path.is_file() and '已完整保存' in d.status.text()
    reopened=DiagnosticReportDialog(window,loaded=path.read_bytes());reopened.show();app.processEvents()
    assert reopened.data==d.data and not reopened.refresh_button.isEnabled()
    assert reopened.grab().save(str(root/'diagnostic-saved-reopened.png'))
    window.people.item(0,0).setText('Casey Example')
    QTest.mouseClick(d.save_button,Qt.LeftButton);assert '異動' in d.status.text()
    assert d.grab().save(str(root/'diagnostic-stale-refused.png'))
    source_path=root/'anonymous-diagnostic-source.svg'
    source_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="90" height="54" fill="white"/></svg>')
    source=window.library.add_source(source_path,import_file(source_path,window.library.assets))
    work=window.library.create_artwork(source['id'],'Synthetic Example',{'crop':asdict(Rect(0,0,90,54)),'work_width':90,'work_height':54,'slots':[asdict(s) for s in template.slots],'visual_confirmed':False})
    quality=DiagnosticReportDialog(window,'training',work['id']);quality.show();wait(quality);app.processEvents()
    assert quality.data['stage']=='DATA_PROCESSING' and any(r['code']=='VISUAL_PENDING' for r in quality.data['issues'])
    assert quality.grab().save(str(root/'diagnostic-work-issues.png'))
    assert window.library.templates()[0].to_dict()==before and window.export_button.isEnabled()==gate
    raw=path.read_bytes();assert read_bundle(raw)==d.data
    audit={'schema_version':1,'evidence_kind':'ACTUAL_QT_DIALOG_AND_SAFE_FILE_FLOW','preview_matches_saved_json':True,
           'historical_reopened':True,'stale_save_refused':True,'original_gate_unchanged':True,'template_unchanged':True,
           'source_stage_issue_shown':True,'report_zip':{'bytes':len(raw),'sha256':sha(raw),'local_only':True},
           'issues':len(d.data['issues']),'measurement_rows':len(d.data['measurements']),'private_locator_exported':False}
    (root/'diagnostic-gui-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    for dialog in (d,reopened,quality):dialog.close();dialog.deleteLater()
    app.processEvents();window.input_timer.stop();window.library.db.close();window.deleteLater();app.processEvents()
    print(json.dumps(audit,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',required=True);capture(parser.parse_args().artifacts_dir)
