"""Affected-source reanalysis as an operation on the original AUTO_JOB worker."""
import copy,json,time
from .training_store import TrainingStore,digest,text
from .model import new_id
from .quality_rechecks import QualityRechecks

OPERATION='MAJOR_SOURCE_RECHECK'
FIELDS=('source_id','path','page','source_hash','work_id','work_scope','expected_pins')


def plan(library,case_id,work_ids):
    store=TrainingStore.bind(library);case=store.get('QUALITY_MAJOR_RECHECK',case_id)
    if not case or case['plan'].get('mode')!='SOURCE_EVIDENCE' or case['state']!='REVIEW_REQUIRED':raise ValueError('來源重審案件已變更／不在待審狀態')
    if not isinstance(work_ids,list) or not 1<=len(work_ids)<=200 or len(set(work_ids))!=len(work_ids):raise ValueError('需明確選取1至200件不同的本案作品；未掃描項不計完成')
    groups={};units={}
    for wid in sorted(work_ids):
        unit=store.get('QUALITY_WORK_QUARANTINE',digest([case_id,wid]))
        if not unit or unit['case_id']!=case_id or unit['state']!='REVIEW_REQUIRED':raise ValueError('作品不在此案目前待審範圍，未重新隔離已解除項')
        pins=store.pins(wid);source=library.source(pins['source_id']);units[wid]=unit['revision']
        item=groups.setdefault(source['id'],dict(source_id=source['id'],path=source['current_path'],page=source['page'],source_hash=source['hash'],work_id=wid,work_scope=[],expected_pins={}))
        item['work_scope'].append(wid);item['expected_pins'][wid]=pins
    result=dict(operation=OPERATION,case_id=case_id,case_plan_digest=case['plan_digest'],work_ids=sorted(work_ids),unit_revisions=units,items=[groups[k] for k in sorted(groups)],automatic_learning=False,automatic_review_approval=False,unselected_items_unchanged=True)
    result['digest']=digest(result);return result


def create(service,value,actor,reason,approved=False):
    if approved is not True:raise ValueError('需明確核對只重分析所選來源，不訓練或解除隔離')
    text(actor,'分析工作核對者',120);text(reason,'所選增量分析依據',2000)
    if value.get('digest')!=digest({k:v for k,v in value.items() if k!='digest'}):raise ValueError('來源分析預覽內容／封印已變更，未建立工作')
    with service.store.transaction():
        fresh=plan(service.library,value['case_id'],value['work_ids'])
        if fresh['digest']!=value.get('digest'):raise ValueError('案件／所選作品／目前來源版次已變更，未排程')
        items=[dict(copy.deepcopy(item),state='READY',attempts=0,unit_ids=[],action='SOURCE_REANALYSIS_NOT_TRAINING') for item in fresh['items']]
        job=dict(operation=OPERATION,phase='READY',items=items,source_review_plan=fresh,unit_revisions=copy.deepcopy(fresh['unit_revisions']),actor=actor,reason=reason,created=time.time(),owner=None,cancel_requested=False,purpose='MAJOR_SOURCE_REANALYSIS_NO_LEARNING_OR_APPROVAL',scope=dict(operation=OPERATION,case_id=fresh['case_id'],case_plan_digest=fresh['case_plan_digest'],source_review_digest=fresh['digest'],work_ids=fresh['work_ids']))
        if len(json.dumps(job,ensure_ascii=False).encode())>1_048_576-4096:raise ValueError('增量工作超過原1MiB metadata預算，請縮小明列選取範圍')
        return service.store._write('AUTO_JOB',new_id(),job,0,'major_source_reanalysis_created_not_executed')


def check(service,job):
    value=job.get('source_review_plan',{});case=service.store.get('QUALITY_MAJOR_RECHECK',value.get('case_id',''))
    if job.get('operation')!=OPERATION or value.get('digest')!=digest({k:v for k,v in value.items() if k!='digest'}):raise ValueError('來源重審工作範圍封印不符')
    expected=dict(operation=OPERATION,case_id=value['case_id'],case_plan_digest=value['case_plan_digest'],source_review_digest=value['digest'],work_ids=value['work_ids'])
    if job.get('scope')!=expected or not case or case['state']!='REVIEW_REQUIRED' or case['plan_digest']!=value['case_plan_digest']:raise ValueError('重審案件已變更／關閉，不沿用舊工作')
    if job['phase']=='COMPLETED':raise ValueError('此分析已保存，請讀回結果，不重跑同一工作')
    if [{k:item[k] for k in FIELDS} for item in job['items']]!=value['items']:raise ValueError('所選來源／作品清單已變更')
    for item in job['items']:
        for wid in item['work_scope']:
            unit=service.store.get('QUALITY_WORK_QUARANTINE',digest([case['id'],wid]))
            if not unit or unit['state']!='REVIEW_REQUIRED' or unit['revision']!=job['unit_revisions'].get(wid) or service.store.pins(wid)!=item['expected_pins'][wid]:raise ValueError('原工作以外已有新來源／人工審核，舊分析不覆寫')


def update_units(service,current,item,state,**extra):
    for wid in item['work_scope']:
        identity=digest([current['scope']['case_id'],wid]);unit=service.store.get('QUALITY_WORK_QUARANTINE',identity)
        if not unit or unit['state']!='REVIEW_REQUIRED' or unit['revision']!=current['unit_revisions'][wid]:raise ValueError('單件審核已由其他操作改變，未覆寫')
        unit.update(review_state=state,analysis_job_id=current['id'],**extra);saved=service.store._write('QUALITY_WORK_QUARANTINE',identity,unit,unit['revision'],'major_source_reanalysis_'+state.lower());current['unit_revisions'][wid]=saved['revision']


def run(service,job,token,cancel=None,progress=None,admission=None):
    from .runtime_admission import require_resources,ResourcePause
    from .source_analysis import analyse_source,ANALYSER_VERSION
    identity=job['id'];check(service,job)
    for index in range(len(job['items'])):
        current=service.owned(identity,token);item=current['items'][index]
        if cancel and cancel.is_set():return service.finish(identity,token,'CANCELLED')
        if item['state']=='SUCCESS':continue
        if item['state']!='READY':continue
        try:
            require_resources(admission)
            with service.store.transaction():
                current=service.owned(identity,token);check(service,current);item=current['items'][index];update_units(service,current,item,'PROCESSING')
                current['items'][index].update(state='RUNNING',action='SOURCE_ANALYSIS_RUNNING_NOT_COMPLETED');current=service.store._write('AUTO_JOB',identity,current,current['revision'],'major_source_analysis_started')
            if progress:progress(current)
            proof=service.store.source_proof(item['work_id']);service.store.checked(item['work_id'],proof)
            source=service.library.source(item['source_id']);suggestions=analyse_source(source,service.library.assets,semantic_model=None)
            if cancel and cancel.is_set():
                with service.store.transaction():
                    current=service.owned(identity,token);update_units(service,current,item,'NEEDS_MANUAL',analysis_cancelled=True);current['items'][index].update(state='READY',action='CANCELLED_UNSAVED_ANALYSIS');service.store._write('AUTO_JOB',identity,current,current['revision'],'major_source_analysis_cancelled_without_adoption')
                return service.finish(identity,token,'CANCELLED')
            with service.store.transaction():
                current=service.owned(identity,token);check(service,current)
                service.store.checked(item['work_id'],service.store.source_proof(item['work_id']))
                originals=[]
                for wid in item['work_scope']:
                    quarantine=service.store.get('QUALITY_WORK_QUARANTINE',digest([current['scope']['case_id'],wid]));revision=quarantine['facts_revision'];raw=service.db.execute("SELECT after_json FROM training_history WHERE kind='FACTS' AND id=? AND revision=?",(wid,revision)).fetchone()
                    originals.append(dict(work_id=wid,facts_revision=revision,facts=json.loads(raw[0]) if raw else None,missing_prior_facts=raw is None))
                result_id=digest([identity,item['source_id']]);result=dict(case_id=current['scope']['case_id'],job_id=identity,source_id=item['source_id'],work_ids=item['work_scope'],source_pins=item['expected_pins'],original_facts=originals,suggestions=suggestions,analyser_version=ANALYSER_VERSION,semantic_model_used=False,review_required=True,formal_eligible=False,original_data_modified=False)
                existing=service.store.get('QUALITY_SOURCE_REANALYSIS',result_id)
                if existing:raise ValueError('已有此分析結果，請讀回原紀錄，不覆寫歷史')
                saved=service.store._write('QUALITY_SOURCE_REANALYSIS',result_id,result,0,'major_source_analysis_saved_pending_manual_review')
                update_units(service,current,item,'NEEDS_MANUAL',analysis_id=result_id,analysis_digest=digest(saved))
                current['items'][index].update(state='SUCCESS',attempts=item['attempts']+1,analysis_id=result_id,action='ANALYSED_PENDING_MANUAL_REVIEW',error=None)
                job=service.store._write('AUTO_JOB',identity,current,current['revision'],'major_source_result_and_unit_checkpoint_saved')
        except ResourcePause as error:return service.finish(identity,token,'CANCELLED' if cancel and cancel.is_set() else 'PAUSED_RESOURCES',str(error))
        except (ValueError,OSError,KeyError) as error:
            with service.store.transaction():
                current=service.owned(identity,token)
                for wid in item['work_scope']:
                    unit=service.store.get('QUALITY_WORK_QUARANTINE',digest([current['scope']['case_id'],wid]))
                    if unit and unit['state']=='REVIEW_REQUIRED' and unit['revision']==current['unit_revisions'][wid]:
                        unit.update(review_state='UNKNOWN',analysis_job_id=identity,analysis_error=str(error));saved=service.store._write('QUALITY_WORK_QUARANTINE',unit['id'],unit,unit['revision'],'major_source_analysis_failed_isolated');current['unit_revisions'][wid]=saved['revision']
                current['items'][index].update(state='FAILED',attempts=item['attempts']+1,error=str(error),action='ANALYSIS_UNVERIFIED_NO_ADOPTION');job=service.store._write('AUTO_JOB',identity,current,current['revision'],'major_source_failure_isolated')
        if progress:progress(job)
    final=service.owned(identity,token);return service.finish(identity,token,'COMPLETED' if all(i['state']=='SUCCESS' for i in final['items']) else 'COMPLETED_WITH_EXCEPTIONS')
