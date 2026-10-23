"""Explicit customer identity operations over the existing normalized graph.

Graph disjoint union preserves people, companies and fields. Code aliases route
to a primary customer; byte equality never authorizes this operation. A split
partitions the CURRENT graph so later, unambiguous value edits survive.
"""
from copy import deepcopy
import json
import time

from .customers import digest
from .input_graph import InputGraph
from .model import new_id
from pathlib import Path


SCHEMA='''
CREATE TABLE IF NOT EXISTS customer_identity_redirects(
 secondary_id TEXT PRIMARY KEY REFERENCES customers(id),primary_id TEXT NOT NULL REFERENCES customers(id),merge_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customer_code_aliases(
 code TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),merge_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customer_style_scopes(
 style_id TEXT PRIMARY KEY REFERENCES customer_styles(id),payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customer_identity_events(
 id TEXT PRIMARY KEY,primary_id TEXT NOT NULL REFERENCES customers(id),secondary_id TEXT NOT NULL REFERENCES customers(id),
 state TEXT NOT NULL,payload TEXT NOT NULL);
'''


def members(db,cid):
    return [cid]+[r[0] for r in db.execute('SELECT secondary_id FROM customer_identity_redirects WHERE primary_id=? ORDER BY secondary_id',(cid,))]


def style_graph(db,graph,style_id):
    record=db.execute('SELECT payload FROM customer_style_scopes WHERE style_id=?',(style_id,)).fetchone()
    if not record:return graph
    selected=set(json.loads(record[0]));available={p['id'] for p in graph['people']}
    if not selected or not selected<=available:raise ValueError('版型人物範圍失效，需要重新核對')
    companies={c for p,c in graph['links'] if p in selected}
    allowed=selected|companies;fields=[]
    for f in graph['fields']:
        users=set(f['users']) & allowed
        if not users:continue
        if f['owner_id'] not in allowed:raise ValueError('跨版型範圍共享欄位需要人工重新核對，未借用別人的資料')
        fields.append(dict(deepcopy(f),users=[p for p in f['users'] if p in allowed]))
    scoped=dict(schema=1,revision=graph['revision'],people=[p for p in graph['people'] if p['id'] in selected],
                companies=[c for c in graph['companies'] if c['id'] in companies],fields=fields,
                links=[link for link in graph['links'] if link[0] in selected and link[1] in companies])
    InputGraph.validate(scoped);return scoped


def scoped_style_ids(store,customer,template_id,people):
    selected=set(people);result=[]
    for style in customer['styles']:
        if style['template_id']!=template_id:continue
        graph=style_graph(store.db,customer['graph'],style['id'])
        if {p['id'] for p in graph['people']}==selected:result.append(style['id'])
    return result


class CustomerIdentity:
    def __init__(self,store):
        self.store=store;self.db=store.db;self.library=store.library

    def _associations(self,ids):
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='customer_source_associations'").fetchone():return []
        marks=','.join('?' for _ in ids)
        cursor=self.db.execute('SELECT * FROM customer_source_associations WHERE customer_id IN ('+marks+') ORDER BY id LIMIT 2001',ids)
        keys=[c[0] for c in cursor.description]
        rows=[dict(zip(keys,row)) for row in cursor]
        if len(rows)>2000:raise ValueError('來源關聯超出2000筆單次審核預算，保持獨立')
        return rows

    def _state(self,cid):
        customer=self.store.get(cid)
        if customer['id']!=cid:raise ValueError('請選目前主客戶，不對已合併別名再合併')
        ids=members(self.db,cid)
        return dict(customer=customer,associations=self._associations(ids),
                    scopes=[dict(style_id=r[0],people=json.loads(r[1])) for r in self.db.execute(
                        'SELECT s.style_id,s.payload FROM customer_style_scopes s JOIN customer_styles t ON t.id=s.style_id WHERE t.customer_id IN ('+','.join('?' for _ in ids)+') ORDER BY s.style_id',ids)])

    def _validate_assets(self,states):
        from .source_links import verify_source
        from .model import Template
        pins={};total=0
        for state in states:
            for association in state['associations']:
                sid=association['source_id']
                if sid in pins:continue
                source=self.library.source(sid);path=Path(source['current_path']);total+=path.stat().st_size
                if total>256*1024*1024:raise ValueError('來源核對超出256MiB單次預算，需縮小範圍')
                proof=verify_source(path,association['source_hash'])
                pins[sid]=dict(hash=proof.hash,path=proof.path)
            for style in state['customer']['styles']:
                row=self.db.execute('SELECT payload FROM templates WHERE id=?',(style['template_id'],)).fetchone()
                if not row or digest(json.loads(row[0]))!=style['template_hash']:raise ValueError('版型版本失聯或已變更，先重新核對')
                self.library._template_provenance(Template.from_dict(json.loads(row[0])))
        return pins

    def comparison(self,a,b):
        left,right=self._state(a),self._state(b)
        if a==b:raise ValueError('請選兩個獨立客戶')
        plan=dict(operation='COMPARE',before=[left,right],primary_code=left['customer']['code'],
                  identity='UNKNOWN',automatic_merge=False)
        if len(json.dumps(plan,ensure_ascii=False).encode())>1_048_576:raise ValueError('比對資料超出1MiB，請縮小範圍')
        plan['sha256']=digest(plan);return plan

    def plan_merge(self,a,b,primary_code=None):
        if a==b:raise ValueError('請選兩個獨立客戶')
        left,right=self._state(a),self._state(b)
        if members(self.db,b)!=[b]:raise ValueError('次客戶仍有已合併歷史，請先逐項拆分並核對，避免巢狀重指派')
        x,y=left['customer'],right['customer']
        from .customer_search import fold
        self.db.create_function('ta_fold',1,fold,deterministic=True)
        allowed=set(members(self.db,a)+members(self.db,b))
        codes=[fold(x['code']),fold(y['code'])]
        conflicts=self.db.execute('SELECT id FROM customers WHERE ta_fold(code) IN (?,?)',codes).fetchall()
        alias_conflicts=self.db.execute('SELECT customer_id FROM customer_code_aliases WHERE ta_fold(code) IN (?,?)',codes).fetchall()
        if any(r[0] not in allowed for r in conflicts+alias_conflicts):raise ValueError('歷史別名與其他主編號正規化衝突，先人工解決')
        if not x.get('graph') or not y.get('graph'):raise ValueError('雙方人物／公司歸屬未確認，保留獨立')
        code=primary_code or x['code']
        if code not in (x['code'],y['code']):raise ValueError('主要顯示編號必須明確選自雙方現有編號')
        graph=deepcopy(x['graph'])
        for k in ('people','companies','fields','links'):graph[k].extend(deepcopy(y['graph'][k]))
        InputGraph.validate(graph)
        # Style IDs stay stable even if both customers used the same template.
        # Physical link rows retain origin; membership is routed by redirect.
        plan=dict(operation='MERGE',primary_id=a,secondary_id=b,primary_code=code,
                  before=[left,right],combined_graph=graph,
                  asset_pins=self._validate_assets([left,right]),
                  identity='HUMAN_CONFIRMATION_REQUIRED',automatic_merge=False,
                  effects=dict(people=len(graph['people']),companies=len(graph['companies']),fields=len(graph['fields']),
                               style_ids=[s['id'] for c in (x,y) for s in c['styles']],
                               source_associations=left['associations']+right['associations'],
                               retained_aliases=[x['code'],y['code']],
                               original_assets_modified=False,published_templates_modified=False))
        if len(json.dumps(plan,ensure_ascii=False).encode())>1_048_576:raise ValueError('合併影響超出1MiB審核預算，需分段核對')
        plan['sha256']=digest(plan);return plan

    def _write_graphs(self,pairs):
        from .customer_entities import insert_graph
        ids=[cid for cid,_ in pairs];marks=','.join('?' for _ in ids)
        for table in ('customer_company_links','customer_field_users','customer_entity_fields','customer_entities','customer_fields','customer_graph_states'):
            self.db.execute('DELETE FROM '+table+' WHERE customer_id IN ('+marks+')',ids)
        for cid,graph in pairs:
            if graph is None:self.db.execute('INSERT INTO customer_graph_states VALUES(?,1,?)',(cid,'IDENTITY_MERGED'))
            else:insert_graph(self.db,cid,graph,write_fields=True)

    @staticmethod
    def _check_plan(plan):
        raw=deepcopy(plan);pin=raw.pop('sha256',None)
        if digest(raw)!=pin:raise ValueError('核准計畫已變更，請重新預覽')

    def merge(self,plan,approved=False,actor='',reason=''):
        if not approved or not actor.strip() or not reason.strip():raise ValueError('需要明確核准、核准者及身份證據理由')
        self._check_plan(plan)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            fresh=self.plan_merge(plan['primary_id'],plan['secondary_id'],plan['primary_code'])
            if fresh!=plan:raise ValueError('雙方主檔／來源／版型／別名版本已改變，請重新預覽')
            a,b=plan['primary_id'],plan['secondary_id'];event_id=new_id()
            for state in plan['before']:
                customer=state['customer'];people=[p['id'] for p in customer['graph']['people']]
                for style in customer['styles']:
                    self.db.execute('INSERT OR IGNORE INTO customer_style_scopes VALUES(?,?)',(style['id'],json.dumps(people)))
            self._write_graphs([(a,plan['combined_graph']),(b,None)])
            x,y=[state['customer'] for state in plan['before']]
            if plan['primary_code']!=x['code']:
                self.db.execute('UPDATE customers SET code=? WHERE id=?',('TEMP-'+new_id(),a))
                self.db.execute('UPDATE customers SET code=? WHERE id=?',(x['code'],b))
                self.db.execute('UPDATE customers SET code=? WHERE id=?',(y['code'],a))
            self.db.execute('INSERT INTO customer_identity_redirects VALUES(?,?,?)',(b,a,event_id))
            for code in (x['code'],y['code']):
                prior=self.db.execute('SELECT customer_id FROM customer_code_aliases WHERE code=?',(code,)).fetchone()
                if prior and prior[0]!=a:raise ValueError('歷史編號別名與其他主客戶衝突，未覆蓋')
                self.db.execute('INSERT OR IGNORE INTO customer_code_aliases VALUES(?,?,?)',(code,a,event_id))
            if plan['before'][1]['associations']:
                self.db.execute('UPDATE customer_source_associations SET customer_id=? WHERE customer_id=?',(a,b))
            self.db.execute('UPDATE customers SET revision=revision+1 WHERE id IN (?,?)',(a,b))
            record=dict(plan=plan,actor=actor[:200],reason=reason[:2048],created=time.time())
            self.db.execute('INSERT INTO customer_identity_events VALUES(?,?,?,?,?)',(event_id,a,b,'MERGED',json.dumps(record,ensure_ascii=False)))
            if self._validate_assets(plan['before'])!=plan['asset_pins']:raise ValueError('執行期間來源變更，全部回退')
            if self.db.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('合併關聯驗證失敗，全部回退')
            self.library.event(event_id,'customer_identity_merged');self.db.commit()
            return dict(id=event_id,state='MERGED',customer=self.store.get(a))
        except BaseException:self.db.rollback();raise

    def history(self,primary_id):
        return [dict(id=r[0],state=r[1],**json.loads(r[2])) for r in self.db.execute(
            'SELECT id,state,payload FROM customer_identity_events WHERE primary_id=? ORDER BY rowid DESC',(primary_id,))]

    def record_review(self,a,b,state,actor,reason):
        if a==b or state not in ('KEEP_SEPARATE','PENDING_REVIEW') or not actor.strip() or not reason.strip():
            raise ValueError('需要兩個客戶、明確審核處置與理由')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            left,right=self._state(a),self._state(b)
            identity=new_id();payload=dict(before=[left,right],actor=actor[:200],reason=reason[:2048],created=time.time(),automatic_merge=False)
            self.db.execute('INSERT INTO customer_identity_events VALUES(?,?,?,?,?)',(identity,a,b,state,json.dumps(payload,ensure_ascii=False)))
            self.library.event(identity,'customer_identity_review_recorded');self.db.commit()
            return dict(id=identity,state=state)
        except BaseException:self.db.rollback();raise

    def export_event(self,event_id,target,approved=False):
        """Explicit local export only; original assets are never in this JSON."""
        if not approved:raise ValueError('稽核包含個資，請明確核准本機匯出，不得公開上傳')
        row=self.db.execute('SELECT primary_id,secondary_id,state,payload FROM customer_identity_events WHERE id=?',(event_id,)).fetchone()
        if not row:raise ValueError('稽核事件不存在')
        target=Path(target)
        if target.suffix.lower()!='.json' or not target.parent.is_dir():raise ValueError('請選本機JSON檔案位置')
        payload=dict(id=event_id,primary_id=row[0],secondary_id=row[1],state=row[2],payload=json.loads(row[3]),privacy='LOCAL_PERSONAL_DATA_DO_NOT_UPLOAD')
        import os,tempfile
        from .safe_publish import publish_complete
        fd,name=tempfile.mkstemp(prefix='.identity-export-',dir=target.parent)
        temporary=Path(name)
        try:
            with os.fdopen(fd,'w',encoding='utf8') as stream:
                json.dump(payload,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
            publish_complete(temporary,target)
        finally:temporary.unlink(missing_ok=True)
        return dict(path=str(target),state='EXPORTED_LOCAL',contains_personal_data=True)

    def redact_event(self,event_id,actor,reason,approved=False):
        if not approved or not actor.strip() or not reason.strip():raise ValueError('清理稽核個資需要明確核准及理由')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT state,payload FROM customer_identity_events WHERE id=?',(event_id,)).fetchone()
            if not row:raise ValueError('稽核事件不存在')
            if row[0]=='MERGED':raise ValueError('有效合併仍依賴原始映射以安全拆分；先核對拆分，再清理已結束事件')
            old=json.loads(row[1])
            if old.get('redacted'):raise ValueError('此事件已清理個資')
            payload=dict(redacted=True,previous_payload_sha256=digest(old),actor=actor[:200],reason=reason[:2048],created=time.time())
            self.db.execute('UPDATE customer_identity_events SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),event_id))
            self.library.event(event_id,'customer_identity_closed_event_redacted');self.db.commit()
            return dict(id=event_id,state='REDACTED',active_customer_fields_changed=False)
        except BaseException:self.db.rollback();raise

    def plan_split(self,event_id):
        row=self.db.execute('SELECT primary_id,secondary_id,state,payload FROM customer_identity_events WHERE id=?',(event_id,)).fetchone()
        if not row or row[2]!='MERGED':raise ValueError('合併記錄不存在或已拆分')
        a,b,_,payload=row;record=json.loads(payload);original=record['plan'];now=self._state(a)
        redir=self.db.execute('SELECT primary_id,merge_id FROM customer_identity_redirects WHERE secondary_id=?',(b,)).fetchone()
        if not redir or tuple(redir)!=(a,event_id):raise ValueError('合併歸屬已變更，先核對後續操作')
        owners=[{e['id'] for k in ('people','companies') for e in state['customer']['graph'][k]} for state in original['before']]
        current=now['customer']['graph'];all_ids={e['id'] for k in ('people','companies') for e in current[k]}
        if all_ids!=owners[0]|owners[1]:raise ValueError('合併後新增／移除人物或公司，須先逐項重新指派，不能歷史覆寫')
        graphs=[]
        for allowed in owners:
            graph=dict(schema=1,revision=current['revision'],people=[p for p in current['people'] if p['id'] in allowed],
                       companies=[c for c in current['companies'] if c['id'] in allowed],fields=[],links=[])
            for f in current['fields']:
                if f['owner_id'] in allowed:
                    if not set(f['users'])<=allowed:raise ValueError('合併後跨客戶共享欄位，請先逐項核對歸屬')
                    graph['fields'].append(deepcopy(f))
            for link in current['links']:
                if any(i in allowed for i in link):
                    if not all(i in allowed for i in link):raise ValueError('合併後跨客戶人物／公司連結，請先核對')
                    graph['links'].append(deepcopy(link))
            InputGraph.validate(graph);graphs.append(graph)
        old_associations={r['id'] for s in original['before'] for r in s['associations']}
        if {r['id'] for r in now['associations']}!=old_associations:raise ValueError('合併後來源關聯有增刪，請先逐項重新指派')
        old_styles={s['id'] for state in original['before'] for s in state['customer']['styles']}
        if {s['id'] for s in now['customer']['styles']}!=old_styles:raise ValueError('合併後版型關聯有增刪，請先逐項重新指派')
        plan=dict(operation='SPLIT',event_id=event_id,primary_id=a,secondary_id=b,now=now,graphs=graphs,
                  original=original,asset_pins=self._validate_assets([now]),new_values_retained=True,conflict_policy='BLOCK_AMBIGUOUS_OWNERSHIP')
        plan['sha256']=digest(plan);return plan

    def split(self,plan,approved=False,actor='',reason=''):
        if not approved or not actor.strip() or not reason.strip():raise ValueError('拆分需要明確核准、核准者及理由')
        self._check_plan(plan);self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.plan_split(plan['event_id'])!=plan:raise ValueError('拆分預覽後版本已改變，未覆寫新值')
            a,b=plan['primary_id'],plan['secondary_id'];x,y=[s['customer'] for s in plan['original']['before']]
            self._write_graphs([(a,plan['graphs'][0]),(b,plan['graphs'][1])])
            self.db.execute('UPDATE customers SET code=? WHERE id=?',('TEMP-'+new_id(),a))
            self.db.execute('UPDATE customers SET code=? WHERE id=?',(y['code'],b))
            self.db.execute('UPDATE customers SET code=? WHERE id=?',(x['code'],a))
            self.db.execute('DELETE FROM customer_identity_redirects WHERE secondary_id=? AND merge_id=?',(b,plan['event_id']))
            self.db.execute('DELETE FROM customer_code_aliases WHERE merge_id=?',(plan['event_id'],))
            for association in plan['original']['before'][1]['associations']:
                self.db.execute('UPDATE customer_source_associations SET customer_id=? WHERE id=?',(b,association['id']))
            self.db.execute('UPDATE customers SET revision=revision+1 WHERE id IN (?,?)',(a,b))
            self.db.execute("UPDATE customer_identity_events SET state='SPLIT' WHERE id=?",(plan['event_id'],))
            split_record=dict(actor=actor[:200],reason=reason[:2048],current_plan=plan,created=time.time())
            self.db.execute('INSERT INTO customer_identity_events VALUES(?,?,?,?,?)',(new_id(),a,b,'SPLIT',json.dumps(split_record,ensure_ascii=False)))
            if self._validate_assets([plan['now']])!=plan['asset_pins']:raise ValueError('執行期間來源變更，全部回退')
            if self.db.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('拆分關聯驗證失敗，全部回退')
            self.library.event(plan['event_id'],'customer_identity_split');self.db.commit()
            return dict(state='SPLIT',customers=[self.store.get(a),self.store.get(b)])
        except BaseException:self.db.rollback();raise
