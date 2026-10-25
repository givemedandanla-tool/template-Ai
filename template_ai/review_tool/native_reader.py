"""Local native input route. Adobe code runs only inside a verified OS boundary."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
import re
import xml.etree.ElementTree as ET

from .native_isolation import WindowsIsolation, IsolationError, local_staging_path, worker_environment

AILIB_SHA256='fb1ded30ca8b3034f91a835ab09ca440d1ab545e193d27897629164d5970d2c2'
LINGUISTIC_SHA256='4d1ccfe62d3261bb61b10ec097a40e90702b67ba3ee2fc4e2a0a9678ff36e00e'

class NativeReaderError(RuntimeError):
    def __init__(self,code,message):
        super().__init__(message);self.code=code;self.safe_message=message

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def svg_preflight(source):
    root=ET.parse(source).getroot();nodes=list(root.iter())
    if len(nodes)>4000:raise NativeReaderError('NATIVE_SVG_BUDGET','SVG 超過本次結構判讀預算。')
    families=[];css=[]
    for n in nodes:
        for key,value in n.attrib.items():
            if key.rsplit('}',1)[-1] in ('href','src') and not value.startswith(('#','data:')):
                raise NativeReaderError('NATIVE_EXTERNAL_RESOURCE','作品含外部資源，請先將圖片與字型內嵌。')
        if n.get('font-family'):families.append(n.get('font-family'))
        css.append(n.get('style',''))
        if n.tag.rsplit('}',1)[-1]=='style':css.append(n.text or '')
    combined='\n'.join(css)
    if re.search(r'(?:^|[;{])\s*font\s*:',combined,re.I) or 'var(' in combined:
        raise NativeReaderError('NATIVE_FONT_DECLARATION_UNRESOLVED','SVG 字型簡寫或變數尚無法核對；請展開 font-family 宣告。')
    families+=re.findall(r'font-family\s*:\s*([^;}]+)',combined,re.I)
    generic={'serif','sans-serif','monospace','cursive','fantasy','system-ui','inherit','initial','unset'}
    # Check the first requested face, not a silently accepted fallback face.
    names={value.split(',')[0].strip().removesuffix('!important').strip().strip('\"\'') for value in families}
    return sorted(name for name in names if name and name.casefold() not in generic)

def configuration():
    default=Path(__file__).resolve().parents[2]/'.local/review-native.json'
    path=Path(os.environ.get('TEMPLATE_AI_NATIVE_CONFIG',str(default)))
    from ..offline_runtime import assert_local_path
    assert_local_path(path)
    if not path.is_file():
        raise NativeReaderError('NATIVE_SETUP_REQUIRED','尚未準備本機離線讀取引擎，請先執行原生讀取環境準備。')
    local_staging_path(path)
    if path.stat().st_size>65536:raise IsolationError('Invalid native configuration')
    config=json.loads(path.read_text(encoding='utf8'));root=local_staging_path(config['root'])
    manifest=root/'runtime-manifest.local.json'
    if digest(manifest)!=config['manifest_sha256']:raise IsolationError('Runtime manifest changed')
    entries=json.loads(manifest.read_text(encoding='utf8'))['files']
    actual={p.relative_to(root).as_posix() for name in ('engine','python','support') for p in (root/name).rglob('*') if p.is_file()}
    if actual!=set(entries):raise IsolationError('Runtime inventory changed')
    for name,expected in entries.items():
        p=local_staging_path(root/name)
        if root not in p.parents or digest(p)!=expected:raise IsolationError('Runtime bytes changed')
    binary=root/'engine/Support Files/Contents/Windows'
    if digest(binary/'AILib.dll')!=AILIB_SHA256 or digest(binary/'AdobeLinguistic.dll')!=LINGUISTIC_SHA256:
        raise IsolationError('Unsupported native engine')
    return root,config

def read_document(source,*,timeout=240,cancelled=None):
    """One document, one OS-isolated process, new outputs and no fallback."""
    from ..offline_runtime import assert_local_document,assert_local_path
    assert_local_path(source);source=local_staging_path(source)
    if source.suffix.lower() not in ('.ai','.pdf','.svg','.eps') or source.stat().st_size>200_000_000:
        raise NativeReaderError('NATIVE_INPUT_UNSUPPORTED','這個格式或檔案大小尚未支援。')
    assert_local_document(source)
    declared_fonts=svg_preflight(source) if source.suffix.lower()=='.svg' else []
    root,config=configuration();before=digest(source)
    job=root/'jobs'/uuid.uuid4().hex;job.mkdir(parents=True,exist_ok=False)
    inputs=job/'input';inputs.mkdir();copy=inputs/('source'+source.suffix.lower());shutil.copyfile(source,copy)
    if digest(copy)!=before or digest(source)!=before:raise IsolationError('Source changed during staging')
    code=job/'code';code.mkdir()
    for p in Path(__file__).with_name('native_worker').glob('*.py'):shutil.copyfile(p,code/p.name)
    output=job/'output';output.mkdir();temp=output/'tmp';temp.mkdir()
    container=WindowsIsolation(root)
    try:
        for p in (root/'engine',root/'python',root/'support',inputs,code):container.grant(p)
        container.grant(output,writable=True)
        env=worker_environment(temp,root/'python');env['REVIEW_PROBE_FONT_DIR']=str(root/'support/fonts')
        env['REVIEW_SOURCE_FONT_FAMILIES']=json.dumps(declared_fonts,ensure_ascii=True)
        helper=root/'engine/Support Files/Contents/Windows/ReviewToolNativeReader.exe'
        proof=container.run([helper,code/'guarded.py','--runtime',root/'engine','--input-dir',inputs,'--source',copy,'--output',output/'result'],env,cwd=output,timeout=timeout,cancelled=cancelled)
        (job/'containment.local.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    finally:container.close()
    if digest(source)!=before or digest(copy)!=before:raise IsolationError('Source changed while reading')
    result=output/'result';font_file=result/'native-fonts.local.json'
    fonts=json.loads(font_file.read_text(encoding='utf8')) if font_file.is_file() else {}
    if fonts.get('status')=='MISSING_FONTS':
        # Font names are user-facing local diagnostics, never a safe upload payload.
        raise NativeReaderError('NATIVE_MISSING_FONTS','缺少字型，已停止以免替換作品：'+', '.join(fonts['missing']))
    if proof['stop_reason'] or proof['exit_code']:
        raise NativeReaderError('NATIVE_READ_FAILED','離線讀取未完成或逾時；原稿未變更，本機診斷已保留。')
    summary=json.loads((result/'summary.json').read_text(encoding='utf8'))
    if summary.get('status')!='EXPORTED' or summary.get('source_sha256')!=before or summary['observation']['visible_window_classes']:
        raise NativeReaderError('NATIVE_OUTPUT_UNVERIFIED','讀取結果未通過檢查，已保留本機診斷。')
    pdf=result/'document.pdf';svg=result/'document.svg'
    if (digest(pdf)!=summary['export']['sha256'] or digest(svg)!=summary['export']['svg']['sha256']
            or pdf.stat().st_size>200_000_000 or svg.stat().st_size>32_000_000):raise IsolationError('Output hash or size invalid')
    # Never allow derived SVG to cause network or arbitrary local resource reads.
    import xml.etree.ElementTree as ET
    svg_root=ET.parse(svg).getroot()
    for n in svg_root.iter():
        for k,v in n.attrib.items():
            if k.rsplit('}',1)[-1] in ('href','src') and not v.startswith(('#','data:')):
                raise NativeReaderError('NATIVE_EXTERNAL_RESOURCE','作品含未內嵌的外部資源，請先將資源內嵌。')
    assert_local_document(svg,require_svg=True)
    artwork=json.loads((result/'artwork.local.json').read_text(encoding='utf8'))
    return dict(pdf=str(pdf),svg=str(svg),pdf_sha256=digest(pdf),svg_sha256=digest(svg),source_sha256=before,
                artboards=artwork['artboards'],artboard_count=artwork['artboard_count'],fonts=fonts,
                containment=proof,diagnostics=str(job),manifest_sha256=config['manifest_sha256'])

def import_page(source,assets,document,page):
    """Render Adobe's PDF; semantics remain explicitly derived, not original AI."""
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtCore import QSize
    from .source_compatibility import visible_pdf_page
    import xml.etree.ElementTree as ET
    from ..offline_runtime import assert_local_document
    if digest(source)!=document['source_sha256'] or digest(document['pdf'])!=document['pdf_sha256']:
        raise IsolationError('Native source or derivative changed')
    pdf=QPdfDocument()
    try:
        if pdf.load(document['pdf'])!=QPdfDocument.Error.None_ or not 1<=page<=pdf.pageCount()<=100:
            raise NativeReaderError('NATIVE_PDF_INVALID','離線輸出尚未取得可讀取的作品頁面。')
        if pdf.pageCount()!=document['artboard_count']:raise IsolationError('Artboard/page count mismatch')
        if visible_pdf_page(Path(document['pdf']),page).get('language'):
            raise NativeReaderError('NATIVE_NOTICE_ONLY','原生讀取仍只有 PDF 相容提示，尚未取得作品。')
        size=pdf.pagePointSize(page-1);w=size.width();h=size.height()
        if not 0<w<=20000 or not 0<h<=20000:raise IsolationError('Unsupported page size')
        folder=Path(assets)/('native-'+uuid.uuid4().hex);folder.mkdir(parents=True)
        scale=min(1600/w,1600/h);image=pdf.render(page-1,QSize(max(1,round(w*scale)),max(1,round(h*scale))))
        image_path=folder/'preview.png'
        if image.isNull() or not image.save(str(image_path),'PNG'):raise IsolationError('Preview render failed')
        count=pdf.pageCount()
    finally:pdf.close()
    if digest(document['svg'])!=document['svg_sha256']:raise IsolationError('Native SVG changed')
    root=ET.parse(document['svg']).getroot()
    board=document['artboards'][page-1]['f64'];first=document['artboards'][0]['f64']
    # AI has y-up coordinates; SVG has y-down coordinates from the first board.
    root.set('viewBox',f'{board[0]-first[0]} {first[1]-board[1]} {w} {h}')
    root.set('width',f'{w}pt');root.set('height',f'{h}pt')
    svg=folder/'semantic.svg';ET.ElementTree(root).write(svg,encoding='utf-8',xml_declaration=True)
    assert_local_document(svg,require_svg=True)
    return dict(hash=document['source_sha256'],image=str(image_path),svg=str(svg),semantic_svg=str(svg),
        width_mm=w*25.4/72,height_mm=h*25.4/72,page=page,page_count=count,calibrated=True,
        engine='Adobe CC 2020 native / isolated offline',renderer_execution='CONTAINED_ADOBE_NATIVE',
        recovery=dict(source_kind='NATIVE_ADOBE',semantic_status='DERIVED_PDF_GLYPHS',fidelity_status='USER_REVIEW_REQUIRED',issues=[]),
        native_derivative=dict(pdf=document['pdf'],sha256=document['pdf_sha256'],source_sha256=document['source_sha256'],
                               policy='ZERO_CAPABILITIES_ONE_DOCUMENT',manifest_sha256=document['manifest_sha256']),
        file_hashes=dict(image=digest(image_path),svg=digest(svg),semantic_svg=digest(svg)))
