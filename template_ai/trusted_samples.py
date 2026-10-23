"""Explicit local geometry sample admission, provenance, quarantine and revocation."""
import copy
import time
from .model import Rect,Slot,learn_from_labels,new_id
from .training_quality import analyse_work
from .batch_import import healthy_source
from pathlib import Path
from .source_links import fingerprint
from .metadata_record import training_record


def cache_stamps(source):
    paths=[source['image'],str(Path(source['image']).parent/'metadata.json')]
    if source.get('svg'):paths.append(source['svg'])
    return {p:list(fingerprint(Path(p).stat())) for p in sorted(set(paths))}


class TrustedSampleMixin:
    def noise_signature(self,work_id):
        from .training_store import digest
        return digest([{k:r[k] for k in ('observation_id','state','protected','observation_digest','rule_matches','local_revision','invalid_rule_ids')} for r in self.noise_decisions(work_id)])

    def sample_approval_plan(self,work_id,rights,bindings=None):
        from .training_store import digest,text
        work=self.library.artwork(work_id);source=self.library.source(work['source_id']);facts=self.facts(work_id);errors=[];bindings=copy.deepcopy(bindings or {});rights=copy.deepcopy(rights);quality=analyse_work(work,source)
        from .quality_rechecks import blocked
        if blocked(self,work_id):errors.append('重大品質跨批次重審尚未完成，不能重新准入繞過隔離')
        if not isinstance(rights,dict) or set(rights)!={'basis','reference','use'} or rights.get('basis') not in ('OWNED','AUTHORIZED','OPEN_LICENSE') or rights.get('use')!='GEOMETRY_TRAINING_LOCAL':errors.append('權利及用途必須明確，沒有神經模型／外傳授权')
        else:
            try:text(rights['reference'],'權利參考')
            except ValueError as error:errors.append(str(error))
        if type(bindings) is not dict or any(not isinstance(k,str) or not isinstance(v,str) for k,v in bindings.items()):errors.append('公司歸屬映射不合法')
        if work['payload'].get('visual_confirmed') is not True:errors.append('需人工對照目前來源與作品，不能把匯入SUCCESS當視覺確認')
        if self.facts_state(work_id)!='CONFIRMED':errors.append('目前來源／作品事實尚未確認或已過期')
        confirmation=facts.get('confirmation') or {};confirmed=set(confirmation.get('observation_ids',[]));by_slot={o['slot_id']:o for o in facts['observations'] if o['slot_id']}
        positive=[];negative=[]
        for slot in work['payload']['slots']:
            observation=by_slot.get(slot.get('id'));expected='LOGO' if slot.get('kind')=='logo' else 'FIELD'
            if not observation or observation['id'] not in confirmed or observation['classification']!=expected:errors.append('必要語意／框連結缺乏當前人工正例：'+str(slot.get('id')))
            else:
                positive.append({'slot_id':slot['id'],'kind':slot['kind'],'owner':slot['owner'],'index':slot['index'],'text':observation['text'],'observation_id':observation['id'],'evidence':'USER_CONFIRMED_CURRENT_SOURCE'})
                if observation.get('prior_prediction') is not None:negative.append({'slot_id':slot['id'],'prior_prediction':observation['prior_prediction'],'correct_text':observation['text'],'evidence':'USER_SUPPLIED_PRIOR_PREDICTION_NOT_GROUND_TRUTH'})
        errors.extend(r['reason'] for r in quality if r['severity']=='BLOCK')
        try:
            payload=work['payload'];slots=[Slot(**{**s,'rect':Rect(**s['rect'])}) for s in payload['slots']];learn_from_labels('sample preflight',payload['work_width'],payload['work_height'],slots,work['source_id'],Rect(**payload['crop']),bindings,work_id,work['revision'])
        except (ValueError,TypeError,KeyError) as error:errors.append('幾何／語意硬條件：'+str(error))
        from .trusted_sample_pool import source_restriction,holdout_admission_errors
        if source_restriction(self,source['hash'],'GEOMETRY_TRAINING_LOCAL'):errors.append('來源幾何訓練用途已停止使用')
        errors.extend(holdout_admission_errors(self.library,source['hash']))
        from .trusted_sample_pool import TrustedSamplePool
        conflicts=TrustedSamplePool(self.library).conflicts(work_id)
        if not conflicts['complete'] or conflicts['conflicting_work_ids']:errors.append('同內容現行人工標記衝突或核實範圍不完整，不能准入')
        decisions=self.noise_decisions(work_id)
        if any(r['state'].startswith(('REVIEW','STALE')) for r in decisions):errors.append('雜訊／來源／規則疑義需先解決')
        deps={r['id']:r['revision'] for row in decisions for r in row['rule_matches']}
        plan={'epoch':self.epoch,'work_id':work_id,'pins':self.pins(work_id),'facts_revision':facts['revision'],'observations_digest':digest(facts['observations']),'noise_signature':self.noise_signature(work_id),'rights':rights,'bindings':bindings,'positive_labels':sorted(positive,key=lambda r:r['slot_id']),'negative_predictions':negative,'label_slots':copy.deepcopy(work['payload']['slots']),'crop':copy.deepcopy(work['payload']['crop']),'width_mm':work['payload']['work_width'],'height_mm':work['payload']['work_height'],'rule_dependencies':[{'id':rid,'revision':deps[rid]} for rid in sorted(deps)],'errors':sorted(set(errors)),'native_mapping':'UNKNOWN','training_scope':'GEOMETRY_ONLY; NO_NEURAL_OR_INDEPENDENT_VISUAL_CLAIM'}
        plan['source_byte_size']=source['byte_size']
        plan['scope_digest']=digest({k:v for k,v in plan.items() if k not in ('epoch','errors')});plan['digest']=digest(plan);return plan

    def approve_sample(self,plan,proof,actor,approved=False):
        with self.transaction():
            return self.approve_sample_in_transaction(plan,proof,actor,approved)

    def approve_sample_in_transaction(self,plan,proof,actor,approved=False):
        from .training_store import text
        if approved is not True:raise ValueError('明確批准准入，並非啟動訓練')
        text(actor,'准入確認者',120)
        if not self.db.in_transaction:raise ValueError('樣本准入需在既有明確交易內')
        current=self.sample_approval_plan(plan['work_id'],plan['rights'],plan['bindings'])
        if current['digest']!=plan.get('digest') or current['errors']:raise ValueError('准入範圍已變更或條件未滿足：'+'；'.join(current['errors']))
        self.checked(current['work_id'],proof)
        if not healthy_source(self.library.source(current['pins']['source_id'])):raise ValueError('來源快取／分析資產不健康，未准入')
        duplicates=list(self.db.execute("SELECT id FROM training_records WHERE kind='SAMPLE' AND json_extract(payload,'$.admission_digest')=? AND json_extract(payload,'$.state')='APPROVED'",(current['scope_digest'],)))
        if duplicates:raise ValueError('同一准入範圍已存在，不重複批准')
        record={k:v for k,v in current.items() if k not in ('errors','epoch','digest')};record.update(state='APPROVED',admission_digest=current['scope_digest'],actor=actor,admitted=time.time(),source_stat=list(proof.stat),cache_stamps=cache_stamps(self.library.source(current['pins']['source_id'])),invalidations=[],used_for_training=False)
        return self._write('SAMPLE',new_id(),record,0,'sample_admitted')

    def sample_state(self,sample_id):
        from .quality_rechecks import blocked
        record=self.get('SAMPLE',sample_id)
        if record and blocked(self,record['work_id']):return 'QUARANTINED_QUALITY_RECHECK'
        from .trusted_sample_pool import source_restriction
        if record and source_restriction(self,record['pins']['source_hash'],'GEOMETRY_TRAINING_LOCAL'):return 'RESTRICTED_USE'
        from .training_store import digest
        record=self.get('SAMPLE',sample_id)
        if not record:return 'MISSING'
        if record.get('state')!='APPROVED':return record.get('state','UNKNOWN')
        if record.get('invalidations'):return 'STALE_RULE'
        try:
            if record['pins']!=self.pins(record['work_id']) or record['facts_revision']!=self.facts(record['work_id'])['revision'] or record['observations_digest']!=digest(self.facts(record['work_id'])['observations']) or self.facts_state(record['work_id'])!='CONFIRMED':return 'STALE'
            if record['noise_signature']!=self.noise_signature(record['work_id']):return 'STALE_RULE'
            if record['cache_stamps']!=cache_stamps(self.library.source(record['pins']['source_id'])):return 'STALE_SOURCE_CACHE'
            return 'APPROVED'
        except (ValueError,OSError,KeyError,TypeError):return 'UNKNOWN'

    def sample_usage_impact(self,sample_id):
        datasets=[r[0] for r in self.db.execute("SELECT DISTINCT d.id FROM training_records d,json_each(d.payload,'$.entries') e WHERE d.kind='DATASET' AND json_extract(e.value,'$.sample_id')=? ORDER BY d.id LIMIT 201",(sample_id,))]
        uses=[training_record(row) for row in self.db.execute("SELECT id,revision,payload FROM training_records WHERE kind='USE' AND json_extract(payload,'$.sample_id')=? ORDER BY id LIMIT 201",(sample_id,))]
        jobs=[r[0] for r in self.db.execute("SELECT DISTINCT j.id FROM training_records j,json_each(j.payload,'$.items') i WHERE j.kind='JOB' AND json_extract(i.value,'$.sample_id')=? ORDER BY j.id LIMIT 201",(sample_id,))]
        design_uses=[training_record(row) for row in self.db.execute("SELECT id,revision,payload FROM training_records WHERE kind='DESIGN_USE' AND json_extract(payload,'$.sample_id')=? ORDER BY id LIMIT 201",(sample_id,))]
        rankers=[row[0] for row in self.db.execute("SELECT DISTINCT r.id FROM training_records r,json_each(r.payload,'$.examples') e JOIN training_records p ON p.kind='DESIGN_PREFERENCE_EXAMPLE' AND p.id=json_extract(e.value,'$.id') WHERE r.kind='DESIGN_RANKER' AND json_extract(p.payload,'$.sample_id')=? ORDER BY r.id LIMIT 201",(sample_id,))]
        return {'dataset_ids':datasets[:200],'template_ids':sorted({u['template_id'] for u in uses[:200]}),'job_ids':jobs[:200],'current_geometry_training_use':bool(uses),'design_model_ids':sorted({row['model_id'] for row in design_uses[:200]}),'current_cross_work_training_use':bool(design_uses),'design_ranker_ids':rankers[:200],'scope':'sample.used_for_training is historical AT_ADMISSION; current use is this exact USE ledger','complete':len(datasets)<=200 and len(uses)<=200 and len(jobs)<=200 and len(design_uses)<=200 and len(rankers)<=200,'models_decontaminated':False,'originals_and_published_templates_unchanged':True}

    def sample_transition_plan(self,sample_id,action):
        from .training_store import digest
        if action not in ('QUARANTINE','REVOKE'):raise ValueError('只支援隔離或撤銷；恢復需新准入版本')
        record=self.get('SAMPLE',sample_id)
        if not record:raise ValueError('樣本不存在')
        plan={'epoch':self.epoch,'sample':record,'action':action,'impact':self.sample_usage_impact(sample_id)};plan['digest']=digest(plan);return plan

    def transition_sample(self,plan,actor,reason,approved=False):
        from .training_store import text
        if approved is not True:raise ValueError('明確確認隔離／撤銷')
        text(actor,'操作人',120);text(reason,'原因')
        with self.transaction():
            current=self.sample_transition_plan(plan['sample']['id'],plan['action'])
            if current['digest']!=plan.get('digest') or not current['impact']['complete']:raise ValueError('樣本版次／使用影響已變更或不完整')
            record=current['sample'];record.update(state={'QUARANTINE':'QUARANTINED','REVOKE':'REVOKED'}[current['action']],transition_actor=actor,transition_reason=reason,transition_at=time.time(),use_impact=current['impact'])
            return self._write('SAMPLE',record['id'],record,record['revision'],'sample_'+current['action'].lower())
