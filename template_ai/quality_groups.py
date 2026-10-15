"""Conservative independence groups in the existing versioned SQLite store.

Relations constrain dataset roles; they never merge source/customer identities.
Revoking a relation does not erase historical leakage or make old holdouts new.
"""
import copy
import time
import networkx as nx
from .training_store import TrainingStore,digest,text,identity

LINK='QUALITY_GROUP_LINK'
MAX_ROWS=10000


class QualityGroups:
    def __init__(self,library):
        self.library=library;self.db=library.db;self.store=TrainingStore.bind(library)

    def rows(self,sql,args=()):
        rows=[];size=0
        for row in self.db.execute(sql+' LIMIT ?',(*args,MAX_ROWS+1)):
            size+=sum(len(value.encode()) if isinstance(value,str) else 16 for value in row)
            if len(rows)>=MAX_ROWS or size>8*1024*1024:raise ValueError('獨立性metadata超過10000筆／8MiB有界範圍，需明確分組核對；未截斷宣稱獨立')
            rows.append(row)
        return rows

    def has_table(self,name):return bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())

    def graph_state(self):
        graph=nx.Graph();edges=[]
        def add(a,b,basis):
            graph.add_edge(a,b);edges.append([*sorted([a,b]),basis])
        sources=self.rows('SELECT id,hash FROM sources ORDER BY id')
        for sid,sha in sources:add('SOURCE:'+sid,'CONTENT:'+sha,'EXACT_SOURCE_CONTENT')
        for wid,sid in self.rows('SELECT id,source_id FROM artworks ORDER BY id'):add('WORK:'+wid,'SOURCE:'+sid,'WHOLE_SOURCE_ALL_WORKS')
        for tid,family,wid,version in self.rows("SELECT id,family_id,json_extract(payload,'$.source_work_id'),version FROM templates ORDER BY id"):
            if wid:add('WORK:'+wid,'TEMPLATE_FAMILY:'+family,'TEMPLATE_VERSION:'+tid+':'+str(version))
        if self.has_table('customer_source_associations'):
            for aid,cid,wid,tid in self.rows('SELECT id,customer_id,artwork_id,template_id FROM customer_source_associations ORDER BY id'):
                add('WORK:'+wid,'CUSTOMER:'+cid,'CONFIRMED_ASSOCIATION:'+aid)
                row=self.db.execute('SELECT family_id FROM templates WHERE id=?',(tid,)).fetchone()
                if row:add('WORK:'+wid,'TEMPLATE_FAMILY:'+row[0],'ASSOCIATED_TEMPLATE:'+tid)
        if self.has_table('customer_identity_redirects'):
            for secondary,primary,merge_id in self.rows('SELECT secondary_id,primary_id,merge_id FROM customer_identity_redirects ORDER BY secondary_id'):add('CUSTOMER:'+secondary,'CUSTOMER:'+primary,'CONFIRMED_IDENTITY_REDIRECT:'+merge_id)
        # Historical links remain conservative constraints even after explicit revocation.
        for lid,revision,raw in self.rows("SELECT id,revision,payload FROM training_records WHERE kind='QUALITY_GROUP_LINK' ORDER BY id"):
            import json
            row=json.loads(raw)
            if row['state'] in ('ACTIVE','REVOKED_RETAIN_HISTORICAL_LEAKAGE'):add(row['left'],row['right'],'DECLARED:'+lid+':'+str(revision)+':'+row['state'])
        roles=[list(row) for row in self.rows("SELECT id,revision,json_extract(payload,'$.role') FROM training_records WHERE kind='GROUP_ROLE' ORDER BY id")]
        if graph.number_of_nodes()>50000 or len(edges)>50000:raise ValueError('獨立性圖超過資源預算；保持未知，未當獨立PASS')
        payload=dict(schema_version=1,edges=sorted(edges),locked_content_roles=roles,unknown_near_duplicate_relations_are_not_assumed_independent=True)
        return graph,payload,digest(payload)

    def validate_key(self,key):
        if not isinstance(key,str) or ':' not in key:raise ValueError('群組關聯需明列實際來源／作品／內容／客戶／版型家族ID')
        kind,value=key.split(':',1);identity(value)
        lookups={'SOURCE':('sources','id'),'WORK':('artworks','id'),'CONTENT':('contents','hash'),'CUSTOMER':('customers','id'),'TEMPLATE_FAMILY':('templates','family_id')}
        if kind not in lookups:raise ValueError('群組關聯類型不支援')
        table,column=lookups[kind]
        if not self.has_table(table) or not self.db.execute(f'SELECT 1 FROM {table} WHERE {column}=?',(value,)).fetchone():raise ValueError('群組關聯對象不存在')
        return key

    def role_conflicts(self,assignments,*,graph=None):
        """Known correlated content must not span TRAIN/VALIDATION/HOLDOUT."""
        if not isinstance(assignments,list) or len(assignments)>MAX_ROWS:raise ValueError('角色核對需有界明列內容清單')
        if graph is None:graph,_,_=self.graph_state()
        roles={};focus={'CONTENT:'+sha for sha,role in assignments}
        for sha,role in assignments:
            if role not in ('TRAIN','VALIDATION','HOLDOUT','UNASSIGNED'):raise ValueError('資料集角色不合法')
            if role!='UNASSIGNED':roles.setdefault('CONTENT:'+sha,set()).add(role)
        for sha,role in self.db.execute("SELECT id,json_extract(payload,'$.role') FROM training_records WHERE kind='GROUP_ROLE'"):
            if role!='UNASSIGNED':roles.setdefault('CONTENT:'+sha,set()).add(role)
        for node in roles:graph.add_node(node)
        conflicts=[]
        for component in nx.connected_components(graph):
            if focus and not focus.intersection(component):continue
            combined=set().union(*(roles.get(node,set()) for node in component))
            if len(combined)>1:conflicts.append(dict(group_digest=digest(sorted(component)),content_hashes=sorted(node.split(':',1)[1] for node in component if node.startswith('CONTENT:')),roles=sorted(combined),reason='同來源／相同內容／客戶或版型家族／已核對近重複跨不同集合角色'))
        return sorted(conflicts,key=lambda row:row['group_digest'])

    def link_plan(self,left,right,relation,reason,evidence):
        self.validate_key(left);self.validate_key(right)
        if left==right or relation not in ('NEAR_DUPLICATE','SAME_DESIGN_FAMILY','RELATED_CUSTOMER_DESIGN','MANUALLY_VERIFIED_RELATION'):raise ValueError('需不同對象及明確關聯種類')
        text(reason,'關聯理由',2000);text(evidence,'來源關聯證據',2000)
        graph,state,sha=self.graph_state();graph.add_edge(left,right);conflicts=self.role_conflicts([],graph=graph);lid=digest(sorted([left,right])+[relation]);prior=self.store.get(LINK,lid)
        plan=dict(left=left,right=right,relation=relation,reason=reason,evidence=evidence,graph_digest=sha,link_id=lid,prior_revision=prior['revision'] if prior else 0,conflicts=conflicts,impact=dict(does_not_merge_sources_customers_or_gold=True,holdouts_in_conflicting_groups_need_new_independent_data=bool(conflicts)))
        plan['digest']=digest(plan);return plan

    def confirm_link(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需核對群組影響並明確確認關聯')
        text(actor,'核對者',120);preview=copy.deepcopy(plan);expected=preview.pop('digest',None)
        if expected!=digest(preview):raise ValueError('關聯預覽已被修改')
        with self.store.transaction():
            current=self.link_plan(plan['left'],plan['right'],plan['relation'],plan['reason'],plan['evidence'])
            if current!=plan:raise ValueError('來源／家族／既有角色已變更，需重新預覽')
            record={key:copy.deepcopy(plan[key]) for key in ('left','right','relation','reason','evidence','impact')};record.update(state='ACTIVE',actor=actor,at=time.time())
            saved=self.store._write(LINK,plan['link_id'],record,plan['prior_revision'],'quality_group_relation_confirmed_not_identity_merge')
            # Newly discovered truth is saved even when it reveals an old split was invalid.
            affected={sha for conflict in plan['conflicts'] for sha in conflict['content_hashes']}
            for did,raw in self.rows("SELECT id,payload FROM training_records WHERE kind='DATASET' ORDER BY id"):
                import json
                dataset=json.loads(raw)
                if any(entry['role']=='HOLDOUT' and entry['source_hash'] in affected for entry in dataset['entries']):
                    prior=self.store.get('HOLDOUT_EXPOSED',did);exposed=copy.deepcopy(prior or {});exposed.update(dataset_id=did,reason='新核實關聯揭露跨角色洩漏，舊測試集不可恢復獨立資格',group_link_id=saved['id'],state='INVALID_INDEPENDENCE_REQUIRES_NEW_DATA',actor=actor,at=time.time())
                    self.store._write('HOLDOUT_EXPOSED',did,exposed,prior['revision'] if prior else 0,'quality_holdout_invalidated_by_group_leakage')
            return saved

    def revoke_link(self,link_id,expected_revision,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確撤回關聯；歷史洩漏不會消失')
        text(actor,'撤回者',120);text(reason,'撤回理由',2000)
        with self.store.transaction():
            row=self.store.get(LINK,link_id)
            if not row or row['revision']!=expected_revision or row['state']!='ACTIVE':raise ValueError('關聯版本已變更')
            row.update(state='REVOKED_RETAIN_HISTORICAL_LEAKAGE',revoke_actor=actor,revoke_reason=reason,revoked_at=time.time())
            return self.store._write(LINK,link_id,row,expected_revision,'quality_group_revoked_history_not_new_holdout')
