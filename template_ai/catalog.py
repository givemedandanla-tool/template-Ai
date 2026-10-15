"""Read-only template/customer style index and verified derivative previews.

The picture is a source reference, never a new layout or a print certificate.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from PySide6.QtCore import QRect,QSize,Qt
from PySide6.QtGui import QImage,QImageReader,QPainter,QColor,QPen
from .model import Template,Rect,KINDS

PAGE_SIZE=48
MAX_PREVIEW_PIXELS=16_000_000
MAX_DERIVATIVE_BYTES=32*1024*1024


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def rows(library,customer=None):
    templates=library.templates();byid={t.id:t for t in templates};result=[]
    pairs=[(t,None) for t in templates] if customer is None else [(byid.get(s['template_id']),s) for s in customer['styles']]
    for t,link in pairs:
        if t:
            d=t.to_dict();width,height=(link['width_mm'],link['height_mm']) if link else (t.width_mm,t.height_mm)
            state='CURRENT' if not link or digest(d)==link['template_hash'] else 'STALE'
            result.append(dict(id=link['id'] if link else t.id,template_id=t.id,template=d,name=t.name,family=t.family_id,version=t.version,
                width=width,height=height,capacity=t.capacity,state=t.state,link=deepcopy(link),reference_state=state,
                signature=digest([d,link]),customer_id=customer['id'] if customer else None))
        else:
            result.append(dict(id=link['id'],template_id=link['template_id'],template=None,name='版型已失聯',family='',version=None,
                width=link['width_mm'],height=link['height_mm'],capacity=None,state='UNKNOWN',link=deepcopy(link),reference_state='MISSING',
                signature=digest(link),customer_id=customer['id']))
    return sorted(result,key=lambda r:(r['width'],r['height'],r['capacity'] or 0,r['name'].casefold(),r['version'] or 0,r['id']))


def filtered(entries,query='',size=None,capacity=None,state=None,version=None):
    tokens=query.strip().casefold().split();result=[]
    for r in entries:
        if size and (r['width'],r['height'])!=tuple(size):continue
        if capacity is not None and r['capacity']!=capacity:continue
        if state and r['state']!=state:continue
        if version is not None and r['version']!=version:continue
        t=r['template'] or {}
        words=' '.join(str(x) for x in (r['name'],r['template_id'],r['family'],r['version'],r['state'],r['reference_state'],t.get('source_id',''),t.get('source_work_id',''))).casefold()
        if all(token in words for token in tokens):result.append(r)
    return result


def hierarchy(entries):
    tree={}
    for r in entries:
        key=(r['width'],r['height']);capacity=r['capacity']
        tree.setdefault(key,{})[capacity]=tree.setdefault(key,{}).get(capacity,0)+1
    return tree


def frame_diagram(entry):
    """Actual template geometry only; visibly distinct from a source thumbnail."""
    image=QImage(240,150,QImage.Format_ARGB32_Premultiplied);image.fill(QColor('#edf0f4'))
    if not entry['template']:return image
    t=Template.from_dict(entry['template']);p=QPainter(image)
    try:
        if not all(math.isfinite(v) and v>0 for v in (t.width_mm,t.height_mm)):return image
        scale=min(216/t.width_mm,124/t.height_mm);p.translate((240-t.width_mm*scale)/2,(150-t.height_mm*scale)/2);p.scale(scale,scale)
        p.fillRect(0,0,round(t.width_mm),round(t.height_mm),QColor('white'));pen=QPen(QColor('#4974a5'));pen.setWidthF(1/scale);p.setPen(pen)
        from PySide6.QtCore import QRectF
        p.drawRect(QRectF(0,0,t.width_mm,t.height_mm))
        for s in t.slots:
            if s.rect.valid():p.drawRect(QRectF(s.rect.x,s.rect.y,s.rect.w,s.rect.h))
    finally:p.end()
    return image


def preview_request(library,entry):
    """SQLite stays on its owning thread. Only plain dictionaries cross threads."""
    if not entry['template']:return dict(entry=deepcopy(entry),source=None,work=None)
    t=entry['template'];source=None;work=None
    if t.get('source_id'):
        try:source=library.source(t['source_id'])
        except (ValueError,KeyError):pass
    if t.get('source_work_id'):
        try:
            current=library.artwork(t['source_work_id'])
            reference=library.db.execute('SELECT revision FROM artwork_revisions WHERE artwork_id=? AND revision=?',(t['source_work_id'],t['source_work_revision'])).fetchone()
            if reference:work=dict(id=current['id'],source_id=current['source_id'],revision=reference[0],current_revision=current['revision'])
        except (ValueError,KeyError):pass
    if source:source={k:source[k] for k in ('id','hash','image','width_mm','height_mm','original_path','current_path','file_hashes','calibrated') if k in source}
    if work:work={k:work[k] for k in ('id','source_id','revision','current_revision')}
    return dict(entry=deepcopy(entry),source=deepcopy(source),work=deepcopy(work))


def source_preview(request,cancel=None):
    """Bounded read/verify/decode/crop, with file-change checks around decoding."""
    from .source_links import hash_source,check_verified,ScanCancelled
    r=request['entry'];t=r['template'];source=request['source'];work=request['work']
    unavailable=lambda status,reason:dict(status=status,reason=reason,image=None,proofs=[])
    if r['reference_state']!='CURRENT':return unavailable(r['reference_state'],'版型引用已異動／失聯；只供核對，不能直接沿用')
    if not t or not source:return unavailable('UNKNOWN','沒有可核對原稿影像；未生成猜測縮圖')
    if t.get('source_id')!=source.get('id'):return unavailable('UNKNOWN','來源識別不符')
    if t.get('source_work_id') and (not work or work['source_id']!=source['id'] or work['revision']!=t.get('source_work_revision')):
        return unavailable('STALE','來源作品版本已異動／失聯')
    if not t.get('artwork'):return unavailable('UNKNOWN','沒有已確認來源作品裁切範圍')
    try:
        original=hash_source(source.get('current_path',source['original_path']),cancel)
        if original.hash!=source['hash']:return unavailable('CHANGED','來源位元已異動')
        path=source.get('image');expected=source.get('file_hashes',{}).get('image')
        if not path or not expected:return unavailable('UNKNOWN','沒有可核對的原稿衍生圖雜湊')
        path=Path(path)
        if path.is_symlink():return unavailable('UNKNOWN','不採用符號連結影像')
        proof=hash_source(path,cancel,MAX_DERIVATIVE_BYTES)
        if proof.hash!=expected:return unavailable('CHANGED','原稿預覽快取已異動')
        reader=QImageReader(str(path));size=reader.size()
        if not size.isValid() or size.width()*size.height()>MAX_PREVIEW_PIXELS:return unavailable('UNKNOWN','原稿預覽超出解碼預算，未截斷冒稱完整')
        crop=Rect(**t['artwork']);width,height=source.get('width_mm'),source.get('height_mm')
        if not all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in (width,height)) or not crop.inside(width,height):
            return unavailable('UNKNOWN','來源單位／裁切範圍無法核對')
        if cancel and cancel.is_set():raise ScanCancelled()
        image=reader.read()
        if image.isNull():return unavailable('UNREADABLE','原稿快取無法解碼')
        rect=QRect(round(crop.x/width*image.width()),round(crop.y/height*image.height()),round(crop.w/width*image.width()),round(crop.h/height*image.height()))
        if rect.width()<1 or rect.height()<1 or not image.rect().contains(rect):return unavailable('UNKNOWN','像素裁切無法核對')
        picture=image.copy(rect).scaled(QSize(480,320),Qt.KeepAspectRatio,Qt.SmoothTransformation)
        check_verified(original,source['hash']);check_verified(proof,expected)
        return dict(status='VERIFIED_DERIVATIVE',reason='雜湊核對的來源作品衍生圖；'+(('引用歷史作品版次'+str(work['revision'])+'（當前'+str(work.get('current_revision'))+'）；') if work and work.get('current_revision')!=work['revision'] else '')+('來源物理尺度已標定；' if source.get('calibrated') else '來源物理尺度UNKNOWN；')+'視覺一致性／印刷品質未由此認證',image=picture,proofs=[original,proof])
    except ScanCancelled:return unavailable('CANCELLED','已取消來源縮圖')
    except (OSError,ValueError,KeyError,TypeError):return unavailable('UNAVAILABLE','來源失聯／異動或資料無法核對；可重新整理後再試')


def metadata(library,entry):
    t=entry['template'];lines=[entry['name'],f"{entry['width']:g} × {entry['height']:g} mm／人物容量 {entry['capacity'] if entry['capacity'] is not None else 'UNKNOWN'}",f"版型ID {entry['template_id']}／版次 {entry['version'] if entry['version'] is not None else 'UNKNOWN'}／{entry['state']}",f"客戶關聯：{entry['reference_state']}；瀏覽不代表本次排版／輸出已通過"]
    if not t:return '\n'.join(lines+['版型失聯，不能用其他客戶／版本替代'])
    source=None
    if t.get('source_id'):
        try:source=library.source(t['source_id'])
        except (ValueError,KeyError):pass
    lines+=['來源：'+(Path(source['original_path']).name if source else 'UNKNOWN／無來源'), '來源作品：'+(t.get('source_work_id') or 'UNKNOWN')+'／作品版次 '+str(t.get('source_work_revision') or 'UNKNOWN'), '模板family：'+t['family_id'], '欄位條件：']
    lines += [f"{s['owner']}／{KINDS.get(s['kind'],s['kind'])} #{s['index']+1} · {'必填' if s['required'] else '可空'} · {s['size_pt']:g}pt · 字寬≥{s['min_scale']:.0%}" for s in t['slots']]
    return '\n'.join(lines)


def geometry_description(entry):
    lines=['實際框位（毫米；不同尺寸各自驗證）：']
    for s in (entry.get('template') or {}).get('slots',[]):
        r=s['rect']
        lines.append(f"{s['owner']}／{KINDS.get(s['kind'],s['kind'])} #{s['index']+1}：X {r['x']:g}、Y {r['y']:g}、寬 {r['w']:g}、高 {r['h']:g} mm；固定{s['size_pt']:g}pt")
    return '\n'.join(lines)
