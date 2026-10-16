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
