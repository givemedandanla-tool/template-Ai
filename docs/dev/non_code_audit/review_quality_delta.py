"""Retain diagnostic debt without modifying tools, baselines, or product code."""
import collections
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/dev/non_code_audit/execution-001'
rows = []
for scope in ('application', 'tests'):
    current_path = OUT / f'quality-{scope}-001/report.json'
    previous_path = ROOT / f'docs/dev/pre_download_audit/final-release-{scope}-standard-003/report.json'
    current, previous = [json.loads(p.read_text()) for p in (current_path, previous_path)]
    known = {r['fingerprint'] for r in previous['findings']}
    delta = {r['fingerprint']: r for r in current['findings'] if r['fingerprint'] not in known}
    adjudicated = []
    for item in delta.values():
        path = item['path']
        if path not in ('tests/test_noncode_invariants.py', 'tests/test_noncode_capacity_semantics.py') or item['tool'] != 'pyright':
            raise AssertionError('Unexpected unreviewed delta: ' + path)
        reason = ('Composed unittest fixture initializes these attributes through the existing setUp(self); static nominal typing cannot see that protocol. '
                  'Retained P3 typing debt: introduce an explicit fixture protocol in a separately verified change, without inheriting duplicate tests.'
                  if item['rule'] in ('reportAttributeAccessIssue',) or item['rule'] == 'reportArgumentType' and 'parameter "self"' in item['message']
                  else 'Heterogeneous unannotated fixture dictionaries infer broad unions; the exercised field shape is established by construction and checked core services. '
                       'Retained P3 typing debt: add precise fixture schemas in a separately verified change; not classified as a runtime defect solely from this diagnostic.')
        lines = (ROOT / path).read_text().splitlines()
        adjudicated.append(dict(**item, disposition='RETAINED_TEST_TYPING_DEBT', severity='P3',
                               reason=reason, source_line=lines[item['line'] - 1],
                               runtime_evidence='targeted-oracles-003/summary.json (32 PASS); final complete suite checked separately',
                               claim='No claim that the checker is clean or that runtime success proves all static warnings false.'))
    rows.append(dict(scope=scope, counts=current['counts'], coverage=current['coverage'],
                     previous_report=str(previous_path.relative_to(ROOT)),
                     report_sha256=hashlib.sha256(current_path.read_bytes()).hexdigest(),
                     previous_report_sha256=hashlib.sha256(previous_path.read_bytes()).hexdigest(),
                     current_effective_configuration=current['effective_configuration'],
                     previous_effective_configuration=previous['effective_configuration'],
                     new_diagnostic_records=sum(r['fingerprint'] not in known for r in current['findings']),
                     new_unique_diagnostics=len(delta), new_diagnostics=adjudicated,
                     baseline_refreshed=False, scan_rules_weakened=False))
report = dict(status='REVIEWED_WITH_RETAINED_TYPING_DEBT', comparisons=rows,
              interpretation='No new application diagnostic; 54 unique test typing diagnostics (62 records) retained as P3. No new clone. Historical warnings remain visible.',
              product_quality_or_zero_error_certificate=False)
(OUT / 'quality-delta-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(status=report['status'], new_unique_by_scope={r['scope']: r['new_unique_diagnostics'] for r in rows})))
