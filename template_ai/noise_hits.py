"""Deterministic current decisions and persistent hit history, without source edits or prompts."""
import copy
from .noise_review import scope_matches


class NoiseHitMixin:
    def active_noise_rules(self):
        ids = [r[0] for r in self.db.execute("SELECT id FROM training_records WHERE kind='RULE' AND json_extract(payload,'$.state')='ACTIVE' ORDER BY id LIMIT 201")]
        if len(ids) > 200: return [], ['ACTIVE_RULE_BUDGET']
        result=[];invalid=[]
        for rid in ids:
            rule=self.get('RULE',rid)
            try:
                review=rule.get('review') or {}
                if review.get('decision')!='APPROVE' or review.get('reviewed_revision')!=rule['revision']-1:raise ValueError('沒有目前版本的人為核准')
                for ref in rule['positive_examples']+rule['counterexamples']:self.validate_ref(ref)
                result.append(rule)
            except (ValueError,OSError,KeyError,TypeError):invalid.append(rid)
        return result,invalid

    def noise_decisions(self,work_id):
        from .training_store import digest
        facts=self.facts(work_id);work=self.library.artwork(work_id);source=self.library.source(work['source_id']);pins=self.pins(work_id);local=self.local_record(work_id);rules,invalid=self.active_noise_rules();confirmed=self.facts_state(work_id)=='CONFIRMED';result=[]
        invalid_rules=[self.get('RULE',rid) for rid in invalid if rid!='ACTIVE_RULE_BUDGET']
        for observation in facts['observations']:
            matches=[r for r in rules if scope_matches(r,work,observation,source) and observation['classification']==r['scope']['classification']];whites=[r for r in matches if r['action']=='KEEP'];excludes=[r for r in matches if r['action']=='EXCLUDE'];protected=self.protected_observation(work_id,observation);item=local['items'].get(observation['id']);local_valid=bool(item and item['pins']==pins and item['observation_digest']==digest(observation))
            state='INCLUDED';reason='沒有符合已核准的完整條件，保留候選；不代表樣本准入'
            if not confirmed or observation['id'] not in facts['confirmation']['observation_ids']:state='STALE_LOCAL' if item else 'REVIEW_UNKNOWN';reason='來源／作品／觀察未確認或已過期，局部決定也失效並保留候選'
            elif protected:state='KEPT_PROTECTED';reason='真實欄位、Logo或未知分類保留'
            elif local_valid and item['intent']=='KEEP':state='KEPT_LOCAL';reason='人工只對此觀察明確保留'
            elif whites:state='KEPT_WHITELIST';reason='目前已核准白名單優先保留'
            elif len(excludes)>1:state='REVIEW_CONFLICT';reason='多個活動版本命中，保留並逐條審核'
            elif 'ACTIVE_RULE_BUDGET' in invalid:state='REVIEW_BUDGET';reason='活動規則超過200條有界核對範圍，保留'
            elif any(scope_matches(r,work,observation,source) for r in invalid_rules if r):state='REVIEW_RULE_STALE';reason='匹配規則的支持／反例來源或核准版本過期，保留'
            elif local_valid and item['intent']=='EXCLUDE':state='EXCLUDED_LOCAL';reason='人工只排除此作品／觀察'
            elif excludes:state='EXCLUDED_RULE';reason='已核准完整literal／type／zone／人工語境命中，無需重複詢問'
            elif item and not local_valid:state='STALE_LOCAL';reason='舊局部決定已過期，保留候選'
            result.append({'work_id':work_id,'source_id':source['id'],'observation_id':observation['id'],'text':observation['text'],'state':state,'reason':reason,'protected':protected,
                           'facts_revision':facts['revision'],'pins':pins,'observation_digest':digest(observation),'local_revision':local['revision'],
                           'rule_matches':[{'id':r['id'],'revision':r['revision'],'action':r['action'],'scope':copy.deepcopy(r['scope'])} for r in matches],
                           'invalid_rule_ids':invalid,'source_and_formal_slots_modified':False,'native_mapping':'UNKNOWN'})
        return result

    def _refresh_noise(self,work_id):
        from .training_store import digest
        rows=self.noise_decisions(work_id);ids=set()
        for row in rows:
            hit_id=digest({'work_id':work_id,'observation_id':row['observation_id']});ids.add(hit_id);prior=self.get('HIT',hit_id)
            if prior and {k:v for k,v in prior.items() if k not in ('id','revision')}==row:continue
            self._write('HIT',hit_id,row,prior['revision'] if prior else 0,'noise_hit_recorded')
        # Removed observations remain in the immutable history with an explicit obsolete current state.
        for rid, in self.db.execute("SELECT id FROM training_records WHERE kind='HIT' AND json_extract(payload,'$.work_id')=?",(work_id,)):
            if rid in ids:continue
            prior=self.get('HIT',rid)
            if prior['state']=='OBSERVATION_REMOVED':continue
            prior.update(state='OBSERVATION_REMOVED',reason='目前觀察已移除；舊命中只作歷史');self._write('HIT',rid,prior,prior['revision'],'noise_hit_obsolete')
        return rows

    def refresh_noise(self,work_id,expected_facts_revision):
        with self.transaction():
            if self.facts(work_id)['revision']!=expected_facts_revision:raise ValueError('事實版次已變更，重新載入')
            return self._refresh_noise(work_id)

    def _refresh_rule_impacts(self,rule_ids):
        rows,complete=self.scan_observations()
        if not complete:raise ValueError('命中更新有界掃描未完成，沒有部分啟用')
        work_ids=set()
        rules=[self.get('RULE',rid) for rid in rule_ids]
        for row in rows:
            if any(scope_matches(r,row['work'],row['observation'],row['source']) for r in rules if r):work_ids.add(row['work']['id'])
        placeholders=','.join('?' for _ in rule_ids)
        prior_ids=[r[0] for r in self.db.execute("SELECT DISTINCT json_extract(h.payload,'$.work_id') FROM training_records h,json_each(h.payload,'$.rule_matches') r WHERE h.kind='HIT' AND json_extract(r.value,'$.id') IN ("+placeholders+") LIMIT 2001",rule_ids)]
        work_ids.update(prior_ids)
        if len(work_ids)>2000:raise ValueError('影響作品超過有界預算，不進行部分更新')
        for wid in sorted(work_ids):self._refresh_noise(wid)
        return sorted(work_ids)
