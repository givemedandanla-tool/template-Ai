"""Actual recovery UI and redacted support JSON, with owned synthetic content."""
import argparse,json,os,sys,tempfile,time
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


def capture(folder):
    from PySide6.QtWidgets import QApplication
    from template_ai.gui import MainWindow
    from template_ai.importer import import_file
    from template_ai.demo import demo_template
    from template_ai.model import Rect
    from template_ai.background import file_digest
    from template_ai.recovery_dialog import RecoveryDialog
    from template_ai.recovery_diagnostics import export_shareable
    app=QApplication.instance() or QApplication([]);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='owned-recovery-capture-') as directory:
        root=Path(directory);window=MainWindow(root/'isolated-data');dialog=None
        try:
            path=root/'owned.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><text x="8" y="14" font-family="DejaVu Sans" font-size="6.35">Alex Example</text></svg>')
            source=window.library.add_source(path,import_file(path,window.library.assets));source=window.library.source(source['id']);template=demo_template()
            work=window.library.create_artwork(source['id'],'Owned recovery capture',dict(crop=asdict(Rect(0,0,90,54)),work_width=90,work_height=54,slots=[asdict(s) for s in template.slots],visual_confirmed=True))
            dialog=RecoveryDialog(window,source,work=work,field=work['payload']['slots'][0],on_candidate=lambda *args:None)
            font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf');dialog.faces=[dict(path=str(font),sha256=file_digest(font),face_index=0)]
            dialog.catalog_complete=True;dialog.text.setText('Alex Example');dialog.verified.setChecked(True);dialog.show();dialog.match()
            deadline=time.monotonic()+20
            while dialog.worker is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            if dialog.worker is not None or not dialog.last_match or not dialog.last_match['candidates']:raise RuntimeError('Actual recovery GUI matching did not complete')
            app.processEvents();assert dialog.grab().save(str(folder/'local-recovery-desktop.png'))
            public=export_shareable(dialog.report,folder/'local-recovery-support.json')
            assert 'Alex Example' not in json.dumps(public) and str(root) not in json.dumps(public)
            (folder/'local-recovery-scope.json').write_text(json.dumps(dict(scope='ACTUAL_QT_UI_AND_OWNED_SYNTHETIC_FONT_MATCH_ONLY',no_real_user_data=True,production_qualification=False,match_status=dialog.last_match['status']),indent=2)+'\n')
        finally:
            if dialog:dialog.close()
            window.close();app.processEvents()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);capture(parser.parse_args().folder)
