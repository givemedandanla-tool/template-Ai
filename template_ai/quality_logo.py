"""Source-derived component identities; human review alone establishes truth."""
from .training_store import digest, text

PAINT = {'path', 'text', 'rect', 'circle', 'ellipse', 'polygon', 'polyline', 'line', 'image', 'use'}


def components(node, source, bounds, *, svg_channel='svg'):
    rows = []; unresolved = []
    for child in node.iter():
        tag = child.tag.rsplit('}', 1)[-1]
        if tag not in PAINT: continue
        identity = child.get('id')
        if not identity or identity not in bounds:
            unresolved.append('MISSING_OBJECT_ID_OR_TRANSFORMED_BOUNDS'); continue
        href = child.get('href') or child.get('{http://www.w3.org/1999/xlink}href') or ''
        if href and not href.startswith(('#', 'data:')): unresolved.append('EXTERNAL_COMPONENT_DEPENDENCY')
        rows.append(dict(id=identity, type=tag, text=tag == 'text'))
    if len(rows) > 200: raise ValueError('單Logo超過200構件，需明列較小品質範圍，不截斷')
    identities = [row['id'] for row in rows]
    if len(set(identities)) != len(identities): unresolved.append('DUPLICATE_SOURCE_OBJECT_ID')
    return dict(root_id=node.get('id'), source_hash=source['hash'], svg_channel=svg_channel,svg_hash=source['file_hashes'][svg_channel],
                component_ids=sorted(identities), text_component_ids=sorted(row['id'] for row in rows if row['text']),
                component_regions={row['id']:vars(bounds[row['id']]) for row in rows},
                component_types={row['id']:row['type'] for row in rows},
                complete=bool(rows and not unresolved), unresolved=sorted(set(unresolved)),
                channel='ACTUAL_SVG_STRUCTURE_NOT_NATIVE_AI_TRUTH', original_correspondence='REQUIRES_HUMAN_REVIEW')


def validate_truth(evidence, source, elements, bounds):
    if not isinstance(evidence, dict) or not {'root_id','component_ids','review_reason','original_correspondence_confirmed'}<=set(evidence) or not set(evidence)<={'root_id','component_ids','review_reason','original_correspondence_confirmed','text_component_ids'}:
        raise ValueError('Logo真值需明列原稿群組、完整構件及人工對照理由')
    text(evidence['review_reason'], '完整Logo原稿圖文對照依據', 2000)
    if evidence['original_correspondence_confirmed'] is not True: raise ValueError('向量衍生檔不自動證明原始Illustrator完整Logo')
    ids = evidence['component_ids']
    if not isinstance(ids, list) or not ids or len(ids)>200 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('需逐項完整Logo構件ID，不能空白／重複／超限')
    roots = [node for node in elements if node.get('id') == evidence['root_id']]
    if len(roots) != 1: raise ValueError('原稿Logo群組ID不唯一或失聯')
    actual = components(roots[0], source, bounds)
    if not actual['complete'] or set(ids) != set(actual['component_ids']): raise ValueError('人工完整構件與已核對向量群組不一致／尚有外部或未知構件')
    semantic_ids=evidence.get('text_component_ids')
    if semantic_ids is not None:
        if not isinstance(semantic_ids,list) or any(not isinstance(i,str) for i in semantic_ids) or len(set(semantic_ids))!=len(semantic_ids) or len(semantic_ids)>200:raise ValueError('人工文字區域需明列有界且不重複的原稿物件ID')
        by_id={node.get('id'):node for node in roots[0].iter() if node.get('id')};covered=set()
        for identity in semantic_ids:
            node=by_id.get(identity)
            if node is None or identity not in bounds:raise ValueError('人工文字區域不在已核實完整Logo群組')
            leaves={child.get('id') for child in node.iter() if child.tag.rsplit('}',1)[-1] in PAINT}
            if not leaves or not leaves<=set(ids) or covered.intersection(leaves):raise ValueError('人工文字區域不可重複包含相同構件／超出Logo；不能重複增加分母')
            covered.update(leaves);actual['component_regions'][identity]=vars(bounds[identity])
        actual['text_component_ids']=sorted(semantic_ids)
        actual['text_paint_ids']=sorted(covered)
    actual['text_content_manually_reviewed']=semantic_ids is not None
    return dict(actual, review_reason=evidence['review_reason'], original_correspondence='MANUALLY_CONFIRMED_ORIGINAL_AND_DERIVATIVE',
                manually_verified=True, component_digest=digest(actual))
