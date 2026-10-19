"""Conditioned profiles and variable grammar learned from shared family members.

Observations, inferred support and runtime policy are separate. A measured joint
configuration is not an independent min/max rectangle or permission to swap.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import math
from statistics import median

from .training_store import digest
from .design_family import number, source_point

VERSION = 'cross-work-profiles-1'


def role_key(field):
    owner = field['owner']
    if not isinstance(owner, str) or not owner or len(owner) > 128:
        raise ValueError('Profile field requires an explicit owner port')
    return owner+':'+field['kind']+':'+str(field.get('index', 0))


def summary(values):
    values = [number(value) for value in values if value is not None]
    if not values:
        return dict(status='UNKNOWN', support=0, centre=None, mad=None, observed_min=None, observed_max=None)
    centre = median(values)
    return dict(status='OBSERVED_DISTRIBUTION_NOT_HARD_CAPACITY', support=len(values),
                centre=centre, mad=median(abs(value-centre) for value in values),
                observed_min=min(values), observed_max=max(values))


def _metric(field, name, unit):
    row = field.get('source_typography', {}).get(name, {})
    if (row.get('status') in ('OBSERVED', 'DERIVED') and row.get('unit') == unit
            and row.get('evidence_refs') and row.get('value') is not None):
        return number(row['value'])
    return None


def _frame(field, example):
    r = field['rect']; w, h = example['width_mm'], example['height_mm']
    return [number(r['x'])/w, number(r['y'])/h, number(r['w'])/w, number(r['h'])/h]


def _container_key(field):
    binding = field.get('container_binding', {})
    if (binding.get('status') == 'CONFIRMED' and binding.get('evidence_refs')
            and isinstance(binding.get('key'), str) and 0 < len(binding['key']) <= 128):
        return binding['key'], 'CONFIRMED_SOURCE_CORRESPONDENCE'
    return role_key(field), 'ROLE_PORT_ONLY_NO_CROSS_TYPE_CONTAINER_CORRESPONDENCE'


def learn_profiles(family_artifact, examples):
    if digest({k: v for k, v in family_artifact.items() if k != 'digest'}) != family_artifact.get('digest'):
        raise ValueError('Family artifact digest differs')
    by_id = {row['id']: row for row in examples}
    if len(by_id) != len(examples) or any(row['role'] != 'TRAIN' for row in examples):
        raise ValueError('Rule fitting requires unique TRAIN observations only')
    result = []
    for family in family_artifact['families']:
        rows = [by_id[identity] for identity in family['members']]
        if len({row['lineage_group'] for row in rows}) < 5:
            raise ValueError('Shared profiles need independent family support')
        roles, data, containers, relations = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        counts, orders, dimensions = [], [], []
        for example in rows:
            dimensions.append((example['width_mm'], example['height_mm']))
            seen = set(); row_counts = Counter(); ordered = []
            for field in example['fields']:
                key = role_key(field)
                if key in seen:
                    raise ValueError('Duplicate role/owner/index in a work observation')
                seen.add(key); frame = _frame(field, example); row_counts[field['owner']+':'+field['kind']] += 1
                semantic = field.get('semantic_type') or field['kind']
                container, basis = _container_key(field)
                point = source_point(field)
                metrics = dict(source_pt=point, horizontal_scale=_metric(field, 'horizontal_scale', 'ratio'),
                    tracking_mm=_metric(field, 'tracking', 'mm'), shaped_advance_mm=_metric(field, 'shaped_advance', 'mm'),
                    frame_width_mm=number(field['rect']['w']), frame_height_mm=number(field['rect']['h']))
                item = dict(example_id=example['id'], lineage_group=example['lineage_group'],
                    role_key=key, kind=field['kind'], owner_port=field['owner'], semantic_type=semantic,
                    frame=frame, source_font_ref=field.get('source_typography', {}).get('font_asset_ref'),
                    align=field.get('source_alignment', 'UNKNOWN'),
                    distribution=field.get('source_distribution', 'UNKNOWN'),
                    label_binding=deepcopy(field.get('label_binding', {'status':'UNKNOWN'})),
                    icon_binding=deepcopy(field.get('icon_binding', {'status':'UNKNOWN'})),
                    container_basis=basis, joint=metrics,
                    grapheme_count=field.get('measured_grapheme_count'),
                    dimensions_mm=[example['width_mm'], example['height_mm']])
                roles[key].append(item); data[semantic].append(item); containers[container].append(item)
                ordered.append((frame[1], frame[0], key))
            counts.append(dict(row_counts)); orders.append(tuple(value[2] for value in sorted(ordered)))
            # Relative observations retain real residuals. No guessed print tolerance.
            fields = {role_key(field):field for field in example['fields']}
            if len(fields) > 64:
                raise ValueError('Pair-relation processing budget exceeded; not truncated')
            for left in sorted(fields):
                for right in sorted(fields):
                    if left >= right:
                        continue
                    a, b = _frame(fields[left], example), _frame(fields[right], example)
                    relations[(left, right)].append(dict(
                        dx=b[0]-a[0], dy=b[1]-a[1], left_delta=b[0]-a[0],
                        right_delta=b[0]+b[2]-a[0]-a[2],
                        centre_delta=b[0]+b[2]/2-a[0]-a[2]/2,
                        vertical_gap=b[1]-a[1]-a[3], horizontal_gap=b[0]-a[0]-a[2]))
        role_profiles = []
        for key, samples in sorted(roles.items()):
            normalized = list(zip(*(sample['frame'] for sample in samples)))
            configurations = {digest(sample['joint']):sample['joint'] for sample in samples}
            role_profiles.append(dict(key=key, kind=samples[0]['kind'], owner_port=samples[0]['owner_port'],
                support=len({sample['lineage_group'] for sample in samples}),
                present_examples=len(samples), observed_optional=len(samples)<len(rows),
                frame_centre=[median(column) for column in normalized],
                frame_distributions=[summary(column) for column in normalized],
                joint_configurations=[configurations[k] for k in sorted(configurations)],
                joint_region='OBSERVED_CONFIGURATIONS_NOT_INDEPENDENT_MINMAX',
                typography_known_examples=sum(sample['joint']['source_pt'] is not None for sample in samples),
                font_identity_known_examples=sum(sample['source_font_ref'] is not None for sample in samples),
                admission='REQUIRES_POLICY_AND_ACTUAL_LAYOUT_VERIFICATION'))
        data_profiles = []
        for semantic, samples in sorted(data.items()):
            data_profiles.append(dict(semantic_type=semantic, family_id=family['id'],
                support=len({sample['lineage_group'] for sample in samples}),
                conditions='FAMILY_SIZE_OWNER_ROLE_FONT_AND_JOINT_CONFIGURATION',
                measured_graphemes=summary(sample['grapheme_count'] for sample in samples),
                measured_advance_mm=summary(sample['joint']['shaped_advance_mm'] for sample in samples),
                presentation_evidence=deepcopy(samples), recommended_region='NOT_CALIBRATED',
                validated_admission=None))
        field_profiles = []
        for container, samples in sorted(containers.items()):
            field_profiles.append(dict(family_id=family['id'], container_key=container,
                observed_semantic_types=sorted({sample['semantic_type'] for sample in samples}),
                owner_ports=sorted({sample['owner_port'] for sample in samples}),
                correspondence_basis=sorted({sample['container_basis'] for sample in samples}),
                label_bindings=[sample['label_binding'] for sample in samples],
                icon_bindings=[sample['icon_binding'] for sample in samples],
                joint_occupations=[sample['joint'] for sample in samples],
                support=len({sample['lineage_group'] for sample in samples}),
                transformation_permission='NOT_GRANTED_BY_OBSERVATION', validated_admission=None))
        relation_profiles = [dict(left=key[0], right=key[1], support=len(samples),
            residuals={metric:summary(sample[metric] for sample in samples) for metric in samples[0]},
            hard_alignment='NOT_INFERRED_FROM_UNCALIBRATED_TOLERANCE')
            for key, samples in sorted(relations.items())]
        order_counts = Counter(orders)
        preferred = sorted(order_counts, key=lambda order:(-order_counts[order], order))[0]
        repeat_keys = sorted({key for row in counts for key in row})
        repeat = {key:dict(observed_counts=sorted({row.get(key, 0) for row in counts}),
                          validated_capacity=None, training_max_is_not_global_limit=True) for key in repeat_keys}
        result.append(dict(family_id=family['id'], independent_support=family['independent_support'],
            observed_dimensions_mm=sorted(set(dimensions)), roles=role_profiles,
            data_requirement_profiles=data_profiles, field_capability_profiles=field_profiles,
            relations=relation_profiles, grammar=dict(optional_roles=[r['key'] for r in role_profiles if r['observed_optional']],
                repeated_groups=repeat, observed_orders=[dict(order=list(order), count=order_counts[order]) for order in sorted(order_counts)],
                default_order=list(preferred), default_basis='CONDITIONAL_TRAIN_FREQUENCY_THEN_STABLE_ROLE_ORDER',
                default_is_not_aesthetic_truth=True),
            source_members=family['members'], policy_status='PENDING_EXPLICIT_ACTIVATION',
            runtime_capacity='NOT_CALIBRATED'))
    artifact = dict(version=VERSION, family_digest=family_artifact['digest'], families=result,
                    scope='SHARED_PROFILES_AND_GRAMMAR_NOT_PRODUCTION_APPROVAL')
    artifact['digest'] = digest(artifact)
    return artifact


def conditional_match(data, capability, context, policy, *, measured_feasibility=None):
    """No geometry-only or one-way match grants an unchecked bidirectional swap."""
    conditions = ('family_id', 'owner_port', 'font_policy_version', 'asset_version')
    if any(key not in context for key in conditions):
        raise ValueError('Conditional match context is incomplete')
    semantic = data['semantic_type']; supported = semantic in capability['observed_semantic_types']
    family_matches = context['family_id'] == capability['family_id'] == data['family_id']
    ownership = context['owner_port'] in capability['owner_ports']
    label_known = bool(capability['label_bindings']) and all(
        binding.get('status') == 'CONFIRMED' for binding in capability['label_bindings'])
    permitted = (family_matches and policy.get('approved') is True
                 and semantic in policy.get('allowed_types', []) and ownership)
    if measured_feasibility not in (None, 'VERIFIED_FEASIBLE', 'VERIFIED_INFEASIBLE', 'NOT_EVALUATED', 'UNKNOWN'):
        raise ValueError('Unknown feasibility state')
    return dict(evidence_status='SUPPORTED' if supported else 'UNKNOWN',
        policy_status='ALLOWED' if permitted and label_known else 'FORBIDDEN' if not ownership or not family_matches else 'UNKNOWN',
        feasibility_status=measured_feasibility or 'NOT_EVALUATED', conditions=deepcopy(context),
        label_binding_status='CONFIRMED' if label_known else 'UNKNOWN',
        trace=dict(family=context['family_id'], container=capability['container_key'],
                   source_support=capability['support'], policy_version=policy.get('version')))
