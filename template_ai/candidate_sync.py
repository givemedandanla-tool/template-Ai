"""Preview explicit cross-candidate properties using exact compiled source IDs.

No names/position/coordinate ratios infer identity. This builds bounded transient
plans only; existing per-candidate whole-card services must verify any adoption.
"""
from copy import deepcopy
from .training_store import digest
from .candidate_changes import manual_delta
from .object_tools import propose

ATTRIBUTES={'align','color','locked'}


def candidate_pin(candidate):
    from .candidate_edit import review_context_token
    return digest(dict(template=candidate.template.to_dict(),generation=candidate.generation,context=review_context_token(candidate.risk_context),assets=candidate.dependency_stamp,risk=candidate.risk['digest']))


def field_reference(candidate,slot):
    snapshot=candidate.risk_context.get('input_snapshot',{});owners=snapshot.get('companies' if slot.owner.startswith('c') else 'people',[])
    try:
        if slot.owner[:1] not in ('p','c') or int(slot.owner[1:])<1:raise ValueError('不合法來源歸屬')
        owner=owners[int(slot.owner[1:])-1]
    except (ValueError,IndexError,TypeError):raise ValueError('來源人物／公司引用無法核實')
    if not owner.get('source_entity_id'):raise ValueError('缺穩定來源實體ID，不能用姓名或欄位位置推測相同身分')
    if slot.kind=='logo':return owner['source_entity_id'],'logo','COMPANY_EXACT_SIZE_ASSET'
    kind='name' if slot.kind=='company' else slot.kind;ids=owner.get('field_ids',{}).get(kind,[])
    if not 0<=slot.index<len(ids) or not ids[slot.index]:raise ValueError('缺穩定來源欄位ID，不能用相同字串推測對應')
    return owner['source_entity_id'],kind,ids[slot.index]


def semantic_pin(candidate):
    snapshot=candidate.risk_context.get('input_snapshot',{})
    return digest([snapshot.get('people'),snapshot.get('companies')])


def cross_property_plan(source,targets,slot_ids,attributes):
    if not 1<=len(targets)<=200 or not 1<=len(slot_ids)<=64:raise ValueError('跨候選預覽需明確1至200目標與1至64來源物件')
    if not attributes or len(set(attributes))!=len(attributes) or not set(attributes)<=ATTRIBUTES:raise ValueError('此跨候選入口只允許明確對齊、顏色、鎖定；不複製物理座標、字級、字型或歸屬')
    slots={s.id:s for s in source.template.slots}
    if len(set(slot_ids))!=len(slot_ids) or any(identity not in slots for identity in slot_ids):raise ValueError('來源物件集合重複或已不存在')
    selected=[slots[identity] for identity in slot_ids];refs=[field_reference(source,s) for s in selected]
    if len(set(refs))!=len(refs):raise ValueError('來源欄位有多個版面消費物件，需明確核對不唯一映射')
    rows=[]
    for key,target in targets:
        row=dict(key=key,target_pin=candidate_pin(target),dimensions=[target.template.width_mm,target.template.height_mm],template_id=target.template.id,state='INCOMPATIBLE',changes=[],reason='')
        try:
            if target.generation!=source.generation or semantic_pin(target)!=semantic_pin(source):raise ValueError('來源資料／世代不一致，先同步並逐尺寸重驗')
            index={}
            for slot in target.template.slots:
                try:index.setdefault(field_reference(target,slot),[]).append(slot)
                except ValueError:continue
            before=target.template.to_dict();after=deepcopy(before);after['state']='draft';mappings=[]
            for slot,reference in zip(selected,refs):
                matches=index.get(reference,[])
                if len(matches)!=1:raise ValueError('無唯一來源實體／欄位對應；不部分套用此目標')
                destination=matches[0];mappings.append(dict(source_slot=slot.id,target_slot=destination.id,source_reference=list(reference)))
                properties={name:getattr(slot,name) for name in attributes if name!='locked' and getattr(slot,name)!=getattr(destination,name)}
                if properties:after=propose(after,'TEMPLATE',dict(operation='PATCH',ids=[destination.id],patch=properties,cross_owner=False))['after']
                if 'locked' in attributes and slot.locked!=destination.locked:after=propose(after,'TEMPLATE',dict(operation='LOCK',ids=[destination.id],locked=slot.locked,cross_owner=False))['after']
            after['state']=before['state']
            if after==before:row.update(state='UNCHANGED',reason='明確屬性已一致，保留當次量測；正式輸出仍需現行Gate',mappings=mappings)
            else:receipt=manual_delta(before,after);row.update(state='READY_FOR_EXPLICIT_CONFIRMATION',reason='僅列出的屬性；每目標仍須整張重驗',changes=receipt['changes'],after=after,mappings=mappings)
        except (ValueError,TypeError,KeyError) as error:row['reason']=str(error)
        rows.append(row)
    if len({row['key'] for row in rows})!=len(rows):raise ValueError('目標集合重複，請重新選取')
    return dict(source_pin=candidate_pin(source),source_template_id=source.template.id,source_slot_ids=list(slot_ids),attributes=list(attributes),targets=rows,applied=False,formal_allowed=False,scope='EXPLICIT_CANDIDATE_AND_PHYSICAL_SIZE',whole_card_validation_required=True)


def verify_cross_plan(plan,source,targets):
    if candidate_pin(source)!=plan['source_pin']:raise ValueError('來源人工／資料版本已變，重新比較')
    current=dict(targets)
    for row in plan['targets']:
        if row['key'] not in current or candidate_pin(current[row['key']])!=row['target_pin']:raise ValueError('目標人工／資料版本已變，舊套用計畫已忽略')
    return True


def prepare_cross_batch(plan,source,adapters,*,approved=False):
    """GUI thread: copy plain envelopes; no candidate/DB/worker mutation."""
    from .candidate_edit import plan_cross_properties,prepare_edit
    if approved is not True:raise ValueError('先逐目標核對差異並明確確認')
    verify_cross_plan(plan,source,[(key,adapter.candidates[index]) for key,(adapter,index) in adapters.items()]);envelopes={}
    for row in plan['targets']:
        if row['state']!='READY_FOR_EXPLICIT_CONFIRMATION':continue
        adapter,index=adapters[row['key']];envelopes[row['key']]=prepare_edit(adapter,plan_cross_properties(adapter,index,row['after'],plan['source_pin']))
    return dict(plan=deepcopy(plan),envelopes=envelopes)


def calculate_cross_batch(batch,library,cancel=None):
    """Existing owned worker: calculate only, never access live GUI adapters."""
    from .candidate_edit import calculate_edit
    results=[]
    for row in batch['plan']['targets']:
        key=row['key'];result=dict(key=key,state=row['state'],reason=row['reason'])
        if row['state']=='READY_FOR_EXPLICIT_CONFIRMATION':
            try:
                if cancel and cancel.is_set():raise InterruptedError('已取消，未套用此目標')
                candidate=calculate_edit(batch['envelopes'][key],library);gate=candidate.risk
                if cancel and cancel.is_set():raise InterruptedError('已取消，計算副本不套用')
                result.update(state='VERIFIED_PENDING_INSTALL' if gate['formal_allowed'] else 'VALIDATION_FAILED',reason=gate['label'],gate=gate,candidate=candidate);candidate.risk_context['comparison_only']=True
            except InterruptedError as error:result.update(state='CANCELLED',reason=str(error))
            except (ValueError,OSError,TypeError,KeyError) as error:result.update(state='FAILED',reason=str(error))
        results.append(result)
    return results


def install_cross_batch(batch,results,source,adapters):
    """GUI thread: reject changed source/targets, install only whole-Gate passes."""
    from .candidate_edit import install_edit
    from .candidate_risk import bind_source
    try:verify_cross_plan(batch['plan'],source,[(key,adapter.candidates[index]) for key,(adapter,index) in adapters.items()])
    except (ValueError,IndexError,KeyError) as error:return [dict(key=row['key'],state='STALE_IGNORED',reason=str(error)) for row in results]
    installed=[]
    for row in results:
        result={key:value for key,value in row.items() if key!='candidate'}
        if row['state']=='VERIFIED_PENDING_INSTALL':
            try:
                adapter,index=adapters[row['key']];candidate=deepcopy(row['candidate']);candidate.risk_context.pop('comparison_only',None);bind_source(candidate,adapter.library,require_registered=True)
                if not candidate.formal_eligible:raise ValueError('現行必要Gate已改，不採用舊檢查')
                install_edit(adapter,batch['envelopes'][row['key']],candidate);result.update(state='APPLIED_VERIFIED',reason='此目標屬性已明確套用並通過整張Gate；可單筆復原')
            except (ValueError,OSError,TypeError,KeyError,IndexError) as error:result.update(state='STALE_IGNORED',reason=str(error))
        installed.append(result)
    return installed
