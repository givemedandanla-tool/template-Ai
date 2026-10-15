"""Read-only, bounded three-level comparisons; scores are review clues, not identity.

SHA-256: bytes. Difference hash/Hamming: rendered page similarity. A canonical
crop raster+content signature: duplicate work candidates. Quantised normalized
slot geometry/Jaccard: template structure. These never authorize deduplication.
"""
from collections import Counter
from pathlib import Path
import tempfile
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from .background import file_digest
from .batch_import import healthy_source
from .importer import import_file
from .source_analysis import analyse_source
from .training_store import digest,TrainingStore

VERSION='three-level-readonly-1'
MAX_WORKS=500
MAX_COMPARISONS=100000


def image_signature(image):
    if image.isNull():raise ValueError('無可讀影像，不能判定相似')
    small=image.scaled(9,8,Qt.IgnoreAspectRatio,Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
    bits=0
    for y in range(8):
        for x in range(8):bits=(bits<<1)|int(small.pixelColor(x,y).red()>small.pixelColor(x+1,y).red())
    normalized=image.scaled(256,256,Qt.IgnoreAspectRatio,Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
    import hashlib
    return dict(dhash=bits,raster=hashlib.sha256(bytes(normalized.constBits())).hexdigest())


def structure(payload):
    w=payload.get('work_width',payload.get('width_mm'));h=payload.get('work_height',payload.get('height_mm'))
    if not w or not h:return None
    result=[]
    for slot in payload.get('slots',[]):
        r=slot['rect'];result.append((slot['kind'],*[round(r[k]/(w if k in ('x','w') else h)*50) for k in ('x','y','w','h')]))
    return sorted(result)


def structure_score(a,b):
    if not a or not b:return None
    x=Counter(map(tuple,a));y=Counter(map(tuple,b));return sum((x&y).values())/sum((x|y).values())


def work_descriptor(payload,image,source):
    c=payload['crop'];w=source['width_mm'];h=source['height_mm']
    crop=image.copy(round(c['x']/w*image.width()),round(c['y']/h*image.height()),max(1,round(c['w']/w*image.width())),max(1,round(c['h']/h*image.height())))
    signature=image_signature(crop)
    content=sorted(o.get('text','') for o in payload.get('observations',[]))
    return dict(structure=structure(payload),design=digest([round(c['w'],2),round(c['h'],2),signature['raster'],content]))


def inspect_report(library,report,cancel=None,progress=None):
    comparisons=0;works=[];pages=[];unknown=[];near=[];duplicates=[];similar=[]
    templates=[]
    # Stable, explicitly bounded population, never silently infer zero beyond it.
    for row in library.db.execute('SELECT id,payload FROM templates ORDER BY id LIMIT 501'):
        import json
        templates.append((row[0],structure(json.loads(row[1]))))
    if len(templates)>500:unknown.append(dict(scope='templates',reason='超過500模板比較預算，尚未全庫核實'));templates=templates[:500]
    known=list(library.db.execute('SELECT id,source_id,payload FROM artworks ORDER BY id LIMIT 501'))
    if len(known)>500:unknown.append(dict(scope='works',reason='超過500既有作品比較預算，尚未全庫核實'));known=known[:500]
    source_cache={};read_bytes=0;store=TrainingStore(library)
    for row in known:
        import json
        payload=json.loads(row[2]);source=source_cache.get(row[1])
        if source is None:
            source=library.source(row[1]);read_bytes+=source.get('byte_size',0)
            if read_bytes>100*1024*1024 or not healthy_source(source):source=False
            source_cache[row[1]]=source
        if not source or payload.get('review_state')=='SUPERSEDED':
            unknown.append(dict(scope=row[0],reason='來源／衍生快取未核實或作品已被取代'));continue
        facts=store.get('FACTS',row[0])
        if facts:payload=dict(payload,observations=facts.get('observations',[]))
        # Existing work geometry remains comparable even if no semantic truth exists.
        try:
            d=work_descriptor(payload,QImage(source['image']),source);d.update(id=row[0],source_hash=source['hash']);works.append(d)
        except (ValueError,KeyError,TypeError):unknown.append(dict(scope=row[0],reason='作品描述不足，未作相同判定'))
    with tempfile.TemporaryDirectory(prefix='template-preflight-') as temp:
        for index,item in enumerate(report['items']):
            if cancel and cancel.is_set():
                from .source_links import ScanCancelled
                raise ScanCancelled()
            if item['status']=='FAILED':unknown.append(dict(scope=item['path'],reason=item['reason']));continue
            try:
                source=item.get('reuse_source')
                if not source:
                    source=import_file(item['path'],temp,item['page']);source.update(id='preflight-'+item['id'],current_path=item['path'])
                if source['hash']!=item['expected_hash']:raise ValueError('掃描期間來源變更，請重新預檢')
                image=QImage(source['image']);sig=image_signature(image)
                current=dict(path=item['path'],hash=source['hash'],width=source['width_mm'],height=source['height_mm'],**sig)
                for other in pages:
                    if comparisons>=MAX_COMPARISONS:raise ValueError('比較預算已滿，剩餘範圍未核實')
                    comparisons+=1
                    distance=(sig['dhash']^other['dhash']).bit_count()
                    aspect=abs(current['width']/current['height']-other['width']/other['height'])
                    if source['hash']!=other['hash'] and distance<=6 and aspect<.01:
                        near.append(dict(left=other['path'],right=item['path'],hamming_distance=distance,bits=64,classification='VISUAL_NEAR_CANDIDATE',warning='未校準；須比對內容，不等同檔案相同'))
                pages.append(current)
                try:predictions=analyse_source(source,temp)
                except ValueError as error:
                    predictions=[];unknown.append(dict(scope=item['path'],reason=str(error)))
                for p in predictions:
                    if len(works)>=MAX_WORKS or comparisons>=MAX_COMPARISONS:
                        unknown.append(dict(scope=item['path'],reason='作品比較預算已滿，未檢查其餘作品'));break
                    d=work_descriptor(p,image,source);d.update(id=p['key'],source_hash=source['hash'],path=item['path'])
                    for old in works:
                        if comparisons>=MAX_COMPARISONS:raise ValueError('比較預算已滿，剩餘作品未核實')
                        comparisons+=1
                        if old['design']==d['design']:duplicates.append(dict(left=old['id'],right=d['id'],source_path=item['path'],classification='EXACT_RENDERED_WORK_CANDIDATE',warning='衍生圖與內容相同；非原生AI物件或客戶身分證明'))
                    for tid,shape in templates:
                        if comparisons>=MAX_COMPARISONS:raise ValueError('比較預算已滿，剩餘模板未核實')
                        comparisons+=1;score=structure_score(d['structure'],shape)
                        if score is not None and score>=.8:similar.append(dict(work=d['id'],template=tid,jaccard=score,classification='STRUCTURE_SIMILAR_CANDIDATE',warning='忽略文字內容；不代表同作品或可直接發布'))
                    works.append(d)
                # Renderer and parser both must leave original bytes unchanged.
                if file_digest(item['path'])!=item['expected_hash']:raise ValueError('預檢來源已變更')
            except (OSError,ValueError,KeyError,TypeError) as error:unknown.append(dict(scope=item['path'],reason=str(error)))
            if progress:progress(index+1,len(report['items']),item['path'])
    result=dict(version=VERSION,near_files=near,duplicate_works=duplicates,similar_templates=similar,unknown=unknown,comparisons=comparisons,automatic_merge=False,thresholds=dict(dhash_max_hamming=6,structure_min_jaccard=.8),calibration='UNVALIDATED_REVIEW_HEURISTIC')
    report.update(similarity=result,near_file_candidates=len(near),artwork_duplicates=len(duplicates),template_similarity=len(similar),similarity_unknown=len(unknown))
    return report
