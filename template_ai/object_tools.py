"""Pure, deterministic object proposals; coordinates are millimetres, not viewport pixels."""
import copy
import math
import re
from .font_review import fingerprint
from .model import Slot,Rect,Template,template_errors

TEXT_FIELDS={'color','size_pt','min_scale','align','font','font_style','font_asset'}
PATCH_FIELDS=TEXT_FIELDS|{'x','y','w','h','required','kind','owner','index'}


def slots_of(payload,cap=True):
    rows=payload.get('slots',[])
    if not isinstance(rows,list) or (cap and len(rows)>200):raise ValueError('物件超過200預算或格式不合法')
    ids=[r.get('id') for r in rows]
    if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):raise ValueError('物件stable ID缺失或重複')
    slots=[Slot(**{**s,'rect':Rect(**s['rect'])}) for s in rows]
    if any(type(s.locked) is not bool or not s.rect.valid() for s in slots):raise ValueError('物件幾何／鎖定格式不合法')
    return slots


def select_slots(payload,ids):
    slots=slots_of(payload);by_id={s.id:s for s in slots}
    if not isinstance(ids,list) or not ids or len(ids)>200 or len(ids)!=len(set(ids)) or any(i not in by_id for i in ids):raise ValueError('需明列唯一存在的1～200物件ID')
    return [by_id[i] for i in ids]


def protect_locked(before,after):
    if not any(s.get('locked') is True for s in before.get('slots',[])):return
    old=slots_of(before,cap=False);new={s.id:s for s in slots_of(after,cap=False)}
    for s in old:
        if s.locked and (s.id not in new or s!=new[s.id]):raise ValueError('已鎖定物件不能修改／刪除；請先明確解鎖')


def common_properties(payload,ids):
    selected=select_slots(payload,ids)
    def value(s,key):return getattr(s.rect,key) if key in ('x','y','w','h') else getattr(s,key)
    keys=['x','y','w','h','kind','owner','index','font','font_style','size_pt','min_scale','align','color','required','locked']
    return {k:{'mixed':any(value(s,k)!=value(selected[0],k) for s in selected[1:]),'value':copy.deepcopy(value(selected[0],k)) if all(value(s,k)==value(selected[0],k) for s in selected) else None} for k in keys}


def dimensions(payload,kind):
    w,h=(payload['width_mm'],payload['height_mm']) if kind=='TEMPLATE' else (payload['work_width'],payload['work_height'])
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0<v<=2000 for v in (w,h)):raise ValueError('實體尺寸不合法')
    return w,h


def warnings_for(payload,kind):
    w,h=dimensions(payload,kind);slots=slots_of(payload)
    if kind=='TEMPLATE':t=Template.from_dict(payload)
    else:
        people=[int(s.owner[1:]) for s in slots if s.owner.startswith('p') and s.owner[1:].isdigit()]
        t=Template('來源標記草稿',w,h,slots,capacity=max(people or [1]),company_bindings=payload.get('company_bindings',{}))
    warnings=template_errors(t)
    return list(dict.fromkeys(warnings+['未提供實際人物文字；字形覆蓋、固定pt尺寸與可讀性仍須排版／正式輸出核驗']))


def _number(value):
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or abs(value)>2000:raise ValueError('毫米或属性數值需有限且在支援範圍')
    return value


def propose(payload,kind,request):
    if kind not in ('TEMPLATE','ARTWORK'):raise ValueError('編輯上下文不合法')
    dimensions(payload,kind)
    if kind=='TEMPLATE' and payload['state']!='draft':raise ValueError('已發布模板唯讀；請建立新版本草稿')
    request=copy.deepcopy(request);selected=select_slots(payload,request.get('ids'));operation=request.get('operation')
    if len({s.owner for s in selected})>1 and request.get('cross_owner') is not True:raise ValueError('跨人物／公司或共享關聯需明確核對範圍')
    if operation!='LOCK' and any(s.locked for s in selected):raise ValueError('範圍包含鎖定物件；整組拒絕，不自動排除')
    by_id={s.id:copy.deepcopy(s) for s in selected};gap=None;reference=None
    if operation=='LOCK':
        if type(request.get('locked')) is not bool:raise ValueError('需明確鎖定／解鎖動作')
        for s in by_id.values():s.locked=request['locked']
    elif operation=='DELETE':
        pass
    elif operation=='PATCH':
        patch=request.get('patch')
        if not isinstance(patch,dict) or not patch or set(patch)-PATCH_FIELDS:raise ValueError('只接受明確修改的已支援共同屬性')
        if len(selected)>1 and set(patch)&{'kind','owner','index'}:raise ValueError('多選不能批次重寫類型／人物公司歸屬／映射序號')
        if any(s.kind=='logo' for s in selected) and set(patch)&TEXT_FIELDS:raise ValueError('完整Logo不適用一般文字共同屬性')
        if set(patch)&{'font','font_style','font_asset'} and not {'font','font_style','font_asset'}<=set(patch):raise ValueError('字型變更需完整核准pin與款式，不能默借其他字型')
        if 'font' in patch:
            from .font_catalog import raw_asset
            raw=raw_asset(patch['font_asset'])
            if (raw.familyName(),raw.styleName())!=(patch['font'],patch['font_style']):raise ValueError('新字面與pin不符')
        for s in by_id.values():
            old=copy.deepcopy(s)
            for key,v in patch.items():
                if key in ('x','y','w','h','size_pt','min_scale'):_number(v)
                if key in ('x','y','w','h'):setattr(s.rect,key,v)
                else:setattr(s,key,copy.deepcopy(v))
            if old.kind=='logo' and s.kind!='logo':raise ValueError('完整Logo不能改成一般文字')
            if not s.rect.valid() or not 1<=s.size_pt<=200 or not .05<=s.min_scale<=1 or type(s.required) is not bool or type(s.index) is not int or s.index<0 or s.align not in ('left','center','right') or not isinstance(s.color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',s.color):raise ValueError('共同屬性不合法，未套用')
            if old.kind=='logo' and abs(s.rect.w/s.rect.h-old.rect.w/old.rect.h)>1e-6:raise ValueError('Logo框尺寸不可不等比變形')
    elif operation=='MOVE':
        dx,dy=_number(request.get('dx')),_number(request.get('dy'))
        for s in by_id.values():s.rect.x+=dx;s.rect.y+=dy
    elif operation in ('ALIGN','DISTRIBUTE'):
        if len(selected)<2:raise ValueError('對齊需至少2物件；分布需至少3')
        ref=request.get('reference')
        if ref=='SELECTION':
            x=min(s.rect.x for s in selected);y=min(s.rect.y for s in selected)
            reference=Rect(x,y,max(s.rect.x+s.rect.w for s in selected)-x,max(s.rect.y+s.rect.h for s in selected)-y)
        elif ref in by_id:reference=copy.deepcopy(by_id[ref].rect)
        else:raise ValueError('請明確選取基準物件或選取邊界')
        if operation=='ALIGN':
            axis=request.get('axis')
            if axis not in ('LEFT','HCENTER','RIGHT','TOP','VCENTER','BOTTOM'):raise ValueError('對齊方向不合法')
            for s in by_id.values():
                r=s.rect
                if axis=='LEFT':r.x=reference.x
                elif axis=='HCENTER':r.x=reference.x+(reference.w-r.w)/2
                elif axis=='RIGHT':r.x=reference.x+reference.w-r.w
                elif axis=='TOP':r.y=reference.y
                elif axis=='VCENTER':r.y=reference.y+(reference.h-r.h)/2
                elif axis=='BOTTOM':r.y=reference.y+reference.h-r.h
        else:
            axis=request.get('axis')
            if len(selected)<3 or axis not in ('HORIZONTAL','VERTICAL'):raise ValueError('等距分布需至少3物件與明確方向')
            coordinate,size=('x','w') if axis=='HORIZONTAL' else ('y','h')
            ordered=sorted(by_id.values(),key=lambda s:(getattr(s.rect,coordinate),s.id))
            first=getattr(ordered[0].rect,coordinate);end=max(getattr(s.rect,coordinate)+getattr(s.rect,size) for s in ordered)
            gap=(end-first-sum(getattr(s.rect,size) for s in ordered))/(len(ordered)-1)
            cursor=first
            for s in ordered:setattr(s.rect,coordinate,cursor);cursor+=getattr(s.rect,size)+gap
    else:raise ValueError('編輯操作未支援')
    after=copy.deepcopy(payload);changes=[]
    for raw in after['slots'][:]:
        if raw['id'] not in by_id:continue
        s=by_id[raw['id']];old=next(i for i in selected if i.id==s.id)
        if operation=='DELETE':after['slots'].remove(raw);new=None
        else:
            if operation=='LOCK':raw['locked']=s.locked
            elif operation=='PATCH':
                for key in request['patch']:
                    if key in ('x','y','w','h'):raw['rect'][key]=getattr(s.rect,key)
                    else:raw[key]=copy.deepcopy(getattr(s,key))
            else:raw['rect']['x'],raw['rect']['y']=s.rect.x,s.rect.y
            new=copy.deepcopy(raw)
        if old!=s or operation=='DELETE':changes.append({'id':s.id,'owner':old.owner,'kind':old.kind,'before':copy.deepcopy(next(r for r in payload['slots'] if r['id']==s.id)),'after':new,'dx':s.rect.x-old.rect.x,'dy':s.rect.y-old.rect.y})
    if not changes:raise ValueError('沒有實際差異；不建立空歷史')
    if kind=='ARTWORK' and operation!='LOCK':after['visual_confirmed']=False
    warnings=warnings_for(after,kind)
    if gap is not None and gap<0:warnings.insert(0,'邊界間距為負值；不偷偷縮小物件，草稿仍待修復')
    return {'before_hash':fingerprint(payload),'after':after,'request':request,'changes':changes,'warnings':warnings,'gap_mm':gap,'reference_rect':reference.__dict__ if reference else None,'scope':{'ids':[s.id for s in selected],'owners':sorted({s.owner for s in selected}),'locked':[s.id for s in selected if s.locked]}}
