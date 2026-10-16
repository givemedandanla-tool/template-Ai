"""Authored SVG/Qt/Inkscape comparison; measurements are not quality thresholds."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT)]

def run(folder):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QGuiApplication,QImage,QPainter
    from PySide6.QtSvg import QSvgRenderer
    from template_ai.digital_output_proof import compare_images
    from template_ai.digital_preflight import svg_characteristics
    app=QGuiApplication.instance() or QGuiApplication([])
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);rows=[]
    body='<rect width="200" height="100" fill="white"/><path d="M10 80 C35 0 70 100 100 30 S160 0 190 80" stroke="#124578" stroke-width="1.2" fill="none"/><circle cx="155" cy="55" r="22" fill="#c99e2d"/><path d="M130 55h50M155 30v50" stroke="#123456" stroke-width=".7"/>'
    for name,effect in [('native-curves',''),('effect-source',' filter="url(#blur)"')]:
        path=folder/(name+'.svg');path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 200 100"><defs><filter id="blur"><feGaussianBlur stdDeviation="4"/></filter></defs><g'+effect+'>'+body+'</g></svg>' if effect else '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 200 100">'+body+'</svg>')
        qt=QImage(600,300,QImage.Format_RGB32);qt.fill('white');p=QPainter(qt)
        try:QSvgRenderer(str(path)).render(p,QRectF(0,0,600,300))
        finally:p.end()
        qt_path=folder/(name+'-qt.png');assert qt.save(str(qt_path))
        external=folder/(name+'-inkscape.png')
        result=subprocess.run(['inkscape',str(path),'--export-type=png','--export-filename='+str(external),'--export-width=600','--export-height=300','--export-background=white','--export-background-opacity=1'],capture_output=True,text=True,timeout=40)
        if result.returncode:raise RuntimeError(result.stderr[-1000:])
        reference=QImage(str(external));assert reference.size()==qt.size()
        rows.append(dict(name=name,source=path.name,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_profile=svg_characteristics(path),qt=qt_path.name,independent_original_source_renderer=external.name,metrics=compare_images(qt,reference),perceptual_fidelity_approved=False))
    version=subprocess.run(['inkscape','--version'],capture_output=True,text=True,timeout=10).stdout.strip()
    report=dict(status='MEASURED',purpose='Authored source curves/effect comparison at exact pixels; no arbitrary perceptual cutoff and no hardware/physical print qualification',inkscape_version=version,rows=rows,paid_services=False)
    (folder/'source-poc.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=run(args.folder);print(json.dumps(dict(status=r['status'],rows=len(r['rows']),inkscape=r['inkscape_version'])))
