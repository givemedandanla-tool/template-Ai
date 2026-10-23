"""Precisely bounded PySide6 buffer/format binding compatibility, not image fidelity."""
import hashlib,json,os,platform,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6 import __version__
from PySide6.QtCore import QByteArray,QBuffer,QIODevice
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QApplication
app=QApplication.instance() or QApplication([])
data=QByteArray();buffer=QBuffer(data);assert buffer.open(QIODevice.WriteOnly)
image=QImage(2,2,QImage.Format_ARGB32);image.fill(0xff332211);assert image.save(buffer,'PNG');buffer.close()
raw=bytes(data);assert QImage.fromData(raw,'PNG').size()==image.size();assert raw.startswith(b'\x89PNG\r\n\x1a\n') and bytes(QByteArray(b'authored'))==b'authored'
pixmap=QPixmap();restored=QImage();assert pixmap.loadFromData(raw,'PNG') and restored.loadFromData(raw,'PNG');assert restored.size()==image.size() and restored.pixel(0,0)==image.pixel(0,0)
with tempfile.TemporaryDirectory() as temp:
 assert image.save(str(Path(temp)/'authored.png'),'PNG') and image.save(str(Path(temp)/'authored.jpg'),'JPEG',95)
 assert Path(temp,'authored.jpg').read_bytes().startswith(b'\xff\xd8')
 assert len(bytes(image.constScanLine(0)[:image.width()*4]))==image.width()*4
F=Path(__file__).resolve().parent;ROOT=F.parents[2];rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];dest=F/'qt-buffer-format-proof.json';proof=json.loads(dest.read_text()).get('proof',{}) if dest.exists() else {};old_count=len(proof)
format_save_locations={(r['original']['path'],r['original']['line']) for r in rows if r['rule']=='reportArgumentType' and 'format' in r['original']['message'] and any(t in r['original']['message'] for t in ['PNG','JPEG']) and '.save(' in r['original']['context']}
for r in rows:
 if r['status']!='UNREVIEWED':continue
 message=r['original']['message'];context=r['original']['context'];kind=None
 if 'QByteArray' in message and 'bytes(data)' in context:kind='QBYTEARRAY_BUFFER_PROTOCOL'
 elif 'loadFromData' in context and ('of type "Literal[\'PNG\']"' in message or message.startswith('No overloads for "loadFromData"')):kind='PYSIDE_STRING_PNG_FORMAT'
 elif 'image.save(buffer, "PNG")' in context and (message.startswith('No overloads for "save"') or 'Literal[\'PNG\']' in message):kind='PYSIDE_STRING_PNG_SAVE_FORMAT'
 if not kind and 'QImage.fromData(' in context and 'format' in message and 'PNG' in message:kind='PYSIDE_STATIC_STRING_PNG_FORMAT'
 if not kind and '.save(' in context and (r['original']['path'],r['original']['line']) in format_save_locations and ('format' in message or message.startswith('No overloads for "save"')):kind='PYSIDE_STRING_IMAGE_SAVE_FORMAT'
 if not kind and 'constScanLine' in context and r['rule'] in ['reportIndexIssue','reportArgumentType']:kind='QIMAGE_SCANLINE_MEMORYVIEW'
 if not kind:continue
 path=ROOT/r['original']['path'];proof[r['id']]=dict(original=r['original'],kind=kind,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),runtime=dict(python=platform.python_version(),pyside=__version__,qbytearray_buffer_pass=True,png_string_save_and_load_pass=True,decoded_size_and_pixel_equal=True),boundary='Only these actual buffer/PNG-format bindings on Linux PySide6 6.8.3; no Windows, arbitrary input or source fidelity qualification')
 r.update(status='TOOL_LIMITATION',severity='P2_PYSIDE_STUB_BUFFER_FORMAT',affected_workflow=r['original']['path'],root_cause_or_blocker='Pinned PySide6 binding accepts QByteArray buffer protocol and str PNG format; its supplied static overload signatures omit these accepted forms. Independent synthetic roundtrip preserved exact size/pixel. Existing decoding failure guards stay active.',evidence=['qt-buffer-format-proof.json#'+r['id']],repro_command_and_result='.venv/bin/python docs/dev/pre_download_audit/review_qt_binding_contracts.py: authored byte buffer and 2x2 PNG roundtrip PASS',regression_and_result='Existing project tests/captures remain separate from this binding demonstration',remaining_condition='Native Windows binding still deferred; no image/OCR/private-corpus quality claim')
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));(F/'qt-buffer-format-proof.json').write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('precise Qt binding occurrences',len(proof),'new',len(proof)-old_count)
