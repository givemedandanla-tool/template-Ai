"""當次輸入的實體圖。穩定 ID 是身分；p1/c1 僅為模板位置埠。

不依姓名／電話推論共享，不保存案件，不更動模板或 Logo 資產。
"""
from copy import deepcopy
import hashlib
import json
import uuid
import itertools
from .model import new_id

KINDS = ('name', 'title', 'phone', 'email', 'line', 'ig', 'address')
CONTACT_KINDS = KINDS[2:]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class InputGraph:
    def __init__(self, data=None):
        self.data = deepcopy(data) if data is not None else dict(schema=1, revision=0, people=[], companies=[], fields=[], links=[])
        self.validate(self.data)
        self.undo_stack, self.redo_stack = [], []
        self.serial = self.data['revision']

    @staticmethod
    def validate(d):
        if not isinstance(d, dict) or set(d) != {'schema','revision','people','companies','fields','links'} or d['schema'] != 1:
            raise ValueError('輸入圖格式不合法')
        if type(d['revision']) is not int or d['revision'] < 0:
            raise ValueError('輸入圖版本不合法')
        if any(not isinstance(d[k], list) for k in ('people','companies','fields','links')):
            raise ValueError('輸入圖集合不合法')
        if len(d['people']) > 20 or len(d['companies']) > 20 or len(d['fields']) > 1000:
            raise ValueError('本版支援20人物／20公司／1000欄位；未截斷輸入')
        entities = {}
        ids = set()
        for kind in ('people','companies'):
            for e in d[kind]:
                expected = {'id'} if kind == 'people' else {'id','logo_id'}
                if not isinstance(e, dict) or set(e) != expected:
                    raise ValueError('實體欄位不合法')
                eid = e['id']
                if not isinstance(eid, str) or not eid or len(eid)>128 or eid in ids:
                    raise ValueError('實體ID重複或不合法')
                if kind == 'companies' and (not isinstance(e['logo_id'], str) or len(e['logo_id'])>128):
                    raise ValueError('Logo引用不合法')
                entities[eid] = kind; ids.add(eid)
        names = set()
        for f in d['fields']:
            if not isinstance(f,dict) or set(f) != {'id','owner_id','kind','value','users'}:
                raise ValueError('欄位格式不合法')
            if not isinstance(f['id'],str) or not f['id'] or len(f['id'])>128 or f['id'] in ids:
                raise ValueError('欄位ID重複或不合法')
            ids.add(f['id'])
            if f['owner_id'] not in entities or f['kind'] not in KINDS or not isinstance(f['value'],str) or len(f['value'])>2048:
                raise ValueError('欄位歸屬／類型／值不合法')
            users = f['users']
            if not isinstance(users,list) or any(not isinstance(x,str) for x in users) or not users or len(set(users)) != len(users) or f['owner_id'] not in users or set(users)-entities.keys():
                raise ValueError('欄位引用不能懸空或遺失所有者')
            if f['kind'] in ('name','title'):
                if users != [f['owner_id']] or (f['owner_id'],f['kind']) in names or (f['kind']=='title' and entities[f['owner_id']]=='companies'):
                    raise ValueError('姓名／公司名稱／職稱需單一明確所有者')
                names.add((f['owner_id'],f['kind']))
        if any((eid,'name') not in names for eid in entities):
            raise ValueError('每個實體需要一個名稱欄位（可待補）')
        seen = set()
        for link in d['links']:
            if not isinstance(link,list) or len(link)!=2 or entities.get(link[0])!='people' or entities.get(link[1])!='companies' or tuple(link) in seen:
                raise ValueError('人物公司關聯不合法')
            seen.add(tuple(link))
        return d

    def entity(self, eid):
        return next(e for e in self.data['people']+self.data['companies'] if e['id']==eid)

    def label(self, eid):
        return next((f['value'] for f in self.data['fields'] if f['owner_id']==eid and f['kind']=='name'), '') or '未命名／待補'

    def field(self, fid):
        try:return next(f for f in self.data['fields'] if f['id']==fid)
        except StopIteration:raise ValueError('欄位不存在') from None

    def references(self, eid):
        """實際引用，含公司欄位影響的每個人物，不比對字串。"""
        if eid not in {e['id'] for e in self.data['people']+self.data['companies']}:
            raise ValueError('實體不存在')
        return sorted({eid}|{p for p,c in self.data['links'] if c==eid})

    def field_impact(self, fid):
        return sorted({x for u in self.field(fid)['users'] for x in self.references(u)})

    @classmethod
    def from_legacy(cls, people, companies, logos=None):
        g=cls(); d=g.data
        pids=[new_id() for _ in people]; cids=[new_id() for _ in companies]
        d['people']=[{'id':i} for i in pids]
        d['companies']=[{'id':i,'logo_id':(logos or {}).get(f'c{j+1}',{}).get('id','')} for j,i in enumerate(cids)]
        for n,(eid,p) in enumerate(zip(pids,people)):
            for kind in KINDS:
                values=p.get(kind,[]);values=values if isinstance(values,list) else [values]
                if kind=='name' and not values:values=['']
                if kind in ('name','title') and len(values)>1:raise ValueError('人物姓名／職稱需一筆，請在卡片內分別新增人物')
                ids=p.get('field_ids',{}).get(kind,[])
                for j,v in enumerate(values):d['fields'].append(dict(id=ids[j] if j<len(ids) else new_id(),owner_id=eid,kind=kind,value=v,users=[eid]))
            bound=p.get('companies',[p.get('company')] if p.get('company') else [])
            for port in bound:
                if port not in {f'c{i+1}' for i in range(len(cids))}:raise ValueError('來源公司序號無對應實體')
                d['links'].append([eid,cids[int(port[1:])-1]])
        for eid,c in zip(cids,companies):
            for kind in ('name',)+CONTACT_KINDS:
                values=c.get(kind,[]);values=values if isinstance(values,list) else [values]
                if kind=='name' and not values:values=['']
                for value in values:d['fields'].append(dict(id=new_id(),owner_id=eid,kind=kind,value=value,users=[eid]))
        # The legacy empty spare company row is not an actual company.
        spare={c['id'] for c in d['companies'] if not any(x[1]==c['id'] for x in d['links']) and not c['logo_id'] and not any(f['value'] for f in d['fields'] if f['owner_id']==c['id'])}
        d['companies']=[c for c in d['companies'] if c['id'] not in spare];d['fields']=[f for f in d['fields'] if f['owner_id'] not in spare]
        cls.validate(d);return g

    def compile(self, assets=None):
        self.validate(self.data)
        d=self.data; cp={c['id']:f'c{i+1}' for i,c in enumerate(d['companies'])}
        def values(eid):
            v={k:[] for k in KINDS}; ids={k:[] for k in KINDS}
            for f in d['fields']:
                if eid in f['users']:
                    # Preserve empty positions: clearing index0 must not move index1.
                    v[f['kind']].append(f['value']);ids[f['kind']].append(f['id'])
            return dict(v,source_entity_id=eid,field_ids=ids)
        people=[];companies=[];logos={};byid={a['id']:a for a in (assets or [])}
        for p in d['people']:
            v=values(p['id']);ports=[cp[c['id']] for c in d['companies'] if [p['id'],c['id']] in d['links']]
            v.update(company=ports[0] if ports else '',companies=ports);people.append(v)
        for c in d['companies']:
            v=values(c['id']);v['name']=v['name'][0];companies.append(v)
            if c['logo_id'] in byid:logos[cp[c['id']]]=deepcopy(byid[c['logo_id']])
        return people,companies,logos

    def preview(self, action, **params):
        g=InputGraph(self.data); affected, destructive=g._execute(action,deepcopy(params))
        self.validate(g.data)
        return dict(action=action,params=deepcopy(params),base=fingerprint(self.data),after=g.data,
                    affected=sorted(set(affected)),requires_confirmation=destructive or len(set(affected))>1,
                    labels=[self.label(x) for x in sorted(set(affected)) if x in {e['id'] for e in self.data['people']+self.data['companies']}])

    def apply(self, plan, approved=False):
        if plan['base']!=fingerprint(self.data):raise ValueError('影響預覽已過期，重新查看引用與差異')
        # Recompute the action. New IDs are carried in params for deterministic plans.
        current=self.preview(plan['action'],**plan['params'])
        if current!=plan:raise ValueError('影響預覽不符，不套用')
        if plan['requires_confirmation'] and not approved:raise ValueError('共享／移除操作需明確確認影響')
        if self.data==plan['after']:return
        self.undo_stack.append(deepcopy(self.data));self.undo_stack=self.undo_stack[-100:];self.redo_stack.clear()
        self.data=deepcopy(plan['after']);self.serial+=1;self.data['revision']=self.serial

    def command(self, action, approved=False, **params):
        # IDs fixed before preview so apply can verify the exact operation.
        if action in ('add_person','add_company','add_field','copy_person','independent_company','independent_field'):
            params.setdefault('new_id',new_id())
        p=self.preview(action,**params);self.apply(p,approved);return p

    def make_plan(self, action, **params):
        if action in ('add_person','add_company','add_field','copy_person','independent_company','independent_field'):
            params.setdefault('new_id',new_id())
        return self.preview(action,**params)

    def _execute(self, action, p):
        d=self.data;entities={e['id']:e for e in d['people']+d['companies']};people={e['id'] for e in d['people']};companies={e['id'] for e in d['companies']}
        allocated=(uuid.uuid5(uuid.NAMESPACE_URL,p.get('new_id','')+':'+str(i)).hex for i in itertools.count())
        def field(eid,kind,value):
            f=dict(id=next(allocated),owner_id=eid,kind=kind,value=value,users=[eid]);d['fields'].append(f)
        def entity(eid):
            if eid not in entities:raise ValueError('實體不存在')
            return entities[eid]
        def clone_company(cid):
            entity(cid)
            if cid not in companies:raise ValueError('不是公司')
            nid=next(allocated);d['companies'].append(dict(id=nid,logo_id=entities[cid]['logo_id']))
            for f in list(d['fields']):
                if cid in f['users']:field(nid,f['kind'],f['value'])
            return nid
        if action=='add_person':
            eid=p['new_id'];d['people'].append({'id':eid});field(eid,'name',p.get('name',''));return [eid],False
        if action=='add_company':
            pid=p['person_id'];entity(pid)
            if pid not in people:raise ValueError('先選人物ROOT')
            cid=p['new_id'];d['companies'].append(dict(id=cid,logo_id=''));field(cid,'name',p.get('name',''));d['links'].append([pid,cid]);return [pid],False
        if action=='add_field':
            eid=p['owner_id'];entity(eid);field(eid,p['kind'],p.get('value',''));return self.references(eid),False
        if action=='edit_field':
            f=self.field(p['field_id']);impact=self.field_impact(f['id']);f['value']=p['value'];return impact,False
        if action=='edit_logo':
            cid=p['company_id'];entity(cid)
            if cid not in companies:raise ValueError('Logo僅屬公司')
            entities[cid]['logo_id']=p['logo_id'];return self.references(cid),False
        if action=='link_company':
            pid,cid=p['person_id'],p['company_id'];entity(pid);entity(cid)
            if pid not in people or cid not in companies or [pid,cid] in d['links']:raise ValueError('人物／公司關聯已存在或不合法')
            affected=self.references(cid)+[pid];d['links'].append([pid,cid]);return affected,False
        if action=='unlink_company':
            pair=[p['person_id'],p['company_id']]
            if pair not in d['links']:raise ValueError('關聯不存在')
            impact=self.references(pair[1]);d['links'].remove(pair);return impact,True
        if action=='delete_company':
            cid=p['company_id'];entity(cid)
            if cid not in companies:raise ValueError('不是公司')
            if any(c==cid for _,c in d['links']):raise ValueError('公司仍被人物引用，請先解除關聯；公司／Logo未刪除')
            owned={f['id'] for f in d['fields'] if f['owner_id']==cid}
            if any(len(f['users'])>1 for f in d['fields'] if f['id'] in owned):raise ValueError('公司欄位仍被其他實體引用，先解除或建立獨立複本')
            d['companies']=[c for c in d['companies'] if c['id']!=cid];d['fields']=[f for f in d['fields'] if f['id'] not in owned]
            for f in d['fields']:f['users']=[u for u in f['users'] if u!=cid]
            return [cid],True
        if action=='delete_person':
            pid=p['person_id'];entity(pid)
            if pid not in people:raise ValueError('不是人物')
            owned={f['id'] for f in d['fields'] if f['owner_id']==pid}
            if any(len(f['users'])>1 for f in d['fields'] if f['id'] in owned):raise ValueError('人物擁有共享欄位，先解除其他引用或建立獨立複本')
            impact={pid}|{x for a,c in d['links'] if a==pid for x in self.references(c)}|{x for f in d['fields'] if pid in f['users'] for x in self.field_impact(f['id'])}
            d['people']=[e for e in d['people'] if e['id']!=pid];d['links']=[l for l in d['links'] if l[0]!=pid];d['fields']=[f for f in d['fields'] if f['id'] not in owned]
            for f in d['fields']:f['users']=[u for u in f['users'] if u!=pid]
            return impact,True
        if action=='copy_person':
            pid=p['person_id'];entity(pid)
            if pid not in people:raise ValueError('不是人物')
            if p.get('company_mode') not in ('SHARED','INDEPENDENT'):raise ValueError('請明確選擇共享或獨立公司')
            nid=p['new_id'];d['people'].append({'id':nid})
            for f in list(d['fields']):
                if pid in f['users']:field(nid,f['kind'],f['value'])
            for person,cid in list(d['links']):
                if person==pid:d['links'].append([nid,cid if p['company_mode']=='SHARED' else clone_company(cid)])
            return {pid}|{x for a,c in d['links'] if a==pid for x in self.references(c)},False
        if action=='independent_company':
            pair=[p['person_id'],p['company_id']]
            if pair not in d['links']:raise ValueError('人物公司關聯不存在')
            impact=self.references(pair[1]);cid=clone_company(pair[1]);d['links'].remove(pair);d['links'].append([pair[0],cid]);return impact,True
        if action=='link_field':
            f=self.field(p['field_id']);eid=p['entity_id'];entity(eid)
            if f['kind'] not in CONTACT_KINDS or eid in f['users']:raise ValueError('只能連結未引用的聯絡資料')
            affected=self.field_impact(f['id'])+self.references(eid);f['users'].append(eid);return affected,False
        if action in ('unlink_field','independent_field'):
            f=self.field(p['field_id']);eid=p['entity_id']
            if eid not in f['users'] or eid==f['owner_id']:raise ValueError('所有者不能直接解除自己；可刪除實體欄位或先讓其他引用獨立')
            impact=self.field_impact(f['id']);f['users'].remove(eid)
            if action=='independent_field':field(eid,f['kind'],f['value'])
            return impact,True
        if action=='delete_field':
            f=self.field(p['field_id'])
            if f['kind']=='name':raise ValueError('名稱保留為待補欄位，不能刪除人物身分')
            impact=self.field_impact(f['id']);d['fields'].remove(f);return impact,True
        raise ValueError('未知輸入圖操作')

    def undo(self):
        if not self.undo_stack:return False
        self.redo_stack.append(deepcopy(self.data));self.data=self.undo_stack.pop();self.serial+=1;self.data['revision']=self.serial;return True

    def redo(self):
        if not self.redo_stack:return False
        self.undo_stack.append(deepcopy(self.data));self.data=self.redo_stack.pop();self.serial+=1;self.data['revision']=self.serial;return True
