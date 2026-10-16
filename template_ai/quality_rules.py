"""Execute exact approved rule versions against predictions, never holdout facts."""
import copy
import json
from .training_store import digest


def snapshots(store,selection=None):
    if selection is None:
        rules,invalid=store.active_noise_rules()
        if invalid:raise ValueError('正式規則支持／反例證據失效，不能作已核對品質版本')
        return rules
    if not isinstance(selection,list) or len(selection)>200:raise ValueError('需明列最多200個exact已核准規則版本')
    result=[];seen=set()
    for reference in selection:
        if not isinstance(reference,dict) or set(reference)!={'id','revision'} or type(reference['revision']) is not int:raise ValueError('規則版本需實際id及整數revision，不能用自訂模型標籤')
        key=(reference['id'],reference['revision'])
        if key in seen:raise ValueError('規則版本不可重複')
        seen.add(key);current=store.get('RULE',key[0]);rule=current if current and current['revision']==key[1] else None
        if rule is None:
            row=store.db.execute("SELECT after_json FROM training_history WHERE kind='RULE' AND id=? AND revision=?",key).fetchone()
            if row:rule=dict(id=key[0],revision=key[1],**json.loads(row[0]))
        from .quality_repair_rules import STATE, checked
        if rule and rule['state']==STATE:rule=checked(store,*key)
        if not rule or rule['state'] not in ('ACTIVE',STATE) or rule['action'] not in ('KEEP','EXCLUDE'):raise ValueError('只能選有實際歷史核准憑證的規則，不執行pending／自填版本')
        if not rule.get('positive_examples') or not rule.get('counterexamples'):raise ValueError('規則缺少支持／反例')
        for ref in rule['positive_examples']+rule['counterexamples']:store.validate_ref(ref)
        result.append(rule)
    return sorted(result,key=lambda r:(r['id'],r['revision']))


def production_current(store,records):
    return all(digest(store.get('RULE',row['id']))==digest(row) and row['state']=='ACTIVE' for row in records)


def approved_for_quality_current(store, records):
    from .quality_repair_rules import STATE, checked
    for row in records:
        if digest(store.get('RULE',row['id']))!=digest(row):return False
        if row['state']=='ACTIVE':continue
        if row['state']!=STATE:return False
        try:checked(store,row['id'],row['revision'])
        except (ValueError, KeyError, OSError):return False
    return True


def evaluate(source,work,records):
    from .noise_review import scope_matches
    wrapper=dict(payload=work)
    for observation in work['observations']:
        matches=[r for r in records if scope_matches(r,wrapper,observation,source)]
        slot=next((s for s in work['slots'] if s['id']==observation.get('slot_id')),None)
        protected=(observation['classification'] in ('FIELD','LOGO','UNKNOWN') or observation['object_type'] in ('LOGO_PART','UNKNOWN') or bool(slot and slot['kind'] in ('name','company','logo')))
        # Source-only predictions carry no human confirmation. Executing the
        # existing policy therefore preserves annotations until that boundary
        # is met; gold answers are never used to grant it during inference.
        decision='KEPT_PROTECTED' if protected else 'KEPT_RULE_CONFLICT' if len({r['action'] for r in matches})>1 else 'KEPT_UNCONFIRMED_SOURCE_CONTEXT' if matches else 'KEPT_NO_MATCH'
        observation['rule_diagnostics']=dict(state=decision,protected=protected,
            matches=[dict(id=r['id'],revision=r['revision'],action=r['action'],classification_matched=observation['classification']==r['scope']['classification']) for r in matches],
            original_observation_retained=True,human_gold_used=False)
    work['evidence']['rule_execution']=dict(method='ACTUAL_FROZEN_SCOPE_MATCHES_AND_SOURCE_PROTECTION',rule_versions=[dict(id=r['id'],revision=r['revision']) for r in records],
                                           gold_context_used=False,raw_text_candidates_removed=0,unconfirmed_context_is_not_exclusion_authority=True)
    return work
