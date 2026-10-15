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
        from .customer_entities import migrate
        migrate(self.db)
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
            from .customer_entities import from_legacy_fields, insert_graph
            insert_graph(self.db,cid,from_legacy_fields([dict(id=fid,owner=o,kind=k,value=v) for fid,o,k,v in checked]))
            self.library.event(cid,'customer_manual_confirmed')
        return self.get(cid)
    def get(self,cid):
        r=self.db.execute('SELECT id,code,name,revision FROM customers WHERE id=?',(cid,)).fetchone()
        if not r:raise ValueError('客戶不存在')
        fields=[dict(zip(('id','owner','kind','value'),x)) for x in self.db.execute('SELECT id,owner,kind,value FROM customer_fields WHERE customer_id=? ORDER BY rowid',(cid,))]
        styles=[dict(zip(('id','template_id','template_hash','width_mm','height_mm'),x)) for x in self.db.execute('SELECT id,template_id,template_hash,width,height FROM customer_styles WHERE customer_id=? ORDER BY id',(cid,))]
        from .customer_entities import read_graph
        graph=read_graph(self.db,cid,r[3])
        state=self.db.execute('SELECT status FROM customer_graph_states WHERE customer_id=?',(cid,)).fetchone()
        return dict(zip(('id','code','name','revision'),r),fields=fields,styles=styles,graph=graph,ownership_state=state[0] if state else 'NOT_MIGRATED')
    def search(self,query,offset=0,field='ANY'):
        from .customer_search import search
        return search(self,query,offset,field)
    def differences(self,snapshot,values):
        current=self.get(snapshot['id']);byid={f['id']:f for f in snapshot['fields']}
        if set(values)-byid.keys():raise ValueError('不能按位置新增或跨客戶更新欄位')
        rows=[]
        from .input_graph import InputGraph
        graph=InputGraph(current['graph']) if current.get('graph') else None
        for fid,new in values.items():
            if not isinstance(new,str) or len(new)>2048:raise ValueError('欄位值不合法')
            old=byid[fid]
            if new!=old['value']:rows.append({**old,'old':old['value'],'new':new,'current':next(f['value'] for f in current['fields'] if f['id']==fid),'operation':'CLEAR' if new=='' else 'EDIT','owner_entity_id':graph.field(fid)['owner_id'] if graph else None,'affected_entities':graph.field_impact(fid) if graph else [],'source_revision':snapshot['revision']})
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
        if c.get('graph'):
            from .input_graph import InputGraph
            people,companies,logos=InputGraph(c['graph']).compile(self.library.logos())
            return {'snapshot':c,'graph':c['graph'],'template_id':t.id,'people':people,'companies':companies,'logos':logos,'width_mm':t.width_mm,'height_mm':t.height_mm,'status':'PREFILL_PENDING_VALIDATION','template_state':t.state}
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

    def create_graph(self,code,name,data,template_id,approved=False):
        from .customer_entities import clone_for_master,insert_graph
        from .input_graph import InputGraph
        code=str(code).strip();name=str(name).strip()
        if not approved or not code or len(code)>64 or not name or len(name)>256:raise ValueError('需人工確認客戶編號與名稱')
        graph=clone_for_master(data);g=InputGraph(graph)
        if not graph['people'] or any(not g.label(e['id']).strip() or g.label(e['id'])=='未命名／待補' for e in graph['people']+graph['companies']):raise ValueError('人工建檔前需補齊人物及公司名稱')
        t=next((t for t in self.library.templates() if t.id==template_id),None)
        if not t or t.capacity!=len(graph['people']):raise ValueError('確切版型容量不符')
        self.library._template_provenance(t);cid=new_id()
        with self.db:
            self.db.execute('INSERT INTO customers VALUES(?,?,?,1)',(cid,code,name))
            insert_graph(self.db,cid,graph,write_fields=True)
            self.db.execute('INSERT INTO customer_styles VALUES(?,?,?,?,?,?)',(new_id(),cid,t.id,digest(t.to_dict()),t.width_mm,t.height_mm))
            self.library.event(cid,'customer_entities_manually_confirmed')
        return self.get(cid)

    def link_style(self,snapshot,template_id,approved=False):
        if not approved:raise ValueError('先確認客戶與確切版型')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            now=self.get(snapshot['id'])
            if digest(now)!=digest(snapshot):raise ValueError('主檔已更新，重新核對')
            t=next((t for t in self.library.templates() if t.id==template_id),None)
            if not t or (now.get('graph') and t.capacity!=len(now['graph']['people'])):raise ValueError('版型不存在或人物容量不符')
            self.library._template_provenance(t)
            self.db.execute('INSERT INTO customer_styles VALUES(?,?,?,?,?,?)',(new_id(),now['id'],t.id,digest(t.to_dict()),t.width_mm,t.height_mm))
            self.db.execute('UPDATE customers SET revision=revision+1 WHERE id=?',(now['id'],))
            self.library.event(now['id'],'customer_exact_style_linked');self.db.commit()
        except BaseException:self.db.rollback();raise
        return self.get(snapshot['id'])

    def history(self,cid):
        self.get(cid)
        return [dict(id=r[0],revision=r[1],payload=json.loads(r[2])) for r in self.db.execute('SELECT id,revision,payload FROM customer_changes WHERE customer_id=? ORDER BY revision DESC',(cid,))]

    def restore_change(self,snapshot,change_id,selected,approved=False):
        change=next((r for r in self.history(snapshot['id']) if r['id']==change_id),None)
        if not change:raise ValueError('變更不屬於此客戶')
        old={f['id']:f['old'] for f in change['payload']['fields']}
        if set(selected)-old.keys():raise ValueError('恢復欄位不屬於此變更')
        return self.writeback(snapshot,old,selected,approved)
