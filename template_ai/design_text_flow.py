"""Shared Qt shaping for source-supported multiline flow, preview and output.

Typography remains core controlled. Line counts are empirical style evidence,
not permission to silently truncate input or wrap phone/email/social tokens.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QTextLayout, QTextOption, QColor

from .fonts import font_errors

MM_PER_POINT=25.4/72
ALLOWED_KINDS={'title','address','company'}


def shape_flow(text, family, pt, scale, width_mm, asset, style, tracking_mm, policy, kind):
    import math
    if kind not in ALLOWED_KINDS or policy.get('status')!='HUMAN_CONFIRMED_SOURCE_RULE':
        raise ValueError('Multiline flow requires supported role and source-reviewed rule')
    if policy.get('break_rule') not in ('WORD_WRAP','WORD_OR_ANYWHERE') or not policy.get('evidence_refs'):
        raise ValueError('Unknown or unreferenced source break rule')
    maximum=policy.get('max_lines_observed');leading=policy.get('line_height_factor')
    if type(maximum) is not int or not 1<=maximum<=16:
        raise ValueError('Observed line count is invalid')
    if type(leading) not in (float,int) or not math.isfinite(leading) or not .5<=leading<=3:
        raise ValueError('Source line height is invalid')
    if any(type(v) not in (float,int) or not math.isfinite(v) or v<=0 for v in (pt,scale,width_mm)):
        raise ValueError('Invalid physical flow size')
    if font_errors(asset,family):raise ValueError('Flow font asset changed or is unavailable')
    from .font_catalog import analyze_font
    check=analyze_font(dict(kind='ASSET',asset=asset),text.replace('\n',' '),pt,2000,.05,style or None,
                       tracking_mm=tracking_mm)
    if not check.get('measurement_verified') or check.get('family')!=family:
        raise ValueError('Flow glyph coverage and exact font face must be verified')
    font=QFontDatabase.font(family,check['style'],1000);font.setPixelSize(1000)
    font.setStyleStrategy(QFont.NoFontMerging);font.setHintingPreference(QFont.PreferNoHinting)
    factor=pt*MM_PER_POINT/1000
    font.setLetterSpacing(QFont.AbsoluteSpacing,tracking_mm/factor)
    option=QTextOption()
    option.setWrapMode(QTextOption.WordWrap if policy['break_rule']=='WORD_WRAP' else QTextOption.WrapAtWordBoundaryOrAnywhere)
    alignment=policy.get('alignment','left')
    alignments={'left':Qt.AlignLeft,'center':Qt.AlignHCenter,'right':Qt.AlignRight,'justify':Qt.AlignJustify}
    if alignment not in alignments:raise ValueError('Unsupported learned flow alignment')
    option.setAlignment(alignments[alignment]);layout=QTextLayout(text,font);layout.setTextOption(option)
    spacing=QFontMetricsF(font).lineSpacing()*leading;lines=[];ink=None
    layout.beginLayout()
    try:
        while True:
            line=layout.createLine()
            if not line.isValid():break
            if len(lines)>=maximum:raise ValueError('Text exceeds source-supported multiline style')
            line.setLineWidth(width_mm/(factor*scale));line.setPosition(QPointF(0,len(lines)*spacing))
            lines.append(dict(start=line.textStart(),length=line.textLength(),natural_width_mm=line.naturalTextWidth()*factor*scale))
    finally:layout.endLayout()
    for run in layout.glyphRuns():
        raw=run.rawFont()
        for glyph,position in zip(run.glyphIndexes(),run.positions()):
            box=raw.boundingRect(glyph).translated(position)
            if not box.isEmpty():ink=box if ink is None else ink.united(box)
    ink=ink or QRectF()
    width=ink.width()*factor*scale;height=ink.height()*factor
    if width>width_mm+1e-6:raise ValueError('Unbreakable shaped text exceeds flow container')
    return dict(layout=layout,ink=ink,factor=factor,width_mm=width,height_mm=height,lines=lines,
                text_length=len(text),source_rule=policy)


def draw_flow(painter,rect,text,slot,scale,tracking_mm):
    result=shape_flow(text,slot.font,slot.size_pt,scale,rect.width(),slot.font_asset,
                      slot.font_style,tracking_mm,slot.text_flow,slot.kind)
    if result['height_mm']>rect.height()+1e-6:raise ValueError('Actual multiline ink exceeds approved container')
    ink=result['ink'];factor=result['factor']
    painter.save()
    try:
        alignment=slot.text_flow.get('alignment','left')
        offset=(rect.width()-result['width_mm'])*(1 if alignment=='right' else .5 if alignment=='center' else 0)
        painter.translate(rect.x()+offset-ink.left()*factor*scale,
                          rect.y()+(rect.height()-result['height_mm'])/2-ink.top()*factor)
        painter.scale(factor*scale,factor);painter.setPen(QColor(slot.color))
        result['layout'].draw(painter,QPointF(0,0))
    finally:painter.restore()
