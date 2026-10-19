"""Original PDF-compatible AI glyph placement through pinned pdfminer.six.

CID/text-state/matrix provenance is retained. Nominal glyph metric boxes are not
ink bounds, container capacity, native Illustrator editability or font licences.
"""
from __future__ import annotations
from io import BytesIO
import hashlib
import math

from .design_observation import ObservedScalar,canonical_digest,effective_point_size,unknown

VERSION='original-pdf-glyphs-1/pdfminer.six20260107'
MAX_GLYPHS=20000
MAX_RUNS=512
MAX_CONTENT_BYTES=16_000_000
MAX_FONT_BYTES=8_000_000
MM_PER_POINT=25.4/72


class GlyphBudget(ValueError):pass


def _number(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('Nonfinite PDF source metric')
    return result


def _name(value):
    value=getattr(value,'name',value)
    return (value.decode('utf-8','replace') if isinstance(value,bytes) else str(value))[:512]


def extract_pdf_glyphs(source,data,*,include_private_text=False):
    """Bounded interpretation of original bytes, never of converted SVG text."""
    if hashlib.sha256(data).hexdigest()!=source['hash'] or not data.startswith(b'%PDF-'):
        raise ValueError('Original PDF content identity differs')
    if len(data)>32_000_000:raise GlyphBudget('Original PDF processing byte budget exceeded')
    from pdfminer.pdfinterp import PDFResourceManager,PDFPageInterpreter
    from pdfminer.pdfpage import PDFPage
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.pdffont import PDFUnicodeNotDefined
    from pdfminer.pdftypes import resolve1,dict_value
    from pdfminer.utils import apply_matrix_pt
    from pdfminer.layout import LTChar
    import pdfminer
    if pdfminer.__version__!='20260107':raise ValueError('PDF glyph interpreter version is not pinned')
    page_number=source.get('page',1)
    if type(page_number) is not int or page_number<1:raise ValueError('Invalid source page')
    resources_meta={}

    class Resources(PDFResourceManager):
        def get_font(self,objid,spec):
            if len(resources_meta)>256:raise GlyphBudget('Source font resource processing budget exceeded')
            font=super().get_font(objid,spec)
            actual=dict_value(resolve1(spec['DescendantFonts'])[0]) if spec.get('DescendantFonts') else spec
            descriptor=dict_value(actual.get('FontDescriptor',{}))
            embedded=None
            for key in ('FontFile','FontFile2','FontFile3'):
                stream=resolve1(descriptor.get(key))
                if stream is not None:
                    program=stream.get_data()
                    if len(program)>MAX_FONT_BYTES:raise GlyphBudget('Embedded font processing budget exceeded')
                    embedded=dict(kind=key,sha256=hashlib.sha256(program).hexdigest());break
            resources_meta[id(font)]=dict(resource_object_id=objid,base_font=_name(actual.get('BaseFont',font.fontname)),
                subtype=_name(actual.get('Subtype','UNKNOWN')),embedded_program=embedded,
                font_asset_identity='UNKNOWN')
            return font

    class Device(PDFPageAggregator):
        def __init__(self,manager):
            super().__init__(manager,laparams=None);self.runs=[];self.active=None;self.count=0;self.depth=0;self.decoded_bytes=0
        def begin_page(self,page,ctm):
            super().begin_page(page,ctm)
            self.page_height=self.cur_item.height;self.page_width=self.cur_item.width
            self.user_unit=_number(page.attrs.get('UserUnit',1))
            if not 0<self.user_unit<=75000:raise ValueError('Invalid PDF UserUnit')
        def begin_figure(self,name,bbox,matrix):
            self.depth+=1
            if self.depth>16:raise GlyphBudget('Nested form processing budget exceeded')
            return super().begin_figure(name,bbox,matrix)
        def end_figure(self,name):
            super().end_figure(name);self.depth-=1
        def paint_path(self,*args,**kwargs):
            pass  # This reader does not collect graphic paths or claim Logo recognition.
        def render_image(self,*args,**kwargs):
            pass  # Large image payloads are not decoded for text observations.
        def render_string(self,textstate,seq,ncs,graphicstate):
            if len(self.runs)>=MAX_RUNS:raise GlyphBudget('Original text run processing budget exceeded')
            seq=list(seq)
            row=dict(index=len(self.runs),font=deepcopy_meta(resources_meta.get(id(textstate.font),{})),
                declared_fontsize=_number(textstate.fontsize),horizontal_scale=_number(textstate.scaling)*.01,
                charspace=_number(textstate.charspace),wordspace=_number(textstate.wordspace),
                rise=_number(textstate.rise),text_render_mode=int(textstate.render),glyphs=[],decoded=[],unicode_length=0)
            previous=self.active;self.active=row;self.runs.append(row)
            try:return super().render_string(textstate,seq,ncs,graphicstate)
            finally:self.active=previous
        def render_char(self,matrix,font,fontsize,scaling,rise,cid,ncs,graphicstate):
            if self.count>=MAX_GLYPHS:raise GlyphBudget('Original glyph processing budget exceeded')
            advance=super().render_char(matrix,font,fontsize,scaling,rise,cid,ncs,graphicstate)
            item=self.cur_item._objs[-1]
            if not isinstance(item,LTChar) or self.active is None:raise ValueError('No exact original character callback')
            matrix=tuple(_number(value) for value in matrix);unit=self.user_unit*MM_PER_POINT
            try:decoded=font.to_unichr(cid);unicode_status='MAPPED'
            except PDFUnicodeNotDefined:decoded='';unicode_status='UNKNOWN'
            row=self.active;start=row['unicode_length'];row['decoded'].append(decoded);row['unicode_length']+=len(decoded)
            anchor=apply_matrix_pt(matrix,(0,_number(rise)))
            x0,y0,x1,y1=item.bbox
            row['glyphs'].append(dict(cid=int(cid),unicode_span=[start,start+len(decoded)],unicode_status=unicode_status,
                text_matrix=list(matrix),origin_mm=dict(x=anchor[0]*unit,y=(self.page_height-anchor[1])*unit),
                metric_box_mm=dict(x=x0*unit,y=(self.page_height-y1)*unit,w=(x1-x0)*unit,h=(y1-y0)*unit),
                advance_in_text_space=_number(advance),writing_mode='VERTICAL' if font.is_vertical() else 'HORIZONTAL'))
            self.count+=1
            return advance

    class Interpreter(PDFPageInterpreter):
        def render_contents(self,resources,streams,ctm=None):
            streams=list(streams)
            for stream in streams:
                value=resolve1(stream)
                if value is None:continue
                self.device.decoded_bytes+=len(value.get_data())
                if self.device.decoded_bytes>MAX_CONTENT_BYTES:raise GlyphBudget('Decoded original content processing budget exceeded')
            return super().render_contents(resources,streams,ctm=ctm) if ctm is not None else super().render_contents(resources,streams)

    def deepcopy_meta(value):
        from copy import deepcopy
        return deepcopy(value)

    with BytesIO(data) as stream:
        pages=PDFPage.get_pages(stream,pagenos={page_number-1},check_extractable=True)
        page=next(pages,None)
        if page is None:raise ValueError('Original PDF page unavailable')
        manager=Resources(caching=False);device=Device(manager)
        try:Interpreter(manager,device).process_page(page)
        finally:device.close()
    unit=device.user_unit*MM_PER_POINT
    width,height=device.page_width*unit,device.page_height*unit
    canvas_verified=(math.isclose(width,source['width_mm'],abs_tol=1e-4)
                     and math.isclose(height,source['height_mm'],abs_tol=1e-4))
    runs=[]
    for raw in device.runs:
        glyphs=raw.pop('glyphs');decoded=''.join(raw.pop('decoded'))
        if not glyphs:continue
        ref='PDF_GLYPH_RUN:'+canonical_digest([source['hash'],page_number,raw['index'],VERSION])
        point=raw['declared_fontsize']
        declared=ObservedScalar(point,'pt','OBSERVED','ORIGINAL_PDF_TF_TEXT_STATE',(ref,)).to_dict() if point>0 else unknown('pt')
        matrix=glyphs[0]['text_matrix'];physical=tuple(v*device.user_unit if i<4 else v for i,v in enumerate(matrix))
        effective=effective_point_size(ObservedScalar(**{**declared,'evidence_refs':tuple(declared['evidence_refs'])}),physical).to_dict()
        if raw['font'].get('subtype') in ('Type3','UNKNOWN'):
            effective=unknown('pt',basis='UNSUPPORTED_FONT_MATRIX')
        boxes=[g['metric_box_mm'] for g in glyphs]
        x=min(box['x'] for box in boxes);y=min(box['y'] for box in boxes)
        right=max(box['x']+box['w'] for box in boxes);bottom=max(box['y']+box['h'] for box in boxes)
        known_scale=effective['value']/point if effective['value'] is not None and point else None
        row=dict(id=ref,source_locator=dict(kind='PDF_ORIGINAL_GLYPH_RUN',page=page_number,text_show_index=raw['index']),
            glyphs=glyphs,glyph_count=len(glyphs),text_sha256=hashlib.sha256(decoded.encode()).hexdigest(),decoded_character_count=len(decoded),
            unicode_status='MAPPED' if all(g['unicode_status']=='MAPPED' for g in glyphs) else 'UNKNOWN',
            declared_pt=declared,source_pt=effective,font_declaration=raw['font'],font_asset_identity='UNKNOWN',
            baseline_anchor_mm=glyphs[0]['origin_mm'],baseline_status='ORIGINAL_PDF_TEXT_ORIGIN_PLUS_RISE',
            source_region_mm=dict(x=x,y=y,w=right-x,h=bottom-y),bounds_basis='PDF_FONT_METRIC_BOX_NOT_INK_OR_CONTAINER',
            horizontal_scale=ObservedScalar(raw['horizontal_scale'],'ratio','OBSERVED','ORIGINAL_PDF_TZ',(ref,)).to_dict(),
            tracking=ObservedScalar(raw['charspace']*known_scale*MM_PER_POINT,'mm','DERIVED',
                'PDF_TC_BEFORE_HORIZONTAL_SCALE',(ref,)).to_dict() if known_scale else unknown('mm'),
            baseline_orientation='HORIZONTAL_FORWARD' if matrix[0]>0 and abs(matrix[1])<1e-9 and abs(matrix[2])<1e-9 and matrix[3]>0 else 'UNKNOWN_OR_UNSUPPORTED_ROTATED',
            wordspace_declared_pt=raw['wordspace'],visibility='NONPAINTING_TEXT' if raw['text_render_mode'] in (3,7) else 'PAINT_REQUEST_CLIP_AND_OCG_NOT_VERIFIED',
            text_render_mode=raw['text_render_mode'],writing_mode=glyphs[0]['writing_mode'],
            native_illustrator_editability='UNKNOWN',role_mapping='UNKNOWN')
        if include_private_text:row['_private_text']=decoded
        runs.append(row)
    result=dict(version=VERSION,source_hash=source['hash'],page=page_number,state='OBSERVED' if runs else 'NO_READABLE_TEXT',
        channel='ORIGINAL_PDF_INTERPRETED_GLYPHS_NOT_ILLUSTRATOR_PRIVATE',physical_page_mm=dict(width=width,height=height),
        source_canvas_mapping='VERIFIED_PHYSICAL_VIEWPORT' if canvas_verified else 'UNKNOWN_VIEWPORT_DIFFERENCE',
        glyph_count=device.count,runs=runs,scope='SOURCE_PAGE_NOT_AUTOMATIC_WORK_OR_PERSON_MAPPING')
    result['document_digest']=canonical_digest(result)
    return result


def resolve_glyph_run(source,reference):
    """Retrieve addressed glyph detail on demand with exact content verification."""
    from pathlib import Path
    from .source_links import verify_source
    verify_source(source['current_path'],source['hash'])
    if source['hash']!=reference['source_hash'] or source.get('page',1)!=reference['page']:
        raise ValueError('Glyph source reference differs')
    path=Path(source['current_path'])
    if path.stat().st_size>32_000_000:raise GlyphBudget('Original glyph source byte budget exceeded')
    evidence=extract_pdf_glyphs(source,path.read_bytes())
    row=next((row for row in evidence['runs'] if row['id']==reference['run_id']),None)
    if not row or canonical_digest(row['glyphs'])!=reference['digest'] or len(row['glyphs'])!=reference['count']:
        raise ValueError('Addressed source glyph detail differs')
    verify_source(source['current_path'],source['hash'])
    return row
