"""Bounded source hypotheses using Inkscape geometry, not native Illustrator truth.

All boxes/text/ownership remain review candidates. Exact bytes identify content,
never a person or customer. The mature SVG renderer supplies transformed bounds.
"""
from dataclasses import asdict
import csv
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from .background import file_digest
from .importer import inkscape_path
from .model import Rect,Slot
from .source_links import verify_source
from .training_store import digest
from .semantic_fields import recognize

ANALYSER_VERSION='source-hypotheses-7-original-glyph-size-clues'


def vector_objects(source,assets):
    verify_source(source['current_path'],source['hash'])
    path=Path(source.get('svg') or '')
    if not source.get('svg') or not path.is_file():raise ValueError('無可核對向量結構，請人工作品框選／本機OCR線索，不假稱已解析')
    if path.is_symlink() or path.stat().st_size>2_000_000 or file_digest(path)!=source['file_hashes']['svg']:raise ValueError('向量來源已變更或超出2MB結構預算')
    root=ET.parse(path).getroot();elements=list(root.iter())
    if len(elements)>4000:raise ValueError('來源超過4000物件，需按作品縮小分析範圍')
    executable=inkscape_path()
    if not executable:raise ValueError('缺少Inkscape幾何引擎，保持待人工')
    environment=os.environ.copy();environment['INKSCAPE_PROFILE_DIR']=str(Path(assets)/'source-query')
    process=subprocess.run([executable,'--query-all',str(path)],capture_output=True,text=True,timeout=30,env=environment,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if process.returncode or len(process.stdout)>1_048_576:raise ValueError('來源幾何查詢失敗／超出預算')
    bounds={}
    for row in csv.reader(process.stdout.splitlines()):
        if len(row)==5:
            try:
                rect=Rect(*(float(value)*25.4/96 for value in row[1:]))
                if rect.valid():bounds[row[0]]=rect
            except ValueError:pass
    if file_digest(path)!=source['file_hashes']['svg']:raise ValueError('幾何查詢期間來源變更')
    verify_source(source['current_path'],source['hash'])
    return root,elements,bounds


def contains(outer,inner,tolerance=.05):
    return inner.x>=outer.x-tolerance and inner.y>=outer.y-tolerance and inner.x+inner.w<=outer.x+outer.w+tolerance and inner.y+inner.h<=outer.y+outer.h+tolerance


def classify(value):
    return recognize(value)['slot_kind']


def analyse_source(source,assets,semantic_model=None,model_context=None):
    root,elements,bounds=vector_objects(source,assets)
    page=Rect(0,0,source['width_mm'],source['height_mm']);byid={e.get('id'):e for e in elements if e.get('id')}
    candidate_rects=[]
    for node in elements:
        key=node.get('id');rect=bounds.get(key)
        if node.tag.rsplit('}',1)[-1]=='rect' and rect and min(rect.w,rect.h)>=15 and contains(page,rect):
            candidate_rects.append((key,rect))
    # Outer backgrounds do not collapse distinct inner card candidates.
    regions=[(key,rect) for key,rect in candidate_rects if not any(
        other!=key and contains(rect,r) and rect.w*rect.h>r.w*r.h*1.01 for other,r in candidate_rects)]
    if not regions:regions=[('page-region-hypothesis',page)]
    if len(regions)>100:raise ValueError('作品候選超過100，需縮小來源範圍，不靜默截斷')
    logos=[];logo_members=set()
    for node in elements:
        label=' '.join([node.get('id',''),*[v for k,v in node.attrib.items() if k.endswith('label')]])
        if node.tag.rsplit('}',1)[-1]=='g' and re.search(r'(?i)logo|brand',label) and node.get('id') in bounds:
            logos.append(node);logo_members.update(id(n) for n in node.iter())
    texts=[]
    for node in elements:
        if id(node) in logo_members:continue
        value=node.get('aria-label') or (''.join(node.itertext()) if node.tag.rsplit('}',1)[-1]=='text' else '')
        rect=bounds.get(node.get('id'))
        if value.strip() and rect:texts.append((node.get('id'),value.strip(),rect))
    from .source_region_hypotheses import original_pdf_texts,region_hypotheses,size_note
    native_texts,native_evidence=original_pdf_texts(source)
    # Exact original runs supplement outlined derivatives; no proximity-based identity merge.
    for native,value,rect in native_texts:
        if any(contains(bounds[node.get('id')],rect) for node in logos):continue
        if any(value==old_value and contains(old_rect,rect,tolerance=.5) for _,old_value,old_rect in texts):continue
        texts.append((native,value,rect))
    region_evidence=region_hypotheses(texts,page)
    if regions==[('page-region-hypothesis',page)] and region_evidence['candidates']:
        proposed=[(row['key'],Rect(**row['crop'])) for row in region_evidence['candidates']]
        content=[row for row in texts if not size_note(row[1])]
        # Uncovered or ambiguously covered data keeps the whole-page fallback.
        if all(sum(contains(crop,row[2]) for _,crop in proposed)==1 for row in content):
            regions=proposed
    from .source_text_evidence import text_evidence
    text_proofs=text_evidence(source,elements,bounds,logo_members)
    result=[]
    for key,crop in sorted(regions,key=lambda item:(item[1].y,item[1].x,item[0])):
        slots=[];observations=[];counts={};clues=[];companies=[];source_map={};oversized=[]
        local=sorted([row for row in texts if contains(crop,row[2])],key=lambda row:(row[2].y,row[2].x,row[0]))
        if len(local)+len(logos)>200:raise ValueError('單作品標記超過200，需人工縮小作品')
        name_used=False
        for native,value,rect in local:
            if len(value)>2048:
                import hashlib
                oversized.append(dict(svg_object_id=native,characters=len(value),sha256=hashlib.sha256(value.encode()).hexdigest(),region=asdict(rect)))
                clues.append('來源文字超出2048字觀察資源預算；未截斷為假完整文字，需來源校正')
                continue
            semantic=recognize(value,model=semantic_model);kind=semantic['slot_kind']
            identity='box-'+digest([source['hash'],source.get('page',1),key,native])[:28]
            if kind is None:
                clues.append('文字語意或平台欄位待確認；未從位置猜人名／職稱')
                observations.append(dict(id='obs-'+identity,slot_id=None,text=value,object_type='TEXT',classification='UNKNOWN',region=asdict(rect),prior_prediction='UNCONFIRMED_SEMANTIC_UNKNOWN',semantic=semantic))
                continue
            if kind=='name':name_used=True
            index=counts.get(kind,0);counts[kind]=index+1
            local_rect=Rect(rect.x-crop.x,rect.y-crop.y,rect.w,rect.h)
            owner='p1'
            if kind=='company':owner='c'+str(len(companies)+1);companies.append(owner)
            slot=Slot(kind,owner,local_rect,index=index,id=identity,required=kind=='name')
            slots.append(asdict(slot))
            source_map[identity]=dict(svg_object_id=native,source_hash=source['hash'],svg_hash=source['file_hashes']['svg'],
                original_run_ref=native if native.startswith('PDF_GLYPH_RUN:') else None)
            observations.append(dict(id='obs-'+identity,slot_id=identity,text=value,object_type='TEXT',classification='FIELD',region=asdict(rect),prior_prediction='UNCONFIRMED_SOURCE_DERIVATIVE',semantic=semantic))
        for node in logos:
            rect=bounds[node.get('id')]
            if not contains(crop,rect):continue
            owner='c'+str(len(companies)+1);companies.append(owner)
            identity='box-'+digest([source['hash'],source.get('page',1),key,node.get('id')])[:28]
            slots.append(asdict(Slot('logo',owner,Rect(rect.x-crop.x,rect.y-crop.y,rect.w,rect.h),id=identity)))
            source_map[identity]=dict(svg_object_id=node.get('id'),source_hash=source['hash'],svg_hash=source['file_hashes']['svg'])
            observations.append(dict(id='obs-'+identity,slot_id=identity,text='完整複合Logo／公司身分待核對',object_type='LOGO_PART',classification='LOGO',region=asdict(rect),prior_prediction='UNCONFIRMED_WHOLE_GROUP'))
            from .quality_logo import components
            observations[-1]['component_prediction']=components(node,source,bounds)
        result.append(dict(key=digest([ANALYSER_VERSION,source['hash'],source.get('page',1),key,asdict(crop)]),
            source_id=source['id'],source_hash=source['hash'],source_page=source.get('page',1),source_object_id=key,
            crop=asdict(crop),work_width=crop.w,work_height=crop.h,slots=slots,observations=observations,
            company_bindings={'p1':companies} if name_used else {},visual_confirmed=False,
            analysis_version=ANALYSER_VERSION,review_state='AI_PENDING_REVIEW',
            evidence=dict(method='INKSCAPE_TRANSFORMED_BOUNDS_AND_SOURCE_LABELS',native_illustrator_mapping='UNKNOWN',
                physical_size='SOURCE_GEOMETRY_HYPOTHESIS_REQUIRES_CONFIRMATION',
                original_glyph_analysis=native_evidence,unframed_region_hypotheses=region_evidence,font_size='DEFAULT_REQUIRES_SOURCE_REVIEW',
                confidence='UNVALIDATED_HEURISTIC',issues=sorted(set(clues)),oversized_text=oversized,
                object_ids=[row[0] for row in local],source_unchanged=True,
                semantic_model=model_context or dict(state='NONE'),
                slot_source_map=source_map,
                text_object_evidence={identity:text_proofs[mapping['svg_object_id']] for identity,mapping in source_map.items() if mapping['svg_object_id'] in text_proofs},
                semantic_candidates={o['id']:o['semantic'] for o in observations if o.get('semantic')})))
    verify_source(source['current_path'],source['hash'])
    return result
