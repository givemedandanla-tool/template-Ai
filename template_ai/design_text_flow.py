"""Shared Qt shaping for source-supported multiline flow, preview and output.

Typography remains core controlled. Line counts are empirical style evidence,
not permission to silently truncate input or wrap phone/email/social tokens.
"""
from PySide6.QtCore import QPointF, QRectF, Qt, QTextBoundaryFinder
from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QTextLayout, QTextOption, QColor

from .fonts import font_errors

MM_PER_POINT=25.4/72
ALLOWED_KINDS={'title','address','company'}


def apply_spacing(font,text,factor,rule):
    if not rule:return dict(mode='LEGACY_CHARACTER_TRACKING',boundary_count=None)
    from fontTools.unicodedata import script
    import math
    if (rule.get('status')!='HUMAN_CONFIRMED_SOURCE_RULE' or not rule.get('evidence_refs')
            or rule.get('mode') not in ('WORDS','CHARACTERS')
            or rule.get('last_line')!='NATURAL' or rule.get('zero_boundaries')!='KEEP_NATURAL'):
        raise ValueError('Unsupported or unreviewed spacing boundary/last-line rule')
    allowed=rule.get('allowed_scripts')
    scripts={script(char) for char in text}-{ 'Zyyy','Zinh' }
    if not isinstance(allowed,list) or not scripts.issubset(set(allowed)):
        raise ValueError('Input script has no reviewed spacing support')
    value=rule.get('value_mm')
    if type(value) not in (float,int) or not math.isfinite(value) or not 0<=value<=2:
        raise ValueError('Source spacing exceeds supported physical policy')
    if rule['mode']=='WORDS':
        if rule.get('boundary_policy')!='ASCII_SPACE_QT_WORD_SPACING' or any(c.isspace() and c not in ' \n' for c in text):
            raise ValueError('Word-spacing boundaries are not source-supported')
        import re
        count=sum(len(match.group()) for match in re.finditer(r'(?<=\S) +(?=\S)',text))
        font.setWordSpacing(value/factor if count else 0.)
    else:
        if rule.get('boundary_policy')!='QT_SHAPED_GRAPHEME_TRACKING':
            raise ValueError('Character spacing requires a shaped grapheme boundary rule')
        finder=QTextBoundaryFinder(QTextBoundaryFinder.Grapheme,text);finder.toStart();count=-1
        while finder.toNextBoundary()!=-1:count+=1
        count=max(0,count)
        font.setLetterSpacing(QFont.AbsoluteSpacing,value/factor if count else 0.)
    return dict(mode=rule['mode'],boundary_count=count,zero_boundary_action='KEEP_NATURAL',last_line='NATURAL')


def shape_flow(text, family, pt, scale, width_mm, asset, style, tracking_mm, policy, kind):
    import math
    rich=policy.get('rich_text')
    single_line=policy.get('break_rule')=='NO_WRAP' and policy.get('max_lines_observed')==1
    if (kind not in ALLOWED_KINDS and not (rich and single_line)) or policy.get('status')!='HUMAN_CONFIRMED_SOURCE_RULE':
        raise ValueError('Multiline flow requires supported role and source-reviewed rule')
    if policy.get('break_rule') not in ('WORD_WRAP','WORD_OR_ANYWHERE','NO_WRAP') or not policy.get('evidence_refs'):
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
    first_text=text.replace('\n',' ')
    if rich:
        from .design_rich_text import resolve_segments
        first_text=resolve_segments(text,rich)[0]['text']
    check=analyze_font(dict(kind='ASSET',asset=asset),first_text,pt,2000,.05,style or None,
                       tracking_mm=tracking_mm)
    if not check.get('measurement_verified') or check.get('family')!=family:
        raise ValueError('Flow glyph coverage and exact font face must be verified')
    font=QFontDatabase.font(family,check['style'],1000);font.setPixelSize(1000)
    font.setStyleStrategy(QFont.NoFontMerging);font.setHintingPreference(QFont.PreferNoHinting)
    factor=pt*MM_PER_POINT/1000
    font.setLetterSpacing(QFont.AbsoluteSpacing,tracking_mm/factor)
    spacing_rule=apply_spacing(font,text,factor,policy.get('spacing_rule'))
    option=QTextOption()
    option.setWrapMode(QTextOption.NoWrap if single_line else QTextOption.WordWrap if policy['break_rule']=='WORD_WRAP' else QTextOption.WrapAtWordBoundaryOrAnywhere)
    alignment=policy.get('alignment','left')
    alignments={'left':Qt.AlignLeft,'center':Qt.AlignHCenter,'right':Qt.AlignRight,'justify':Qt.AlignJustify}
    if alignment not in alignments:raise ValueError('Unsupported learned flow alignment')
    if policy.get('spacing_rule',{}).get('mode')=='WORDS' and alignment=='justify' and spacing_rule['boundary_count']:
        raise ValueError('Word-only spacing cannot use Qt mixed-boundary justification')
    if policy.get('spacing_rule') and spacing_rule['boundary_count']==0 and alignment=='justify':
        alignment='left' # No implicit CJK/character justification in a word-only rule.
    option.setAlignment(alignments[alignment]);layout=QTextLayout(text,font);layout.setTextOption(option)
    rich_proof=[]
    if rich:
        from .design_rich_text import formats
        rich_formats,rich_proof=formats(text,pt,rich);layout.setFormats(rich_formats)
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
    if rich:
        from .design_rich_text import verify_layout
        verify_layout(layout,rich_proof)
    for run in layout.glyphRuns():
        raw=run.rawFont()
        for glyph,position in zip(run.glyphIndexes(),run.positions()):
            box=raw.boundingRect(glyph).translated(position)
            if not box.isEmpty():ink=box if ink is None else ink.united(box)
    ink=ink or QRectF()
    width=ink.width()*factor*scale;height=ink.height()*factor
    if width>width_mm+1e-6:raise ValueError('Unbreakable shaped text exceeds flow container')
    return dict(layout=layout,ink=ink,factor=factor,width_mm=width,height_mm=height,lines=lines,
                natural_advance_mm=max((line['natural_width_mm']/scale for line in lines),default=0.),
                text_length=len(text),source_rule=policy,spacing_rule=spacing_rule,
                first_baseline_mm=(layout.lineAt(0).position().y()+layout.lineAt(0).ascent()-ink.top())*factor if lines else None)


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
