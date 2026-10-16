"""Versioned quality-only gold references with explicit local evaluation rights.

Geometry-training consent is never broadened into quality evaluation or upload.
Facts remain the source of truth; immutable snapshots pin their exact versions.
"""
import copy
import time
from .training_store import TrainingStore,digest,text
from .coverage_evidence import work_context
from .source_links import verify_source,check_verified,VerifiedSource
from .model import new_id
from .trusted_samples import cache_stamps
from .batch_import import healthy_source

GOLD='QUALITY_GOLD'
USE='INDEPENDENT_QUALITY_EVALUATION_LOCAL'
DOMAINS=('source_readability','work_segmentation','text_candidates','field_types','person_ownership','company_ownership','whole_logo','physical_size','customer_style_mapping')


class QualityGold:
    def __init__(self,library):self.library=library;self.db=library.db;self.store=TrainingStore.bind(library)

    def dependencies(self,work_id):
        context=work_context(self,work_id)
        # An independent gold answer must not change merely because a candidate model changes.
        truth={k:v for k,v in context['context'].items() if k not in ('analyser_version','semantic_active_digest','semantic_model_digest','active_rule_versions','related_digest')}
        source=self.library.source(context['source_id']);truth['source_derivative_manifest']=digest(source.get('file_hashes',{}))
        return context,truth,digest(truth)

    def plan(self,work_id,rights,domain_truth,reason,evidence,*,logo_truth=None,mapping_truth=None):
        if not isinstance(rights,dict) or set(rights)!={'basis','reference','use'} or rights['basis'] not in ('OWNED','AUTHORIZED','OPEN_LICENSE') or rights['use']!=USE:raise ValueError('需另行明列獨立品質驗收本機用途及權利；幾何訓練同意不等於此用途／外傳許可')
        text(rights['reference'],'品質驗收權利依據',2000);text(reason,'真值核對理由',2000);text(evidence,'原始作品與黃金答案證據',2000)
        if not isinstance(domain_truth,dict) or set(domain_truth)!=set(DOMAINS) or any(v not in ('MANUALLY_VERIFIED','INSUFFICIENT_EVIDENCE') for v in domain_truth.values()):raise ValueError('需逐層明列人工真值已核實／證據不足，沒有默認全部正確')
        context,truth,sha=self.dependencies(work_id);facts=self.store.facts(work_id);work=self.library.artwork(work_id);source=self.library.source(work['source_id'])
        if context['facts_state']!='CONFIRMED' or context['unconfirmed_observation_ids'] or context['unobserved_slot_ids'] or context['unresolved_observation_ids'] or not facts['observations']:raise ValueError('黃金答案需目前有效、逐項真正人工核對的來源事實；AI候選／未確認／爭議不算真值')
        if context['quality_blockers'] or context['unresolved_customer_candidates']:raise ValueError('標記／身分歧義尚未解決，不能宣稱黃金答案')
        if not work['payload'].get('visual_confirmed'):raise ValueError('需先人工對照可信原始作品及標記')
        if len(facts['observations'])>200:raise ValueError('單作品gold最多200觀察，需明確分組，不截斷')
        slots={s['id']:s for s in work['payload']['slots']};objects=[]
        for observation in facts['observations']:
            slot=slots.get(observation['slot_id']);kind=slot['kind'] if slot else observation['classification']
            objects.append(dict(id=observation['id'],slot_id=observation['slot_id'],kind=kind,owner=slot.get('owner') if slot else None,text=observation['text'],rect=copy.deepcopy(observation['region']),object_type=observation['object_type'],classification=observation['classification']))
        if logo_truth is not None:
            if not isinstance(logo_truth,dict) or not set(logo_truth)<={o['id'] for o in objects if o['kind']=='logo'}:raise ValueError('Logo真值只可指定本作品已確認Logo觀察')
            from .source_analysis import vector_objects
            from .quality_logo import validate_truth
            root,elements,bounds=vector_objects(source,self.library.assets)
            for obj in objects:
                if obj['id'] in logo_truth:obj['component_truth']=validate_truth(logo_truth[obj['id']],source,elements,bounds)
        proof=verify_source(source['current_path'],source['hash'])
        if not healthy_source(source):raise ValueError('原稿／渲染來源cache健康不足，不能把畫面當黃金答案')
        inventory=[row[0] for row in self.db.execute("SELECT id FROM artworks WHERE source_id=? AND COALESCE(json_extract(payload,'$.segmentation_state'),'')!='SUPERSEDED' ORDER BY id LIMIT 2001",(source['id'],))]
        if len(inventory)>2000:raise ValueError('來源作品清單超過2000，全部作品真值尚未完整核實')
        plan=dict(work_id=work_id,source_id=source['id'],source_hash=source['hash'],source_page=source['page'],source_page_count=source['page_count'],original_path=source['original_path'],current_path=source['current_path'],truth_dependencies=truth,truth_dependency_digest=sha,source_inventory_work_ids=inventory,facts_revision=facts['revision'],facts_confirmation=copy.deepcopy(facts['confirmation']),objects=objects,crop=copy.deepcopy(work['payload']['crop']),width_mm=work['payload']['work_width'],height_mm=work['payload']['work_height'],rights=copy.deepcopy(rights),domain_truth=copy.deepcopy(domain_truth),reason=reason,evidence=evidence,source_proof=dict(path=proof.path,hash=proof.hash,stat=list(proof.stat)),local_only=True,training_admission=False,model_prediction_is_gold=False)
        if mapping_truth is not None:
            from .quality_mapping import truth as mapping_oracle
            plan['mapping_truth']=mapping_oracle(self.library,mapping_truth)
        plan['source_cache_stamps']=cache_stamps(source);plan['digest']=digest(plan);return plan

    def confirm(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需核對品質用途／真值各層與來源，明確批准本次gold版本')
        text(actor,'gold核對者',120);preview=copy.deepcopy(plan);expected=preview.pop('digest',None)
        if expected!=digest(preview):raise ValueError('gold預覽已被修改')
        with self.store.transaction():
            self.check_mapping(plan)
            context,truth,sha=self.dependencies(plan['work_id'])
            if sha!=plan['truth_dependency_digest'] or context['facts_state']!='CONFIRMED':raise ValueError('真值來源／標記／歸屬已變更，需重新逐項核對')
            proof=plan['source_proof'];check_verified(VerifiedSource(proof['path'],proof['hash'],tuple(proof['stat'])),plan['source_hash'])
            if cache_stamps(self.library.source(plan['source_id']))!=plan['source_cache_stamps']:raise ValueError('gold預覽後來源cache已改變')
            inventory=[row[0] for row in self.db.execute("SELECT id FROM artworks WHERE source_id=? AND COALESCE(json_extract(payload,'$.segmentation_state'),'')!='SUPERSEDED' ORDER BY id LIMIT 2001",(plan['source_id'],))]
            if inventory!=plan['source_inventory_work_ids']:raise ValueError('同來源作品清單已變更，不能漏作品')
            identity=new_id();record=copy.deepcopy(plan);record.update(actor=actor,confirmed_at=time.time(),state='MANUALLY_VERIFIED_QUALITY_ONLY_GOLD',immutable=True)
            return self.store._write(GOLD,identity,record,0,'independent_quality_gold_confirmed_not_training_admission')

    def validity(self,gold_id,verify_bytes=True):
        gold=self.store.get(GOLD,gold_id)
        if not gold:return dict(valid=False,errors=['gold版本不存在'],gold=None)
        errors=[]
        if self.store.get('QUALITY_GOLD_INVALIDATION',gold_id):return dict(valid=False,errors=['品質真值／用途許可已撤回，舊版本只保留證據，未重新讀取原稿'],gold=gold)
        try:
            self.check_mapping(gold)
            context,truth,sha=self.dependencies(gold['work_id'])
            if sha!=gold['truth_dependency_digest'] or context['facts_state']!='CONFIRMED':errors.append('真值來源／標記／歸屬版本已失效')
            inventory=[row[0] for row in self.db.execute("SELECT id FROM artworks WHERE source_id=? AND COALESCE(json_extract(payload,'$.segmentation_state'),'')!='SUPERSEDED' ORDER BY id LIMIT 2001",(gold['source_id'],))]
            if inventory!=gold['source_inventory_work_ids']:errors.append('來源作品集合已變更，完整作品真值尚未重核')
            source=self.library.source(gold['source_id'])
            if cache_stamps(source)!=gold['source_cache_stamps'] or verify_bytes and not healthy_source(source):errors.append('原稿cache／來源對照證據已失效')
            if verify_bytes:verify_source(gold['current_path'],gold['source_hash'])
            else:
                p=gold['source_proof'];check_verified(VerifiedSource(p['path'],p['hash'],tuple(p['stat'])),gold['source_hash'])
        except (OSError,ValueError,KeyError) as error:errors.append(str(error))
        return dict(valid=not errors,errors=errors,gold=gold)

    def check_mapping(self,gold):
        if gold.get('mapping_truth'):
            from .quality_mapping import truth as mapping_oracle
            expected=gold['mapping_truth'];evidence={key:expected[key] for key in ('customer_id','style_id','review_reason')}
            if mapping_oracle(self.library,evidence)!=expected:raise ValueError('映射真值客戶／exact版型版本已改變，需新gold核對')

    def withdraw(self,gold_id,expected_revision,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確撤回品質真值／用途許可')
        text(actor,'撤回者',120);text(reason,'撤回原因',2000)
        with self.store.transaction():
            gold=self.store.get(GOLD,gold_id)
            if not gold or gold['revision']!=expected_revision:raise ValueError('gold版本已變更／失聯')
            prior=self.store.get('QUALITY_GOLD_INVALIDATION',gold_id)
            return self.store._write('QUALITY_GOLD_INVALIDATION',gold_id,dict(gold_id=gold_id,actor=actor,reason=reason,at=time.time(),state='WITHDRAWN_REQUIRES_NEW_EXPLICIT_GOLD_VERSION'),prior['revision'] if prior else 0,'quality_gold_scope_or_truth_withdrawn')
