"""Source-reviewed multi-face text with explicit, content-preserving selectors.

Selectors describe rules, not fixed character offsets copied onto new strings.
Unreviewed selectors may replay only their exact original text. Qt formats and
raw-face verification are shared by measurement, preview and output.
"""
import hashlib
import math
import re

from PySide6.QtGui import QFont, QFontDatabase, QTextCharFormat, QTextLayout

from .font_catalog import analyze_font
from .fonts import font_errors


def resolve_segments(text, policy):
    if (policy.get('status')!='HUMAN_CONFIRMED_SOURCE_RULE' or not policy.get('evidence_refs')
            or not isinstance(text,str) or not text or len(text)>4096):
        raise ValueError('Composite text needs reviewed selectors and bounded full text')
    segments=policy.get('segments')
    if not isinstance(segments,list) or not 1<=len(segments)<=32:
        raise ValueError('Composite span budget exceeded')
    words=list(re.finditer(r'\S+',text));boundaries=[0]+[m.start() for m in words[1:]]+[len(text)]
    result=[];cursor=0
    for segment in segments:
        selector=segment.get('selector',{});kind=selector.get('kind')
        if kind=='WORD_SLICE':
            start,end=selector.get('start'),selector.get('end')
            if type(start) is not int or start<0 or start>=len(words) or end is not None and (type(end) is not int or not start<end<=len(words)):
                raise ValueError('Input has unsupported word structure for source rich-text rule')
            begin,finish=boundaries[start],boundaries[end if end is not None else len(words)]
        elif kind=='EXACT_SOURCE_RANGE':
            if hashlib.sha256(text.encode()).hexdigest()!=policy.get('source_text_sha256'):
                raise ValueError('Source-only spans have no reviewed new-text selector')
            begin,finish=selector.get('start'),selector.get('end')
        elif kind=='LITERAL_PREFIX':
            prefix=selector.get('literal')
            if not isinstance(prefix,str) or not prefix or not text.startswith(prefix):
                raise ValueError('Reviewed static prefix does not match full display text')
            begin,finish=0,len(prefix)
        elif kind=='AFTER_LITERAL_PREFIX':
            prefix=selector.get('literal')
            if not isinstance(prefix,str) or not prefix or not text.startswith(prefix):
                raise ValueError('Reviewed value prefix is missing')
            begin,finish=len(prefix),len(text)
        else:raise ValueError('Unknown source rich-text selector')
        if type(begin) is not int or type(finish) is not int or begin!=cursor or not begin<finish<=len(text):
            raise ValueError('Composite spans must cover every character once in order')
        result.append(dict(segment=segment,start=begin,end=finish,text=text[begin:finish]));cursor=finish
    if cursor!=len(text):raise ValueError('Composite rule leaves text uncovered')
    return result


def formats(text,pt,policy):
    result=[];proof=[]
    for part in resolve_segments(text,policy):
        row=part['segment'];asset=row.get('font_asset');ratio=row.get('pt_ratio')
        if (type(ratio) not in (int,float) or not math.isfinite(ratio) or not .05<=ratio<=20
                or not isinstance(asset,dict) or not asset.get('families')):
            raise ValueError('Composite font/relative point size is invalid')
        family=asset['families'][0]
        if font_errors(asset,family):raise ValueError('Composite source font changed or unavailable')
        tracking=row.get('tracking_mm',0.)
        measured=analyze_font(dict(kind='ASSET',asset=asset),part['text'],pt*ratio,2000,.05,
            (asset.get('styles') or [''])[0] or None,tracking_mm=tracking)
        if not measured.get('measurement_verified'):raise ValueError('Composite segment glyphs/face cannot be verified')
        font=QFontDatabase.font(family,measured['style'],1000);font.setPixelSize(round(1000*ratio))
        horizontal=row.get('horizontal_scale_ratio',1.)
        if type(horizontal) not in (int,float) or not math.isfinite(horizontal) or not .05<=horizontal<=20:
            raise ValueError('Composite horizontal ratio is invalid')
        font.setStretch(round(100*horizontal))
        font.setStyleStrategy(QFont.NoFontMerging);font.setHintingPreference(QFont.PreferNoHinting)
        font.setLetterSpacing(QFont.AbsoluteSpacing,tracking/(pt*25.4/72/1000))
        char=QTextCharFormat();char.setFont(font)
        value=QTextLayout.FormatRange();value.start=len(text[:part['start']].encode('utf-16-le'))//2
        value.length=len(part['text'].encode('utf-16-le'))//2;value.format=char
        result.append(value);proof.append(dict(start=value.start,length=value.length,fingerprint=measured['face_fingerprint']))
    return result,proof


def verify_layout(layout,proof):
    from .font_catalog import face_fingerprint
    for row in proof:
        runs=layout.glyphRuns(row['start'],row['length'])
        if not runs or any(face_fingerprint(run.rawFont())!=row['fingerprint'] for run in runs):
            raise ValueError('Composite layout used an unverified font fallback')
