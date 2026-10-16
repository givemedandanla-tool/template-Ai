"""Trusted samples through the existing owned quality-command transport."""
from .trusted_sample_pool import TrustedSamplePool
from .quality_rechecks import QualityRechecks


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
    if command=='TRACE':
        row=pool.store.get('SAMPLE_CANDIDATE',payload['identity'])
        if not row:raise ValueError('修正候選不存在')
        return QualityRechecks(library).source_dependencies(row['work_id'],include_quality_evidence=True)
    if command=='PRIVACY_RECORDS':
        sha=pool.store.pins(payload['work_id'])['source_hash'];rows=[]
        for kind in ('SAMPLE','SEMANTIC_MODEL'):
            sql="SELECT id,revision,COALESCE(json_extract(payload,'$.state'),'UNKNOWN') FROM training_records WHERE kind=? AND "
            condition="json_extract(payload,'$.pins.source_hash')=?" if kind=='SAMPLE' else "EXISTS(SELECT 1 FROM json_each(payload,'$.plan.scopes') s WHERE json_extract(s.value,'$.pins.source_hash')=?)"
            matches=list(pool.db.execute(sql+condition+' ORDER BY id LIMIT 51',(kind,sha)))
            rows.extend(dict(kind=kind,id=r[0],revision=r[1],state=r[2]) for r in matches[:50])
            if len(matches)>50:raise ValueError('此來源副本超過50筆，需明列更小處理範圍')
        return dict(rows=rows,source_hash=sha,actual_record_scope=True,external_copies_known=False)
    raise ValueError('不支援的可信樣本操作')
