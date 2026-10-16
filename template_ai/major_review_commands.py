"""Major review projections on the original quality command transport."""
import json
from collections import Counter
from .quality_rechecks import QualityRechecks


def execute(library,command,payload):
    service=QualityRechecks(library);store=service.store
    if command=='PLAN':return service.source_plan(**payload)
    if command=='CONFIRM':return service.confirm_source(**payload)
    if command=='JOB_PLAN':
        from .major_review_jobs import plan
        return plan(library,**payload)
    if command=='CREATE_JOB':
        from .major_review_jobs import create
        from .automatic_training import AutomaticTraining
        return create(AutomaticTraining(library),**payload)
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
    if command=='STATUS':
        case=store.get('QUALITY_MAJOR_RECHECK',payload['case_id'])
        if not case or case['plan'].get('mode')!='SOURCE_EVIDENCE':raise ValueError('此來源證據重大重審案件不存在；品質評估案件請由既有品質總覽開啟')
        rows=[]
        for kind,identity,revision,raw in library.db.execute("SELECT kind,id,revision,payload FROM training_records WHERE kind IN ('QUALITY_WORK_QUARANTINE','QUALITY_TEMPLATE_QUARANTINE') AND json_extract(payload,'$.case_id')=? ORDER BY kind,id",(case['id'],)):
            row=json.loads(raw);row.update(kind=kind,id=identity,revision=revision)
            state='REAPPROVED' if row['state']=='RESOLVED_AFTER_NEW_HUMAN_FACTS' else row.get('review_state','UNSCANNED')
            if state=='UNSCANNED' and row.get('precheck')=='SOURCE_UNKNOWN':state='UNKNOWN'
            if state=='PROCESSING' and row.get('analysis_job_id'):
                from .automatic_training import AutomaticTraining
                job=store.get('AUTO_JOB',row['analysis_job_id']);phase=AutomaticTraining(library).phase(job) if job else 'INTERRUPTED'
                if phase!='RUNNING':state='INTERRUPTED' if phase in ('INTERRUPTED','FAILED_SYSTEM') else 'CANCELLED' if phase=='CANCELLED' else 'NEEDS_MANUAL'
            row['effective_state']=state;rows.append(row)
        counts=dict(Counter(row['effective_state'] for row in rows));filtered=[row for row in rows if all(term in json.dumps(row,ensure_ascii=False).casefold() for term in query.casefold().split())]
        return dict(case=case,summary=dict(total=len(rows),checked=sum(count for state,count in counts.items() if state not in ('UNSCANNED','UNKNOWN','PROCESSING','INTERRUPTED','CANCELLED')),states=counts,whole_corpus_safe=False,unknown_unrecorded_dependencies=True),total=len(filtered),rows=filtered[offset:offset+50],offset=offset,coverage=case['plan']['coverage'])
    raise ValueError('重大重審命令不支援')
