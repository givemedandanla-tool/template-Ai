"""Exact template case clearances; no old publication flag or renamed-version bypass."""
import copy,json,time
from .training_store import digest,text


def template_pin(value):return digest({k:v for k,v in value.items() if k!='state'})


def clearance_current(db,case_id,template,*,exact_content=False):
    identity=digest([case_id,template.id,template.version]);raw=db.execute("SELECT payload FROM training_records WHERE kind='QUALITY_TEMPLATE_CLEARANCE' AND id=?",(identity,)).fetchone()
    if not raw:return False
    try:
        receipt=json.loads(raw[0]);registered=db.execute('SELECT payload FROM templates WHERE id=?',(template.id,)).fetchone();payload=template.to_dict() if exact_content or not registered else json.loads(registered[0])
        if payload['version']!=template.version or receipt.get('template_pin')!=template_pin(payload):return False
        from .model import Template
        from .layout import layout_dependency
        from .candidate_risk import engine_digest
        if receipt.get('engine_digest')!=engine_digest():return False
        normalized=Template.from_dict(copy.deepcopy(payload));normalized.state='draft'
        if layout_dependency(normalized,receipt['inputs']['logos'])!=receipt['validation_dependency']:return False
        wid=receipt.get('source_work_id')
        if wid:
            from .major_review_findings import resolution_current
            current=dict(work_id=wid,resolved_facts_revision=receipt['facts_revision'])
            if not resolution_current(db,current):return False
        return receipt.get('reviewed') is True
    except (ValueError,KeyError,TypeError,OSError):return False


CHECKS=('source_mapping','ownership','whole_logo','size_asset','fixed_font','safe_geometry','semantic_lossless')
ADMIN_CONDITIONS={'PUBLISHED_BASE_APPROVAL','APPROVED_OR_REVIEWED_BASE','SOURCE_AND_QUALITY_TRUST','CURRENT_MAJOR_REVIEW_TRUST','EXACT_PUBLISHED_SOURCE_VERSION'}


def plan(service,case_id,unit_id,template_id,people,companies,logos,manual_checks,evidence,slot_bindings=None):
    from .model import Template
    from .layout import generate
    from .candidate_risk import bind_source,verify_original_source,engine_digest
    from .quality_rechecks import blocked
    text(evidence,'此確切模板與尺寸的人工核對證據',3000)
    case=service.store.get('QUALITY_MAJOR_RECHECK',case_id);unit=service.store.get('QUALITY_TEMPLATE_QUARANTINE',unit_id)
    if not case or case['plan'].get('mode')!='SOURCE_EVIDENCE' or not unit or unit['case_id']!=case_id:raise ValueError('模板不屬於此來源重審案件')
    if not isinstance(manual_checks,dict) or set(manual_checks)!=set(CHECKS) or any(v is not True for v in manual_checks.values()):raise ValueError('需逐項人工核對來源映射／人物公司／完整Logo／尺寸資產／固定字級／安全幾何／語意無損')
    snapshot=service.library.object_snapshot('TEMPLATE',template_id);template=Template.from_dict(snapshot['payload']);old=service.library.object_snapshot('TEMPLATE',unit['template_id'])['payload'];blockers=[]
    if template.family_id!=old['family_id'] and (not template.source_work_id or template.source_work_id!=old.get('source_work_id')):raise ValueError('替代模板與原案件無可核對版型／來源關係')
    work=service.library.artwork(template.source_work_id) if template.source_work_id else None;facts=None;bindings=copy.deepcopy(slot_bindings or {})
    if not work:blockers.append('缺可追溯直接來源作品，需由原訓練／已核實來源修正流程建立草稿')
    else:
        facts=service.store.facts(work['id'])
        if blocked(service.store,work['id']) or service.store.facts_state(work['id'])!='CONFIRMED':blockers.append('來源作品仍隔離或缺目前完整人工事實')
        if template.source_work_revision!=work['revision']:blockers.append('模板仍引用舊標記版次，需明確建立目前來源的修正草稿')
        source_slots={s['id']:s for s in work['payload']['slots']};roles={}
        for source in source_slots.values():roles.setdefault((source['kind'],source['owner'],source['index']),[]).append(source['id'])
        if slot_bindings is None:
            for slot in template.slots:
                candidates=roles.get((slot.kind,slot.owner,slot.index),[])
                if slot.id in source_slots:bindings[slot.id]=slot.id
                elif len(candidates)==1:bindings[slot.id]=candidates[0]
        if set(bindings)!={slot.id for slot in template.slots} or set(bindings.values())!=set(source_slots) or len(bindings.values())!=len(set(bindings.values())):blockers.append('模板未完整一對一對應目前原稿標記集合；歧義需明確逐物件核對，不以省略輸入隱藏來源欄位')
        for slot in template.slots:
            source=source_slots.get(bindings.get(slot.id))
            if source is None or any(source[k]!=getattr(slot,k) for k in ('kind','owner','index')):blockers.append('模板欄位／人物公司對應不符合目前原稿標記：'+slot.id)
    try:
        structural=copy.deepcopy(template);structural.state='draft';service.library._template_provenance(structural,allow_quarantined_draft=True)
    except (ValueError,OSError) as error:blockers.append(str(error))
    candidate=generate(template,copy.deepcopy(people),copy.deepcopy(companies),copy.deepcopy(logos),0)
    try:verify_original_source(candidate,service.library);bind_source(candidate,service.library)
    except (ValueError,OSError) as error:blockers.append(str(error))
    conditions=copy.deepcopy(candidate.risk['conditions'])
    blockers.extend(c['id']+'：'+c.get('reason','未通過') for c in conditions if c.get('required',True) and c['id'] not in ADMIN_CONDITIONS and c['status']!='PASS')
    normalized=copy.deepcopy(template);normalized.state='draft'
    from .layout import layout_dependency
    value=dict(case_id=case_id,case_revision=case['revision'],unit_id=unit_id,unit_revision=unit['revision'],template_id=template.id,template_version=template.version,template_snapshot_digest=digest(snapshot),template_pin=template_pin(template.to_dict()),source_work_id=template.source_work_id,slot_bindings=bindings,facts_revision=facts['revision'] if facts else None,facts_digest=digest(facts) if facts else None,source_pins=service.store.pins(work['id']) if work else None,inputs=dict(people=people,companies=companies,logos=logos),manual_checks=manual_checks,evidence=evidence,conditions=conditions,blockers=sorted(set(blockers)),can_release=not blockers,validation_dependency=layout_dependency(normalized,logos),engine_digest=engine_digest(),model_quality_released=False,formal_output_authorized=False)
    value['digest']=digest(value);return value


def confirm(service,value,actor,reason,approved=False):
    if approved is not True:raise ValueError('需明確核對此模板版本／物理尺寸的完整重驗')
    text(actor,'模板重審人',120);text(reason,'本版本核准依據',2000)
    if value.get('digest')!=digest({k:v for k,v in value.items() if k!='digest'}):raise ValueError('模板版本／人工核對／完整驗證結果封印已變更')
    with service.store.transaction():
        receipt_id=digest([value['case_id'],value['template_id'],value['template_version']]);prior=service.store.get('QUALITY_TEMPLATE_CLEARANCE',receipt_id)
        if prior and prior.get('plan_digest')==value['digest']:return dict(prior,replayed=True)
        fresh=plan(service,**{k:value[k] for k in ('case_id','unit_id','template_id','manual_checks','evidence','slot_bindings')},**value['inputs'])
        if fresh['digest']!=value['digest'] or not fresh['can_release']:raise ValueError('來源／事實／模板／尺寸／資產／整卡驗證已變更或仍有阻擋')
        receipt=service.store._write('QUALITY_TEMPLATE_CLEARANCE',receipt_id,dict(**{k:v for k,v in fresh.items() if k!='digest'},plan_digest=fresh['digest'],reviewed=True,actor=actor,reason=reason,at=time.time(),old_publication_unchanged=True),prior['revision'] if prior else 0,'major_exact_template_version_reviewed_not_global_model_or_output_approval')
        unit=service.store.get('QUALITY_TEMPLATE_QUARANTINE',value['unit_id']);unit.update(state='REPLACED_WITH_VERIFIED_TEMPLATE',review_state='REAPPROVED',approved_template_id=value['template_id'],approved_template_version=value['template_version'],clearance_id=receipt_id,review_actor=actor,review_reason=reason,reviewed_at=time.time());service.store._write('QUALITY_TEMPLATE_QUARANTINE',unit['id'],unit,unit['revision'],'major_template_original_held_exact_reviewed_version_cleared')
        return receipt
