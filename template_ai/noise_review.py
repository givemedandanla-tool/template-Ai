"""Recomputed, version-pinned rule review with explainable scope and risk."""
import copy
from pathlib import Path
import time
from .noise import normalized, contains, relative_region


def scope_matches(rule, work, observation, source):
    scope = rule['scope']
    return (Path(source['original_path']).suffix.lower() == scope['source_extension']
            and observation['object_type'] == scope['object_type']
            and normalized(observation['text'], rule['normalization']) == normalized(rule['literal'], rule['normalization'])
            and contains(scope['zone'], relative_region(work, observation)))


class RuleReviewMixin:
    def scan_observations(self, limit=2000):
        rows = []; offset = 0; more = False
        while True:
            facts_page = self.records('FACTS', offset); offset += len(facts_page)
            for facts in facts_page:
                work = self.library.artwork(facts['id']); source = self.library.source(work['source_id']); confirmed = self.facts_state(work['id']) == 'CONFIRMED'
                for observation in facts['observations']:
                    if len(rows) >= limit: more = True; break
                    rows.append({'facts': facts, 'work': work, 'source': source, 'observation': observation,
                                 'confirmed': confirmed and observation['id'] in facts['confirmation']['observation_ids']})
                if more: break
            if more or len(facts_page) < 200: break
        return rows, not more

    def inspect_rule(self, rule_id):
        from .training_store import digest
        rule = self.get('RULE', rule_id)
        if not rule: raise ValueError('規則不存在')
        errors = []; risks = []; matches = []; rows, complete = self.scan_observations()
        if not rule.get('positive_examples') or not rule.get('counterexamples'): errors.append('支持或反例缺證')
        for ref in rule.get('positive_examples', [])+rule.get('counterexamples', []):
            try: self.validate_ref(ref)
            except (ValueError, OSError): errors.append('支持／反例來源或版次過期：'+ref.get('work_id', '?'))
        for ref in rule.get('positive_examples', []):
            try:
                work = self.library.artwork(ref['work_id']); source = self.library.source(work['source_id'])
                if not scope_matches(rule, work, ref['observation'], source): errors.append('正例不符合規則的完整條件')
                if rule['action'] == 'EXCLUDE' and self.protected_observation(work['id'], ref['observation']): errors.append('保護真實欄位／Logo不能作排除正例')
            except (ValueError, KeyError, TypeError): errors.append('正例schema無法核對')
        if not complete: errors.append('有界掃描未涵蓋全部觀察，不能批准未知影響')
        if rule['normalization'] == 'NFC': risks.append('NFC需逐條核對完整字串正規化差異')
        if rule['scope']['object_type'] == 'TEXT': risks.append('一般TEXT物件需逐條核對語境')
        for row in rows:
            observation = row['observation']
            if not scope_matches(rule, row['work'], observation, row['source']): continue
            protected = self.protected_observation(row['work']['id'], observation)
            excluded = rule['action'] == 'EXCLUDE' and row['confirmed'] and not protected and observation['classification'] == rule['scope']['classification']
            if not row['confirmed'] or observation['classification'] == 'UNKNOWN': risks.append('完整字串有未知／未確認語境，將保留')
            matches.append({'work_id': row['work']['id'], 'source_id': row['source']['id'], 'observation_id': observation['id'], 'text': observation['text'], 'protected': protected,
                            'confirmed': row['confirmed'], 'decision_if_active': 'EXCLUDED_RULE' if excluded else 'KEPT', 'work_revision': row['work']['revision'], 'facts_revision': row['facts']['revision']})
        matches.sort(key=lambda r: (r['source_id'], r['work_id'], r['observation_id']))
        affected = sorted({r['work_id'] for r in matches if r['decision_if_active'] == 'EXCLUDED_RULE'})
        templates = sorted(t.id for t in self.library.templates() if t.source_work_id in affected)
        scope_group = digest({'scope': rule['scope'], 'normalization': rule['normalization'], 'action': rule['action']})
        return {'id': rule_id, 'revision': rule['revision'], 'state': rule['state'], 'risk': 'BLOCK' if errors else 'HIGH' if risks else 'LOW', 'errors': sorted(set(errors)), 'risk_reasons': sorted(set(risks)),
                'scope_group': scope_group, 'rule': rule, 'matches': matches, 'affected_work_ids': affected, 'linked_template_ids': templates,
                'impact_complete': complete, 'scanned_observations': len(rows), 'customer_identity': 'UNKNOWN', 'templates_rewritten': False,
                'history': self.history('RULE', rule_id)}

    def rule_review_plan(self, rule_ids):
        from .training_store import digest
        if not isinstance(rule_ids, list) or not 1 <= len(rule_ids) <= 200 or len(rule_ids) != len(set(rule_ids)): raise ValueError('明列1～200條不重複規則')
        rows = [self.inspect_rule(rid) for rid in sorted(rule_ids)]
        plan = {'epoch': self.epoch, 'ids': sorted(rule_ids), 'rows': rows, 'batch_eligible': all(r['risk'] == 'LOW' and r['impact_complete'] for r in rows) and len({r['scope_group'] for r in rows}) == 1}
        plan['digest'] = digest(plan); return plan

    def review_rules(self, plan, action, actor, reason, approved=False, detail_reviewed=False):
        from .training_store import text
        if approved is not True or action not in ('APPROVE', 'REJECT', 'DEFER'): raise ValueError('需要明確的規則審核決定')
        text(actor, '審核者', 120); text(reason, '審核原因')
        with self.transaction():
            current = self.rule_review_plan(plan['ids'])
            if current['digest'] != plan.get('digest'): raise ValueError('規則版次／來源證據／影響範圍已變更，重新審核')
            if any(r['state'] not in ('PENDING', 'DEFERRED') for r in current['rows']): raise ValueError('只能審核目前PENDING或DEFERRED版本')
            if action == 'APPROVE':
                if any(r['risk'] == 'BLOCK' for r in current['rows']): raise ValueError('缺證或未知完整影響不能批准')
                if len(current['rows']) > 1 and not current['batch_eligible']: raise ValueError('只有同前提且已驗證LOW風險可批次批准')
                if any(r['risk'] == 'HIGH' for r in current['rows']) and (len(current['rows']) != 1 or detail_reviewed is not True): raise ValueError('HIGH風險需逐條詳審')
            result = []
            for row in current['rows']:
                record = copy.deepcopy(row['rule']); record['state'] = {'APPROVE': 'ACTIVE', 'REJECT': 'REJECTED', 'DEFER': 'DEFERRED'}[action]
                record['review'] = {'actor': actor, 'reason': reason, 'decision': action, 'reviewed_revision': row['revision'], 'plan_digest': current['digest'], 'risk': row['risk'], 'impact': row['matches'], 'timestamp': time.time(), 'detail_reviewed': detail_reviewed}
                result.append(self._write('RULE', row['id'], record, row['revision'], 'rule_'+action.lower()))
            return result
