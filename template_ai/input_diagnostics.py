"""Source-bound field warnings, without invented global character limits."""
from .layout import text_geometry
from .text_policy import tracking_geometry
from .model import input_company_ports

KINDS=('name','title','phone','email','line','ig','address')

def diagnose(people,companies,templates,width,height):
    issues=[];eligible=[t for t in templates if t.width_mm==width and t.height_mm==height and t.capacity==len(people)]
    def add(table,row,owner,code,reason,kind='name',index=0,**extra):
        entity=(people if table=='people' else companies)[row];ids=entity.get('field_ids',{}).get(kind,[])
        issues.append(dict(table=table,row=row,col=KINDS.index(kind) if table=='people' and kind in KINDS else 0,owner=owner,entity_id=entity.get('source_entity_id'),field_id=ids[index] if index<len(ids) else None,field_kind=kind,index=index,code=code,reason=reason,severity='WARNING',**extra))
    def check(table,row,owner,kind,index,value,slot_kind=None):
        mapped=[s for t in eligible for s in t.slots if s.owner==owner and s.kind==(slot_kind or kind) and s.index==index]
        if eligible and not mapped:
            add(table,row,owner,'NO_SLOT',f'{kind} 第{index+1}筆在目前同尺寸同容量模板沒有映射；不得忽略或混配，試排仍逐模板驗證',kind,index);return
        if not mapped:return
        evidence=[];geometry=[]
        for slot in mapped[:200]:
            tw,th,errors,tracking,strategy=tracking_geometry(slot,value,text_geometry);ratio=min(1,slot.rect.w/tw) if tw>0 else 1
            geometry.append(dict(size_pt=slot.size_pt,width_mm=slot.rect.w,height_mm=slot.rect.h,text_width_mm=None if errors else tw,text_height_mm=None if errors else th,required_scale=None if errors else ratio,min_scale=slot.min_scale,tracking_mm=tracking,tracking_strategy=strategy))
            if errors or ratio<slot.min_scale or th>slot.rect.h:evidence.append(f'{slot.id}: 固定{slot.size_pt:g}pt／量得寬{tw:.3f}mm／可用{slot.rect.w:.3f}mm／需X{ratio:.1%}／下限{slot.min_scale:.1%}；'+','.join(errors))
        if len(mapped)>200:add(table,row,owner,'UNCHECKED_FIELDS','超過200框位量測預算；其餘尚未核實，不宣稱所有模板無解',kind,index)
        if evidence and len(evidence)==min(200,len(mapped)):add(table,row,owner,'FIT_RISK','印刷效果可能不佳：已檢查框位皆有風險；非全域無解：'+'；'.join(evidence[:4]),kind,index,parameters=geometry[0])
    for i,person in enumerate(people):
        owner=f'p{i+1}'
        if not any(person.get('name',[])):add('people',i,owner,'MISSING_NAME','姓名未提供；必要欄位待補，尚未完成版面驗證')
        if any(c not in {f'c{j+1}' for j in range(len(companies))} for c in input_company_ports(person)):
            add('people',i,owner,'UNKNOWN_COMPANY','公司序號無對應公司；不得混配');issues[-1]['col']=7
        for kind in KINDS:
            for index,value in enumerate(person.get(kind,[])):
                if value:check('people',i,owner,kind,index,value)
    for i,company in enumerate(companies):
        owner=f'c{i+1}'
        if not any(owner in input_company_ports(person) for person in people):add('companies',i,owner,'UNBOUND_COMPANY','公司尚無人物引用；不會無聲刪除或當成已排版')
        name=company.get('name','');name=name[0] if isinstance(name,list) and name else name
        if name:check('companies',i,owner,'name',0,name,'company')
        for kind in KINDS[2:]:
            for index,value in enumerate(company.get(kind,[])):
                if value:check('companies',i,owner,kind,index,value)
    return dict(state='ESTIMATED_RISK_PENDING_VALIDATION' if issues else 'PENDING_LAYOUT_VALIDATION',issues=issues,templates_checked=len(eligible),global_unsolvable=False)
