"""Real marked preview encoding/readback; never a parallel formal exporter.

The original exporter keeps the card body unchanged and puts diagnostic text
outside it. PDF/JPEG differences are measurements, not perceptual approval.
"""
import math,shutil,tempfile
from collections import Counter
from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument
from .background import file_digest
from .digital_preflight import inspect_candidate,validate_scope,options

MAX_COMPARE_PIXELS=1_000_000


def rgb_bytes(image):
    image=image.convertToFormat(QImage.Format_RGB888);data=image.constBits();stride=image.bytesPerLine();width=image.width()*3
    return b''.join(bytes(data[y*stride:y*stride+width]) for y in range(image.height()))


def compare_images(reference,actual):
    if reference.isNull() or actual.isNull() or reference.size()!=actual.size():raise ValueError('實際比對影像尺寸不符／無法讀回，未插值補成一致')
    pixels=reference.width()*reference.height()
    if pixels>MAX_COMPARE_PIXELS:return dict(status='NOT_CHECKED',reason='超過100萬實際像素比對預算，需明列局部區域；未偷偷降採樣',pixels=pixels)
    total=squares=maximum=changed=0
    for a,b in zip(rgb_bytes(reference),rgb_bytes(actual)):
        difference=abs(a-b);total+=difference;squares+=difference*difference;maximum=max(maximum,difference);changed+=difference!=0
    n=pixels*3
    return dict(status='MEASURED',pixels=pixels,channels=3,mse=squares/n,mae=total/n,max_absolute_error=maximum,changed_channels=changed,exact_equal=not changed,perceptual_quality_approved=False,physical_print_verified=False)


def pdf_evidence(path):
    """Use existing pypdf resources/ContentStream, not a custom PDF parser."""
    from pypdf import PdfReader
    from pypdf.generic import ContentStream
    reader=PdfReader(str(path),strict=True)
    if len(reader.pages)!=1:raise ValueError('數位比較需確切單頁PDF')
    page=reader.pages[0];fonts=[];images=[];operators=Counter();seen=set();budget=0
    def resources(value,stream):
        nonlocal budget
        if stream is not None:
            contents=stream if hasattr(stream,'operations') else ContentStream(stream,reader)
            operators.update(operator.decode('ascii',errors='replace') for _,operator in contents.operations)
        if not value:return
        value=value.get_object();font_map=value.get('/Font',{});font_map=font_map.get_object() if hasattr(font_map,'get_object') else font_map
        for name,ref in font_map.items():
            font=ref.get_object();subtype=str(font.get('/Subtype'));faces=font.get('/DescendantFonts',[font]);embedded=[]
            for face in faces:
                face=face.get_object();descriptor=face.get('/FontDescriptor');descriptor=descriptor.get_object() if descriptor else {}
                embedded.append(any(bool(descriptor[k].get_object().get_data()) for k in ('/FontFile','/FontFile2','/FontFile3') if k in descriptor) or str(face.get('/Subtype'))=='/Type3' and bool(face.get('/CharProcs')))
            fonts.append(dict(resource=str(name),base_font=str(font.get('/BaseFont','')),subtype=subtype,embedded=bool(embedded) and all(embedded)))
        xobjects=value.get('/XObject',{});xobjects=xobjects.get_object() if hasattr(xobjects,'get_object') else xobjects
        for name,ref in xobjects.items():
            obj=ref.get_object();key=(getattr(ref,'idnum',None),getattr(ref,'generation',None)) if getattr(ref,'idnum',None) else id(obj)
            if key in seen:continue
            seen.add(key);budget+=1
            if budget>5000:raise ValueError('PDF資源超過5000件有界核對預算')
            if obj.get('/Subtype')=='/Image':images.append(dict(resource=str(name),width=int(obj.get('/Width',0)),height=int(obj.get('/Height',0)),filter=str(obj.get('/Filter','')),stream_digest=__import__('hashlib').sha256(obj.get_data()).hexdigest()))
            elif obj.get('/Subtype')=='/Form':resources(obj.get('/Resources'),obj)
    resources(page.get('/Resources'),page.get_contents())
    return dict(page_count=1,size_mm=[float(page.mediabox.width)*25.4/72,float(page.mediabox.height)*25.4/72],fonts=fonts,all_fonts_embedded=all(f['embedded'] for f in fonts),image_xobjects=images,vector_operator_count=sum(operators[k] for k in ('m','l','c','re','S','s','f','f*','B','B*')),text_operator_count=sum(operators[k] for k in ('Tj','TJ',"'",'"')),operator_histogram=dict(operators),pdfa_or_print_certified=False,individual_logo_fidelity_approved=False)


def decoded_image(path,size_mm,dpi):
    expected=QSize(*[max(1,round(v*dpi/25.4)) for v in size_mm]);path=Path(path)
    if expected.width()*expected.height()>24_000_000:raise ValueError('實際讀回超過像素預算')
    if path.suffix.lower()=='.pdf':
        document=QPdfDocument()
        try:
            if document.load(str(path))!=QPdfDocument.Error.None_ or document.pageCount()!=1:raise ValueError('PDF未能實際讀回單頁')
            size=document.pagePointSize(0)
            if any(abs(v*25.4/72-e)>.001 for v,e in zip((size.width(),size.height()),size_mm)):raise ValueError('實際PDF頁面毫米不符')
            image=document.render(0,expected)
        finally:document.close()
    else:image=QImage(str(path))
    if image.isNull() or image.size()!=expected:raise ValueError('實際編碼像素尺寸不符／損毀，未自動縮放補齊')
    return image


def build_proof(candidate,format,dpi,root):
    """A single selected format, real original marked preview, current byte receipt."""
    from .render import export,render_image,preview_height
    value=inspect_candidate(candidate,format,dpi);pin=value['scope'];root=Path(root);root.mkdir(parents=True,exist_ok=True);folder=Path(tempfile.mkdtemp(prefix='PREVIEW-preflight-',dir=root));path=folder/('PREVIEW-digital-output.'+pin['format'].lower())
    try:
        export(candidate,path,dpi,True,candidate.generation)
        page_mm=[candidate.template.width_mm,preview_height(candidate)];decoded=decoded_image(path,page_mm,dpi);width,height=pin['pixels'];body=decoded.copy(0,0,width,height);reference=render_image(candidate,dpi,False);metrics=compare_images(reference,body)
        pdf=pdf_evidence(path) if pin['format']=='PDF' else None
        validate_scope(candidate,pin)
        file=dict(path=str(path),sha256=file_digest(path),bytes=path.stat().st_size)
        exact_file=None
        if pin['format']!='PNG':
            exact_path=folder/('PREVIEW-exact-card.'+pin['format'].lower());export(candidate,exact_path,dpi,True,candidate.generation,exact_preview=True);decoded_image(exact_path,pin['size_mm'],dpi);exact_file=dict(path=str(exact_path),sha256=file_digest(exact_path),bytes=exact_path.stat().st_size)
            validate_scope(candidate,pin)
        for check in value['rows']:
            if check['code']=='ENCODED_FORMAT':check.update(status='PASS',reason='此診斷格式已實際編碼並讀回；附註在卡片外，尚非正式成品',measurements=dict(format=pin['format'],card_body_mm=pin['size_mm'],actual_preview_page_mm=page_mm))
            if check['code']=='PDF_FONT_EMBEDDING' and pdf:check.update(status='PASS' if pdf['all_fonts_embedded'] else 'BLOCKED',reason='實際PDF字型程式已讀回' if pdf['all_fonts_embedded'] else '實際PDF含未內嵌字型，需修正',measurements=dict(fonts=pdf['fonts']))
        consistent=metrics.get('exact_equal') is True
        value['rows'].append(dict(code='ENCODED_BODY_COMPARISON',status='PASS' if consistent else 'NOT_CHECKED' if metrics['status']=='NOT_CHECKED' else 'WARNING',reason='目前卡片本體逐像素一致；不等於原稿／印刷認證' if consistent else '已列實測差異或未涵蓋區域，需局部對照；不以任意分數自動核准',slot_ids=[],measurements=metrics))
        return dict(scope=pin,exact_file=exact_file,rows=value['rows'],file=file,preview_page_mm=page_mm,card_body_mm=pin['size_mm'],body_comparison=metrics,pdf=pdf,formal_output_allowed=False,output_written=False,diagnostic_preview_written=True,explicit_visual_review_required=True,physical_print_verified=False,reason='此檔含矩形外PREVIEW附註；只比對原尺寸卡片本體，不能把預覽頁面當正式成品尺寸')
    except BaseException:
        shutil.rmtree(folder);raise


def region_images(candidate,proof,slot_id):
    """Exact selected object's current source render and actual encoded crop."""
    from .render import render_image
    validate_scope(candidate,proof['scope']);file=proof.get('exact_file') or proof['file']
    if file_digest(file['path'])!=file['sha256']:raise ValueError('實際數位比較檔已變更，不能沿用舊憑證')
    matches=[p for p in candidate.items if p.slot.id==slot_id]
    if len(matches)!=1:raise ValueError('需確切唯一物件ID；不靠相同字串選取')
    dpi=proof['scope']['dpi'];rect=matches[0].slot.rect;page=decoded_image(file['path'],proof['scope']['size_mm'] if proof.get('exact_file') else proof['preview_page_mm'],dpi);source=render_image(candidate,dpi,False)
    x=max(0,math.floor(rect.x*dpi/25.4));y=max(0,math.floor(rect.y*dpi/25.4));right=min(source.width(),math.ceil((rect.x+rect.w)*dpi/25.4));bottom=min(source.height(),math.ceil((rect.y+rect.h)*dpi/25.4))
    if right<=x or bottom<=y:raise ValueError('物件實際區域無法核對')
    a=source.copy(x,y,right-x,bottom-y);b=page.copy(x,y,right-x,bottom-y)
    validate_scope(candidate,proof['scope'])
    if file_digest(file['path'])!=file['sha256']:raise ValueError('實際比較檔在讀回期間變更')
    return a,b,dict(slot_id=slot_id,region_mm=as_rect(rect),pixels=[right-x,bottom-y],metrics=compare_images(a,b),source_label='原繪圖引擎目前來源渲染；非原生Illustrator外觀認證',output_label='確切已編碼並讀回的物件區域')


def as_rect(rect):return dict(x=rect.x,y=rect.y,w=rect.w,h=rect.h)
