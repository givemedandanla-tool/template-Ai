"""Candidate-local dependency and three-way/manual delta policy, no business writes.

Reachability scopes recalculation; only whole-card current gates grant export.
Reuses NetworkX BFS and the existing geometry proposal engine.
"""
from copy import deepcopy

CARD=('GATE','WHOLE_CARD')

def fields(people,companies):
    values={};identities={}
    for prefix,entities in (('p',people),('c',companies)):
        for number,entity in enumerate(entities,1):
            owner=f'{prefix}{number}'
            for kind,items in entity.items():
                if kind=='field_ids':continue
                items=items if isinstance(items,list) else [items]
                for index,value in enumerate(items):
                    key=(owner,kind,index);values[key]=deepcopy(value);ids=entity.get('field_ids',{}).get(kind,[]);identities[key]=ids[index] if index<len(ids) else key
    return values,identities


def graph(template,people,companies):
    import networkx as nx
    values,identities=fields(people,companies)
    if len(values)>2000 or len(template.slots)>64:raise ValueError('欄位／物件超過本次預算，未宣稱部分結果安全')
    dag=nx.DiGraph();dag.add_node(CARD)
    for key in values:
        node=('FIELD',identities[key]);dag.add_edge(node,('OWNER_GATE',key[0]));dag.add_edge(('OWNER_GATE',key[0]),CARD)
        # An unmapped field still reaches lossless whole-card validation.
        dag.add_edge(node,CARD)
        if key[1] in ('company','companies'):dag.add_edge(node,('OWNER_BINDING',key[0]))
    for slot in template.slots:
        node=('SLOT',slot.id);dag.add_edge(node,CARD);kind='name' if slot.kind in ('logo','company') else slot.kind;key=(slot.owner,kind,slot.index)
        if key in identities:dag.add_edge(('FIELD',identities[key]),node)
        if slot.kind=='logo':dag.add_edge(('LOGO',slot.owner,(template.width_mm,template.height_mm)),node)
        else:dag.add_edge(('FONT',slot.font,getattr(slot,'font_style','')),node)
        dag.add_edge(('OWNER_BINDING',slot.owner),node)
    assert nx.is_directed_acyclic_graph(dag)
    return dag


def affected(template,old_people,old_companies,new_people,new_companies,changed_assets=()):
    import networkx as nx
    old,old_ids=fields(old_people,old_companies);new,new_ids=fields(new_people,new_companies);dag=graph(template,new_people,new_companies);changed={key for key in set(old)|set(new) if old.get(key)!=new.get(key) or old_ids.get(key)!=new_ids.get(key)};nodes=set(changed_assets)
    for key in changed:
        if key in new_ids:nodes.add(('FIELD',new_ids[key]))
        else:
            nodes.add(CARD)
            for slot in template.slots:
                kind='name' if slot.kind in ('logo','company') else slot.kind
                if (slot.owner,kind,slot.index)==key:nodes.add(('SLOT',slot.id))
        if key[1] in ('company','companies') and key[0].startswith('p'):
            from .model import input_company_ports
            try:
                number=int(key[0][1:])-1;old_person=old_people[number];new_person=new_people[number]
                for person in (old_person,new_person):
                    raw=person.get('companies',person.get('company',''))
                    if raw and not(isinstance(raw,str) or isinstance(raw,list) and all(isinstance(v,str) for v in raw)):raise ValueError('公司歸屬格式無法核對')
                ports=set(input_company_ports(old_person))|set(input_company_ports(new_person))
            except (ValueError,IndexError,TypeError):ports={s.owner for s in template.slots}
            nodes.add(('OWNER_BINDING',key[0]))
            nodes.update(('SLOT',slot.id) for slot in template.slots if slot.owner in ports)
    if len(old_people)!=len(new_people) or len(old_companies)!=len(new_companies):nodes|={CARD}|{n for n in dag if n[0]=='SLOT'}
    reached=set()
    for node in nodes:
        reached.add(node)
        if node in dag:reached.update(nx.descendants(dag,node))
    return dict(changed_fields=sorted(changed),affected_slot_ids=sorted(n[1] for n in reached if n[0]=='SLOT'),whole_card_validation_required=CARD in reached,can_reuse_without_current_source_gate=False,reason='Explicit dependency paths; unknown/deleted fields retain global Gate, no cache grants final permission')


def merge_properties(base,current,suggestion,locked=False):
    """Common base/current human/suggestion: retain manual values on all conflicts."""
    if set(base)!=set(current) or set(base)!=set(suggestion):raise ValueError('物件／屬性增刪需另外明確核對')
    merged=deepcopy(current);conflicts=[];decisions=[]
    for key in sorted(base):
        before,local,remote=base[key],current[key],suggestion[key]
        if key=='size_pt' and (local!=before or remote!=before):reason='FIXED_FONT_SIZE_CHANGE_BLOCKED'
        elif remote==local or remote==before:reason='KEEP_CURRENT'
        elif locked:reason='LOCKED_OBJECT_CONFLICT'
        elif key in ('owner','kind','index'):reason='SEMANTIC_OWNERSHIP_REVIEW'
        elif local==before:reason='PROPOSE_REMOTE_CHANGE';merged[key]=deepcopy(remote)
        else:reason='DIVERGENT_MANUAL_AND_SUGGESTION_CONFLICT'
        if reason.endswith('CONFLICT') or reason in ('FIXED_FONT_SIZE_CHANGE_BLOCKED','SEMANTIC_OWNERSHIP_REVIEW'):conflicts.append(key)
        if local!=remote or reason=='FIXED_FONT_SIZE_CHANGE_BLOCKED':decisions.append(dict(property=key,before=deepcopy(before),current=deepcopy(local),suggestion=deepcopy(remote),reason=reason))
    return dict(merged=merged,conflicts=conflicts,decisions=decisions,applied=False,whole_card_recheck_required=True,formal_allowed=False)


EDITABLE={'rect.x','rect.y','rect.w','rect.h','align','color','locked','tracking_mm','tracking_min_mm','tracking_max_mm'}

def slot_properties(slot):
    values={key:deepcopy(value) for key,value in slot.items() if key!='rect'}
    values.update({'rect.'+key:value for key,value in slot['rect'].items()});return values


def manual_delta(before,after):
    """Store only actual geometry/property deltas, never a customer/input snapshot."""
    from .training_store import digest
    from .model import new_id
    for key in ('id','family_id','version','width_mm','height_mm','capacity','source_id','company_bindings'):
        if before.get(key)!=after.get(key):raise ValueError('單筆復原不能跨來源／版次／尺寸／歸屬')
    old={row['id']:slot_properties(row) for row in before['slots']};new={row['id']:slot_properties(row) for row in after['slots']}
    if set(old)!=set(new):raise ValueError('物件增刪需另外核對已授權邊界')
    changes=[]
    for identity,values in old.items():
        for key,value in values.items():
            if value!=new[identity].get(key):
                if key not in EDITABLE:raise ValueError('不能無聲修改固定字級／來源／語意歸屬：'+key)
                changes.append(dict(object_id=identity,property=key,before=deepcopy(value),after=deepcopy(new[identity][key])))
    if not changes or len(changes)>640:raise ValueError('空白或超過預算的人工差異，未記錄')
    receipt=dict(id=new_id(),changes=changes,before_digest=digest(before),after_digest=digest(after),template_id=before['id'],dimensions=[before['width_mm'],before['height_mm']],scope='THIS_CANDIDATE_ONLY',undone=False)
    receipt['digest']=digest(receipt);return receipt


def inverse_delta(current,receipt):
    """Reviewable inverse only while touched properties still equal recorded after.

    Other objects/coordinates remain current. The caller must regenerate the full
    card with current input and fresh source gates; this does not grant export.
    """
    from .training_store import digest
    from .object_tools import propose
    if receipt.get('undone') or digest({k:v for k,v in receipt.items() if k!='digest'})!=receipt.get('digest'):raise ValueError('差異憑證已變更或已復原')
    if current['id']!=receipt['template_id'] or [current['width_mm'],current['height_mm']]!=receipt['dimensions']:raise ValueError('復原範圍／來源／尺寸不符')
    live={row['id']:slot_properties(row) for row in current['slots']};patches={}
    for change in receipt['changes']:
        identity=change['object_id'];key=change['property']
        if key not in EDITABLE or identity not in live or live[identity].get(key)!=change['after']:raise ValueError('此屬性已在後續修改，保留目前人工內容並核對衝突')
        patches.setdefault(identity,{})[key]=deepcopy(change['before'])
    after=deepcopy(current);state=after['state'];after['state']='draft'
    for identity,values in patches.items():
        if values.keys()=={'locked'}:
            after=propose(after,'TEMPLATE',dict(operation='LOCK',ids=[identity],locked=values['locked'],cross_owner=False))['after'];continue
        if 'locked' in values:raise ValueError('鎖定與幾何變動需分別明確復原')
        patch={key.removeprefix('rect.'):value for key,value in values.items()};after=propose(after,'TEMPLATE',dict(operation='PATCH',ids=[identity],patch=patch,cross_owner=False))['after']
    after['state']=state
    return dict(template=after,actual_changes=deepcopy(receipt['changes']),applied=False,whole_card_recheck_required=True,formal_allowed=False,receipt_id=receipt['id'])
