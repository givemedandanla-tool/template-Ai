"""Cluster-level uncertainty; descriptive object counts never become IID samples."""
from collections import Counter, defaultdict

from .quality_gold import DOMAINS
from .quality_metrics import counts, wilson_interval


def aggregate(rows, manifest, policy):
    """One Bernoulli failure per related source group, regardless of object count.

    A group fails when any known applicable object fails. Unknown evidence is
    retained separately and prevents acceptance; it is never imputed as success.
    Empty target classes provide no positive-example evidence.
    """
    components = manifest['group_components']
    groups = {node.removeprefix('CONTENT:'): str(index)
              for index, component in enumerate(components)
              for node in component if node.startswith('CONTENT:')}
    critical = Counter()
    for row in rows:
        critical.update(row['evaluation']['critical_errors'])
    domains = {}
    for name in DOMAINS:
        threshold = policy['thresholds'][name]
        classes = threshold.get('required_classes', [None])
        evaluations = {}
        for kind in classes:
            totals = [0, 0, 0]
            buckets = defaultdict(lambda: dict(counts=[0, 0, 0], gold=0, errors=[]))
            unknown = []
            for row in rows:
                domain = row['evaluation']['domains'][name]
                group = groups.get(row.get('source_hash'))
                if domain['state'] != 'MEASURED_DESCRIPTIVE_ONLY' or group is None:
                    unknown.append(row.get('item_id', row.get('source_id')))
                    continue
                metric = domain.get('per_class', {}).get(kind) if kind is not None else domain.get('metrics')
                bucket = buckets[group]
                if name == 'physical_size':
                    bucket['gold'] += domain['required_gold']
                    bucket['errors'].extend(domain['errors_mm'])
                elif metric is not None:
                    values = [metric[key] for key in ('tp', 'fp', 'fn')]
                    for index, value in enumerate(values):
                        bucket['counts'][index] += value
                        totals[index] += value
                    bucket['gold'] += metric['tp'] + metric['fn']
                elif kind is None:
                    unknown.append(row.get('item_id', row.get('source_id')))
            positive_groups = sum(bucket['gold'] > 0 for bucket in buckets.values())
            applicable = [bucket for bucket in buckets.values()
                          if bucket['gold'] or bucket['counts'][1]]
            failures = sum(any(error > threshold['maximum_absolute_error_mm'] for error in bucket['errors'])
                           if name == 'physical_size' else bool(bucket['counts'][1] or bucket['counts'][2])
                           for bucket in applicable)
            interval = wilson_interval(failures, len(applicable), policy['confidence']) if applicable else None
            metric = counts(*totals) if name != 'physical_size' else None
            gold_count = sum(bucket['gold'] for bucket in buckets.values())
            sufficient = (not unknown and positive_groups >= threshold['minimum_independent_groups']
                          and gold_count >= threshold['minimum_gold_objects'])
            rates_ok = (name == 'physical_size' or
                        all(metric[key] is not None and metric[key] >= threshold['minimum_' + key]
                            for key in ('precision', 'recall')))
            accepted = bool(sufficient and rates_ok and interval is not None
                            and interval['upper'] <= threshold['maximum_group_failure_rate'])
            evaluations[kind or 'ALL'] = dict(
                state='PASS' if accepted else 'EVIDENCE_INSUFFICIENT' if not sufficient else 'FAILED_THRESHOLD',
                descriptive_counts=metric, gold_objects=gold_count,
                positive_independent_groups=positive_groups, applicable_independent_groups=len(applicable),
                failed_independent_groups=failures, failure_rate_interval=interval,
                unknown_source_units=unknown, required_policy=threshold,
                uncertainty_unit='WHOLE_RELATED_SOURCE_GROUP_NOT_OBJECT')
        domains[name] = dict(state='PASS' if all(e['state'] == 'PASS' for e in evaluations.values())
                             else 'EVIDENCE_INSUFFICIENT' if any(e['state'] == 'EVIDENCE_INSUFFICIENT' for e in evaluations.values())
                             else 'FAILED_THRESHOLD', classes=evaluations)
    observed_groups = {groups.get(row.get('source_hash')) for row in rows}
    missing_groups = sorted(set(groups.values()) - observed_groups)
    insufficient = (not manifest['independence_scope_ready'] or bool(missing_groups)
                    or any(d['state'] == 'EVIDENCE_INSUFFICIENT' for d in domains.values()))
    passed = not any(critical.values()) and not insufficient and all(d['state'] == 'PASS' for d in domains.values())
    return dict(domains=domains, critical_errors=dict(critical),
                quality_gate='FAILED_CRITICAL' if any(critical.values()) else 'EVIDENCE_INSUFFICIENT' if insufficient else 'PASS' if passed else 'FAILED_THRESHOLD',
                quality_pass=passed, required_independent_groups=manifest['independent_group_count'],
                required_source_units=len(rows), confidence=policy['confidence'],
                missing_independent_groups=missing_groups,
                confidence_scope='PER_DOMAIN_PER_CLASS_MARGINAL_NOT_SIMULTANEOUS',
                automatic_recommendation_allowed=False,
                policy_scope=policy['scope'], acceptance_is_not_publication=True)
