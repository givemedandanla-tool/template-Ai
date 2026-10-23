"""Bounded, read-only full-rectangle comparison. No inferred original text or fallback."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPen
from .background import file_digest, background_errors
from .font_catalog import analyze_font
from .font_review import fingerprint, source_row
from .importer import cache_matches
from .model import Template, Rect, template_errors
from .render import paint_background, draw_text

MAX_FILE=50*1024*1024
MAX_BYTES=64*1024*1024
MAX_TEMPLATE_PIXELS=6_000_000
MAX_SOURCE_PIXELS=12_000_000


def source_point(mapping,u,v):
    c=mapping['crop'];w,h=mapping['template_size']
    return c['x']+u*c['w']/w,c['y']+v*c['h']/h


def template_point(mapping,x,y):
    c=mapping['crop'];w,h=mapping['template_size']
    return (x-c['x'])*w/c['w'],(y-c['y'])*h/c['h']


def pixel_point(mapping,u,v):
    x,y=source_point(mapping,u,v);pw,ph=mapping['page_size'];iw,ih=mapping['pixel_size']
    return x*iw/pw,y*ih/ph


def png(image):
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer,'PNG'):raise ValueError('對照PNG編碼失敗')
    return bytes(data)


class Assets:
    def __init__(self):self.files={};self.total=0
    def add(self,path,expected=None):
        path=Path(path)
        if path.is_symlink() or not path.is_file():raise ValueError('對照資產失聯或符號連結')
        size=path.stat().st_size
        if size>MAX_FILE:raise ValueError('對照單資產超過50 MiB預算')
        key=str(path.absolute())
        if key not in self.files:
            if self.total+size>MAX_BYTES:raise ValueError('對照資產超過64 MiB預算')
            self.total+=size
        sha=file_digest(path)
        if expected is not None and sha!=expected:raise ValueError('對照資產內容已異動')
        self.files[key]=sha
    def verify(self):
        for path,sha in self.files.items():
            p=Path(path)
            if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_FILE or file_digest(p)!=sha:raise ValueError('對照期間資產內容已異動／失聯，請重新核對')


def check_source(context,t,assets):
    if context.get('status')=='UNKNOWN':return {'status':'UNKNOWN','reason':context['reason'],'mapping':None,'image':None}
    work,src=context['work'],context['source']
    if context['work_id']!=t.source_work_id or context['revision']!=t.source_work_revision or src['id']!=t.source_id:raise ValueError('來源身份與模板不符')
    crop=Rect(**work['crop']);pw,ph=src['width_mm'],src['height_mm']
    if not crop.inside(pw,ph) or not all(math.isfinite(v) and 0<v<=2000 for v in (pw,ph,work['work_width'],work['work_height'])):raise ValueError('來源範圍不合法')
    if abs(work['work_width']-t.width_mm)>1e-6 or abs(work['work_height']-t.height_mm)>1e-6 or (t.artwork and t.artwork!=crop):raise ValueError('模板與历史來源裁切／標定尺寸不符')
    original=Path(src['current_path'])
    if not original.is_file() and not original.is_symlink():return {'status':'UNKNOWN','reason':'原始來源失聯；不以衍生圖冒稱可核對原稿','mapping':None,'image':None}
    assets.add(original,src['hash'])
    image_path=Path(src['image']);folder=image_path.parent;meta_path=folder/'metadata.json'
    assets.add(meta_path)
    if meta_path.stat().st_size>1_000_000:raise ValueError('來源metadata超過預算')
    meta=json.loads(meta_path.read_text(encoding='utf-8'))
    for key in ('hash','page','page_count','width_mm','height_mm','calibrated','image','svg','file_hashes','cache_version','metadata_sha256'):
        if meta.get(key)!=src.get(key):raise ValueError('來源登錄與快取metadata不符')
    for key in ('image','svg'):
        if src.get(key):assets.add(src[key],src['file_hashes'][key])
    if not cache_matches(meta,folder,src['hash'],src['page']):raise ValueError('來源快取不健康／metadata身份不符')
    reader=QImageReader(str(image_path));size=reader.size()
    if size.width()<=0 or size.height()<=0 or size.width()*size.height()>MAX_SOURCE_PIXELS:raise ValueError('來源解碼超過12 MP／48 MB像素預算')
    image=reader.read()
    if image.isNull():raise ValueError('來源圖像無法解析')
    mapping={'crop':copy.deepcopy(work['crop']),'template_size':[t.width_mm,t.height_mm],'page_size':[pw,ph],
             'pixel_size':[image.width(),image.height()],'unit':'mm（來源已標定）' if src['calibrated'] else '參考單位／像素（來源未物理標定）',
             'work_id':context['work_id'],'revision':context['revision'],'source_id':src['id'],'page':src['page'],'source_sha256':src['hash']}
    return {'status':'VERIFIED_REFERENCE','reason':'已核對衍生預覽身份；不代表原生文字／效果或視覺一致','mapping':mapping,'image':image}


def verify_comparison(result):
    a=Assets();a.files=result['files'];a.verify()
    return True


def build_comparison(snapshot,row,target,text,context,dpi=150):
    t=Template.from_dict(snapshot['template']);assets=Assets()
    if row['template_id']!=t.id or row['template_hash']!=fingerprint(snapshot['template']) or row['revision']!=snapshot['revision']:raise ValueError('模板核驗版本過期')
    if type(dpi) is not int or not 72<=dpi<=300:raise ValueError('對照DPI超出預算')
    if len(t.slots)>200 or len({s.id for s in t.slots})!=len(t.slots):raise ValueError('對照欄位過多或stable ID重複')
    geometry=copy.deepcopy(t)
    for s in geometry.slots:s.font_asset=None;s.font_style=''
    errors=template_errors(geometry)
    if errors:raise ValueError('；'.join(errors))
    selected=next((s for s in t.slots if s.id==row['slot_id']),None)
    if not selected or selected.kind=='logo':raise ValueError('所選文字框不存在')
    if not isinstance(text,str) or not text.strip():raise ValueError('需提供所選欄文字；其他欄文字不會借用')
    if not row['eligible']:raise ValueError('所選欄未通過字型核驗')
    pxw,pxh=max(1,round(t.width_mm*dpi/25.4)),max(1,round(t.height_mm*dpi/25.4))
    if pxw*pxh>MAX_TEMPLATE_PIXELS:raise ValueError('模板對照超過6 MP預算')
    # Budget before font parsing / SVG rendering, including original and target bytes.
    for asset in (selected.font_asset,target.get('asset')):
        if asset and Path(asset.get('path','')).is_file():assets.add(asset['path'],asset['hash'])
    if t.background:
        for key in ('image','svg'):
            if t.background.get(key):assets.add(t.background[key],t.background['files'][key])
    errors=background_errors(t.background,t.width_mm,t.height_mm)
    if errors:raise ValueError('；'.join(errors))
    source=check_source(context,t,assets)
    from .text_policy import analyse_slot_font
    after=analyse_slot_font(target,selected,text,row['proposed']['style'])
    if fingerprint(after)!=fingerprint(row['proposed']) or after['status']!='FEASIBLE_WIDTH' or after['height_mm']>selected.rect.h+1e-6:raise ValueError('目標字型／尺寸核驗已變更')
    before=analyse_slot_font(source_row(selected),selected,text,selected.font_style or None)
    # Original drawing is a verified template binding, never an inferred original-source font.
    known=bool(before.get('measurement_verified') and before.get('family')==selected.font and before.get('scale') is not None and before['height_mm']<=selected.rect.h+1e-6 and before['status']=='FEASIBLE_WIDTH')
    if known and before.get('asset_hash') and selected.font_asset:assets.add(selected.font_asset['path'],selected.font_asset['hash'])
    def render(analysis):
        image=QImage(pxw,pxh,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.white)
        p=QPainter(image);p.setRenderHint(QPainter.Antialiasing);p.scale(pxw/t.width_mm,pxh/t.height_mm)
        try:
            paint_background(p,t)
            pen=QPen(QColor('#94a3b8'));pen.setWidthF(.12);pen.setStyle(Qt.DashLine);p.setPen(pen)
            for s in t.slots:p.drawRect(QRectF(s.rect.x,s.rect.y,s.rect.w,s.rect.h))
            if analysis:
                r=selected.rect
                asset=target.get('asset') if analysis is after else selected.font_asset
                draw_text(p,QRectF(r.x,r.y,r.w,r.h),text,analysis['family'],selected.size_pt,analysis['scale'],selected.align,selected.color,analysis['style'],asset,analysis.get('tracking_mm',0))
        finally:p.end()
        return png(image)
    before_png=render(before if known else None);after_png=render(after)
    source_png=png(source.pop('image')) if source['image'] is not None else b''
    source.pop('image',None);assets.verify()
    return {'template_id':t.id,'slot_id':selected.id,'template_hash':row['template_hash'],'revision':snapshot['revision'],
            'template_size':[t.width_mm,t.height_mm],'slots':[{'id':s.id,'kind':s.kind,'owner':s.owner,'index':s.index,'rect':s.rect.__dict__} for s in t.slots],
            'before_png':before_png,'after_png':after_png,'source_png':source_png,'source':source,'original_known':known,
            'original_reason':'原模板字型綁定已核對（不代表原稿字型）' if known else '原模板文字未知／尺寸不合格；未使用fallback繪製',
            'files':dict(assets.files),'bytes_budgeted':assets.total,'pixel_size':[pxw,pxh],'context_hash':fingerprint(context),'scope':'唯讀人工對照；其他文字／Logo資產未提供時只畫空框，非正式輸出或原稿一致性保證'}
