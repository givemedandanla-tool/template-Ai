"""Real Windows GUI/worker acceptance with authored synthetic artwork only."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

def run(output):
    output.mkdir(exist_ok=False)
    from template_ai.review_tool.diagnostics import LocalQtDiagnostics
    diagnostics=LocalQtDiagnostics(output/'diagnostics',role='test')
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtTest import QTest
    from template_ai.review_tool.window import ReviewWindow
    from template_ai.review_tool.native_reader import digest
    app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False)
    from template_ai.review_tool.ui_font import configure_ui_font
    configure_ui_font(app)
    def save_close(target):
        timer=QTimer();timer.setInterval(50)
        def accept_save():
            dialog=app.activeModalWidget()
            if isinstance(dialog,QMessageBox):
                button=next((b for b in dialog.buttons() if b.text()=='保存後離開'),None)
                if button is not None:QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        timer.timeout.connect(accept_save);timer.start()
        try:target.close();app.processEvents()
        finally:timer.stop()
    source=output/'synthetic.svg';source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="180pt" height="90pt" viewBox="0 0 180 90"><rect width="180" height="90" fill="white"/><text x="12" y="30" font-family="ArialMT" font-size="12">SYNTHETIC ARTWORK</text><text x="12" y="55" font-family="ArialMT" font-size="10">test@example.com</text></svg>')
    before=digest(source);window=ReviewWindow(output/'session');checks={};started=time.monotonic()
    try:
        window.show();window.add_files([str(source)]);app.processEvents()
        QTest.mouseClick(window.start_button,Qt.MouseButton.LeftButton)
        deadline=time.monotonic()+480
        while window.jobs.is_running() and time.monotonic()<deadline:
            app.processEvents();time.sleep(.02)
        assert not window.jobs.is_running(),'Native GUI read timed out'
        works=window.store.works();assert works and works[0]['fields'],'No real native results in GUI'
        cap=window.store.sources()[0]['analysis']['capabilities']
        assert cap['adobe_native']['isolation']['capability_count']==0
        assert not cap['inkscape_conversion_executed'];checks['actual_qprocess_native_result']=True
        work=works[0];field=work['fields'][0];window.select_work(work['id']);app.processEvents()
        QTest.mouseClick(window.canvas.viewport(),Qt.MouseButton.LeftButton,pos=window.canvas.field_center(field['id']));app.processEvents()
        assert window.text_edit.toPlainText()==field['text'];checks['canvas_editor_link']=True
        window.text_edit.setPlainText('SYNTHETIC LOCAL CORRECTION');QTest.mouseClick(window.apply_field_button,Qt.MouseButton.LeftButton);app.processEvents()
        assert window.store.get_field(work['id'],field['id'])['text']=='SYNTHETIC LOCAL CORRECTION'
        assert window.save_progress();checks['edit_save']=True
        assert window.grab().save(str(output/'synthetic-window.png'))
        assert not any('Illustrator' in action.text() for action in window.more_button.menu().actions());checks['no_com_menu']=True
        safe=json.dumps(window.store.safe_report());assert 'SYNTHETIC LOCAL CORRECTION' not in safe and str(output) not in safe;checks['safe_report']=True
        save_close(window);reopened=ReviewWindow(output/'session')
        try:
            assert reopened.store.get_field(work['id'],field['id'])['text']=='SYNTHETIC LOCAL CORRECTION';checks['reopen_preserves_edit']=True
        finally:save_close(reopened)
        assert digest(source)==before;checks['source_unchanged']=True
        summary=dict(passed=True,checks=checks,seconds=round(time.monotonic()-started,2),diagnostics=diagnostics.safe_summary())
        (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps(summary))
    finally:
        if window.jobs.is_running():window.jobs.stop()
        window.save_progress();save_close(window);diagnostics.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
