"""Independent static labels/icons and dynamic values inside a learned container.

Frames are source-reviewed fractions of container width. The shared Qt path
measures every component and rejects overlap/overflow; no customer controls are
added. Local SVG icons must be hash-pinned, self-contained vector resources.
"""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from PySide6.QtCore import QPointF,QRectF
from PySide6.QtGui import QGlyphRun,QRawFont
from PySide6.QtSvg import QSvgRenderer

from .background import file_digest,ensure_embedded_svg


def component_fonts(flow):
    flow=flow or {}
    return [row.get('font_asset') for row in flow.get('rich_text',{}).get('segments',[])]+[
        row.get('font_asset') for row in flow.get('presentation',{}).get('components',[]) if row.get('kind')=='STATIC_TEXT']


def frame(value):
    if (not isinstance(value,list) or len(value)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value)
            or min(value)<0 or value[2]<=0 or value[3]<=0 or value[0]+value[2]>1.0000001):
        raise ValueError('Invalid source component frame per container width')
    return value


def checked_icon(asset):
    if not isinstance(asset,dict) or not isinstance(asset.get('path'),str):raise ValueError('Local icon evidence missing')
    path=Path(asset['path'])
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2_000_000 or file_digest(path)!=asset.get('hash'):
        raise ValueError('Source icon changed,missing or oversized')
    raw=path.read_bytes()
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('Icon external declarations unsupported')
    root=ET.fromstring(raw);nodes=list(root.iter())
    if len(nodes)>4000 or any(node.tag.rsplit('}',1)[-1] in ('text','image','script','foreignObject') for node in nodes):
        raise ValueError('Static icon must be bounded self-contained vector geometry')
    ensure_embedded_svg(path)
    renderer=QSvgRenderer(raw)
    if not renderer.isValid():raise ValueError('Static icon cannot render')
    return renderer


def validate_presentation(presentation):
    if (not isinstance(presentation,dict) or presentation.get('status')!='HUMAN_CONFIRMED_SOURCE_RULE'
            or not presentation.get('evidence_refs')):
        raise ValueError('Static presentation needs reviewed source structure')
    frame(presentation.get('value_frame'))
    parts=presentation.get('components')
    if not isinstance(parts,list) or not 1<=len(parts)<=16:raise ValueError('Static component budget exceeded')
    for part in parts:
        frame(part.get('frame'))
        if part.get('kind')=='STATIC_TEXT':
            if not isinstance(part.get('text'),str) or not part['text'] or len(part['text'])>256:
                raise ValueError('Static label needs bounded source text')
            ratio=part.get('pt_ratio')
            if type(ratio) not in (int,float) or not math.isfinite(ratio) or not .05<=ratio<=20:
                raise ValueError('Static label relative typography is invalid')
        elif part.get('kind')=='SVG_ICON':checked_icon(part.get('asset'))
        else:raise ValueError('Unknown source component kind')
    return presentation


def compose(base,width_mm,pt,scale,presentation):
    from .design_text_flow import shape_flow
    validate_presentation(presentation)
    factor=base['factor'];value_frame=frame(presentation['value_frame'])
    bounds=base['ink'];runs=[];icons=[];rectangles=[]
    dx=value_frame[0]*width_mm/(factor*scale)-bounds.left()
    dy=value_frame[1]*width_mm/factor-bounds.top()
    if base['width_mm']>value_frame[2]*width_mm+1e-6 or base['height_mm']>value_frame[3]*width_mm+1e-6:
        raise ValueError('Dynamic value exceeds learned component frame')

    def translated(original,delta,ratio=1.):
        result=QGlyphRun(original)
        if ratio!=1.:
            raw=QRawFont(original.rawFont());raw.setPixelSize(raw.pixelSize()*ratio);result.setRawFont(raw)
        result.setPositions([QPointF(p.x()*ratio+delta.x(),p.y()*ratio+delta.y()) for p in original.positions()])
        return result

    for original in base['positioned_runs'] if base['positioned_runs'] is not None else base['layout'].glyphRuns():
        runs.append(translated(original,QPointF(dx,dy)))
    rectangles.append(QRectF(value_frame[0]*width_mm,value_frame[1]*width_mm,base['width_mm'],base['height_mm']))
    for part in presentation['components']:
        r=frame(part['frame']);area=QRectF(r[0]*width_mm,r[1]*width_mm,r[2]*width_mm,r[3]*width_mm)
        if part['kind']=='SVG_ICON':
            checked_icon(part['asset']);icons.append(dict(asset=deepcopy(part['asset']),rect=area));rectangles.append(area)
        else:
            asset=part['font_asset'];ratio=part['pt_ratio']
            policy=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',break_rule='NO_WRAP',max_lines_observed=1,
                line_height_factor=1.,alignment='left',evidence_refs=presentation['evidence_refs'])
            shaped=shape_flow(part['text'],asset['families'][0],pt*ratio,scale,area.width(),asset,
                (asset.get('styles') or [''])[0],part.get('tracking_mm',0.),policy,'address')
            if shaped['height_mm']>area.height()+1e-6:raise ValueError('Static label exceeds learned component frame')
            b=shaped['ink'];delta=QPointF(area.x()/(factor*scale)-b.left()*ratio,area.y()/factor-b.top()*ratio)
            for original in shaped['layout'].glyphRuns():runs.append(translated(original,delta,ratio))
            rectangles.append(QRectF(area.x(),area.y(),shaped['width_mm'],shaped['height_mm']))
    for i,a in enumerate(rectangles):
        if any(a.intersects(b) for b in rectangles[i+1:]):raise ValueError('Static component/value collision')
    ink=None
    for run in runs:
        for glyph,position in zip(run.glyphIndexes(),run.positions()):
            box=run.rawFont().boundingRect(glyph).translated(position)
            if not box.isEmpty():ink=box if ink is None else ink.united(box)
    for icon in icons:
        r=icon['rect'];box=QRectF(r.x()/(factor*scale),r.y()/factor,r.width()/(factor*scale),r.height()/factor)
        icon['layout_rect']=box;ink=box if ink is None else ink.united(box)
    result=dict(base,ink=ink,width_mm=ink.width()*factor*scale,height_mm=ink.height()*factor,
        positioned_runs=runs,static_icons=icons,
        first_baseline_mm=(base['layout'].lineAt(0).ascent()+dy-ink.top())*factor)
    return result


def presentation_errors(flow):
    presentation=(flow or {}).get('presentation')
    if not presentation:return []
    try:validate_presentation(presentation);return []
    except (ValueError,OSError,ET.ParseError) as error:return [str(error)]
