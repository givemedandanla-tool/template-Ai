"""Complete-literal scoped noise metadata; never deletes source or layout objects."""
import copy
import math
from pathlib import Path
import time
import unicodedata
from .model import new_id


def normalized(value, mode):
    if mode not in ('NONE', 'NFC'): raise ValueError('只支援明確NONE或NFC')
    return unicodedata.normalize('NFC', value) if mode == 'NFC' else value


def relative_region(work, observation):
    crop = work['payload']['crop']; r = observation['region']
    return {'x': (r['x']-crop['x'])/crop['w'], 'y': (r['y']-crop['y'])/crop['h'], 'w': r['w']/crop['w'], 'h': r['h']/crop['h']}


def contains(zone, region):
    return (zone['x']-2e-6 <= region['x'] and zone['y']-2e-6 <= region['y'] and zone['x']+zone['w']+2e-6 >= region['x']+region['w'] and zone['y']+zone['h']+2e-6 >= region['y']+region['h'])


def validate_zone(zone):
    if not isinstance(zone, dict) or set(zone) != {'x', 'y', 'w', 'h'} or any(type(v) not in (float, int) or not math.isfinite(v) for v in zone.values()): raise ValueError('相對來源區域不合法')
    if zone['x'] < 0 or zone['y'] < 0 or zone['w'] <= 0 or zone['h'] <= 0 or zone['x']+zone['w'] > 1+2e-6 or zone['y']+zone['h'] > 1+2e-6: raise ValueError('相對區域需在作品0～1內')
    return copy.deepcopy(zone)


class NoiseMixin:
    def observation(self, work_id, observation_id, confirmed=True):
        facts = self.facts(work_id)
        row = next((o for o in facts['observations'] if o['id'] == observation_id), None)
        if row is None: raise ValueError('觀察不存在')
        if confirmed and (self.facts_state(work_id) != 'CONFIRMED' or observation_id not in facts['confirmation']['observation_ids']): raise ValueError('需要目前來源健康且人工確認的exact觀察')
        return facts, row

    def protected_observation(self, work_id, observation):
        work = self.library.artwork(work_id); linked = next((s for s in work['payload']['slots'] if s.get('id') == observation['slot_id']), None)
        return observation['classification'] in ('FIELD', 'LOGO', 'UNKNOWN') or observation['object_type'] in ('LOGO_PART', 'UNKNOWN') or bool(linked and linked.get('kind') in ('name', 'company', 'logo'))

    def evidence_ref(self, work_id, observation_id):
        from .training_store import digest
        facts, row = self.observation(work_id, observation_id)
        return {'work_id': work_id, 'observation_id': observation_id, 'facts_revision': facts['revision'], 'observations_digest': digest(facts['observations']), 'pins': facts['pins'], 'observation': copy.deepcopy(row), 'confirmed_at': facts['confirmation']['timestamp']}

    def validate_ref(self, reference):
        current = self.evidence_ref(reference['work_id'], reference['observation_id'])
        if current != reference: raise ValueError('規則支持／反例證據版次已過期')
        return current

    def local_record(self, work_id):
        return self.get('LOCAL', work_id) or {'id': work_id, 'revision': 0, 'items': {}}

    def _local_write(self, work_id, ids, expected_revision, expected_facts_revision, action):
        from .training_store import digest
        if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or len(set(ids)) != len(ids): raise ValueError('選取1～200個不重複觀察')
        local = self.local_record(work_id); facts = self.facts(work_id)
        if facts['revision'] != expected_facts_revision: raise ValueError('作品事實版次已變更')
        for oid in ids:
            _, observation = self.observation(work_id, oid)
            if action == 'EXCLUDE' and (self.protected_observation(work_id, observation) or observation['classification'] != 'ANNOTATION'): raise ValueError('真實欄位／Logo／未知不能當雜訊剔除')
            local['items'][oid] = {'intent': action, 'observation_digest': digest(observation), 'pins': self.pins(work_id), 'created': time.time()}
        return self._write('LOCAL', work_id, local, expected_revision, 'local_noise_'+action.lower())

    def local_noise(self, work_id, ids, expected_revision, expected_facts_revision, approved=False):
        if approved is not True: raise ValueError('需要確認只排除此作品的exact選項')
        with self.transaction(): return self._local_write(work_id, ids, expected_revision, expected_facts_revision, 'EXCLUDE')

    def clear_local_noise(self, work_id, ids, expected_revision, expected_facts_revision, approved=False):
        if approved is not True or not isinstance(ids, list) or not 1 <= len(ids) <= 200 or len(ids) != len(set(ids)): raise ValueError('明列需撤銷的局部剔除')
        with self.transaction():
            local = self.local_record(work_id)
            if self.facts(work_id)['revision'] != expected_facts_revision or not set(ids) <= set(local['items']): raise ValueError('局部剔除或事實範圍已變更')
            for oid in ids: del local['items'][oid]
            return self._write('LOCAL', work_id, local, expected_revision, 'local_noise_cleared')

    def noise_candidates(self, work_id):
        from .training_store import digest
        facts = self.facts(work_id); local = self.local_record(work_id); pins = self.pins(work_id); result = []
        confirmed = self.facts_state(work_id) == 'CONFIRMED'
        for observation in facts['observations']:
            item = local['items'].get(observation['id']); state = 'INCLUDED'; reason = '未排除；不代表已准入訓練'
            if item:
                if confirmed and observation['id'] in facts['confirmation']['observation_ids'] and item['pins'] == pins and item['observation_digest'] == digest(observation): state = 'EXCLUDED_LOCAL' if item['intent'] == 'EXCLUDE' else 'KEPT_LOCAL'; reason = '人工只對此作品／觀察決定'
                else: state = 'STALE_LOCAL'; reason = '舊局部決定過期，保留候選'
            result.append({'work_id': work_id, 'observation_id': observation['id'], 'text': observation['text'], 'state': state, 'reason': reason, 'protected': self.protected_observation(work_id, observation)})
        return result

    def propose_noise_rule(self, work_id, observation_id, counterexamples, zone, normalization, expected_facts_revision, expected_epoch, actor, approved=False, normalization_approved=False):
        from .training_store import text
        if approved is not True: raise ValueError('需要確認剔除並建立待審規則，不自動啟用')
        text(actor, '規則提出者', 120); zone = validate_zone(zone); normalized('', normalization)
        if normalization == 'NFC' and normalization_approved is not True: raise ValueError('NFC需明確同意及對照')
        if not isinstance(counterexamples, list) or not 1 <= len(counterexamples) <= 200 or any(not isinstance(r, dict) or not {'work_id', 'observation_id'} <= set(r) for r in counterexamples) or len({(r['work_id'], r['observation_id']) for r in counterexamples}) != len(counterexamples): raise ValueError('至少一個且不重複的人工反例')
        with self.transaction():
            if self.epoch != expected_epoch: raise ValueError('影響範圍已变更，請重新預覽')
            facts, observation = self.observation(work_id, observation_id)
            if facts['revision'] != expected_facts_revision: raise ValueError('作品事實已變更')
            if self.protected_observation(work_id, observation) or observation['classification'] != 'ANNOTATION': raise ValueError('真實欄位／Logo／未知不能當正例')
            work = self.library.artwork(work_id)
            if not contains(zone, relative_region(work, observation)): raise ValueError('適用區域未涵蓋正例')
            positives = [self.evidence_ref(work_id, observation_id)]; negatives = []
            for ref in counterexamples:
                if (ref['work_id'], ref['observation_id']) == (work_id, observation_id): raise ValueError('正例不能同時當反例')
                item = self.evidence_ref(ref['work_id'], ref['observation_id'])
                if not self.protected_observation(ref['work_id'], item['observation']): raise ValueError('反例需人工確認應保留的真實欄位或Logo')
                negatives.append(item)
            rule = {'state': 'PENDING', 'action': 'EXCLUDE', 'literal': observation['text'], 'normalization': normalization, 'normalization_approved': normalization_approved,
                    'scope': {'source_extension': Path(self.library.source(work['source_id'])['original_path']).suffix.lower(), 'object_type': observation['object_type'], 'classification': 'ANNOTATION', 'zone': zone},
                    'positive_examples': positives, 'counterexamples': sorted(negatives, key=lambda r: (r['work_id'], r['observation_id'])), 'author': actor, 'created': time.time(), 'review': None}
            saved = self._write('RULE', new_id(), rule, 0, 'noise_rule_proposed')
            self._local_write(work_id, [observation_id], self.local_record(work_id)['revision'], expected_facts_revision, 'EXCLUDE')
            return saved
