"""Adopt only a complete current-source run; never grant Windows/EXE qualification."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from dev_common import read_json, write_json
from dev_governance import verify_run, verify_acceptance, execution_passed, test_ids, render

RUN = 'docs/evidence/runs/RUN-IMPORT-ZERO-FIELDS-001/run.json'
PRIOR = 'docs/evidence/runs/RUN-BUNDLED-INKSCAPE-BETA2-004/tests.json'


def main():
    run, results = verify_run(ROOT, RUN)
    if not execution_passed(run, results) or set(results) != test_ids(ROOT) or len(results) != 1997:
        raise ValueError('Require all1997 actual current-source tests, original captures and no runtime failures')
    prior = {row['id'] for row in read_json(ROOT / PRIOR)}
    if len(prior) != 1986 or not prior <= set(results):
        raise ValueError('All original1986 cases must remain present and pass')
    registry = read_json(ROOT / 'docs/dev/REQUIREMENTS.json')
    completed = [row for row in registry['requirements'] if row['completed']]
    if len(registry['requirements']) != 172 or len(completed) != 166:
        raise ValueError('No requirement scope/count changes authorized')
    claims = read_json(ROOT / Path(RUN).parent / 'claims.json')
    for row in completed:
        verify_acceptance(row, run, results, claims)
    for row in completed:
        row['evidence_run'] = RUN
    report = dict(status='LOCAL_SOURCE_QUALIFIED_NOT_WINDOWS_OR_EXE_RELEASED',
                  source_commit=run['source_commit'], source_manifest_sha256=run['source_manifest_sha256'],
                  formal_run=RUN, actual_tests=len(results), original_preserved=len(prior),
                  added_test_ids=sorted(set(results) - prior), runtime_errors=run['unhandled_runtime_errors'],
                  capture_exit_code=run['capture_exit_code'], requirements=172, completed_scoped=166,
                  goal_status=run['status'], windows_verified=False, exe_verified=False,
                  published_product_unchanged='v0.2.0-beta.2',
                  external_qualifications='Original private-corpus/hardware/print/novice/disconnect qualifications unchanged')
    write_json(ROOT / 'docs/dev/bugfixes/import-zero-fields-20261023/source-qualification.json', report)
    write_json(ROOT / 'docs/dev/REQUIREMENTS.json', registry)
    state = read_json(ROOT / 'docs/dev/STATE.json')
    state['latest_evidence_run'] = RUN
    state['active_task'] = 'ZERO_FIELDS_SOURCE_FIXED_STARTUP_ANALYZED'
    issue = state['import_zero_fields_bugfix']
    issue['status'] = 'LOCAL_SOURCE_QUALIFIED_NO_NEW_WINDOWS_EXE_RELEASE'
    issue['source_qualification'] = 'docs/dev/bugfixes/import-zero-fields-20261023/source-qualification.json'
    issue['full_run'].update(status='LOCAL_CURRENT_SOURCE_QUALIFIED', tests=len(results))
    state['next_tasks'] = [
        'User can start current200-source PREFLIGHT via confirm/start button; this stage has not analysed files yet.',
        'Before a separately authorized new Release: review/include the new11-case regression module in the Windows scope; run Windows, actual EXE and real download checks on the new source/version.',
        'Startup early visibility/failure and local phase timings remain unimplemented; actual Windows bottleneck unmeasured. See STARTUP_FINDINGS.',
    ]
    write_json(ROOT / 'docs/dev/STATE.json', state)
    render(ROOT)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
