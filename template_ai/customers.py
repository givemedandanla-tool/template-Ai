"""Local customer identity: normalized stable fields, explicit links and CAS writes."""
import json
import hashlib
import time
from .model import new_id


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class CustomerStore:
    def __init__(self, library):
        self.library=library;self.db=library.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS customer_fields(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), owner TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS customer_styles(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), template_id TEXT NOT NULL REFERENCES templates(id), template_hash TEXT NOT NULL, width REAL NOT NULL, height REAL NOT NULL, UNIQUE(customer_id,template_id));
        CREATE TABLE IF NOT EXISTS customer_changes(id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),revision INTEGER NOT NULL,payload TEXT NOT NULL);
        ''');self.db.commit()
    def create(self,code,name,fields,template_id,approved=False):
        code=str(code).strip();name=str(name).strip()
        if not approved or not code or len(code)>64 or not name or len(name)>256:raise ValueError('需人工確認非空字串客戶編號與名稱')
        if not 1<=len(fields)<=100:raise ValueError('需1至100個具明確人物歸屬欄位')
        checked=[]
        for f in fields:
            owner,kind,value=f['owner'],f['kind'],f['value']
            if not isinstance(owner,str) or not owner.startswith('p') or not owner[1:].isdigit() or not 1<=int(owner[1:])<=20:raise ValueError('需明確人物ROOT')
            if kind not in ('name','title','phone','email','line','ig','address') or not isinstance(value,str) or not value.strip() or len(value)>2048:raise ValueError('欄位類型或值不合法')
            checked.append((new_id(),owner,kind,value))
        templates={t.id:t for t in self.library.templates()}
        if template_id not in templates:raise ValueError('確切模板版本不存在')
        t=templates[template_id];self.library._template_provenance(t)
        owners={o for _,o,_,_ in checked}
        if owners!={f'p{i+1}' for i in range(len(owners))} or len(owners)!=t.capacity or any(not any(o==owner and k=='name' for _,o,k,_ in checked) for owner in owners):raise ValueError('人物ROOT需連續、具姓名且容量對應版型；公司關聯稍後擴充')
        cid=new_id()
        with self.db:
            self.db.execute('INSERT INTO customers VALUES(?,?,?,1)',(cid,code,name))
            self.db.executemany('INSERT INTO customer_fields VALUES(?,?,?,?,?)',[(fid,cid,o,k,v) for fid,o,k,v in checked])
            self.db.execute('INSERT INTO customer_styles VALUES(?,?,?,?,?,?)',(new_id(),cid,t.id,digest(t.to_dict()),t.width_mm,t.height_mm))
            self.library.event(cid,'customer_manual_confirmed')
        return self.get(cid)
    def get(self,cid):
        r=self.db.execute('SELECT id,code,name,revision FROM customers WHERE id=?',(cid,)).fetchone()
        if not r:raise ValueError('客戶不存在')
        fields=[dict(zip(('id','owner','kind','value'),x)) for x in self.db.execute('SELECT id,owner,kind,value FROM customer_fields WHERE customer_id=? ORDER BY rowid',(cid,))]
        styles=[dict(zip(('id','template_id','template_hash','width_mm','height_mm'),x)) for x in self.db.execute('SELECT id,template_id,template_hash,width,height FROM customer_styles WHERE customer_id=? ORDER BY id',(cid,))]
        return dict(zip(('id','code','name','revision'),r),fields=fields,styles=styles)
    def search(self,query,offset=0):
        q=query.strip().casefold()
        if not q:return []
        if offset<0:raise ValueError('分頁不合法')
        # instr is literal: user %/_ are not SQL wildcard expressions.
        rows=self.db.execute('SELECT DISTINCT c.id FROM customers c LEFT JOIN customer_fields f ON f.customer_id=c.id WHERE instr(lower(c.code),?) OR instr(lower(c.name),?) OR instr(lower(f.value),?) ORDER BY c.code LIMIT 101 OFFSET ?',(q,q,q,offset)).fetchall()
        return [self.get(r[0]) for r in rows]
    def differences(self,snapshot,values):
        current=self.get(snapshot['id']);byid={f['id']:f for f in snapshot['fields']}
        if set(values)-byid.keys():raise ValueError('不能按位置新增或跨客戶更新欄位')
        rows=[]
        for fid,new in values.items():
            if not isinstance(new,str) or len(new)>2048:raise ValueError('欄位值不合法')
            old=byid[fid]
            if new!=old['value']:rows.append({**old,'old':old['value'],'new':new,'current':next(f['value'] for f in current['fields'] if f['id']==fid),'operation':'CLEAR' if new=='' else 'EDIT'})
        return {'customer_id':snapshot['id'],'revision':snapshot['revision'],'current_revision':current['revision'],'rows':rows,'snapshot_digest':digest(snapshot)}
    def writeback(self,snapshot,values,selected,approved=False):
        if not approved or not selected or len(set(selected))!=len(selected):raise ValueError('需明確勾選與確認')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            plan=self.differences(snapshot,values);now=self.get(snapshot['id'])
            if now['revision']!=snapshot['revision'] or digest(now)!=digest(snapshot):raise ValueError('主檔已更新；重新比對三方值')
            rows={r['id']:r for r in plan['rows']}
            if set(selected)-rows.keys():raise ValueError('選取不是當次差異')
            for fid in selected:self.db.execute('UPDATE customer_fields SET value=? WHERE id=? AND customer_id=?',(rows[fid]['new'],fid,snapshot['id']))
            revision=now['revision']+1;self.db.execute('UPDATE customers SET revision=? WHERE id=?',(revision,now['id']))
            self.db.execute('INSERT INTO customer_changes VALUES(?,?,?,?)',(new_id(),now['id'],revision,json.dumps({'fields':[rows[x] for x in selected]},ensure_ascii=False)))
            self.library.event(now['id'],'customer_selected_fields_updated');self.db.commit()
        except BaseException:self.db.rollback();raise
        return self.get(snapshot['id'])
    def reorder(self,cid,style_id,approved=False):
        if not approved:raise ValueError('先確認客戶身份與確切版型')
        c=self.get(cid);link=next((r for r in c['styles'] if r['id']==style_id),None)
        if not link:raise ValueError('版型不屬於此客戶')
        t=next((t for t in self.library.templates() if t.id==link['template_id']),None)
        if not t or digest(t.to_dict())!=link['template_hash']:raise ValueError('版型版本已改變，需重新核對')
        self.library._template_provenance(t)
        people=[]
        for owner in sorted({f['owner'] for f in c['fields']},key=lambda x:int(x[1:])):
            p={}
            for f in c['fields']:
                if f['owner']==owner and f['value']:p.setdefault(f['kind'],[]).append(f['value'])
            p['source_owner_id']=owner;p['source_field_ids']=[f['id'] for f in c['fields'] if f['owner']==owner];people.append(p)
        return {'snapshot':c,'template_id':t.id,'people':people,'width_mm':t.width_mm,'height_mm':t.height_mm,'status':'PREFILL_PENDING_VALIDATION','template_state':t.state}
    def compare(self,a,b):
        if a==b:raise ValueError('選取兩個不同客戶')
        x,y=self.get(a),self.get(b);keys=lambda c:{(f['kind'],f['value'].casefold()) for f in c['fields'] if f['value']}
        common=sorted(keys(x)&keys(y))
        return {'left':x,'right':y,'shared_clues':common,'identity':'UNKNOWN','automatic_merge':False,'reason':'相同姓名／聯絡資料／內容不足以判定同一客戶'}
