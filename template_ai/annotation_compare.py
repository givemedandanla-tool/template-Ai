"""Annotation overlays in source millimetres, using the existing linked viewer."""
from copy import deepcopy
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QImage,QPainter,QColor,QPen
from .batch_import import healthy_source
from .canvas_compare import png


def build_annotation_comparison(session):
    source=session.library.source(session.base['source_id'])
    if not healthy_source(source):raise ValueError('來源／衍生快取未核實，不能繪製可信對照')
    old=session.base['payload'];new=session.payload
    if old['crop']!=new['crop']:raise ValueError('作品範圍已變更，先保存／重載來源對照')
    original=QImage(source['image']);c=new['crop'];w,h=new['work_width'],new['work_height']
    rect=QRectF(c['x']/source['width_mm']*original.width(),c['y']/source['height_mm']*original.height(),c['w']/source['width_mm']*original.width(),c['h']/source['height_mm']*original.height())
    image=original.copy(rect.toAlignedRect()).scaled(1600,1600,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    def overlay(payload,color):
        rendered=image.copy();painter=QPainter(rendered)
        try:
            painter.scale(rendered.width()/w,rendered.height()/h);pen=QPen(QColor(color));pen.setWidthF(.25);painter.setPen(pen)
            for slot in payload['slots']:
                r=slot['rect'];painter.drawRect(QRectF(r['x'],r['y'],r['w'],r['h']))
        finally:painter.end()
        return png(rendered)
    slots={s['id']:deepcopy(s) for s in old['slots']}
    slots.update({s['id']:deepcopy(s) for s in new['slots']})
    for slot in slots.values():slot.setdefault('index',0)
    return dict(window_title='原稿／修正前標記／修正草稿 · 同步唯讀對照',view_labels=dict(source='原作品衍生圖（未修改）',before='修正前標記（紅框）',after='修正草稿（綠框；未核准事實）'),template_id=session.base['id'],slot_id=None,template_size=[w,h],slots=list(slots.values()),view_slots=dict(source=[],before=old['slots'],after=new['slots']),source_png=png(image),before_png=overlay(old,'#dc2626'),after_png=overlay(new,'#16a34a'),source=dict(reason='同來源／頁次／作品裁切已核對；非原生Illustrator圖層',mapping=dict(page_size=[w,h],template_size=[w,h],crop=dict(x=0,y=0,w=w,h=h),page=source['page'],unit='mm',revision=session.base['revision'])),original_known=True,original_reason='原稿及修正前後共享物件ID、視角與毫米座標',scope='疊圖只顯示標記；沒有重畫原稿文字，非正式輸出或學習核准')
