"""Major review projections on the original quality command transport."""
import json
from collections import Counter
from .quality_rechecks import QualityRechecks


def execute(library,command,payload):
    service=QualityRechecks(library);store=service.store
    if command=='PLAN':return service.source_plan(**payload)
    if command=='CONFIRM':return service.confirm_source(**payload)
    if command=='FINDING_PLAN':
        from .major_review_findings import plan
        return plan(service,**payload)
    if command=='CONFIRM_FINDING':
        from .major_review_findings import confirm
        return confirm(service,**payload)
    if command=='REOPEN_PLAN':
        from .major_review_findings import reopen_plan
        return reopen_plan(service,**payload)
    if command=='REOPEN_UNIT':
        from .major_review_findings import reopen
        return reopen(service,**payload)
    if command=='TEMPLATE_PLAN':
        from .major_template_review import plan
        return plan(service,**payload)
    if command=='CONFIRM_TEMPLATE':
        from .major_template_review import confirm
        return confirm(service,**payload)
    if command=='JOB_PLAN':
        from .major_review_jobs import plan
        return plan(library,**payload)
    if command=='CREATE_JOB':
        from .major_review_jobs import create
        from .automatic_training import AutomaticTraining
        return create(AutomaticTraining(library),**payload)
    if command=='JOB':
        from .automatic_training import AutomaticTraining
        job=store.get('AUTO_JOB',payload['job_id'])
        if not job or job.get('operation')!='MAJOR_SOURCE_RECHECK' or job['scope']['case_id']!=payload['case_id']:raise ValueError('分析工作不屬於目前來源重審案件')
        return dict(job=job,effective_phase=AutomaticTraining(library).phase(job))
    if command=='ANALYSIS':
        unit=store.get('QUALITY_WORK_QUARANTINE',payload['unit_id'])
        if not unit or unit['case_id']!=payload['case_id'] or not unit.get('analysis_id'):raise ValueError('此件尚無已保存的實際分析；請先重分析並讀回')
        result=store.get('QUALITY_SOURCE_REANALYSIS',unit['analysis_id'])
        from .training_store import digest
        if not result or digest(result)!=unit.get('analysis_digest') or result['case_id']!=unit['case_id'] or unit['work_id'] not in result['work_ids']:raise ValueError('舊新對照憑證已變更，未混配其他來源')
        wid=unit['work_id'];current=store.pins(wid)==result['source_pins'][wid];raw=library.db.execute('SELECT payload FROM artwork_revisions WHERE artwork_id=? AND revision=?',(wid,unit['pins']['work_revision'])).fetchone()
        return dict(unit=unit,analysis=result,current=current,original_work=json.loads(raw[0]) if raw else None,formal_eligible=False)
    offset=payload.get('offset',0);query=payload.get('query','')
    if type(offset) is not int or offset<0 or not isinstance(query,str) or len(query)>500:raise ValueError('重大重審搜尋範圍無效')
    if command=='CASES':
        where="kind='QUALITY_MAJOR_RECHECK' AND json_extract(payload,'$.plan.mode')='SOURCE_EVIDENCE'";args=[]
        for term in query.casefold().split():where+=' AND instr(training_casefold(id||payload),?)>0';args.append(term)
        total=library.db.execute('SELECT count(*) FROM training_records WHERE '+where,args).fetchone()[0]
        rows=[]
        for identity in library.db.execute('SELECT id FROM training_records WHERE '+where+' ORDER BY rowid DESC LIMIT 50 OFFSET ?',(*args,offset)):
            case=store.get('QUALITY_MAJOR_RECHECK',identity[0]);rows.append(dict(id=case['id'],revision=case['revision'],state=case['state'],category=case['plan']['category'],affected_works=case['affected_works'],affected_templates=case['affected_templates']))
        return dict(rows=rows,total=total,offset=offset)
    if command=='JOBS':
        from .automatic_training import AutomaticTraining
        where="kind='AUTO_JOB' AND json_extract(payload,'$.operation')='MAJOR_SOURCE_RECHECK' AND json_extract(payload,'$.scope.case_id')=?";args=[payload['case_id']]
        total=library.db.execute('SELECT count(*) FROM training_records WHERE '+where,args).fetchone()[0];rows=[]
        for row in library.db.execute('SELECT id FROM training_records WHERE '+where+' ORDER BY rowid DESC LIMIT 50 OFFSET ?',(*args,offset)):
            job=store.get('AUTO_JOB',row[0]);rows.append(dict(id=job['id'],phase=AutomaticTraining(library).phase(job),source_count=len(job['items']),work_count=len(job['scope']['work_ids'])))
        return dict(rows=rows,total=total,offset=offset)
    if command=='STATUS':
        case=store.get('QUALITY_MAJOR_RECHECK',payload['case_id'])
        if not case or case['plan'].get('mode')!='SOURCE_EVIDENCE':raise ValueError('此來源證據重大重審案件不存在；品質評估案件請由既有品質總覽開啟')
        rows=[]
        for kind,identity,revision,raw in library.db.execute("SELECT kind,id,revision,payload FROM training_records WHERE kind IN ('QUALITY_WORK_QUARANTINE','QUALITY_TEMPLATE_QUARANTINE') AND json_extract(payload,'$.case_id')=? ORDER BY kind,id",(case['id'],)):
            row=json.loads(raw);row.update(kind=kind,id=identity,revision=revision)
            state=row.get('review_state','UNSCANNED')
            if row['state']=='RESOLVED_AFTER_NEW_HUMAN_FACTS':
                from .major_review_findings import resolution_current
                state=row.get('review_state','REAPPROVED') if resolution_current(library.db,row) else 'STALE_REVIEW'
            elif kind=='QUALITY_TEMPLATE_QUARANTINE' and row['state']=='REPLACED_WITH_VERIFIED_TEMPLATE':
                from .major_template_review import clearance_current
                from .model import Template
                try:template=Template.from_dict(library.object_snapshot('TEMPLATE',row['approved_template_id'])['payload']);valid=clearance_current(library.db,case['id'],template)
                except (ValueError,KeyError):valid=False
                if not valid:state='STALE_REVIEW'
            if state=='UNSCANNED' and row.get('precheck')=='SOURCE_UNKNOWN':state='UNKNOWN'
            if state=='PROCESSING' and row.get('analysis_job_id'):
                from .automatic_training import AutomaticTraining
                job=store.get('AUTO_JOB',row['analysis_job_id']);phase=AutomaticTraining(library).phase(job) if job else 'INTERRUPTED'
                if phase!='RUNNING':state='INTERRUPTED' if phase in ('INTERRUPTED','FAILED_SYSTEM') else 'CANCELLED' if phase=='CANCELLED' else 'NEEDS_MANUAL'
            row['effective_state']=state;rows.append(row)
        counts=dict(Counter(row['effective_state'] for row in rows));filtered=[row for row in rows if all(term in json.dumps(row,ensure_ascii=False).casefold() for term in query.casefold().split())]
        return dict(case=case,summary=dict(total=len(rows),checked=sum(count for state,count in counts.items() if state not in ('UNSCANNED','UNKNOWN','PROCESSING','INTERRUPTED','CANCELLED','STALE_REVIEW')),states=counts,whole_corpus_safe=False,unknown_unrecorded_dependencies=True),total=len(filtered),rows=filtered[offset:offset+50],offset=offset,coverage=case['plan']['coverage'])
    raise ValueError('重大重審命令不支援')
