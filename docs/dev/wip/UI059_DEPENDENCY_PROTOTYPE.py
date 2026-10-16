"""UI059 pure-math draft, not imported by the app or registered as completed scope.
Prepared while the active source batch is frozen. Reuse NetworkX, no parallel DB.
"""
from copy import deepcopy
import networkx as nx

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
    values,identities=fields(people,companies)
    if len(values)>2000 or len(template.slots)>64:raise ValueError('Explicit field/object budget exceeded; no partial-safe claim')
    dag=nx.DiGraph();dag.add_node(CARD)
    for key in values:
        node=('FIELD',identities[key]);dag.add_edge(node,('OWNER_GATE',key[0]));dag.add_edge(('OWNER_GATE',key[0]),CARD)
        # An unmapped field still reaches lossless whole-card validation.
        dag.add_edge(node,CARD)
    for slot in template.slots:
        node=('SLOT',slot.id);dag.add_edge(node,CARD);kind='name' if slot.kind in ('logo','company') else slot.kind;key=(slot.owner,kind,slot.index)
        if key in identities:dag.add_edge(('FIELD',identities[key]),node)
        if slot.kind=='logo':dag.add_edge(('LOGO',slot.owner,(template.width_mm,template.height_mm)),node)
        else:dag.add_edge(('FONT',slot.font,getattr(slot,'font_style','')),node)
        dag.add_edge(('OWNER_BINDING',slot.owner),node)
    assert nx.is_directed_acyclic_graph(dag)
    return dag


def affected(template,old_people,old_companies,new_people,new_companies,changed_assets=()):
    old,old_ids=fields(old_people,old_companies);new,new_ids=fields(new_people,new_companies);dag=graph(template,new_people,new_companies);changed={key for key in set(old)|set(new) if old.get(key)!=new.get(key) or old_ids.get(key)!=new_ids.get(key)};nodes=set(changed_assets)
    for key in changed:
        if key in new_ids:nodes.add(('FIELD',new_ids[key]))
        else:nodes.add(CARD)  # Deletion/unknown map conservatively rechecks global losslessness.
    if len(old_people)!=len(new_people) or len(old_companies)!=len(new_companies):nodes|={CARD}|{n for n in dag if n[0]=='SLOT'}
    reached=set()
    for node in nodes:
        reached.add(node)
        if node in dag:reached.update(nx.descendants(dag,node))
    return dict(changed_fields=sorted(changed),affected_slot_ids=sorted(n[1] for n in reached if n[0]=='SLOT'),whole_card_validation_required=CARD in reached,can_reuse_without_current_source_gate=False,reason='Explicit dependency paths; unknown/deleted fields retain global Gate, no cache grants final permission')


def merge_properties(base,current,suggestion,locked=False):
    """Common base/current human/suggestion: retain manual values on all conflicts."""
    if set(base)!=set(current) or set(base)!=set(suggestion):raise ValueError('Object/property additions or deletions require explicit review')
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
    from template_ai.training_store import digest
    from template_ai.model import new_id
    for key in ('id','family_id','version','width_mm','height_mm','capacity','source_id','company_bindings'):
        if before.get(key)!=after.get(key):raise ValueError('Undo does not cross source/style/dimension/ownership identities')
    old={row['id']:slot_properties(row) for row in before['slots']};new={row['id']:slot_properties(row) for row in after['slots']}
    if set(old)!=set(new):raise ValueError('Object addition/deletion needs separate bounded review')
    changes=[]
    for identity,values in old.items():
        for key,value in values.items():
            if value!=new[identity].get(key):
                if key not in EDITABLE:raise ValueError('Cannot silently alter fixed font/source/semantic binding: '+key)
                changes.append(dict(object_id=identity,property=key,before=deepcopy(value),after=deepcopy(new[identity][key])))
    if not changes or len(changes)>640:raise ValueError('Empty/oversized manual delta, not recorded')
    receipt=dict(id=new_id(),changes=changes,before_digest=digest(before),after_digest=digest(after),template_id=before['id'],dimensions=[before['width_mm'],before['height_mm']],scope='THIS_CANDIDATE_ONLY',undone=False)
    receipt['digest']=digest(receipt);return receipt


def inverse_delta(current,receipt):
    """Reviewable inverse only while touched properties still equal recorded after.

    Other objects/coordinates remain current. The caller must regenerate the full
    card with current input and fresh source gates; this does not grant export.
    """
    from template_ai.training_store import digest
    from template_ai.object_tools import propose
    if receipt.get('undone') or digest({k:v for k,v in receipt.items() if k!='digest'})!=receipt.get('digest'):raise ValueError('Delta changed or already undone')
    if current['id']!=receipt['template_id'] or [current['width_mm'],current['height_mm']]!=receipt['dimensions']:raise ValueError('Undo scope/source/dimension mismatch')
    live={row['id']:slot_properties(row) for row in current['slots']};patches={}
    for change in receipt['changes']:
        identity=change['object_id'];key=change['property']
        if key not in EDITABLE or identity not in live or live[identity].get(key)!=change['after']:raise ValueError('Current property changed after this action; preserve manual state and review conflict')
        patches.setdefault(identity,{})[key]=deepcopy(change['before'])
    after=deepcopy(current);state=after['state'];after['state']='draft'
    for identity,values in patches.items():
        if values.keys()=={'locked'}:
            after=propose(after,'TEMPLATE',dict(operation='LOCK',ids=[identity],locked=values['locked'],cross_owner=False))['after'];continue
        if 'locked' in values:raise ValueError('Mixed lock/geometry inverse requires separate explicit actions')
        patch={key.removeprefix('rect.'):value for key,value in values.items()};after=propose(after,'TEMPLATE',dict(operation='PATCH',ids=[identity],patch=patch,cross_owner=False))['after']
    after['state']=state
    return dict(template=after,actual_changes=deepcopy(receipt['changes']),applied=False,whole_card_recheck_required=True,formal_allowed=False,receipt_id=receipt['id'])
