"""Current digital output inspection on the original candidate and Qt/PDF engines.

A measured or decoded preview is evidence, never a print or model approval.
"""
import copy,math
from dataclasses import asdict
from pathlib import Path
from xml.etree import ElementTree
from PySide6.QtGui import QImageReader
from .training_store import digest
from .background import file_digest
from .logo_assets import geometry,errors as logo_errors

MAX_PIXELS=24_000_000
MAX_SVG_BYTES=16*1024*1024
FORMATS={'PDF','PNG','JPG'}


def options(candidate,format,dpi):
    format=str(format).upper().lstrip('.')
    if format=='JPEG':format='JPG'
    if format not in FORMATS or type(dpi) is not int or not 72<=dpi<=600:raise ValueError('需明列 PDF／PNG／JPG 與72～600數位取樣DPI；不是印刷品質門檻')
    t=candidate.template
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=2000 for v in (t.width_mm,t.height_mm)):raise ValueError('實體尺寸無效')
    pixels=[max(1,round(v*dpi/25.4)) for v in (t.width_mm,t.height_mm)]
    if pixels[0]*pixels[1]>MAX_PIXELS:raise ValueError('數位核對超過2400萬像素預算，未偷偷降解析度')
    return dict(format=format,dpi=dpi,size_mm=[t.width_mm,t.height_mm],pixels=pixels)


def scope(candidate,format,dpi):
    from .candidate_risk import engine_digest
    from .layout import layout_dependency
    spec=options(candidate,format,dpi);logos={str(i):p.logo for i,p in enumerate(candidate.items) if p.logo}
    validation_code=digest({name:file_digest(Path(__file__).with_name(name)) for name in ('digital_preflight.py','digital_final.py','digital_output_proof.py','digital_preflight_panel.py','preflight_detail.py') if Path(__file__).with_name(name).exists()})
    value=dict(**spec,validation_code=validation_code,template_digest=digest(candidate.template.to_dict()),items_digest=digest([asdict(p) for p in candidate.items]),generation=candidate.generation,input_digest=candidate.risk_context.get('input_digest'),risk_digest=candidate.risk['digest'],engine_digest=engine_digest(),dependency=layout_dependency(candidate.template,logos))
    value['digest']=digest(value);return value


def row(code,status,reason,slot_ids=(),**measurements):
    return dict(code=code,status=status,reason=reason,slot_ids=list(slot_ids),measurements=measurements)


def logo_sampling(item,dpi):
    """Actual source pixels divided by placed millimetres; ignore DPI metadata."""
    asset=item.logo;slot=item.slot
    if not asset:return row('LOGO_SOURCE','BLOCKED','此Logo缺實際來源',[slot.id])
    health=logo_errors(asset)
    if health:return row('LOGO_SOURCE','BLOCKED','；'.join(health),[slot.id])
    try:
        fit=geometry(asset,slot.rect);actual=fit['actual'];svg=asset.get('svg')
        if svg:
            path=Path(svg)
            if path.stat().st_size>MAX_SVG_BYTES:raise ValueError('向量來源超過有界核對預算')
            xml=ElementTree.fromstring(path.read_bytes());nodes=list(xml.iter())
            if len(nodes)>50000:raise ValueError('向量節點超過有界核對預算')
            embedded=any(n.tag.rsplit('}',1)[-1].lower()=='image' for n in nodes)
            if embedded:return row('LOGO_SOURCE','NOT_CHECKED','混合向量／點陣來源需逐件核對內嵌影像；不能把SVG副檔名當成無限解析度',[slot.id],source_type='MIXED',actual_mm=actual,fit=fit)
            return row('LOGO_SOURCE','PASS','原生向量由原QSvgRenderer保留整組／比例；實際編碼仍須核對',[slot.id],source_type='VECTOR',actual_mm=actual,fit=fit,encoded_fidelity_verified=False)
        reader=QImageReader(str(asset.get('image','')));size=reader.size()
        if not reader.canRead() or size.isEmpty():raise ValueError('點陣原始來源無法實際解碼尺寸')
        crop=asset.get('crop') or dict(x=0,y=0,w=asset['source_width_mm'],h=asset['source_height_mm'])
        available=[size.width()*crop['w']/asset['source_width_mm'],size.height()*crop['h']/asset['source_height_mm']]
        ppi=[available[0]*25.4/actual['w'],available[1]*25.4/actual['h']];adequate=min(ppi)+1e-6>=dpi
        return row('LOGO_SOURCE','PASS' if adequate else 'BLOCKED','來源像素足以涵蓋目前明列輸出取樣；仍需實際細節比對' if adequate else '目前尺寸／DPI需插值放大來源；提高DPI標記不會增加真實細節',[slot.id],source_type='RASTER',source_pixels=[size.width(),size.height()],available_crop_pixels=available,effective_ppi=ppi,requested_dpi=dpi,actual_mm=actual,fit=fit,physical_print_verified=False)
    except (ValueError,KeyError,OSError,ZeroDivisionError,ElementTree.ParseError) as error:return row('LOGO_SOURCE','BLOCKED',str(error),[slot.id])


def inspect_candidate(candidate,format,dpi):
    spec=scope(candidate,format,dpi);t=candidate.template;risk=candidate.risk;rows=[]
    rows.append(row('PHYSICAL_SIZE','PASS','依目前模板真實毫米及明列數位取樣核對',**{k:spec[k] for k in ('size_mm','pixels','dpi','format')}))
    outside=[p.slot.id for p in candidate.items if not p.slot.rect.inside(t.width_mm,t.height_mm)]
    rows.append(row('TRIM_BOUNDS','BLOCKED' if outside else 'PASS','實際物件超出成品裁切邊界' if outside else '實際物件均在成品邊界內',outside))
    margin=t.safe_margin_mm;unsafe=[]
    valid_margin=type(margin) in (int,float) and math.isfinite(margin) and 0<=margin<min(t.width_mm,t.height_mm)/2
    if not valid_margin:unsafe=[p.slot.id for p in candidate.items]
    else:
        for p in candidate.items:
            r=p.slot.rect
            if r.x<margin-1e-6 or r.y<margin-1e-6 or r.x+r.w>t.width_mm-margin+1e-6 or r.y+r.h>t.height_mm-margin+1e-6:unsafe.append(p.slot.id)
    rows.append(row('SAFE_ZONE','BLOCKED' if unsafe or not valid_margin else 'PASS','安全邊距無效' if not valid_margin else '超出目前模板明列安全區' if unsafe else '已核對目前模板安全邊距；未虛構出血量',unsafe,margin_mm=margin))
    groups=[('TEXT_COMPLETE',{'REQUIRED','MISSING_NAME','NO_SLOT','LOSSLESS'}),('FIXED_FONT',{'HEIGHT','FONT_UNVERIFIED','FIELD_PROPERTIES'}),('HORIZONTAL_SCALE',{'WIDTH'}),('OWNERSHIP',{'UNKNOWN_COMPANY','COMPANY_BINDING','UNBOUND_COMPANY','OWNER'}),('OVERLAP',{'OVERLAP_REVIEW','CONTAINMENT_UNKNOWN'})]
    for code,codes in groups:
        failures=[d for d in candidate.diagnostics if d['code'] in codes];slots=sorted({identity for d in failures for identity in d.get('slot_ids',[])})
        rows.append(row(code,'BLOCKED' if failures else 'PASS','原排版引擎此項仍有阻擋' if failures else '依原排版引擎實測與目前候選核對',slots,original_diagnostics=copy.deepcopy(failures)))
    from itertools import islice
    from .model import overlapping_pairs
    pairs=list(islice(overlapping_pairs(t.slots),201));overlap=next(r for r in rows if r['code']=='OVERLAP')
    if pairs:
        overlap.update(status='BLOCKED',reason='原矩形相交檢查仍有阻擋；不自動刪除或放行',slot_ids=sorted({s.id for pair in pairs[:200] for s in pair}),measurements=dict(pairs=[[a.id,b.id] for a,b in pairs[:200]],more_pairs_unlisted=len(pairs)>200))
    scales=[dict(slot_id=p.slot.id,size_pt=p.slot.size_pt,scale=p.scale,min_scale=p.slot.min_scale) for p in candidate.items if p.text]
    bad=[v['slot_id'] for v in scales if not math.isfinite(v['scale']) or not v['min_scale']-1e-6<=v['scale']<=1+1e-6]
    if bad:rows.append(row('HORIZONTAL_SCALE','BLOCKED','目前實際比例不符合固定字級的模板範圍',bad,actual=scales))
    rows.append(row('CURRENT_WHOLE_CARD_GATE','PASS' if risk['formal_allowed'] else 'BLOCKED','原完整目前Gate通過；仍須本格式實際編碼核對' if risk['formal_allowed'] else risk['label'],conditions=copy.deepcopy(risk['conditions']),text_measurements=copy.deepcopy(candidate.measurements),actual_text=scales))
    rows.extend(logo_sampling(p,dpi) for p in candidate.items if p.slot.kind=='logo')
    rows.append(row('ENCODED_FORMAT','NOT_CHECKED','尚未實際編碼、讀回與比對；預覽不是已輸出',format=spec['format']))
    rows.append(row('PDF_FONT_EMBEDDING','NOT_CHECKED' if spec['format']=='PDF' else 'PASS','實際PDF字型資源尚未讀回' if spec['format']=='PDF' else '此點陣格式不使用PDF內嵌字型'))
    return dict(scope=spec,rows=rows,can_encode=all(r['status']=='PASS' for r in rows if r['code'] not in ('ENCODED_FORMAT','PDF_FONT_EMBEDDING')),formal_output_allowed=False,physical_print_verified=False,output_written=False)


def validate_scope(candidate,value):
    if scope(candidate,value['format'],value['dpi'])!=value:raise ValueError('候選／輸入／來源／字型／Logo／尺寸／格式依賴已變更，不能沿用舊預檢')
