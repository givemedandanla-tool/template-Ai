"""Read-only learned-family projections and local, versioned review worksets.

The existing TrainingStore remains the authority. A family row is not a new
global Template, and an observation is never a publication permission.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import math

from .design_learning import CrossWorkLearning
from .training_store import TrainingStore, digest, text
from .model import new_id


def records(store, kind):
    """Walk the existing bounded API without silently stopping at 200 rows."""
    offset = 0
    while True:
        page = store.records(kind, offset=offset, limit=200)
        yield from page
        if len(page) < 200:
            return
        offset += len(page)


def reference(model, profile):
    return dict(model_id=model['id'], model_revision=model['revision'],
                weights_digest=model['weights_digest'], manifest_digest=model['manifest_digest'],
                family_id=profile['family_id'], family_digest=digest(profile))


def validate_query(query):
    allowed = {'text', 'semantic', 'health', 'model_id', 'min_support', 'size',
               'people', 'field_count', 'has_unknown'}
    if not isinstance(query, dict) or set(query)-allowed:
        raise ValueError('Unsupported family search conditions')
    result = deepcopy(query)
    for key in ('text', 'semantic', 'model_id'):
        if key in result and (not isinstance(result[key], str) or len(result[key]) > 512):
            raise ValueError('Invalid search text')
    if result.get('health') not in (None, 'READY_PREVIEW', 'QUALIFIED', 'UNKNOWN', 'STALE'):
        raise ValueError('Unknown family health filter')
    for key in ('min_support', 'people', 'field_count'):
        if key in result and (type(result[key]) is not int or result[key] < 0):
            raise ValueError('Invalid numeric family filter')
    if 'has_unknown' in result and type(result['has_unknown']) is not bool:
        raise ValueError('Unknown-information filter must be boolean')
    if 'size' in result:
        size = result['size']
        if (not isinstance(size, list) or len(size) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 2000 for v in size)):
            raise ValueError('Physical size needs two positive millimetre values')
    return result


def profile_summary(profile):
    roles = profile['roles']
    unknown = sum(r.get('typography_known_examples', 0) < r.get('present_examples', 0)
                  or r.get('font_identity_known_examples', 0) < r.get('present_examples', 0)
                  for r in roles if r['kind'] != 'logo')
    patterns = profile['grammar'].get('observed_joint_counts', [])
    counts = sorted({sum(row['pattern'].values()) for row in patterns})
    people = sorted({r['owner_port'] for r in roles if r['owner_port'].startswith('p')})
    return dict(independent_support=profile['independent_support'],
                sizes=deepcopy(profile['observed_dimensions_mm']),
                semantic_types=sorted({r['semantic_type'] for r in profile['data_requirement_profiles']}),
                people=len(people), field_counts=counts, unknown_roles=unknown,
                role_count=len(roles), source_count=len(profile['source_members']))


def profile_differences(left, right):
    """Functional differences, including rule evidence, rather than JSON order."""
    groups = ('roles', 'data_requirement_profiles', 'field_capability_profiles', 'relations',
              'conditional_geometry', 'grammar', 'object_spacing_rules', 'observed_dimensions_mm',
              'editor_relation_strengths', 'editor_container_types', 'editor_preferred_sources')
    return [dict(section=key, before=deepcopy(left.get(key)), after=deepcopy(right.get(key)))
            for key in groups if digest(left.get(key)) != digest(right.get(key))]


class FamilyWorkspace:
    def __init__(self, library):
        self.library = library
        self.store = TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)
        self.learning = CrossWorkLearning(library)

    def resolve(self, ref):
        if not isinstance(ref, dict):
            raise ValueError('An exact family reference is required')
        model, dataset = self.learning.checked_model(ref.get('model_id', 'missing'))
        profile = next((p for p in model['artifact']['profile_model']['families']
                        if p['family_id'] == ref.get('family_id')), None)
        if profile is None or reference(model, profile) != ref:
            raise ValueError('Family/model/source version is stale; reload before editing')
        return model, dataset, deepcopy(profile)

    def index(self, query=None, *, page=0, page_size=48):
        query = validate_query(query or {})
        if type(page) is not int or page < 0 or type(page_size) is not int or not 1 <= page_size <= 200:
            raise ValueError('Invalid family page')
        matches = []
        health_counts = Counter()
        for model in records(self.store, 'DESIGN_MODEL'):
            if query.get('model_id') and model['id'] != query['model_id']:
                continue
            try:
                self.learning.checked_model(model['id'])
                valid, reason = True, None
            except (ValueError, KeyError, OSError) as error:
                valid, reason = False, str(error)
            qualified = False
            if valid and model.get('formal_qualification') == 'PASS':
                from .design_qualification import validate_certificate
                try:
                    validate_certificate(self.library, model)
                    qualified = True
                except (ValueError, KeyError, OSError):
                    pass
            for profile in model['artifact']['profile_model']['families']:
                summary = profile_summary(profile)
                health = ('STALE' if not valid else 'QUALIFIED' if qualified
                          else 'UNKNOWN' if summary['unknown_roles'] else 'READY_PREVIEW')
                row = dict(id=model['id']+':'+profile['family_id'], kind='LEARNED_FAMILY',
                           ref=reference(model, profile), health=health, issue=reason,
                           qualification=model.get('formal_qualification', 'NOT_EVALUATED'), **summary)
                tokens = query.get('text', '').casefold().split()
                haystack = ' '.join([row['id'], *summary['semantic_types'], health]).casefold()
                if any(token not in haystack for token in tokens):
                    continue
                if query.get('semantic') and query['semantic'] not in summary['semantic_types']:
                    continue
                if query.get('health') and query['health'] != health:
                    continue
                if summary['independent_support'] < query.get('min_support', 0):
                    continue
                if 'people' in query and summary['people'] != query['people']:
                    continue
                if 'field_count' in query and query['field_count'] not in summary['field_counts']:
                    continue
                if 'has_unknown' in query and bool(summary['unknown_roles']) != query['has_unknown']:
                    continue
                if 'size' in query and not any(list(s) == query['size'] for s in summary['sizes']):
                    continue
                matches.append(row)
                health_counts[health] += 1
        matches.sort(key=lambda row: row['id'])
        start = page*page_size
        return dict(rows=matches[start:start+page_size], total=len(matches), page=page,
                    page_size=page_size, health_counts=dict(health_counts),
                    actual_template_objects_created=0)

    def save_view(self, name, query, actor, *, view_id=None, expected_revision=0):
        text(name, 'Workset name', 120); text(actor, 'Workset actor', 120)
        query = validate_query(query)
        with self.store.transaction():
            return self.store._write('FAMILY_VIEW', view_id or new_id(),
                                     dict(name=name, query=query, actor=actor), expected_revision,
                                     'family_dynamic_query_saved_not_frozen_batch_targets')

    def open_view(self, view_id, **paging):
        view = self.store.get('FAMILY_VIEW', view_id)
        if not view:
            raise ValueError('Saved workset is missing')
        return self.index(view['query'], **paging)

    def freeze_selection(self, refs):
        if not isinstance(refs, list) or not refs or len(refs) > 10000:
            raise ValueError('Explicit bounded family selection required')
        if len({digest(ref) for ref in refs}) != len(refs):
            raise ValueError('Duplicate family selection')
        for ref in refs:
            self.resolve(ref)
        return dict(refs=deepcopy(refs), digest=digest(refs), selection_kind='EXACT_VERSION_SNAPSHOT')

    def sources(self, ref):
        _, dataset, profile = self.resolve(ref)
        members = set(profile['source_members'])
        return [deepcopy(e) for e in dataset['entries'] if e['sample_id'] in members]

    def representatives(self, ref, budget=12):
        from .design_family import feature_vector, project
        if type(budget) is not int or not 1 <= budget <= 200:
            raise ValueError('Review budget must be1–200')
        model, dataset, profile = self.resolve(ref)
        members = set(profile['source_members'])
        examples = [e for e in dataset['manifest']['examples'] if e['id'] in members and e['role'] == 'TRAIN']
        examples.sort(key=lambda e: e['id'])
        strata = defaultdict(list)
        vectors = {}
        for example in examples:
            pattern = tuple(sorted(Counter(f['owner']+':'+f['kind'] for f in example['fields']).items()))
            strata[(example['width_mm'], example['height_mm'], pattern)].append(example)
            vectors[example['id']] = project(feature_vector(example), model['artifact']['family_model']['preprocessing'])
        centre = model['artifact']['family_model']['families']
        centre = next(r['feature_centre'] for r in centre if r['id'] == profile['family_id'])
        selected, used_lineages, covered = [], set(), set()
        def choose(example, reason, stratum):
            selected.append(dict(example_id=example['id'], lineage_group=example['lineage_group'], reason=reason))
            used_lineages.add(example['lineage_group']); covered.add(stratum)
        for stratum, candidates in sorted(strata.items(), key=lambda pair: (len(pair[1]), pair[0])):
            options = [e for e in candidates if e['lineage_group'] not in used_lineages]
            if len(selected) >= budget:
                break
            if options:
                example = min(options, key=lambda e: (math.dist(vectors[e['id']], centre), e['id']))
                choose(example, 'STRATIFIED_RARE_AND_CENTRAL', stratum)
        while len(selected) < budget:
            options = [e for e in examples if e['lineage_group'] not in used_lineages]
            if not options:
                break
            def distance(e):
                return min(math.dist(vectors[e['id']], vectors[s['example_id']]) for s in selected) if selected else 0.
            example = min(options, key=lambda e: (-distance(e), e['id']))
            choose(example, 'DISTANT_BOUNDARY', None)
        return dict(selected=selected, stratum_count=len(strata), uncovered_strata=max(0, len(strata)-len(covered-{None})),
                    independent_groups=len(used_lineages), role='TRAIN', aesthetic_qualification=False,
                    full_impacted_hard_checks_required=True)

    def compare(self, left_ref, right_ref):
        _, _, left = self.resolve(left_ref); _, _, right = self.resolve(right_ref)
        return dict(left=left_ref, right=right_ref, differences=profile_differences(left, right),
                    auto_merge=False, source_members_preserved=True)

    def impact(self, ref, *, source_hashes=None, page=0, page_size=100):
        """Source changes affect every model using that source, not just one family."""
        _, dataset, _ = self.resolve(ref)
        if type(page) is not int or page < 0 or type(page_size) is not int or not 1 <= page_size <= 200:
            raise ValueError('Invalid impact page')
        hashes = set(source_hashes or [])
        if not hashes <= {e['source_hash'] for e in dataset['entries']}:
            raise ValueError('Impact source is outside the pinned model')
        model_ids = {ref['model_id']}
        if hashes:
            for model in records(self.store, 'DESIGN_MODEL'):
                data = self.store.get('DATASET', model['dataset_id'])
                if data and any(e['source_hash'] in hashes for e in data['entries']):
                    model_ids.add(model['id'])
        rows = []
        kinds = ('DESIGN_MODEL', 'DESIGN_SESSION', 'DESIGN_INSTANCE', 'DESIGN_ACCEPTED_ARTIFACT',
                 'FAMILY_DRAFT', 'FAMILY_CASE', 'FAMILY_RUN', 'DESIGN_QUALIFICATION', 'DESIGN_JOB_PLAN')
        for kind in kinds:
            for row in records(self.store, kind):
                linked = {row.get('model_id'), row.get('base_ref', {}).get('model_id'),
                          row.get('reference', {}).get('model_id'), row.get('ref', {}).get('model_id'),
                          row.get('plan', {}).get('model_id')}
                linked.update(item.get('ref', {}).get('model_id') for item in row.get('plan', {}).get('items', []))
                if (kind == 'DESIGN_MODEL' and row['id'] in model_ids) or linked & model_ids:
                    rows.append(dict(kind=kind, id=row['id'], revision=row['revision'],
                                     action='KEEP_EXACT_BYTES_RECHECK_RIGHTS' if kind == 'DESIGN_ACCEPTED_ARTIFACT' else 'RECHECK_DEPENDENCIES'))
        rows.sort(key=lambda row: (row['kind'], row['id']))
        counts = dict(Counter(r['kind'] for r in rows))
        return dict(models=sorted(model_ids), counts=counts, total=len(rows), page=page,
                    rows=rows[page*page_size:(page+1)*page_size],
                    accepted_output_bytes_changed=False, auto_activation=False)
