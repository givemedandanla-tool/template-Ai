"""Versioned local text models in the existing TrainingStore, with held-out data.

Semantic use is separately approved; geometry-only SAMPLE rights are never
silently reused. Training, evaluating, activating and restoring are distinct.
"""
from collections import Counter
import time
from .semantic_fields import CharacterModel,recognize,normalized,VERSION,TYPES
from .training_store import TrainingStore,digest,text
from .model import new_id


class SemanticLearning:
    def __init__(self,library):self.library=library;self.store=TrainingStore(library)

    def plan(self,work_roles):
        if not isinstance(work_roles,dict) or not 2<=len(work_roles)<=200 or set(work_roles.values())!={'TRAIN','VALIDATION'}:raise ValueError('需明確列出2～200作品及TRAIN／VALIDATION角色')
        scopes=[];examples=[];source_roles={};literal_roles={};source_sizes={}
        for wid,role in sorted(work_roles.items()):
            work=self.library.artwork(wid);facts=self.store.facts(wid);pins=self.store.pins(wid)
            if work['payload'].get('segmentation_state')=='SUPERSEDED' or not work['payload'].get('visual_confirmed') or self.store.facts_state(wid)!='CONFIRMED':raise ValueError('只收現行、來源有效、已視覺核對與明確確認的文字事實')
            source_hash=pins['source_hash']
            source_sizes[source_hash]=self.library.source(pins['source_id'])['byte_size']
            if sum(source_sizes.values())>100_000_000:raise ValueError('本次語意來源核驗超過100MB，請縮小明確範圍')
            if source_hash in source_roles and source_roles[source_hash]!=role:raise ValueError('同一原來源hash不可跨訓練與留出集')
            source_roles[source_hash]=role;slots={s['id']:s for s in work['payload']['slots']};selected=set(facts['confirmation']['observation_ids'])
            for observation in facts['observations']:
                slot=slots.get(observation.get('slot_id'))
                if observation['id'] not in selected or not slot or observation['classification']!='FIELD' or observation['object_type']!='TEXT':continue
                kind=slot['kind'];semantic=recognize(observation['text'])
                if kind=='phone':kind=semantic['semantic_type'] if semantic['semantic_type'] in ('phone','mobile','landline','fax') else 'phone'
                if kind in ('line','ig'):kind='social_id'
                if kind not in TYPES:continue
                key=normalized(observation['text']).casefold()
                if key in literal_roles and literal_roles[key]!=role:raise ValueError('相同正規化字串不可跨訓練與留出集，避免記憶冒充泛化')
                literal_roles[key]=role
                examples.append(dict(sample_id=wid+'-'+observation['id'],work_id=wid,text=observation['text'],semantic_type=kind,confirmed=True,use='SEMANTIC_CLASSIFICATION_LOCAL',role=role))
            scopes.append(dict(work_id=wid,pins=pins,facts_revision=facts['revision'],observations_digest=digest(facts['observations']),role=role))
        train=[e for e in examples if e['role']=='TRAIN'];counts=Counter(e['semantic_type'] for e in train);validation=Counter(e['semantic_type'] for e in examples if e['role']=='VALIDATION')
        if len(examples)>2000 or len(counts)<2 or any(n<2 for n in counts.values()) or set(validation)!=set(counts):raise ValueError('需至少兩類、每類TRAIN至少2筆及各類獨立留出；每版上限2000字串')
        result=dict(work_roles=work_roles,scopes=scopes,examples=examples,training_counts=dict(counts),validation_counts=dict(validation),
            use='SEMANTIC_CLASSIFICATION_LOCAL',algorithm=VERSION+'/character-multinomial-naive-bayes-1',publication='LOCAL_ONLY_PENDING_SEPARATE_ACTIVATION')
        result['digest']=digest(result);return result

    def evaluate(self,model,rows):
        result={}
        for row in rows:
            expected=row['semantic_type'];cell=result.setdefault(expected,dict(total=0,correct=0,unknown=0,errors=[]))
            predicted=recognize(row['text'],model=model)['semantic_type'];cell['total']+=1;cell['correct']+=int(predicted==expected);cell['unknown']+=int(predicted=='unknown')
            if predicted!=expected:cell['errors'].append(dict(sample_id=row['sample_id'],predicted=predicted))
        return result

    def train(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需明確授權所列確認文字作本機語意分類訓練；不沿用僅幾何授權')
        text(actor,'訓練者',120)
        with self.store.transaction():
            fresh=self.plan(plan['work_roles'])
            if fresh['digest']!=plan.get('digest'):raise ValueError('語意訓練來源／確認版已變更')
            for scope in fresh['scopes']:self.store.checked(scope['work_id'],self.store.source_proof(scope['work_id']))
            model=CharacterModel([e for e in fresh['examples'] if e['role']=='TRAIN'])
            metrics=self.evaluate(model,[e for e in fresh['examples'] if e['role']=='VALIDATION'])
            baseline=self.evaluate(None,[e for e in fresh['examples'] if e['role']=='VALIDATION'])
            return self.store._write('SEMANTIC_MODEL',new_id(),dict(state='PENDING',plan=fresh,actor=actor,created=time.time(),metrics=metrics,baseline_metrics=baseline,
                parameter_count=sum(len(v) for v in model.counts.values())+len(model.documents),vocabulary_size=len(model.vocabulary),
                weights_digest=digest({k:dict(v) for k,v in model.counts.items()}),score_kind='UNCALIBRATED_LOG_LIKELIHOOD_MARGIN',scope='LOCAL_TEXT_ONLY; NO_NEURAL_ARCHITECTURE_CHANGE'),0,'semantic_model_candidate_trained_not_activated')

    def checked_model(self,identity):
        row=self.store.get('SEMANTIC_MODEL',identity)
        if not row:raise ValueError('模型版本不存在')
        if self.plan(row['plan']['work_roles'])['digest']!=row['plan']['digest']:raise ValueError('模型訓練／留出來源或確認已失效')
        for scope in row['plan']['scopes']:self.store.checked(scope['work_id'],self.store.source_proof(scope['work_id']))
        model=CharacterModel([e for e in row['plan']['examples'] if e['role']=='TRAIN'])
        if digest({k:dict(v) for k,v in model.counts.items()})!=row['weights_digest']:raise ValueError('模型權重摘要不符')
        return row,model

    def activate(self,identity,revision,expected_active_revision,actor,reason,approved=False):
        if approved is not True:raise ValueError('模型啟用／回退必須另行明確核准')
        text(reason,'啟用理由');text(actor,'核准者',120)
        with self.store.transaction():
            row,model=self.checked_model(identity)
            if row['revision']!=revision:raise ValueError('模型已更新，重新核對')
            if not row['metrics'] or any(c['total']<1 or c['correct']/c['total']<.8 for c in row['metrics'].values()):raise ValueError('各類留出驗證未達80%，仍待審；測試集不代表真實部署正確率')
            if row['state']!='APPROVED':
                row.update(state='APPROVED',approval_actor=actor,approval_reason=reason)
                row=self.store._write('SEMANTIC_MODEL',identity,row,revision,'semantic_model_explicitly_approved')
            return self.store._write('SEMANTIC_ACTIVE','local-text',dict(model_id=identity,model_revision=row['revision'],manifest_digest=row['plan']['digest'],actor=actor,reason=reason,
                activated=time.time(),scope='NEW_SOURCE_HYPOTHESES_ONLY; NO_CONFIRMED_FACT_OVERWRITE'),expected_active_revision,'semantic_model_explicitly_activated_or_restored')

    def active(self):
        active=self.store.get('SEMANTIC_ACTIVE','local-text')
        if not active:return None,dict(state='NONE',reason='未核准語意模型，使用可拒答的明確內容辨識')
        try:
            row,model=self.checked_model(active['model_id'])
            if row['state']!='APPROVED' or row['revision']!=active['model_revision'] or row['plan']['digest']!=active['manifest_digest']:raise ValueError('啟用模型版本不符')
            return model,dict(state='ACTIVE',model_id=row['id'],model_revision=row['revision'],weights_digest=row['weights_digest'],manifest_digest=active['manifest_digest'])
        except (ValueError,OSError) as error:return None,dict(state='STALE',model_id=active['model_id'],reason=str(error))
