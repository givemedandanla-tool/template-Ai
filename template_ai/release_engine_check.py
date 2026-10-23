"""Authored-fixture-only checks of the real frozen converter, never a substitute engine."""
import json
from pathlib import Path
import subprocess
import sys


def exercise(root, output, phase):
    from .inkscape_runtime import bundled_runtime
    from .importer import import_file, _run
    info = bundled_runtime()
    selected = Path(info['executable']).resolve()
    calls = []
    original = subprocess.run
    def observe(command, *args, **kwargs):
        if isinstance(command, (list, tuple)) and command and Path(command[0]).name.lower() in {'inkscape.exe', 'inkscape.com'}:
            actual = Path(command[0]).resolve()
            if actual != selected:
                raise ValueError('Actual converter call escaped the verified bundle')
            calls.append('engines/inkscape/bin/'+actual.name)
        return original(command, *args, **kwargs)
    work = root/('engine-'+phase)
    work.mkdir()
    svg = work/'authored.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 900 540"><rect id="known" x="10" y="20" width="300" height="100"/><text x="30" y="200">Example 123</text></svg>', encoding='utf-8')
    subprocess.run = observe
    try:
        first = import_file(svg, work/'assets')
        if first.get('renderer_execution') != 'SELECTED_INKSCAPE_CONVERSION_SUCCEEDED':
            raise ValueError('SVG silently fell back instead of exercising bundled Inkscape')
        geometry = _run(str(selected), [str(svg), '--query-all'], work)
        if not any(line.startswith('known,') for line in geometry.splitlines()):
            raise ValueError('Actual bundled geometry query failed')
        pdf = work/'authored.pdf'
        _run(str(selected), [str(svg), '--export-type=pdf', '--export-filename='+str(pdf)], work)
        ai = work/'authored-pdf-compatible.ai'
        ai.write_bytes(pdf.read_bytes())
        second = import_file(ai, work/'ai-assets')
        if second.get('renderer_execution') != 'SELECTED_INKSCAPE_CONVERSION_SUCCEEDED':
            raise ValueError('PDF-compatible AI did not use bundled Inkscape')
        if len(calls) < 5:
            raise ValueError('Insufficient actual converter observations')
        result = dict(status='PASS', phase=phase, actual_callees=sorted(set(calls)), calls=len(calls),
                      svg_conversion=True, geometry_query=True, pdf_compatible_ai_conversion=True,
                      bundle_manifest_sha256=info['runtime_manifest_sha256'], verified_files=info['verified_files'],
                      external_override_present=bool(__import__('os').environ.get('TEMPLATE_AI_INKSCAPE')),
                      scope='ACTUAL_FROZEN_EXECUTABLE_AUTHORED_FIXTURES_ONLY')
        (output/('bundled-engine-'+phase+'.json')).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    finally:
        subprocess.run = original


def invalid(root, output):
    from .inkscape_runtime import inkscape_path, runtime_report
    from .importer import import_file
    from PySide6.QtGui import QImage
    try:
        inkscape_path()
    except ValueError:
        pass
    else:
        raise ValueError('Broken bundle unexpectedly selected a converter')
    info = runtime_report()
    if info['state'] != 'UNAVAILABLE' or info['error_code'] != 'BUNDLED_RUNTIME_INVALID':
        raise ValueError('Broken bundle cannot be safely reported')
    source = root/'invalid-source.svg'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"/>')
    try:
        import_file(source, root/'vector-assets')
    except ValueError:
        pass
    else:
        raise ValueError('Broken bundle silently used an external converter or fallback')
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(0xffffff)
    image.save(str(root/'raster.png'))
    if not Path(import_file(root/'raster.png', root/'raster-assets')['image']).is_file():
        raise ValueError('Broken vector engine blocked independent raster input')
    (output/'invalid-engine.json').write_text(json.dumps(dict(status='PASS', vector_blocked=True,
         safe_report_available=True, raster_available=True, runtime=info), indent=2)+'\n', encoding='utf-8')
    return 0
