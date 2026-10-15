"""Version-pinned classification diagnostics, explicitly separate from model/visual certification."""
import copy,platform,time
from PySide6 import __version__ as qt_version
from .training_store import digest,text
from .model import KINDS,new_id
from .batch_import import healthy_source


def evaluation_plan(store,dataset_id,versions,predictions):
    validity=store.dataset_validity(dataset_id)
    if not validity['valid']:raise ValueError('固定資料集已過期／隔離：'+'；'.join(validity['errors']))
    dataset=validity['dataset'];entries=dataset['entries']
    if not entries or any(e['role']!='HOLDOUT' for e in entries):raise ValueError('分類驗收僅使用明確HOLDOUT，不准拿TRAIN分數當獨立驗收')
    if not isinstance(versions,dict) or set(versions)!={'model','parser','ocr','rules'}:raise ValueError('需完整模型／解析器／OCR／規則版本識別')
    for value in versions.values():text(value,'exact版本標籤',120)
    if not isinstance(predictions,list) or len(predictions)>2000:raise ValueError('最多2000筆明確預測記錄')
    gold={};samples={}
    for e in entries:
        s=store.get('SAMPLE',e['sample_id']);samples[s['id']]=s
        if not healthy_source(store.library.source(s['pins']['source_id'])):raise ValueError('來源／cache健康不足')
        for slot in s['label_slots']:gold[(s['id'],slot['id'])]={'kind':slot['kind'],'owner':slot['owner'],'work_id':s['work_id']}
    if len(gold)>2000:raise ValueError('真值超過2000筆，需另建較小固定驗收集')
    parsed={}
    for row in predictions:
        if not isinstance(row,dict) or set(row)!={'sample_id','slot_id','kind','owner'} or row['sample_id'] not in samples or row['kind'] not in KINDS or not isinstance(row['slot_id'],str) or not row['slot_id'] or not isinstance(row['owner'],str) or not row['owner']:raise ValueError('預測需sample/slot exact ID與合法分類／歸屬')
        k=(row['sample_id'],row['slot_id'])
        if k in parsed:raise ValueError('同一預測ID重複，不能重複計分')
        parsed[k]=row
    metrics={k:{'tp':0,'fp':0,'fn':0} for k in KINDS};cases=[];matrix={};critical=0
    for key in sorted(set(gold)|set(parsed)):
        g=gold.get(key);p=parsed.get(key);actual=g['kind'] if g else 'EXTRA';predicted=p['kind'] if p else 'MISSING';matrix[actual+'→'+predicted]=matrix.get(actual+'→'+predicted,0)+1
        if g and p and actual==predicted:metrics[actual]['tp']+=1
        else:
            if g:metrics[actual]['fn']+=1
            if p:metrics[predicted]['fp']+=1
        owner_error=bool(g and p and g['owner']!=p['owner']);critical+=int(owner_error)
        if not g or not p or actual!=predicted or owner_error:cases.append({'sample_id':key[0],'slot_id':key[1],'work_id':g['work_id'] if g else samples[key[0]]['work_id'],'gold':copy.deepcopy(g),'prediction':copy.deepcopy(p),'critical_owner_mismatch':owner_error})
    for m in metrics.values():
        m['precision']=m['tp']/(m['tp']+m['fp']) if m['tp']+m['fp'] else None;m['recall']=m['tp']/(m['tp']+m['fn']) if m['tp']+m['fn'] else None
    plan={'dataset_id':dataset_id,'dataset_revision':dataset['revision'],'manifest_digest':dataset['manifest_digest'],'gold_digest':digest(gold_to_rows(gold)),'sample_revisions':{s['id']:s['revision'] for s in samples.values()},'versions':copy.deepcopy(versions),'predictions':copy.deepcopy(predictions),'prediction_origin':'USER_SUPPLIED_RECORDS_NOT_EXECUTED_MODEL_INFERENCE','metrics':metrics,'matrix':matrix,'cases':cases,'critical_owner_errors':critical,'gold_count':len(gold),'predicted_count':len(parsed),'environment':{'python':platform.python_version(),'qt':qt_version,'system':platform.system()},'independence':'EXACT_SOURCE_ROLE_LOCKED; NEAR_DUPLICATE_CUSTOMER_FAMILY_UNKNOWN','gate':'FAILED_CRITICAL' if critical else 'EVIDENCE_INSUFFICIENT','automatic_recommendation_allowed':False,'visual_consistency':'NOT_EVALUATED','threshold_policy':'NO_APPROVED_STATISTICAL_THRESHOLD','holdout_exposed_for_repair':bool(store.get('HOLDOUT_EXPOSED',dataset_id))}
    plan['digest']=digest(plan);return plan

def gold_to_rows(gold):return [dict(sample_id=k[0],slot_id=k[1],**v) for k,v in sorted(gold.items())]

def save_evaluation(store,plan,actor,approved=False):
    if not approved:raise ValueError('需確認固定資料集及預測來源；不是品質放行')
    text(actor,'評估人',120)
    with store.transaction():
        current=evaluation_plan(store,plan['dataset_id'],plan['versions'],plan['predictions'])
        if current!=plan:raise ValueError('資料／版本／真值已改變，重新評估')
        return store._write('EVALUATION',new_id(),{**current,'actor':actor,'created':time.time()},0,'classification_evaluated')

def compare_evaluations(store,left_id,right_id):
    a,b=store.get('EVALUATION',left_id),store.get('EVALUATION',right_id)
    if not a or not b:raise ValueError('評估記錄不存在')
    for k in ('dataset_id','dataset_revision','manifest_digest','gold_digest','environment','threshold_policy'):
        if a[k]!=b[k]:raise ValueError('驗收集／真值／口徑／環境不同，不能公平A/B比較')
    return {'left':a['id'],'right':b['id'],'fixed_gold_count':a['gold_count'],'critical_delta':b['critical_owner_errors']-a['critical_owner_errors'],'failure_case_delta':len(b['cases'])-len(a['cases']),'quality_pass':False,'reason':'僅分類紀錄比較；獨立性與正式品質門檻證據仍不足'}

def create_repair(store,evaluation_id,hypothesis,candidate_version,actor,approved=False):
    if not approved:raise ValueError('先確認隔離修復範圍')
    text(hypothesis,'根因候選',512);text(candidate_version,'候選版本',120);text(actor,'操作人',120)
    with store.transaction():
        e=store.get('EVALUATION',evaluation_id)
        if not e or not e['cases']:raise ValueError('需要實際失敗案例，不能憑空生成修復')
        if not store.dataset_validity(e['dataset_id'])['valid']:raise ValueError('評估來源已過期，先核對真值')
        if candidate_version in e['versions'].values():raise ValueError('修復候選需與現行版本分開')
        exposed=store.get('HOLDOUT_EXPOSED',e['dataset_id']);store._write('HOLDOUT_EXPOSED',e['dataset_id'],{'reason':'REPAIR_DESIGN_USES_HOLDOUT_FAILURE','evaluation_id':evaluation_id,'requires_new_independent_holdout':True},exposed['revision'] if exposed else 0,'holdout_exposed_for_repair')
        return store._write('QUALITY_REPAIR',new_id(),{'evaluation_id':evaluation_id,'evaluation_digest':e['digest'],'hypothesis':hypothesis,'root_cause':'USER_HYPOTHESIS_NOT_VERIFIED','candidate_version':candidate_version,'affected_cases':e['cases'],'actor':actor,'state':'ISOLATED_PENDING_REGRESSION_AND_NEW_HOLDOUT','can_activate':False,'originals_templates_models_unchanged':True},0,'quality_repair_proposed')

def rollback_gate(store,baseline_id,candidate_id):
    compare_evaluations(store,baseline_id,candidate_id)
    return {'allowed':False,'reason':'兩版沒有可核實的獨立品質PASS與正式啟用憑證；不得把舊版當無條件安全','state':'REVIEW_REQUIRED'}


def recheck_plan(store,rule_id):
    rule=store.get('RULE',rule_id)
    if not rule:raise ValueError('先選取確切既有規則')
    # SQL addresses every stored SAMPLE, including historical batches; page display is not the denominator.
    query="SELECT DISTINCT s.id FROM training_records s,json_each(s.payload,'$.rule_dependencies') d WHERE s.kind='SAMPLE' AND json_extract(d.value,'$.id')=? ORDER BY s.id"
    total=store.db.execute('SELECT count(*) FROM ('+query+')',(rule_id,)).fetchone()[0];ids=[r[0] for r in store.db.execute(query+' LIMIT 201',(rule_id,))];rows=[]
    for sid in ids[:200]:
        sample=store.get('SAMPLE',sid);impact=store.sample_usage_impact(sid);rows.append({'sample_id':sid,'sample_revision':sample['revision'],'sample_state':store.sample_state(sid),'work_id':sample['work_id'],'rule_dependencies':sample['rule_dependencies'],'impact':impact})
    plan={'rule_id':rule_id,'rule_revision':rule['revision'],'rule_digest':digest(rule),'direct_total':total,'scanned':len(rows),'complete':len(ids)<=200 and all(r['impact']['complete'] for r in rows),'rows':rows,'unknown_dependency_families':['models','native_logo_assets','customer_identity'],'scope':'EXACT_STORED_RULE_DEPENDENCIES_ONLY','not_global_safety_claim':True};plan['digest']=digest(plan);return plan

def start_recheck(store,plan,selected,reason,actor,approved=False):
    if not approved or not selected or len(set(selected))!=len(selected):raise ValueError('需確認具名樣本範圍與隔離')
    text(reason,'重大錯誤證據／原因',512);text(actor,'重審人',120)
    with store.transaction():
        current=recheck_plan(store,plan['rule_id'])
        if current!=plan or not current['complete']:raise ValueError('依賴範圍已變更或未檢索完整，需縮小可驗範圍')
        rows={r['sample_id']:r for r in current['rows']}
        if set(selected)-rows.keys():raise ValueError('選取不在exact依賴範圍')
        case_id=new_id();results=[]
        for sid in selected:
            sample=store.get('SAMPLE',sid)
            if sample['state']!='APPROVED':raise ValueError('只隔離仍核准的樣本；其他狀態保留人工核對')
            sample.update(state='QUARANTINED',transition_actor=actor,transition_reason=reason,recheck_case=case_id,use_impact=rows[sid]['impact'])
            store._write('SAMPLE',sid,sample,sample['revision'],'sample_major_recheck_quarantine');results.append({'sample_id':sid,'state':'REVIEW_REQUIRED','original_approval_revision':rows[sid]['sample_revision']})
        return store._write('MAJOR_RECHECK',case_id,{'plan':current,'selected':selected,'results':results,'reason':reason,'actor':actor,'state':'REVIEW_REQUIRED','completed':False,'historical_approvals_retained':True,'models_decontaminated':False},0,'major_recheck_started')
