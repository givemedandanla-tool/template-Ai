"""Source-linked correction candidates, not a second training store."""
import copy
import json
import time
from .training_store import TrainingStore,digest,text
from .quality_groups import QualityGroups

CANDIDATE='SAMPLE_CANDIDATE'
PURPOSES=('GEOMETRY_TRAINING_LOCAL','SEMANTIC_CLASSIFICATION_LOCAL','INDEPENDENT_QUALITY_EVALUATION_LOCAL','QUALITY_DIAGNOSTICS_LOCAL_ONLY','RULE_APPROVAL_LOCAL')


def source_restriction(store,source_hash,purpose):
    row=store.get('SOURCE_USE_RESTRICTION',digest([source_hash,purpose]))
    return row if row and row.get('state')=='STOPPED' else None


def holdout_admission_errors(library,source_hash,graph=None):
    groups=QualityGroups(library)
    if graph is None:graph,_,_=groups.graph_state()
    training=groups.role_conflicts([(source_hash,'TRAIN')],graph=graph)
    validation=groups.role_conflicts([(source_hash,'VALIDATION')],graph=graph)
    return ['來源或相關家族屬於保留測試／歷史角色衝突，不能准入訓練池'] if training and validation else []


class TrustedSamplePool:
    def __init__(self,library):
        self.library=library;self.store=TrainingStore.bind(library);self.db=library.db

    def collect_in_transaction(self,work_id,before,after):
        """Called inside the existing FACTS transaction; references, never extra PII copies."""
        if before.get('observations')==after.get('observations') and before.get('pins')==after.get('pins'):return None
        identity=digest([CANDIDATE,work_id,after['revision'],after['pins']])
        if self.store.get(CANDIDATE,identity):return self.store.get(CANDIDATE,identity)
        record=dict(has_user_reported_negative_diagnostic=any(o.get('prior_prediction') is not None for o in after['observations']),work_id=work_id,pins=after['pins'],facts_revision=after['revision'],facts_digest=digest(after['observations']),previous_facts_revision=before.get('revision',0),previous_facts_digest=digest(before.get('observations',[])),state='COLLECTED',correction_kind='CONFIRMED_HUMAN_CORRECTION' if before.get('confirmation') else 'INITIAL_OR_UNCONFIRMED_LABEL_EDIT',prediction_evidence='NONE_UNLESS_EXACT_EXISTING_SOURCE_RECEIPT',source_truth='PENDING_EXPLICIT_CURRENT_CONFIRMATION',created=time.time(),training_admission=False,rule_approval=False,model_training_started=False)
        return self.store._write(CANDIDATE,identity,record,0,'correction_candidate_collected')

    def exact_scope(self,work_id):
        work=self.library.artwork(work_id);source=self.library.source(work['source_id']);payload=work['payload']
        return digest([source['hash'],source['byte_size'],source.get('page',1),payload['crop'],payload['work_width'],payload['work_height']])

    def labels(self,work_id):
        work=self.library.artwork(work_id);facts=self.store.facts(work_id)
        return digest(dict(slots=sorted([{k:v for k,v in s.items() if k!='id'} for s in work['payload']['slots']],key=lambda s:json.dumps(s,sort_keys=True)),observations=sorted([{k:o.get(k) for k in ('text','classification','object_type','region','slot_kind','owner')} for o in facts['observations']],key=lambda o:json.dumps(o,sort_keys=True))))

    def conflicts(self,work_id):
        work=self.library.artwork(work_id);source=self.library.source(work['source_id']);scope=self.exact_scope(work_id);labels=self.labels(work_id);conflicts=[]
        rows=list(self.db.execute('SELECT a.id FROM artworks a JOIN sources s ON s.id=a.source_id WHERE s.hash=? ORDER BY a.id LIMIT 201',(source['hash'],)))
        if len(rows)>200:return dict(conflicting_work_ids=[],complete=False,reason='超過200同內容作品，縮小範圍或明確逐批核實')
        for row in rows:
            other=row[0]
            if other==work_id:continue
            if self.store.facts_state(other)=='CONFIRMED' and self.exact_scope(other)==scope and self.labels(other)!=labels:conflicts.append(other)
        return dict(conflicting_work_ids=conflicts,complete=True,reason='同位元及尺寸／區域的現行人工真值互相矛盾；不採最新者勝出' if conflicts else None)

    def detail(self,identity):
        row=self.store.get(CANDIDATE,identity)
        if not row:raise ValueError('修正候選不存在')
        work=self.library.artwork(row['work_id']);source=self.library.source(work['source_id']);facts=self.store.facts(row['work_id']);errors=[]
        if row['pins']!=self.store.pins(row['work_id']) or row['facts_digest']!=digest(facts['observations']):errors.append('來源／作品／標記已變更，原候選僅保留歷史')
        if self.store.facts_state(row['work_id'])!='CONFIRMED':errors.append('尚未真正人工核對目前來源')
        conflict=self.conflicts(row['work_id']);role_errors=holdout_admission_errors(self.library,source['hash'])
        if not conflict['complete'] or conflict['conflicting_work_ids']:errors.append('人工標記衝突或核對範圍不完整')
        if role_errors:errors.extend(role_errors)
        if source_restriction(self.store,source['hash'],'GEOMETRY_TRAINING_LOCAL'):errors.append('此來源用途已停止使用')
        people={s.get('owner') for s in work['payload']['slots'] if str(s.get('owner','')).startswith('p')};high=bool(len(people)>1 or any(s.get('kind')=='logo' for s in work['payload']['slots']) or conflict['conflicting_work_ids'])
        restrictions={purpose:value for purpose in PURPOSES if (value:=source_restriction(self.store,source['hash'],purpose)) is not None}
        role=self.store.get('GROUP_ROLE',source['hash']);sample=self.store.get('SAMPLE',row.get('sample_id','')) if row.get('sample_id') else None
        return dict(source_restrictions=restrictions,candidate=row,work_label=work['name'],source_label=source.get('filename') or source.get('original_name') or source.get('current_path'),current_facts_revision=facts['revision'],current_confirmation=facts.get('confirmation'),conflict=conflict,role=role,errors=sorted(set(errors)),risk='HIGH' if high else 'LOW',sample_state=self.store.sample_state(sample['id']) if sample else None,usage=self.store.sample_usage_impact(sample['id']) if sample else None,customer_identities_merged=False,prior_prediction_is_truth=False)

    def batch_plan(self,items,rights):
        if not isinstance(items,list) or not 1<=len(items)<=50 or len({i['id'] for i in items})!=len(items):raise ValueError('每批需1～50個不重複候選')
        planned=[];size=0;seen=set()
        for item in items:
            if set(item)-{'id','action','bindings','high_risk_reviewed'} or item.get('action') not in ('APPROVE','REJECT','DEFER'):raise ValueError('逐項明列准入／拒絕／待審及必要核實')
            detail=self.detail(item['id']);row=detail['candidate'];errors=[];admission=None
            if row['state'] in ('ADMITTED','REJECTED'):errors.append('此候選已有結論；更正須建立新的標記版本')
            if item['action']=='APPROVE':
                errors+=detail['errors'];admission=self.store.sample_approval_plan(row['work_id'],rights,item.get('bindings',{}));errors+=admission['errors']
                if detail['risk']=='HIGH' and item.get('high_risk_reviewed') is not True:errors.append('高風險歸屬／Logo需逐項明確審核')
                source=self.library.source(row['pins']['source_id'])
                if source['hash'] not in seen:size+=source['byte_size'];seen.add(source['hash'])
            planned.append(dict(item=copy.deepcopy(item),candidate_revision=row['revision'],detail=detail,admission=admission,errors=sorted(set(errors))))
        if size>100_000_000:raise ValueError('本批原稿核驗超過100MB，縮小範圍')
        plan=dict(items=planned,rights=copy.deepcopy(rights),source_bytes=size,epoch=self.store.epoch,training_started=False,global_rule_created=False);plan['digest']=digest(plan);return plan

    def confirm_batch(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需明確批准逐項結果與用途；不會啟動訓練')
        text(actor,'審核人',120)
        items=[x['item'] for x in plan['items']]
        proofs={x['item']['id']:self.store.source_proof(x['detail']['candidate']['work_id']) for x in plan['items'] if x['item']['action']=='APPROVE'}
        with self.store.transaction():
            current=self.batch_plan(items,plan['rights'])
            if current['digest']!=plan.get('digest') or any(x['errors'] for x in current['items']):raise ValueError('候選／來源／權利／角色範圍變更或有未解阻擋')
            saved=[]
            for step in current['items']:
                item=step['item'];row=step['detail']['candidate']
                if item['action']=='APPROVE':
                    fresh=self.store.sample_approval_plan(row['work_id'],current['rights'],item.get('bindings',{}))
                    if fresh['scope_digest']!=step['admission']['scope_digest']:raise ValueError('准入依賴範圍已改變')
                    sample=self.store.approve_sample_in_transaction(fresh,proofs[item['id']],actor,True);row['sample_id']=sample['id']
                row.update(state={'APPROVE':'ADMITTED','REJECT':'REJECTED','DEFER':'DEFERRED'}[item['action']],actor=actor,reviewed_at=time.time(),training_admission=item['action']=='APPROVE',high_risk_reviewed=item.get('high_risk_reviewed',False))
                saved.append(self.store._write(CANDIDATE,row['id'],row,row['revision'],'correction_candidate_'+item['action'].lower()))
            return saved

    def restriction_plan(self,work_id,purposes,action,retention_days):
        if not isinstance(purposes,list) or not purposes or len(purposes)!=len(set(purposes)) or not set(purposes)<=set(PURPOSES):raise ValueError('明列停止使用用途')
        if action not in ('STOP_USE','REQUEST_LOCAL_ERASURE') or type(retention_days) is not int or not 0<=retention_days<=365:raise ValueError('需明列處理動作與最長365日的必要審核期限')
        from .quality_rechecks import QualityRechecks
        pins=self.store.pins(work_id);impact=QualityRechecks(self.library).source_dependencies(work_id,include_quality_evidence=True)
        plan=dict(work_id=work_id,pins=pins,purposes=sorted(purposes),action=action,retention_days=retention_days,impact=impact,epoch=self.store.epoch,erasure_completed=False,external_backups_erased=False,model_decontaminated=False);plan['digest']=digest(plan);return plan

    def stop_use(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需明確確認停止用途及原資料／備份的處理界線')
        text(actor,'核實人',120)
        with self.store.transaction():
            current=self.restriction_plan(plan['work_id'],plan['purposes'],plan['action'],plan['retention_days'])
            if current['digest']!=plan.get('digest'):raise ValueError('來源或影響範圍已變更')
            saved=[]
            for purpose in current['purposes']:
                key=digest([current['pins']['source_hash'],purpose]);prior=self.store.get('SOURCE_USE_RESTRICTION',key)
                row=dict(state='STOPPED',source_hash=current['pins']['source_hash'],purpose=purpose,actor=actor,action=current['action'],requested_at=time.time(),review_due_at=time.time()+current['retention_days']*86400,local_erasure_state='REQUIRES_SCOPED_REDACTION_REVIEW' if current['action']=='REQUEST_LOCAL_ERASURE' else 'NOT_REQUESTED',erasure_completed=False,external_backups_erased=False,model_decontaminated=False)
                saved.append(self.store._write('SOURCE_USE_RESTRICTION',key,row,prior['revision'] if prior else 0,'source_purpose_stopped'))
            return saved

    def redaction_plan(self,work_id,records):
        """Logical minimization of explicitly selected local training copies, not originals."""
        if not isinstance(records,list) or not 1<=len(records)<=50 or len({(r['kind'],r['id']) for r in records})!=len(records):raise ValueError('明列1～50筆本機訓練副本')
        pins=self.store.pins(work_id);sha=pins['source_hash'];items=[]
        for selected in records:
            kind=selected['kind']
            if set(selected)!={'kind','id'} or kind not in ('SAMPLE','SEMANTIC_MODEL'):raise ValueError('只處理明列樣本／語意模型訓練副本')
            row=self.store.get(kind,selected['id'])
            if not row:raise ValueError('訓練副本不存在')
            if kind=='SAMPLE':
                allowed=row['pins']['source_hash']==sha;purpose='GEOMETRY_TRAINING_LOCAL'
            else:
                allowed=any(s['pins']['source_hash']==sha for s in row['plan']['scopes']);purpose='SEMANTIC_CLASSIFICATION_LOCAL'
            restriction=source_restriction(self.store,sha,purpose)
            if not allowed or not restriction:raise ValueError('先明確停止該來源用途，且副本必須實際包含此來源')
            history=[dict(revision=h['revision'],before_sha256=digest(h['before']),after_sha256=digest(h['after'])) for h in self.store.history(kind,row['id'])]
            count=self.db.execute('SELECT count(*) FROM training_history WHERE kind=? AND id=?',(kind,row['id'])).fetchone()[0]
            if count>200:raise ValueError('歷史超過單批可完整核實範圍，不能宣稱已全部刪除')
            items.append(dict(kind=kind,id=row['id'],revision=row['revision'],payload_sha256=digest(row),history=history,restriction_id=restriction['id'],restriction_revision=restriction['revision']))
        plan=dict(work_id=work_id,pins=pins,items=items,scope='EXPLICIT_SELECTED_LOCAL_TRAINING_TEXT_COPIES_ONLY',source_files_deleted=False,business_facts_deleted=False,external_backups_deleted=False,filesystem_secure_erasure=False,model_decontaminated=False);plan['digest']=digest(plan);return plan

    def redact_training_copies(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需逐筆明確批准本機訓練副本邏輯刪除；原稿／FACTS／外部備份另行處理')
        text(actor,'資料處理人',120)
        with self.store.transaction():
            current=self.redaction_plan(plan['work_id'],[dict(kind=i['kind'],id=i['id']) for i in plan['items']])
            if current['digest']!=plan.get('digest'):raise ValueError('訓練副本或停止用途憑證已變更')
            sha=current['pins']['source_hash'];receipt_id=digest([current['digest'],actor]);saved=[]
            def cleaned(kind,payload):
                if payload is None:return None
                payload=copy.deepcopy(payload)
                if kind=='SAMPLE':
                    for label in payload.get('positive_labels',[]):
                        if label.get('text') and not label.get('text_redacted'):
                            label['text_sha256']=digest(label['text']);label['text']='';label['text_redacted']=True
                    for label in payload.get('negative_predictions',[]):
                        for key in ('prior_prediction','correct_text'):
                            if label.get(key):label[key+'_sha256']=digest(label[key]);label[key]=''
                else:
                    scopes=payload.get('plan',{}).get('scopes',[]);works={s['work_id'] for s in scopes if s['pins']['source_hash']==sha}
                    for example in payload.get('plan',{}).get('examples',[]):
                        if example.get('work_id') in works and example.get('text'):
                            example['text_sha256']=digest(example['text']);example['text']='';example['text_redacted']=True
                payload['local_training_text_redacted']=True;payload['privacy_receipt_id']=receipt_id
                return payload
            for item in current['items']:
                kind=item['kind'];row=self.store.get(kind,item['id']);redacted=cleaned(kind,row);redacted['state']='REVOKED' if kind=='SAMPLE' else 'PRIVACY_WITHDRAWN'
                saved.append(self.store._write(kind,row['id'],redacted,row['revision'],'local_training_copy_logically_redacted'))
                histories=list(self.db.execute('SELECT revision,before_json,after_json FROM training_history WHERE kind=? AND id=?',(kind,row['id'])))
                for revision,before,after in histories:
                    before=cleaned(kind,json.loads(before)) if before else None;after=cleaned(kind,json.loads(after))
                    self.db.execute('UPDATE training_history SET before_json=?,after_json=? WHERE kind=? AND id=? AND revision=?',(json.dumps(before,ensure_ascii=False) if before else None,json.dumps(after,ensure_ascii=False),kind,row['id'],revision))
            receipt=dict(plan=current,actor=actor,at=time.time(),scope=current['scope'],original_payload_hashes_retained=True,logical_local_training_copy_redaction=True,source_files_deleted=False,business_facts_deleted=False,external_backups_deleted=False,filesystem_secure_erasure=False,model_decontaminated=False)
            self.store._write('TRAINING_PRIVACY_REDACTION',receipt_id,receipt,0,'training_copy_minimization_receipt')
            return dict(receipt=self.store.get('TRAINING_PRIVACY_REDACTION',receipt_id),records=saved)

    def directory(self,collection='PENDING',offset=0,query=''):
        filters=('PENDING','ADMITTED','CONFLICTS','DATASETS','POLLUTED','LINEAGE')
        if collection not in filters or type(offset) is not int or offset<0 or not isinstance(query,str) or len(query)>500:raise ValueError('樣本目錄需有效篩選及50筆分頁')
        where="t.kind=?";args=[CANDIDATE]
        for token in query.casefold().split():
            where+=" AND instr(training_casefold(t.id||' '||a.name||' '||s.original_path),?)>0";args.append(token)
        base=" FROM training_records t JOIN artworks a ON a.id=json_extract(t.payload,'$.work_id') JOIN sources s ON s.id=a.source_id WHERE "+where
        total=self.db.execute('SELECT count(*)'+base,args).fetchone()[0]
        candidates=list(self.db.execute('SELECT t.id'+base+' ORDER BY t.rowid DESC LIMIT 50 OFFSET ?',(*args,offset)));rows=[]
        for (identity,) in candidates:
            detail=self.detail(identity);candidate=detail['candidate'];sample=candidate.get('sample_id');usage=detail['usage'] or {};state=candidate['state']
            semantic=[r[0] for r in self.db.execute("SELECT DISTINCT m.id FROM training_records m,json_each(m.payload,'$.plan.scopes') s WHERE m.kind='SEMANTIC_MODEL' AND json_extract(s.value,'$.work_id')=? ORDER BY m.id LIMIT 51",(candidate['work_id'],))]
            match=dict(PENDING=state in ('COLLECTED','DEFERRED'),ADMITTED=state=='ADMITTED',CONFLICTS=bool(detail['conflict']['conflicting_work_ids'] or candidate.get('has_user_reported_negative_diagnostic')),DATASETS=bool(usage.get('dataset_ids')),POLLUTED=bool(detail['source_restrictions'] or detail['errors']) or detail['sample_state'] not in (None,'APPROVED'),LINEAGE=bool(usage.get('dataset_ids') or usage.get('template_ids') or semantic))[collection]
            if match:rows.append(dict(id=identity,revision=candidate['revision'],work_id=candidate['work_id'],label=detail['work_label'],source_label=detail['source_label'],state=state,current_sample_state=detail['sample_state'],risk=detail['risk'],errors=detail['errors'],sample_id=sample,semantic_model_ids=semantic[:50],semantic_lineage_complete=len(semantic)<=50))
        return dict(rows=rows,total_candidates=total,scanned=len(candidates),offset=offset,next_offset=offset+len(candidates),complete_scan=offset+len(candidates)>=total,scope='MATCHES_IN_THIS_SCANNED_CANDIDATE_PAGE; NOT_GLOBAL_MATCH_COUNT',collection=collection,images_loaded=False,model_weights_loaded=False,training_started=False)

    def comparison(self,identity):
        detail=self.detail(identity);row=detail['candidate'];history={h['revision']:dict(h['after'],revision=h['revision']) for h in self.store.history('FACTS',row['work_id'])};previous=history.get(row['previous_facts_revision']);selected=history.get(row['facts_revision'])
        return dict(detail=detail,previous_human_label_version=previous,current_candidate_label_version=selected,current_confirmed_facts=self.store.facts(row['work_id']),prior_AI_prediction='UNKNOWN_UNLESS_LINKED_ACTUAL_PREDICTION_RECEIPT',user_supplied_prior_predictions=[dict(observation_id=o['id'],prediction=o['prior_prediction'],evidence='USER_REPORTED_DIAGNOSTIC_ONLY_NOT_TRAINING_TRUTH') for o in (selected or {}).get('observations',[]) if o.get('prior_prediction') is not None],history_complete=selected is not None and (row['previous_facts_revision']==0 or previous is not None),model_prediction_is_gold=False)
