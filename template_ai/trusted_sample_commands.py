"""Trusted samples through the existing owned quality-command transport."""
from .trusted_sample_pool import TrustedSamplePool,source_restriction
from .quality_rechecks import QualityRechecks


def trace_page(library,pool,identity,offset=0):
    from pathlib import Path
    from collections import Counter
    if type(offset) is not int or offset<0:raise ValueError('用途追溯需50筆分頁')
    candidate=pool.store.get('SAMPLE_CANDIDATE',identity)
    if not candidate:raise ValueError('修正候選不存在')
    graph=QualityRechecks(library).source_dependencies(candidate['work_id'],include_quality_evidence=True);rows=[]
    names=dict(SOURCE='來源檔案',WORK='原始作品',SAMPLE='准入樣本',DATASET='精確訓練資料集',MODEL='語意分類模型',RULE='通用規則',TEMPLATE='幾何模板',STYLE='模板家族',CUSTOMER='既有客戶關聯',GOLD='品質人工真值',QUALITY_SET='獨立品質資料集',PIPELINE='凍結解析版本',PROTOCOL='固定品質測試',QUALITY_REPORT='品質比較憑證',QUALITY_DECISION='品質接受憑證',DEPLOYMENT='部署憑證',GEOMETRY_JOB='幾何訓練工作',AUTO_JOB='來源／候選訓練工作')
    record_kinds=dict(MODEL='SEMANTIC_MODEL',GOLD='QUALITY_GOLD',PIPELINE='QUALITY_PIPELINE',PROTOCOL='QUALITY_PROTOCOL',QUALITY_REPORT='QUALITY_PAIR_REPORT',QUALITY_DECISION='QUALITY_VERSION_DECISION',DEPLOYMENT='QUALITY_PIPELINE_DEPLOYMENT',GEOMETRY_JOB='JOB')
    for node in graph['nodes'][offset:offset+50]:
        parts=node['key'].split(':',2);kind=parts[0];key=parts[1];version=parts[2] if len(parts)>2 else None;label=None;current_revision=None;state=None
        if kind=='SOURCE':
            found=library.db.execute('SELECT original_path FROM sources WHERE id=?',(key,)).fetchone();label=Path(found[0]).name if found and found[0] else None
        elif kind=='WORK':
            found=library.db.execute('SELECT name,revision FROM artworks WHERE id=?',(key,)).fetchone()
            if found:label,current_revision=found
        elif kind in ('TEMPLATE','STYLE'):
            column='id' if kind=='TEMPLATE' else 'family_id';found=library.db.execute("SELECT json_extract(payload,'$.name'),version,state FROM templates WHERE "+column+'=? ORDER BY version DESC LIMIT 1',(key,)).fetchone()
            if found:label,current_revision,state=found
        elif kind!='CUSTOMER':
            found=library.db.execute("SELECT COALESCE(json_extract(payload,'$.name'),json_extract(payload,'$.manifest.name'),json_extract(payload,'$.scope.name'),json_extract(payload,'$.literal'),json_extract(payload,'$.operation')),revision,COALESCE(json_extract(payload,'$.state'),json_extract(payload,'$.phase')) FROM training_records WHERE kind=? AND id=?",(record_kinds.get(kind,kind),key)).fetchone()
            if found:label,current_revision,state=found
        rows.append(dict(key=node['key'],kind=kind,type_label=names.get(kind,'其他歷史憑證'),label=str(label or names.get(kind,'歷史憑證'))[:200],dependency_match=node['dependency_match'],historical_revision=version,current_revision=current_revision,saved_state=state))
    return dict(rows=rows,total_nodes=len(graph['nodes']),offset=offset,counts_by_kind=dict(Counter(n['key'].split(':',1)[0] for n in graph['nodes'])),source_graph_digest=graph['digest'],missing_historical_nodes=graph['missing_historical_nodes'],complete_known_graph=graph['complete_known_graph'],unknown_unrecorded_dependencies=True,weights_loaded=False,images_loaded=False)


def execute(library,command,payload):
    pool=TrustedSamplePool(library)
    if command=='LIST':return pool.directory(**payload)
    if command=='DETAIL':return pool.comparison(**payload)
    if command=='PLAN':return pool.batch_plan(**payload)
    if command=='CONFIRM':return pool.confirm_batch(**payload)
    if command=='RESTRICT_PLAN':return pool.restriction_plan(**payload)
    if command=='RESTRICT':return pool.stop_use(**payload)
    if command=='REDACTION_PLAN':return pool.redaction_plan(**payload)
    if command=='REDACT':return pool.redact_training_copies(**payload)
    if command=='TRACE':return trace_page(library,pool,**payload)
    if command=='PRIVACY_RECORDS':
        sha=pool.store.pins(payload['work_id'])['source_hash'];rows=[]
        for kind in ('SAMPLE','SEMANTIC_MODEL'):
            sql="SELECT id,revision,COALESCE(json_extract(payload,'$.state'),'UNKNOWN') FROM training_records WHERE kind=? AND "
            condition="json_extract(payload,'$.pins.source_hash')=?" if kind=='SAMPLE' else "EXISTS(SELECT 1 FROM json_each(payload,'$.plan.scopes') s WHERE json_extract(s.value,'$.pins.source_hash')=?)"
            matches=list(pool.db.execute(sql+condition+' ORDER BY id LIMIT 51',(kind,sha)))
            for row in matches[:50]:
                effective=pool.store.sample_state(row[0]) if kind=='SAMPLE' else 'RESTRICTED_USE' if source_restriction(pool.store,sha,'SEMANTIC_CLASSIFICATION_LOCAL') else row[2]
                rows.append(dict(kind=kind,id=row[0],revision=row[1],state=row[2],effective_state=effective))
            if len(matches)>50:raise ValueError('此來源副本超過50筆，需明列更小處理範圍')
        return dict(rows=rows,source_hash=sha,actual_record_scope=True,external_copies_known=False)
    raise ValueError('不支援的可信樣本操作')
