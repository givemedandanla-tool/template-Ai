"""Pinned manual findings and original newer-facts work resolution."""
import json,time
from pathlib import Path
from .training_store import digest,text

FINDINGS=('CHECKED_OK','REAPPROVED','ERROR_NEEDS_FIX','NEEDS_MANUAL','BLOCKED','UNKNOWN','EXCLUDED_HOLD')


def resolution_current(db,row):
    """Read the original full confirmed facts/source pins, including for read-only risk."""
    try:
        raw=db.execute("SELECT revision,payload FROM training_records WHERE kind='FACTS' AND id=?",(row['work_id'],)).fetchone()
        if not raw or raw[0]!=row.get('resolved_facts_revision'):return False
        facts=json.loads(raw[1]);confirmation=facts.get('confirmation')
        if not confirmation or confirmation.get('observations_digest')!=digest(facts['observations']):return False
        current=db.execute('SELECT a.source_id,a.revision,a.payload,s.hash,s.payload,COALESCE(l.revision,0),COALESCE(l.current_path,s.original_path) FROM artworks a JOIN sources s ON s.id=a.source_id LEFT JOIN source_links l ON l.source_id=s.id WHERE a.id=?',(row['work_id'],)).fetchone()
        if not current:return False
        pins=dict(work_id=row['work_id'],work_revision=current[1],work_digest=digest(json.loads(current[2])),source_id=current[0],source_hash=current[3],page=json.loads(current[4]).get('page',1),link_revision=current[5])
        if pins!=facts['pins']:return False
        from .source_links import fingerprint
        return list(fingerprint(Path(current[6]).resolve().stat()))==confirmation['source_stat']
    except (OSError,ValueError,KeyError,TypeError):return False


def plan(service,case_id,unit_id,finding,evidence):
    if finding not in FINDINGS:raise ValueError('重審結論無效')
    text(evidence,'人工核對／修正／範圍排除的可核對證據',2000)
    case=service.store.get('QUALITY_MAJOR_RECHECK',case_id);unit=service.store.get('QUALITY_WORK_QUARANTINE',unit_id)
    if not case or case['state']!='REVIEW_REQUIRED' or not unit or unit['case_id']!=case_id or unit['state']!='REVIEW_REQUIRED':raise ValueError('先讀回目前本案待重審作品；已解除或排除項不重複處理')
    wid=unit['work_id'];facts=service.store.facts(wid);proof=None;source_error=None
    try:
        verified=service.store.source_proof(wid);service.store.checked(wid,verified);proof=dict(path=verified.path,hash=verified.hash,stat=list(verified.stat))
    except (ValueError,OSError) as error:source_error=str(error)
    if finding in ('CHECKED_OK','REAPPROVED') and (not proof or facts['revision']<=unit['facts_revision'] or service.store.facts_state(wid)!='CONFIRMED'):raise ValueError('解除需比隔離時更新且已人工確認、目前來源仍有效的完整事實')
    value=dict(case_id=case_id,case_revision=case['revision'],unit_id=unit_id,unit_revision=unit['revision'],work_id=wid,finding=finding,evidence=evidence,pins=service.store.pins(wid),facts_revision=facts['revision'],facts_digest=digest(facts),source_proof=proof,source_error=source_error,release_work=finding in ('CHECKED_OK','REAPPROVED'),model_quality_released=False,template_quality_released=False)
    value['digest']=digest(value);return value


def confirm(service,value,actor,reason,approved=False):
    if approved is not True:raise ValueError('需具名核對此件原新判定並明確確認結論')
    text(actor,'本件重審人',120);text(reason,'本件結論依據',2000)
    if value.get('digest')!=digest({k:v for k,v in value.items() if k!='digest'}):raise ValueError('本件結論／證據預覽已改變')
    unit=service.store.get('QUALITY_WORK_QUARANTINE',value['unit_id'])
    if unit and unit.get('finding_plan_digest')==value['digest']:return dict(unit,replayed=True)
    fresh=plan(service,**{k:value[k] for k in ('case_id','unit_id','finding','evidence')})
    if fresh['digest']!=value['digest']:raise ValueError('來源／人工事實／審核版次已變更，未沿用舊結論')
    if value['release_work']:
        return service.resolve(value['unit_id'],value['unit_revision'],actor,reason,value['evidence'],True,review_state=value['finding'],expected_facts_digest=value['facts_digest'],expected_pins=value['pins'],review_plan_digest=value['digest'])
    with service.store.transaction():
        fresh=plan(service,**{k:value[k] for k in ('case_id','unit_id','finding','evidence')})
        if fresh['digest']!=value['digest']:raise ValueError('核對期間本件已變更')
        unit=service.store.get('QUALITY_WORK_QUARANTINE',value['unit_id']);unit.update(review_state='EXCLUDED_VERIFIED' if value['finding']=='EXCLUDED_HOLD' else value['finding'],review_actor=actor,review_reason=reason,review_evidence=value['evidence'],finding_plan_digest=value['digest'],finding_snapshot=value,reviewed_at=time.time())
        if value['finding']=='EXCLUDED_HOLD':unit['state']='EXCLUDED_HOLD'
        return service.store._write('QUALITY_WORK_QUARANTINE',unit['id'],unit,unit['revision'],'major_source_manual_finding_saved_not_quality_release')
