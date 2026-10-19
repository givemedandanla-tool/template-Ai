"""Unframed work hypotheses; geometry/text clues are never confirmed identity.

DBSCAN groups nearby source boxes. Explicit size notes condition candidate crops;
ambiguous associations remain review clues, never automatic sample admission.
"""
from dataclasses import asdict
import math
import re

from .model import Rect
from .training_store import digest

DIMENSION = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(mm|cm)?\s*[xX×*＊]\s*(\d+(?:\.\d+)?)\s*(mm|cm)\s*$', re.I)


def original_pdf_texts(source):
    """Private text stays in the existing local review/facts pipeline only."""
    from pathlib import Path
    from .source_links import verify_source
    from .original_pdf_glyphs import extract_pdf_glyphs, GlyphBudget
    before=verify_source(source['current_path'],source['hash']);path=Path(source['current_path'])
    with path.open('rb') as stream:header=stream.read(5)
    if header!=b'%PDF-':return [],dict(state='NOT_PDF_COMPATIBLE')
    if path.stat().st_size>32_000_000:return [],dict(state='BUDGET_EXCEEDED')
    try:
        evidence=extract_pdf_glyphs(source,path.read_bytes(),include_private_text=True)
    except GlyphBudget:return [],dict(state='BUDGET_EXCEEDED')
    except Exception as error:
        verify_source(source['current_path'],source['hash'])
        return [],dict(state='UNAVAILABLE',reason=type(error).__name__)
    after=verify_source(source['current_path'],source['hash'])
    if before.stat!=after.stat:raise ValueError('Original source changed during glyph analysis')
    if evidence['source_canvas_mapping']!='VERIFIED_PHYSICAL_VIEWPORT':
        return [],dict(state='UNKNOWN_VIEWPORT_DIFFERENCE')
    rows=[]
    for run in evidence['runs']:
        if (run['visibility']=='NONPAINTING_TEXT' or run['unicode_status']!='MAPPED'
                or run['writing_mode']!='HORIZONTAL' or not run.get('_private_text','').strip()):continue
        rect=Rect(**run['source_region_mm'])
        if min(rect.w,rect.h)<=0:continue
        rows.append((run['id'],run['_private_text'].strip(),rect))
    return rows,dict(state='ORIGINAL_GLYPH_RUN_REVIEW_CANDIDATES',document_digest=evidence['document_digest'],
        source_canvas_mapping=evidence['source_canvas_mapping'],glyph_count=evidence['glyph_count'],
        bounds='FONT_METRIC_NOT_CONTAINER_OR_INK',person_and_role='UNKNOWN',visibility='CLIP_AND_OCG_NOT_VERIFIED')


def size_note(value):
    match=DIMENSION.fullmatch(value)
    if not match:return None
    left,left_unit,right,right_unit=match.groups()
    left_unit=(left_unit or right_unit).lower();right_unit=right_unit.lower()
    width=float(left)*(10 if left_unit=='cm' else 1)
    height=float(right)*(10 if right_unit=='cm' else 1)
    if not (1<=width<=2000 and 1<=height<=2000):return None
    return dict(width_mm=width,height_mm=height,status='SOURCE_TEXT_SIZE_CLAIM_NOT_MEASURED_WORK')


def region_hypotheses(texts, page):
    from sklearn.cluster import DBSCAN
    notes=[dict(object_id=key,rect=asdict(rect),**size_note(value))
           for key,value,rect in texts if size_note(value)]
    content=[(key,value,rect) for key,value,rect in texts if not size_note(value)]
    result=dict(version='unframed-size-clues-1',notes=notes,candidates=[],
        state='NO_UNAMBIGUOUS_SIZE_REGION',identity='UNKNOWN',review_required=True)
    if not notes or not content:return result
    # Named engineering hypothesis radius; not a learned print tolerance.
    radius=min(math.hypot(row['width_mm'],row['height_mm']) for row in notes)*.35
    coordinates=[[rect.x+rect.w/2,rect.y+rect.h/2] for _,_,rect in content]
    labels=DBSCAN(eps=radius,min_samples=1,n_jobs=1).fit_predict(coordinates)
    clusters=[]
    for label in sorted(set(labels)):
        members=[row for i,row in enumerate(content) if labels[i]==label]
        x=min(row[2].x for row in members);y=min(row[2].y for row in members)
        right=max(row[2].x+row[2].w for row in members);bottom=max(row[2].y+row[2].h for row in members)
        clusters.append(dict(members=members,frame=Rect(x,y,right-x,bottom-y)))
    proposals=[]
    for note in notes:
        n=note['rect'];nx=n['x']+n['w']/2;ny=n['y']+n['h']/2;eligible=[]
        for index,cluster in enumerate(clusters):
            rect=cluster['frame'];w,h=note['width_mm'],note['height_mm']
            if rect.w>w or rect.h>h or w>page.w or h>page.h:continue
            distance=math.hypot(rect.x+rect.w/2-nx,rect.y+rect.h/2-ny)
            if distance<=math.hypot(w,h):eligible.append((distance,index))
        eligible.sort()
        if not eligible or (len(eligible)>1 and eligible[1][0]-eligible[0][0]<radius):continue
        proposals.append((note,eligible[0][1]))
    # A cluster associated with multiple notes is ambiguous, not duplicated work truth.
    for note,index in proposals:
        if sum(other==index for _,other in proposals)!=1:continue
        cluster=clusters[index];rect=cluster['frame'];w,h=note['width_mm'],note['height_mm']
        x=max(page.x,min(rect.x+rect.w/2-w/2,page.x+page.w-w))
        y=max(page.y,min(rect.y+rect.h/2-h/2,page.y+page.h-h))
        crop=Rect(x,y,w,h)
        result['candidates'].append(dict(key='unframed-'+digest([note,index,asdict(crop)]),crop=asdict(crop),
            object_ids=sorted(row[0] for row in cluster['members']),size_note_ref=note['object_id'],
            basis='DBSCAN_BOX_CENTRES_AND_EXPLICIT_SIZE_NOTE_HYPOTHESIS',radius_mm=radius,
            extent='CENTERED_CONTENT_PROPOSAL_NOT_OBSERVED_WORK_EDGE',review_required=True))
    if result['candidates']:result['state']='PENDING_SOURCE_REGION_REVIEW'
    return result
