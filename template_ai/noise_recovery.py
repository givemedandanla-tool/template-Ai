"""Local keeps, pending whitelist/version candidates and immutable controlled rollback."""
import copy
import time
from .model import new_id
from .noise import validate_zone, relative_region, contains, normalized
from .noise_review import scope_matches


class NoiseRecoveryMixin:
    def local_keep(self,work_id,ids,expected_revision,expected_facts_revision,approved=False):
        if approved is not True:raise ValueError('明確確認只保留此作品觀察')
        with self.transaction():return self._local_write(work_id,ids,expected_revision,expected_facts_revision,'KEEP')

    def replacement_rule(self,work_id,observation_id,counterexamples,zone,normalization,actor,action,normalization_approved=False):
        from pathlib import Path
        from .training_store import text
        text(actor,'提出者',120);zone=validate_zone(zone);normalized('',normalization)
        if normalization=='NFC' and normalization_approved is not True:raise ValueError('NFC需明確對照')
        facts,observation=self.observation(work_id,observation_id);work=self.library.artwork(work_id)
        if action not in ('EXCLUDE','KEEP') or observation['classification']=='UNKNOWN' or observation['object_type']=='UNKNOWN':raise ValueError('未知語境不能形成規則')
        if action=='EXCLUDE' and (self.protected_observation(work_id,observation) or observation['classification']!='ANNOTATION'):raise ValueError('真實欄位／Logo不得作排除正例')
        if not contains(zone,relative_region(work,observation)):raise ValueError('區域未包含正例')
        if not isinstance(counterexamples,list) or not 1<=len(counterexamples)<=200 or any(not isinstance(r,dict) or not {'work_id','observation_id'}<=set(r) for r in counterexamples) or len({(r['work_id'],r['observation_id']) for r in counterexamples})!=len(counterexamples):raise ValueError('需要不重複的真實反例')
        rule={'state':'PENDING','action':action,'literal':observation['text'],'normalization':normalization,'normalization_approved':normalization_approved,
              'scope':{'source_extension':Path(self.library.source(work['source_id'])['original_path']).suffix.lower(),'object_type':observation['object_type'],'classification':observation['classification'],'zone':zone},
              'positive_examples':[self.evidence_ref(work_id,observation_id)],'counterexamples':[],'author':actor,'created':time.time(),'review':None}
        for ref in counterexamples:
            if (ref['work_id'],ref['observation_id'])==(work_id,observation_id):raise ValueError('正例不能兼反例')
            item=self.evidence_ref(ref['work_id'],ref['observation_id']);counter_work=self.library.artwork(ref['work_id']);counter_source=self.library.source(counter_work['source_id'])
            if scope_matches(rule,counter_work,item['observation'],counter_source) and item['observation']['classification']==rule['scope']['classification']:raise ValueError('完整条件同时匹配正反例，需縮小範圍')
            rule['counterexamples'].append(item)
        rule['counterexamples'].sort(key=lambda r:(r['work_id'],r['observation_id']));return rule,facts

    def propose_whitelist(self,work_id,observation_id,counterexamples,zone,normalization,expected_facts_revision,expected_epoch,actor,approved=False,normalization_approved=False):
        if approved is not True:raise ValueError('明確確認局部保留與PENDING白名單')
        with self.transaction():
            if self.epoch!=expected_epoch:raise ValueError('範圍已變更，重新預覽')
            rule,facts=self.replacement_rule(work_id,observation_id,counterexamples,zone,normalization,actor,'KEEP',normalization_approved)
            if facts['revision']!=expected_facts_revision:raise ValueError('事實版次已變更')
            result=self._write('RULE',new_id(),rule,0,'whitelist_proposed');self._local_write(work_id,[observation_id],self.local_record(work_id)['revision'],facts['revision'],'KEEP');return result

    def rule_sample_impacts(self,rule_id):
        rows=list(self.db.execute("SELECT DISTINCT s.id FROM training_records s,json_each(s.payload,'$.rule_dependencies') d WHERE s.kind='SAMPLE' AND json_extract(d.value,'$.id')=? ORDER BY s.id LIMIT 201",(rule_id,)))
        return [r[0] for r in rows[:200]],len(rows)<=200

    def rule_version_plan(self,rule_id,operation,history_revision=None,replacement=None):
        from .training_store import digest
        if operation not in ('DISABLE','ROLLBACK','CHANGE'):raise ValueError('版本動作不支援')
        rule=self.get('RULE',rule_id)
        if not rule:raise ValueError('規則不存在')
        proposal=copy.deepcopy(rule)
        if operation=='DISABLE':proposal.update(state='DISABLED',review=None)
        elif operation=='ROLLBACK':
            historical=next((h for h in self.history('RULE',rule_id) if h['revision']==history_revision),None)
            if not historical:raise ValueError('明列可用歷史版次，沒有覆寫原歷史')
            proposal=copy.deepcopy(historical['after']);proposal.update(state='PENDING',review=None,rollback_from_revision=history_revision)
        elif replacement:proposal=copy.deepcopy(replacement);proposal.update(state='PENDING',review=None)
        else:raise ValueError('CHANGE需目前人工證據建立的完整候選')
        current=self.inspect_rule(rule_id);rows,complete=self.scan_observations();matches=[]
        for row in rows:
            old=scope_matches(rule,row['work'],row['observation'],row['source']);new=scope_matches(proposal,row['work'],row['observation'],row['source'])
            if old or new:matches.append({'work_id':row['work']['id'],'source_id':row['source']['id'],'observation_id':row['observation']['id'],'old_predicate':old,'new_predicate':new,'work_revision':row['work']['revision'],'facts_revision':row['facts']['revision']})
        samples,samples_complete=self.rule_sample_impacts(rule_id)
        plan={'epoch':self.epoch,'rule_id':rule_id,'expected_revision':rule['revision'],'operation':operation,'history_revision':history_revision,'before':rule,'after':proposal,'matches':sorted(matches,key=lambda r:(r['work_id'],r['observation_id'])),'sample_ids':samples,'impact_complete':complete and samples_complete,'review_risk':current['risk'],'existing_models_decontaminated':False,'published_templates_modified':False}
        stable=copy.deepcopy(plan);stable['after'].pop('created',None);plan['digest']=digest(stable);return plan

    def _invalidate_rule_samples(self,rule_id,before_revision,after_revision,operation):
        ids,complete=self.rule_sample_impacts(rule_id)
        if not complete:raise ValueError('樣本影響超過200項預算，沒有部分修改')
        for sid in ids:
            record=self.get('SAMPLE',sid);record.setdefault('invalidations',[]).append({'rule_id':rule_id,'before_revision':before_revision,'after_revision':after_revision,'operation':operation,'timestamp':time.time()});self._write('SAMPLE',sid,record,record['revision'],'sample_rule_dependency_invalidated')
        return ids

    def apply_rule_version(self,plan,actor,reason,approved=False):
        from .training_store import text
        if approved is not True or plan['operation']=='CHANGE':raise ValueError('DISABLE／ROLLBACK需exact批准；CHANGE由人工證據重建')
        text(actor,'操作人',120);text(reason,'原因')
        with self.transaction():
            current=self.rule_version_plan(plan['rule_id'],plan['operation'],plan['history_revision'])
            if current['digest']!=plan.get('digest') or not current['impact_complete']:raise ValueError('版本／來源／影響已變更或不完整')
            payload=copy.deepcopy(current['after']);payload['version_action']={'actor':actor,'reason':reason,'operation':current['operation'],'plan_digest':current['digest'],'timestamp':time.time()}
            saved=self._write('RULE',current['rule_id'],payload,current['expected_revision'],'rule_version_'+current['operation'].lower());self._refresh_rule_impacts([saved['id']]);self._invalidate_rule_samples(saved['id'],current['expected_revision'],saved['revision'],current['operation']);return saved

    def change_rule_candidate(self,rule_id,work_id,observation_id,counterexamples,zone,normalization,expected_rule_revision,expected_facts_revision,expected_epoch,actor,reason,approved=False,normalization_approved=False,expected_plan_digest=None):
        from .training_store import text
        if approved is not True:raise ValueError('需明確停止舊版本並建立新版候選')
        text(reason,'變更原因')
        with self.transaction():
            before=self.get('RULE',rule_id)
            if not before or before['revision']!=expected_rule_revision or self.epoch!=expected_epoch:raise ValueError('規則／影響版次已變更')
            proposal,facts=self.replacement_rule(work_id,observation_id,counterexamples,zone,normalization,actor,before['action'],normalization_approved)
            if facts['revision']!=expected_facts_revision:raise ValueError('事實版次已變更')
            plan=self.rule_version_plan(rule_id,'CHANGE',replacement=proposal)
            if not plan['impact_complete'] or plan['digest']!=expected_plan_digest:raise ValueError('變更影響已異動或超過預算，未部分停用')
            proposal['version_action']={'actor':actor,'reason':reason,'operation':'CHANGE','before_revision':before['revision'],'plan_digest':plan['digest'],'timestamp':time.time()}
            result=self._write('RULE',rule_id,proposal,before['revision'],'rule_version_change');self._refresh_rule_impacts([rule_id]);self._invalidate_rule_samples(rule_id,before['revision'],result['revision'],'CHANGE');return result
