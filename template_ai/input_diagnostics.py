"""Shared field warnings; estimates never become an invented universal character limit."""
from .layout import text_geometry

KINDS=('name','title','phone','email','line','ig','address')

def diagnose(people,companies,templates,width,height):
    issues=[];eligible=[t for t in templates if t.width_mm==width and t.height_mm==height and t.capacity==len(people)]
    for i,p in enumerate(people):
        owner=f'p{i+1}'
        if not p.get('name'):issues.append(dict(table='people',row=i,col=0,owner=owner,code='MISSING_NAME',reason='姓名未提供；必要欄位待補，尚未完成版面驗證'))
        company=p.get('company','')
        if company and company not in {f'c{j+1}' for j in range(len(companies))}:issues.append(dict(table='people',row=i,col=7,owner=owner,code='UNKNOWN_COMPANY',reason='公司序號無對應公司；不得混配'))
        for k in KINDS:
            values=p.get(k,[])
            for n,value in enumerate(values):
                if not value:continue
                mapped=[s for t in eligible for s in t.slots if s.owner==owner and s.kind==k and s.index==n]
                if eligible and not mapped:issues.append(dict(table='people',row=i,col=KINDS.index(k),owner=owner,code='NO_SLOT',reason=f'{k} 第{n+1}筆在目前同尺寸同容量模板沒有映射；試排仍逐模板驗證'))
                elif mapped:
                    evidence=[];geometry=[]
                    for s in mapped[:200]:
                        tw,th,errors=text_geometry(s.font,s.size_pt,value,s.font_style,s.font_asset);ratio=min(1,s.rect.w/tw) if tw>0 else 1
                        geometry.append(dict(size_pt=s.size_pt,width_mm=s.rect.w,height_mm=s.rect.h,text_width_mm=None if errors else tw,text_height_mm=None if errors else th,required_scale=None if errors else ratio,min_scale=s.min_scale))
                        if errors or ratio<s.min_scale or th>s.rect.h:evidence.append(f'{s.id}: 固定{s.size_pt:g}pt／量得寬{tw:.3f}mm／可用{s.rect.w:.3f}mm／需X{ratio:.1%}／下限{s.min_scale:.1%}；'+','.join(errors))
                    if len(evidence)==len(mapped):issues.append(dict(table='people',row=i,col=KINDS.index(k),owner=owner,code='FIT_RISK',parameters=geometry[0] if geometry else {},reason='此欄位的已檢查框位皆有風險；非全域無解：'+'；'.join(evidence[:4])))
    return {'state':'ESTIMATED_RISK_PENDING_VALIDATION' if issues else 'PENDING_LAYOUT_VALIDATION','issues':issues,'templates_checked':len(eligible),'global_unsolvable':False}
