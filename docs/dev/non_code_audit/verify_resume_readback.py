"""Reconstruct bounded handoff from genuinely fetched Git objects, without chat."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--proof', type=Path, required=True)
a = p.parse_args()
proof = json.loads(a.proof.read_text())
assert proof['method'] == 'NATIVE_AUTHENTICATED_GIT_FETCH_INDEPENDENT_BARE_REPOSITORY'
bare = Path(json.loads(Path('/tmp/template-ai-current-readback-location.json').read_text())['git_dir'])
assert not (bare / 'objects/info/alternates').exists()
head = proof['snapshot_commit']
def remote(path):
    return subprocess.check_output(['git', '--git-dir', str(bare), 'show', head + ':' + path])
def load(path):
    return json.loads(remote(path))
state = load('docs/dev/STATE.json')
receipt = load(state['last_confirmed_checkpoint'])
assert receipt['phase'] == 'REMOTE_VERIFIED'
run = load(state['latest_evidence_run'])
tests_path = str(Path(state['latest_evidence_run']).parent / 'tests.json')
tests_raw = remote(tests_path)
assert hashlib.sha256(tests_raw).hexdigest() == run['tests_sha256']
tests = json.loads(tests_raw)
assert len(tests) == 1942 and all(r['status'] == 'PASS' for r in tests)
assert run['software_execution_status'] == 'PASS'
requirements = load('docs/dev/REQUIREMENTS.json')['requirements']
assert len(requirements) == 172
assert sum(len(r['acceptance']) for r in requirements) == 825
summary = dict(branch=state['working_branch'], active_task=state['active_task'],
               last_confirmed_commit=state['last_confirmed_commit'], checkpoint=state['last_confirmed_checkpoint'],
               latest_evidence=state['latest_evidence_run'], next_tasks=state['next_tasks'],
               pending_remote=state['pending_remote'], test_count=1942,
               overall_run_status=run['status'], software_execution=run['software_execution_status'],
               original_external_requirements_retained=[r['id'] for r in requirements if r['status'] in ('PARTIAL', 'DEFERRED')])
assert summary['last_confirmed_commit'] == receipt['snapshot_commit']
assert summary['branch'] == 'dev/v0.1-first-version' and summary['next_tasks']
paths = ['AGENTS.md', 'docs/dev/STATE.json', 'docs/dev/ACTIVE_DEVELOPMENT_HANDOFF.md',
         state['active_contract'], state['last_confirmed_checkpoint'], state['latest_evidence_run']]
rows = [dict(path=path, sha256=hashlib.sha256(remote(path)).hexdigest()) for path in paths]
out = ROOT / 'docs/dev/non_code_audit/execution-001/recovery-readback.json'
report = dict(status='PASS', method='FRESH_INDEPENDENT_GIT_OBJECT_READBACK_BOUNDED_HANDOFF',
              fetched_snapshot=head, remote_proof=proof, files=rows, reconstructed_summary=summary,
              full_chat_required=False, private_data_required=False, production_launch_performed=False,
              limits='Handoff reconstruction, not a full independent product installation or novice qualification. Pending checkpoints remain pending as recorded at this snapshot.')
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(status='PASS', snapshot=head, bounded_handoff_files=len(paths), tests_verified=1942)))
