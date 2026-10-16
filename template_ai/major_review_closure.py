"""Close only the pinned reviewed case scope; never claim corpus/model/output safety."""
import json,time
from .training_store import digest,text
from .major_review_findings import resolution_current
from .major_template_review import clearance_current
from .model import Template


def plan(service,case_id):
    case=service.store.get('QUALITY_MAJOR_RECHECK',case_id)
    if not case or case['plan'].get('mode')!='SOURCE_EVIDENCE':raise ValueError('來源證據重審案件不存在')
    if case.get('completed'):raise ValueError('此指定範圍已結案；舊收據保留，新疑義請明確重新開啟相關項目')
    rows=[];blockers=[]
    for kind,identity in service.db.execute("SELECT kind,id FROM training_records WHERE kind IN ('QUALITY_WORK_QUARANTINE','QUALITY_TEMPLATE_QUARANTINE') AND json_extract(payload,'$.case_id')=? ORDER BY kind,id",(case_id,)):
        row=service.store.get(kind,identity);valid=False
        if kind=='QUALITY_WORK_QUARANTINE':
            valid=row['state']=='RESOLVED_AFTER_NEW_HUMAN_FACTS' and resolution_current(service.db,row)
        elif row['state']=='REPLACED_WITH_VERIFIED_TEMPLATE':
            try:t=Template.from_dict(service.library.object_snapshot('TEMPLATE',row['approved_template_id'])['payload']);valid=clearance_current(service.db,case_id,t)
            except (ValueError,KeyError):valid=False
        excluded=row['state']=='EXCLUDED_HOLD' and bool(row.get('review_evidence')) and bool(row.get('review_actor'))
        if not valid and not excluded:blockers.append(dict(kind=kind,id=identity,state=row['state'],reason='尚待逐件重審／完整模板核准或目前憑證已過期'))
        rows.append(dict(kind=kind,id=identity,revision=row['revision'],valid=valid,excluded_but_still_untrusted=excluded))
    missing=case['plan'].get('missing_historical_nodes',[])
    if missing:blockers.append(dict(kind='HISTORICAL_MISSING',ids=missing,reason='指定歷史依賴仍失聯，未假造已核對'))
    root=case['plan']['work_id'];current=service.source_dependencies(root,include_quality_evidence=True);known={service.store.get(row['kind'],row['id']).get('work_id') for row in rows if row['kind']=='QUALITY_WORK_QUARANTINE'}
    newly_known=sorted(set(current['affected_work_ids'])-known)
    value=dict(case_id=case_id,case_revision=case['revision'],case_plan_digest=case['plan_digest'],scope='PINNED_ORIGINAL_CASE_UNITS_ONLY',units=rows,total=len(rows),reapproved=sum(row['valid'] for row in rows),excluded_still_untrusted=sum(row['excluded_but_still_untrusted'] for row in rows),blockers=blockers,can_close=bool(rows) and not blockers,new_known_unscanned_work_ids=newly_known,unknown_unrecorded_dependencies=True,whole_corpus_safe=False,models_decontaminated=False,independent_model_quality_approval=False,formal_output_approval=False,old_closure_receipts_preserved=True)
    value['digest']=digest(value);return value


def confirm(service,value,actor,reason,approved=False):
    if approved is not True:raise ValueError('需核對全部指定案件項目與未知範圍，明確結束此受控範圍')
    text(actor,'範圍結案核對者',120);text(reason,'範圍結案依據',2000)
    if value.get('digest')!=digest({k:v for k,v in value.items() if k!='digest'}):raise ValueError('結案範圍／憑證封印已變更')
    with service.store.transaction():
        current=service.store.get('QUALITY_MAJOR_RECHECK',value['case_id'])
        if current and current.get('closure_plan_digest')==value['digest']:return dict(current,replayed=True)
        fresh=plan(service,value['case_id'])
        if fresh['digest']!=value['digest'] or not fresh['can_close']:raise ValueError('仍有未檢查／失聯／錯誤／過期憑證，不可結束指定範圍')
        current.update(state='SCOPED_REVIEW_COMPLETED',completed=True,closure_plan_digest=value['digest'],closure_receipt=value,closed_actor=actor,closed_reason=reason,closed_at=time.time(),whole_corpus_safe=False,models_decontaminated=False,formal_output_approval=False)
        return service.store._write('QUALITY_MAJOR_RECHECK',current['id'],current,current['revision'],'major_pinned_scope_closed_unknown_corpus_and_model_quality_not_approved')
