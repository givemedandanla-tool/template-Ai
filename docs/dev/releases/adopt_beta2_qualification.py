"""Link completed original requirements to an actual, complete beta2 source run.

No results/claims are generated here. Existing governance validates every claim
before any requirement is changed. Full remote checkpoint verification remains
a separate mandatory operation before the publishing workflow.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT),str(ROOT/'tools')]
from dev_common import read_json, write_json
from dev_governance import verify_run, verify_acceptance, execution_passed, test_ids, render

RUN = 'docs/evidence/runs/RUN-BUNDLED-INKSCAPE-BETA2-003/run.json'
PRIOR = 'docs/evidence/runs/RUN-WINDOWS-BETA-FINAL-LINUX-001'


def main():
    run, results = verify_run(ROOT, RUN)
    if not execution_passed(run,results) or set(results) != test_ids(ROOT) or len(results) != 1986:
        raise ValueError('Actual full current-source execution must pass all1986 cases and original GUI captures')
    prior = {r['id'] for r in read_json(ROOT/PRIOR/'tests.json')}
    if len(prior) != 1963 or not prior <= set(results):
        raise ValueError('Original1963 test IDs must be preserved')
    registry = read_json(ROOT/'docs/dev/REQUIREMENTS.json')
    claims = read_json(ROOT/Path(RUN).parent/'claims.json')
    completed = [row for row in registry['requirements'] if row['completed']]
    if len(completed) != 166 or len(registry['requirements']) != 172:
        raise ValueError('This release cannot change adopted requirement counts')
    for row in completed:
        verify_acceptance(row,run,results,claims)
    for row in completed:
        row['evidence_run'] = RUN
    report = dict(status='LOCAL_SOURCE_QUALIFIED_PENDING_COMPLETE_REMOTE_CHECKPOINT',
         source_commit=run['source_commit'],source_manifest_sha256=run['source_manifest_sha256'],
         formal_run=RUN,actual_tests=len(results),original_preserved=len(prior),additional_tests=len(set(results)-prior),
         runtime_errors=run['unhandled_runtime_errors'],capture_exit_code=run['capture_exit_code'],
         requirements=172,completed_scoped_requirements=166,goal_status=run['status'],
         external_qualifications='Original private-corpus/hardware/print/novice/disconnect qualifications unchanged',
         scope='Source qualification only; native EXE and Release publication still separate')
    write_json(ROOT/'docs/dev/releases/v0.2.0-beta.2/source-qualification.json',report)
    write_json(ROOT/'docs/dev/REQUIREMENTS.json',registry)
    state = read_json(ROOT/'docs/dev/STATE.json')
    state['latest_evidence_run'] = RUN
    state['pending_release'].update(status='SOURCE_QUALIFIED_PENDING_FULL_REMOTE_CP_AND_FINAL_NATIVE_RELEASE',
         source_qualification='docs/dev/releases/v0.2.0-beta.2/source-qualification.json',
         next='Complete all-attachment checkpoint, exact remote readback, strict governance; final198-case native/EXE/source-assets/download verification.')
    write_json(ROOT/'docs/dev/STATE.json',state)
    render(ROOT)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
