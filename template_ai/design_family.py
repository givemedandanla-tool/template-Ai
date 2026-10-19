"""Cross-work family candidates; IDs/strings are provenance, never fit features.

This module is fitted on TRAIN observations only. HDBSCAN is batch re-estimation,
not incremental fitting. Family membership/support is distinct from rule approval.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import math
from statistics import median

from .training_store import digest

VERSION = 'cross-work-family-1'
ROLES = ('name', 'title', 'company', 'phone', 'email', 'line', 'ig', 'address', 'logo')
FEATURES = ('aspect', 'object_count', 'occupied_area') + tuple(
    role+'_'+dimension for role in ROLES for dimension in ('count', 'x', 'y', 'w', 'h', 'pt'))
MAX_EXAMPLES = 10000


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Family features require finite measured numbers')
    return float(value)


def source_point(field):
    point = field.get('source_typography', {}).get('source_pt', {})
    if (point.get('status') in ('OBSERVED', 'DERIVED') and point.get('unit') == 'pt'
            and point.get('evidence_refs') and type(point.get('value')) in (int, float)
            and math.isfinite(point['value']) and point['value'] > 0):
        return point['value']
    return None


def feature_vector(example):
    """Layout features exclude private text, identifiers and default typography."""
    width, height = number(example['width_mm']), number(example['height_mm'])
    if width <= 0 or height <= 0 or not 1 <= len(example['fields']) <= 512:
        raise ValueError('Invalid observation dimensions or bounded field count')
    grouped = defaultdict(list); area = 0
    for field in example['fields']:
        role = field['kind']
        if role not in ROLES:
            raise ValueError('Unknown typed field role')
        rect = field['rect']; x, y, w, h = (number(rect[k]) for k in ('x', 'y', 'w', 'h'))
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > width+1e-6 or y+h > height+1e-6:
            raise ValueError('Source observation is not an in-page field frame')
        grouped[role].append((x/width, y/height, w/width, h/height, source_point(field)))
        area += w*h/(width*height)
    values = [width/height, float(len(example['fields'])), area]
    for role in ROLES:
        rows = grouped[role]; values.append(float(len(rows)))
        values.extend(median(row[i] for row in rows) if rows else None for i in range(4))
        points = [row[4] for row in rows if row[4] is not None]
        values.append(median(points) if points else None)
    return values


def project(values, preprocessing):
    if len(values) != len(FEATURES):
        raise ValueError('Feature schema does not match trained artifact')
    result = []
    for value, centre, scale in zip(values, preprocessing['centres'], preprocessing['scales']):
        result.append((number(value)-centre)/scale if value is not None else 0.)
    result.extend(float(value is None) for value in values)
    return result


def train_families(examples, settings=None, previous=None):
    import numpy as np
    import sklearn
    from sklearn.cluster import HDBSCAN
    settings = deepcopy(settings or {})
    allowed = {'min_independent_support', 'min_cluster_size', 'min_samples', 'cluster_selection_epsilon'}
    if set(settings)-allowed:
        raise ValueError('Unknown family hyperparameter')
    configuration = dict(min_independent_support=5, min_cluster_size=5, min_samples=2,
                         cluster_selection_epsilon=0.)
    configuration.update(settings)
    for key in ('min_independent_support', 'min_cluster_size', 'min_samples'):
        if type(configuration[key]) is not int or not 2 <= configuration[key] <= 10000:
            raise ValueError('Invalid family integer hyperparameter')
    if configuration['min_independent_support'] < 5:
        raise ValueError('Retained contract requires five independent lineages per supported family')
    epsilon = number(configuration['cluster_selection_epsilon'])
    if epsilon < 0:
        raise ValueError('Negative family distance threshold')
    if not isinstance(examples, list) or not 1 <= len(examples) <= MAX_EXAMPLES:
        raise ValueError('Need a bounded nonempty TRAIN corpus')
    if len({e['id'] for e in examples}) != len(examples):
        raise ValueError('Repeated example identity')
    if any(e.get('role') != 'TRAIN' or not e.get('lineage_group') for e in examples):
        raise ValueError('Fitting requires explicit TRAIN role and lineage; no heldout access')

    ordered = sorted(examples, key=lambda row: row['id'])
    vectors = {e['id']: feature_vector(e) for e in ordered}
    # Identical observations from the same correlated group do not add density.
    independent_rows, aliases, exact_seen = [], {}, {}
    for example in ordered:
        signature = digest([example['lineage_group'], vectors[example['id']]])
        if signature in exact_seen:
            aliases[example['id']] = exact_seen[signature]
        else:
            exact_seen[signature] = example['id']; independent_rows.append(example)
    raw = [vectors[e['id']] for e in independent_rows]
    centres, scales = [], []
    for column in zip(*raw):
        known = [v for v in column if v is not None]
        centre = median(known) if known else 0.
        q1, q3 = np.quantile(known, [.25, .75]).tolist() if known else (0., 0.)
        centres.append(float(centre)); scales.append(float(q3-q1) if q3-q1 > 1e-9 else 1.)
    preprocessing = dict(centres=centres, scales=scales, missing='TRAIN_MEDIAN_PLUS_EXPLICIT_MASK')
    matrix = np.asarray([project(row, preprocessing) for row in raw])
    if len(independent_rows) < configuration['min_cluster_size']:
        labels = [-1]*len(independent_rows)
    else:
        labels = HDBSCAN(min_cluster_size=configuration['min_cluster_size'],
            min_samples=min(configuration['min_samples'], len(independent_rows)),
            cluster_selection_epsilon=epsilon, allow_single_cluster=True, n_jobs=1).fit_predict(matrix).tolist()

    by_label, assignment, unclassified = defaultdict(list), {}, []
    for example, label in zip(independent_rows, labels):
        by_label[label].append(example)
    families = []
    for label, rows in sorted(by_label.items()):
        groups = sorted({row['lineage_group'] for row in rows})
        if label == -1 or len(groups) < configuration['min_independent_support']:
            reason = 'DENSITY_UNCLASSIFIED' if label == -1 else 'INSUFFICIENT_INDEPENDENT_SUPPORT'
            for row in rows:
                assignment[row['id']] = None
                unclassified.append(dict(example_id=row['id'], reason=reason, qualified_style_not_discarded=True))
            continue
        members = sorted(row['id'] for row in rows)
        identity = 'family-'+digest([VERSION, groups, members])[:32]
        member_vectors = [project(vectors[row['id']], preprocessing) for row in rows]
        centre = [float(median(column)) for column in zip(*member_vectors)]
        distances = [math.dist(vector, centre) for vector in member_vectors]
        families.append(dict(id=identity, members=members, independent_lineages=groups,
            independent_support=len(groups), feature_centre=centre,
            observed_distance_max=max(distances), admission='NOT_CALIBRATED_NOT_POLICY_APPROVAL',
            labels_count=dict(Counter(f['kind'] for row in rows for f in row['fields']))))
        for row in rows:
            assignment[row['id']] = identity
    for alias, representative in aliases.items():
        assignment[alias] = assignment[representative]
        if assignment[alias] is None:
            unclassified.append(dict(example_id=alias, reason='CORRELATED_REPEAT_UNCLASSIFIED',
                                     qualified_style_not_discarded=True))
    correspondence = []
    if previous:
        for family in families:
            for old in previous['families']:
                a, b = set(family['members']), set(old['members'])
                overlap = len(a & b)/len(a | b) if a | b else 0.
                if overlap:
                    correspondence.append(dict(previous_id=old['id'], current_id=family['id'],
                                               member_jaccard=overlap, identity_merge='NOT_AUTOMATIC'))
    artifact = dict(version=VERSION, algorithm='sklearn.HDBSCAN_BATCH_REESTIMATION',
        sklearn_version=sklearn.__version__, settings=configuration, features=list(FEATURES),
        preprocessing=preprocessing, families=sorted(families, key=lambda row: row['id']),
        assignment=assignment, correlated_repeat_aliases=aliases,
        unclassified=sorted(unclassified, key=lambda row: row['example_id']),
        previous_membership_correspondence=correspondence,
        training_example_ids=sorted(assignment), independent_group_count=len({e['lineage_group'] for e in examples}),
        actual_template_objects_created=0, scope='FAMILY_CANDIDATES_NOT_RULE_ACTIVATION_OR_PRODUCTION_QUALIFICATION')
    artifact['digest'] = digest(artifact)
    return artifact
