"""Bounded exact-source consumers for draft source edits and undo confirmation."""
from .candidate_sync import field_reference


def consumers(window):
    from .multi_size_dialog import MultiSizeDialog
    provider=getattr(window,'source_candidates',None)
    result=list(provider()) if callable(provider) else [('目前輸出',candidate) for candidate in window.candidates]
    for dialog in window.findChildren(MultiSizeDialog):
        if dialog.service is not None and (dialog.isVisible() or dialog.running):
            for entry in dialog.service.entries:
                result.extend(('多尺寸 '+str(entry['size_mm'][0])+'×'+str(entry['size_mm'][1])+' mm',candidate) for candidate in entry['candidates'])
    return result


def source_change_impact(candidates,before,after):
    old={row['id']:row for row in before['fields']};new={row['id']:row for row in after['fields']};changed={key for key in old.keys()|new.keys() if old.get(key)!=new.get(key)};entities=set();relations=set();logo_entities=set()
    def field_orders(data):
        result={}
        for field in data['fields']:
            for consumer in field['users']:result.setdefault((consumer,field['kind']),[]).append(field['id'])
        return result
    a_orders,b_orders=field_orders(before),field_orders(after)
    for consumer in a_orders.keys()|b_orders.keys():
        old_order={identity:i for i,identity in enumerate(a_orders.get(consumer,[]))};new_order={identity:i for i,identity in enumerate(b_orders.get(consumer,[]))};changed.update(key for key in old_order.keys()&new_order.keys() if old_order[key]!=new_order[key])
    company_ids={row['id'] for row in before['companies']+after['companies']}
    for key in changed:
        for field in (old.get(key),new.get(key)):
            if field:
                entities.update(field['users']);entities.add(field['owner_id'])
                if field['kind']=='name' and field['owner_id'] in company_ids:logo_entities.add(field['owner_id'])
    for kind in ('people','companies'):
        a={row['id']:row for row in before[kind]};b={row['id']:row for row in after[kind]}
        if [r['id'] for r in before[kind]]!=[r['id'] for r in after[kind]]:relations.update(a.keys()|b.keys())
        for key in a.keys()|b.keys():
            if a.get(key)!=b.get(key):
                if kind=='companies':logo_entities.add(key)
                else:relations.add(key)
    for link in set(map(tuple,before['links']))^set(map(tuple,after['links'])):relations.update(link)
    if not changed and not relations and not logo_entities:return []
    result=[]
    if len(candidates)>400:raise ValueError('超過可核對的400作品集合，未截斷影響清單；請縮小目前工作範圍')
    for scope,candidate in candidates:
        snapshot=candidate.risk_context.get('input_snapshot',{});owner_ids={row.get('source_entity_id') for row in snapshot.get('people',[])+snapshot.get('companies',[])};affected=[];unknown=False
        for slot in candidate.template.slots:
            try:
                entity,kind,field=field_reference(candidate,slot)
                if field in changed or entity in relations or slot.kind=='logo' and entity in logo_entities:affected.append(slot.id)
            except ValueError:unknown=True
        if not affected and not unknown and not owner_ids.intersection(entities|relations|logo_entities):continue
        if unknown:affected=[slot.id for slot in candidate.template.slots]
        result.append(dict(scope=scope,template_id=candidate.template.id,label=candidate.template.name,dimensions=[candidate.template.width_mm,candidate.template.height_mm],affected_slot_ids=affected,whole_card_validation_required=True,unknown_scope=unknown,reason='來源欄位ID未能核實，保守核對整張作品' if unknown else '引用同一來源實體／欄位；若採用變更須逐作品重驗，保留人工版面'))
        if len(result)>200:raise ValueError('超過200受影響作品預算，未截斷清單或回復來源；請縮小目前工作範圍')
    return result


def describe(rows):
    return '\n'.join(row['scope']+'／'+row['label']+'／'+str(row['dimensions'][0])+'×'+str(row['dimensions'][1])+' mm：'+row['reason']+'\n涉及框位：'+('、'.join(row['affected_slot_ids']) or '沒有對應局部框位，仍須整張語意核對') for row in rows)
