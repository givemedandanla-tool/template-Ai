"""Repair routing inside the existing quality command transport and same Library."""
from .training_store import TrainingStore,digest
from .quality_repairs import QualityRepairs
from .quality_repair_gates import QualityRepairGates
from .quality_repair_releases import QualityRepairReleases,ACTIVE,KEY,EVENT
from . import quality_repair_truth as truth


def work_page(library,offset=0,query=''):
    if type(offset) is not int or offset<0 or not isinstance(query,str) or len(query)>500:raise ValueError('作品目錄需50筆分頁及有界搜尋')
    from .quality_groups import QualityGroups
    store=TrainingStore.bind(library);groups=QualityGroups(library);graph,_,_=groups.graph_state()
    where="COALESCE(json_extract(a.payload,'$.segmentation_state'),'')!='SUPERSEDED'";args=[]
    for token in query.casefold().split():where+=" AND instr(training_casefold(a.id||' '||a.name||' '||s.original_path),?)>0";args.append(token)
    base=' FROM artworks a JOIN sources s ON s.id=a.source_id WHERE '+where
    total=library.db.execute('SELECT count(*)'+base,args).fetchone()[0];rows=[]
    for wid,name,sid,path,sha in library.db.execute('SELECT a.id,a.name,s.id,s.original_path,s.hash'+base+' ORDER BY a.id LIMIT 50 OFFSET ?',(*args,offset)):
        state=store.facts_state(wid);allowed=[];blockers=[]
        for role in ('TRAIN','VALIDATION'):
            conflicts=groups.role_conflicts([(sha,role)],graph=graph)
            if state=='CONFIRMED' and not conflicts:allowed.append(role)
            blockers.extend(row['reason'] for row in conflicts)
        if state!='CONFIRMED':blockers.append('來源人工事實尚未確認')
        lock=store.get('GROUP_ROLE',sha)
        rows.append(dict(id=wid,name=name,source_id=sid,source_path=path,facts_state=state,
                         locked_role=lock['role'] if lock else None,allowed_roles=allowed,blockers=sorted(set(blockers)),
                         default_selected=False,preview_only_backend_plan_rechecks_actual_source=True))
    return dict(rows=rows,total=total,offset=offset,limit=50,images_loaded=False,model_weights_loaded=False)


def job_status(library,identity,offset=0):
    if type(offset) is not int or offset<0:raise ValueError('進度需50筆分頁')
    keys=('id','revision','phase','semantic_training_state','model_id','candidate_id','root_review_id','error','restore_state','total')
    row=library.db.execute("SELECT id,revision,json_extract(payload,'$.phase'),json_extract(payload,'$.semantic_training_state'),json_extract(payload,'$.model_id'),json_extract(payload,'$.candidate_id'),json_extract(payload,'$.root_review_id'),json_extract(payload,'$.error'),json_extract(payload,'$.restore_state'),json_array_length(payload,'$.items') FROM training_records WHERE kind='AUTO_JOB' AND id=? AND json_extract(payload,'$.operation')='SEMANTIC_REPAIR_CANDIDATE'",(identity,)).fetchone()
    if not row:raise ValueError('需選實際局部修復訓練工作')
    result=dict(zip(keys,row));item_keys=('work_id','state','attempts','action','error')
    result['items']=[dict(zip(item_keys,item)) for item in library.db.execute("SELECT json_extract(i.value,'$.work_id'),json_extract(i.value,'$.state'),json_extract(i.value,'$.attempts'),json_extract(i.value,'$.action'),json_extract(i.value,'$.error') FROM training_records r,json_each(r.payload,'$.items') i WHERE r.kind='AUTO_JOB' AND r.id=? ORDER BY CAST(i.key AS INTEGER) LIMIT 50 OFFSET ?",(identity,offset))]
    result.update(offset=offset,limit=50,weights_loaded=False);return result


def decision_plan(library,report_id):
    from .quality_reports import QualityReports
    store=TrainingStore.bind(library);report=store.get('QUALITY_PAIR_REPORT',report_id)
    if not report:raise ValueError('先保存實際固定雙側報告')
    current=QualityReports(library).plan(report['plan']['protocol_id'])
    if current!=report['plan']:raise ValueError('報告品質／版本／來源證據已改變')
    result=dict(report_id=report_id,report_digest=digest(report),candidate_decision_eligible=current['candidate_decision_eligible'],
                blockers=[] if current['candidate_decision_eligible'] else ['新的獨立來源／品質門檻／類別退步／重大錯誤或當前版本證據尚未符合'],
                automatic_activation=False)
    result['digest']=digest(result);return result


def execute(library,command,payload):
    store=TrainingStore.bind(library);repairs=QualityRepairs(library);gates=QualityRepairGates(library);releases=QualityRepairReleases(library)
    if command=='ISSUES':return repairs.page(**payload)
    if command=='WORKS':return work_page(library,**payload)
    if command=='SOURCE_PLAN':return repairs.plan_source_issue(**payload)
    if command=='QUALITY_PLAN':return repairs.plan_quality_issue(**payload)
    if command=='ROOT_PLAN':return repairs.root_plan(**payload)
    if command=='ISSUE_IMPACT':return repairs.impact_plan(**payload)
    if command=='TRUTH_PLAN':return truth.plan(repairs,**payload)
    if command=='SEMANTIC_PLAN':
        from .semantic_learning import SemanticLearning
        return SemanticLearning.bind(library).plan(**payload)
    if command=='RULE_PLAN':return store.rule_review_plan(**payload)
    if command=='CANDIDATE_PLAN':return gates.candidate_plan(**payload)
    if command=='STAGE_PLAN':return gates.protocol_plan(**payload)
    if command=='GATE_PLAN':return gates.plan(**payload)
    if command=='IMPACT_PLAN':return releases.impact_plan(**payload)
    if command=='RELEASE_PLAN':return releases.plan(**payload)
    if command=='ROLLBACK_PLAN':
        event=store.get(EVENT,payload['target_event_id'])
        if not event:raise ValueError('歷史部署不存在')
        return releases.plan(event['plan']['decision_id'],payload['expected_revision'],'ROLLBACK',target_event_id=event['id'])
    if command=='STATUS':
        pointer=store.get(ACTIVE,KEY);pin=None;errors=[]
        try:pin=releases.pin()
        except (ValueError,OSError,KeyError) as error:errors.append(str(error))
        return dict(active_revision=pointer['revision'] if pointer else 0,pointer=pointer,pin=pin,errors=errors,automatic_fallback=False)
    if command=='GET':
        if payload['kind'] not in ('QUALITY_REPAIR_ISSUE','QUALITY_REPAIR_ROOT_REVIEW','QUALITY_REPAIR_PIPELINE_CANDIDATE','QUALITY_REPAIR_GATE','QUALITY_PIPELINE_DEPLOYMENT','QUALITY_REPAIR_IMPACT_REVIEW','QUALITY_REPAIR_TRUTH_REVIEW'):raise ValueError('修復讀回僅支援具體憑證；不載入模型權重')
        row=store.get(payload['kind'],payload['id'])
        if not row:raise ValueError('持久修復憑證不存在')
        return row
    if command=='JOB_STATUS':return job_status(library,payload['id'],payload.get('offset',0))
    if command=='DECISION_PLAN':return decision_plan(library,**payload)
    if command=='CONFIRM':
        kind=payload['kind'];plan=payload['plan'];actor=payload['actor'];approved=payload.get('approved',False);reason=payload.get('reason','')
        if kind=='DECISION':
            from .quality_reports import QualityReports
            if decision_plan(library,plan['report_id'])!=plan:raise ValueError('品質接受預覽已改變')
            return QualityReports(library).decide(plan['report_id'],actor,reason,approved,expected_report_digest=plan['report_digest'])
        if kind=='ISSUE':return (repairs.create_quality_issue if plan.get('origin')=='ACTUAL_QUALITY_CASE' else repairs.create_source_issue)(plan,actor,reason,approved)
        if kind=='ROOT':return repairs.confirm_root(plan,actor,approved)
        if kind=='TRUTH':return truth.confirm(repairs,plan,actor,approved)
        if kind=='CANDIDATE':return gates.register(plan,actor,reason,approved)
        if kind=='GATE':return gates.confirm(plan,actor,approved)
        if kind=='IMPACT':return releases.confirm_impact(plan,actor,reason,approved)
        if kind=='RELEASE':return releases.confirm(plan,actor,reason,approved)
        if kind=='TRAIN':
            from .automatic_training import AutomaticTraining
            from .quality_repair_training import create
            return create(AutomaticTraining(library),payload['review_id'],plan,actor,approved)
        if kind=='RULE':
            from .quality_repair_rules import approve
            return approve(store,payload['review_id'],plan,actor,reason,approved,payload.get('detail_reviewed',False))
        raise ValueError('不支援的明確修復確認種類')
    raise ValueError('不支援的修復命令')
