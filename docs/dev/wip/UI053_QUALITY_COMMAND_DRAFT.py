"""Bounded quality commands reuse the existing owned subprocess transport."""
from .coverage_command import MAX_BYTES


def execute(root,command,payload):
    from .storage import Library
    from .training_store import TrainingStore
    from .quality_gold import QualityGold
    from .quality_sets import QualitySets
    from .quality_policy import QualityPolicies
    from .quality_pipeline import QualityPipelines
    from .quality_protocol import QualityProtocols
    from .quality_jobs import EvaluationJobs
    from .quality_reports import QualityReports
    from .quality_diagnostics import QualityDiagnostics
    from .quality_rechecks import QualityRechecks
    with Library(root) as library:
        store=TrainingStore(library)
        if command=='LIST':
            kind=payload['kind'];offset=payload.get('offset',0);query=payload.get('query','')
            if kind not in ('QUALITY_GOLD','QUALITY_SET','QUALITY_POLICY','QUALITY_PIPELINE','QUALITY_PROTOCOL','QUALITY_PAIR_REPORT','QUALITY_MAJOR_RECHECK','QUALITY_WORK_QUARANTINE','SEMANTIC_MODEL'):raise ValueError('不支援的品質目錄')
            if type(offset) is not int or offset<0 or not isinstance(query,str) or len(query)>500:raise ValueError('目錄範圍無效')
            where='kind=?';args=[kind]
            for token in query.casefold().split():where+=" AND instr(training_casefold(id||' '||payload),?)>0";args.append(token)
            total=library.db.execute('SELECT count(*) FROM training_records WHERE '+where,args).fetchone()[0]
            sql="SELECT id,revision,COALESCE(json_extract(payload,'$.name'),json_extract(payload,'$.manifest.name'),json_extract(payload,'$.plan.name'),json_extract(payload,'$.work_id'),''),COALESCE(json_extract(payload,'$.state'),'') FROM training_records WHERE "+where+' ORDER BY rowid DESC LIMIT 50 OFFSET ?'
            return dict(rows=[dict(id=r[0],revision=r[1],label=r[2],state=r[3]) for r in library.db.execute(sql,(*args,offset))],total=total,offset=offset,images_loaded=False)
        if command=='PLAN_GOLD':return QualityGold(library).plan(**payload)
        if command=='PLAN_SET':return QualitySets(library).plan(**payload)
        if command=='PLAN_POLICY':return QualityPolicies(library).plan(**payload)
        if command=='FREEZE_PIPELINE':return QualityPipelines(library).freeze(**payload)
        if command=='PLAN_PROTOCOL':return QualityProtocols(library).plan(**payload)
        if command=='CONFIRM':
            service,method={'GOLD':(QualityGold,'confirm'),'SET':(QualitySets,'create'),'POLICY':(QualityPolicies,'approve'),'PROTOCOL':(QualityProtocols,'freeze'),'REPORT':(QualityReports,'save')}[payload['kind']]
            return getattr(service(library),method)(payload['plan'],payload['actor'],payload.get('approved',False))
        if command=='CREATE_PAIR':return EvaluationJobs(library).create_pair(**payload)
        if command=='PAIR_STATUS':
            pair=store.get('QUALITY_PROTOCOL_JOBS',payload['protocol_id'])
            if not pair:return dict(jobs={},results={})
            jobs={side:EvaluationJobs(library).get(identity) for side,identity in pair['jobs'].items()}
            results={side:store.get('QUALITY_EVAL_RESULT',job.get('result_id','')) for side,job in jobs.items()}
            return dict(jobs={side:{key:row.get(key) for key in ('id','revision','phase','items','result_id','side','error')} for side,row in jobs.items()},results=results)
        if command=='COMPARE':return QualityReports(library).plan(payload['protocol_id'])
        if command=='DECIDE':return QualityReports(library).decide(**payload)
        if command=='WITHDRAW_DECISION':return QualityReports(library).withdraw(**payload)
        if command=='EXPOSE':return QualityProtocols(library).expose(**payload)
        if command=='DIAGNOSTICS':return QualityDiagnostics(library).page(**payload)
        if command=='DIAGNOSTIC_DETAIL':return QualityDiagnostics(library).detail(**payload)
        if command=='PLAN_RECHECK':return QualityRechecks(library).plan(**payload)
        if command=='CONFIRM_RECHECK':return QualityRechecks(library).confirm(**payload)
        if command=='RESOLVE_RECHECK':return QualityRechecks(library).resolve(**payload)
        raise ValueError('品質操作不支援')


def run_command(root,command,payload,**kwargs):
    from .coverage_command import run_command as transport
    return transport(root,command,payload,module='template_ai.quality_command',**kwargs)


if __name__=='__main__':
    from .coverage_command import main
    main(execute)
