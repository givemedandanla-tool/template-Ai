"""Current evidence references for coverage; never creates facts, styles or rules."""
import json
from .training_store import digest

LAYERS = ('native_or_ocr', 'people', 'companies', 'whole_logo', 'fields', 'customer', 'styles')
HIGH_RISK = {'people', 'companies', 'whole_logo', 'fields', 'customer', 'styles'}


def table_exists(db, name):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def bounded_rows(db, query, args=(), maximum=2000):
    rows = db.execute(query+' LIMIT ?', (*args, maximum+1)).fetchall()
    if len(rows)>maximum: raise ValueError('證據超過有界核對範圍，需明確分組；未截斷當完整')
    return [list(row) for row in rows]


def work_context(service, work_id):
    """Pins actual source/facts/rules/ownership/style versions, including absence."""
    store, db = service.store, service.db
    work = service.library.artwork(work_id); facts = store.facts(work_id)
    slots = work['payload'].get('slots', [])
    associations = []
    if table_exists(db, 'customer_source_associations'):
        associations = bounded_rows(db, 'SELECT id,customer_id,source_id,artwork_id,template_id,source_hash,artwork_revision,template_hash,person_scope,candidate_id FROM customer_source_associations WHERE artwork_id=? ORDER BY id', (work_id,))
    owners, styles, templates = [], [], []
    for customer_id in sorted({row[1] for row in associations}):
        owners += bounded_rows(db, 'SELECT id,code,name,revision FROM customers WHERE id=?', (customer_id,))
        styles += bounded_rows(db, 'SELECT id,customer_id,template_id,template_hash,width,height FROM customer_styles WHERE customer_id=? ORDER BY id', (customer_id,))
    template_ids = sorted({row[4] for row in associations}|{row[2] for row in styles})
    for template_id in template_ids:
        # Hash the entire exact template row instead of assuming its schema/version field.
        row = db.execute('SELECT * FROM templates WHERE id=?', (template_id,)).fetchone()
        templates.append(dict(id=template_id, row_digest=digest(list(row)) if row else None))
    active_rules = bounded_rows(db, "SELECT id,revision,payload FROM training_records WHERE kind='RULE' AND json_extract(payload,'$.state')='ACTIVE' ORDER BY id", maximum=200)
    related = bounded_rows(db, "SELECT kind,id,revision,payload FROM training_records WHERE (id=? OR json_extract(payload,'$.work_id')=?) AND kind IN ('FACTS','LOCAL_NOISE','HIT','SAMPLE','AUTO_UNIT','RULE_HINT','LABEL_REVIEW') ORDER BY kind,id", (work_id, work_id))
    active_model = store.get('SEMANTIC_ACTIVE','local-text')
    model = store.get('SEMANTIC_MODEL', active_model['model_id']) if active_model else None
    from .source_analysis import ANALYSER_VERSION
    context = dict(pins=store.pins(work_id), analyser_version=ANALYSER_VERSION, semantic_active_digest=digest(active_model), semantic_model_digest=digest(model), facts_digest=digest(facts), associations_digest=digest(associations), owners_digest=digest(owners), styles_digest=digest(styles), templates=templates, related_digest=digest(related), active_rule_versions=[dict(id=r[0], revision=r[1], payload_digest=digest(json.loads(r[2]))) for r in active_rules])
    confirmed = set((facts.get('confirmation') or {}).get('observation_ids', [])) if store.facts_state(work_id)=='CONFIRMED' else set()
    observations = facts.get('observations', [])
    missing = [o['id'] for o in observations if o['id'] not in confirmed]
    unobserved_slots = [slot['id'] for slot in slots if slot.get('id') not in {o.get('slot_id') for o in observations}]
    unresolved_observations = [o['id'] for o in observations if o.get('classification')=='UNKNOWN' or o.get('review',{}).get('state') in ('REJECTED','QUARANTINED')]
    people = sorted({str(slot.get('owner')) for slot in slots if slot.get('kind')=='name'})
    companies = sorted({str(slot.get('owner')) for slot in slots if slot.get('kind')=='company'})
    return dict(work_id=work_id, source_id=work['source_id'], revision=work['revision'], context=context, context_digest=digest(context), facts_state=store.facts_state(work_id), observation_count=len(observations), unconfirmed_observation_ids=missing, unobserved_slot_ids=unobserved_slots, unresolved_observation_ids=unresolved_observations, person_root_candidates=people, company_candidates=companies, whole_logo_candidates=sum(slot.get('kind')=='logo' for slot in slots), association_count=len(associations), style_version_count=len(styles), required_layers=list(LAYERS), automated_analysis_is_review=False)


def low_risk_rule_evidence(service, work_id):
    """Reuse only existing approved noise-rule decisions; never confidence thresholds."""
    result = []
    for decision in service.store.noise_decisions(work_id):
        if decision['state']=='EXCLUDED_RULE' and not decision['protected']:
            result.append(dict(observation_id=decision['observation_id'], rules=decision['rule_matches'], facts_revision=decision['facts_revision'], pins=decision['pins'], disposition='APPROVED_RULE_ANNOTATION_ONLY', counts_as_style_or_customer_approval=False))
    return result
