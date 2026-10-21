"""Package completed, source-identical executions; never invent or rerun results.

The existing governance verifier remains authoritative. Claim generation is
executed from the unchanged AST of tools/run_evidence.py, so its original
external qualifications and NOT_VERIFIED clauses remain intact.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from dev_common import contract_digest, digest, manifest, manifest_digest, read_json, write_json


def require(value, message):
    if not value:
        raise ValueError(message)


def checked_execution(folder, current):
    source = read_json(folder / 'source.json')
    summary = read_json(folder / 'summary.json')
    records = read_json(folder / 'tests.json')
    require(source['source_manifest'] == current, 'Execution source differs from current code')
    raw_hash = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    require(source['manifest_sha256'] == raw_hash, 'Original execution manifest hash mismatch')
    require(summary['software_execution'] == 'PASS', 'Execution was not PASS')
    require(summary['source_unchanged_during_run'] is True, 'Source changed during execution')
    require(summary['runtime_errors'] == 0, 'Unhandled runtime errors')
    expected = read_json(folder / 'catalog.json')
    ids = [r['id'] for r in records]
    require(bool(expected) and len(ids) == len(set(ids)), 'Empty or duplicate execution records')
    require(set(ids) == set(expected), 'Missing or extra test records')
    require(summary['planned'] == summary['completed'] == len(ids), 'Incomplete execution')
    require(source['expected'] == len(expected), 'Catalog count differs from source record')
    require(summary['healthy_modules'] == summary['modules'], 'Unhealthy test module')
    require(all(r['status'] == 'PASS' for r in records), 'Non-PASS test record')
    return source, summary, records


def generate_original_claims(folder, source_commit, records):
    """Reuse the existing claim/contract computation verbatim, without CLI fiction."""
    path = ROOT / 'tools/run_evidence.py'
    tree = ast.parse(path.read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    def assigns(node, name):
        return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    first = next(i for i, n in enumerate(main.body) if assigns(n, 'tests_lookup'))
    last = next(i for i, n in enumerate(main.body) if assigns(n, 'attachments'))
    block = ast.Module(body=main.body[first:last], type_ignores=[])
    env = dict(ROOT=ROOT, folder=folder, args=SimpleNamespace(source_commit=source_commit),
               records=records, status='PASS', source_unchanged=True, read_json=read_json,
               write_json=write_json, contract_digest=contract_digest)
    exec(compile(block, str(path), 'exec'), env)
    return env['status'], env['claims'], digest(path.read_bytes())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execution', type=Path, required=True)
    p.add_argument('--stock', type=Path, required=True)
    p.add_argument('--readback', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    a = p.parse_args()
    require(a.run_id.replace('-', '').isalnum(), 'Invalid run ID')
    current = manifest(ROOT, code_only=True)
    source, summary, records = checked_execution(a.execution, current)
    from dev_governance import test_ids
    require({r['id'] for r in records} == test_ids(ROOT), 'Formal adoption requires the full current catalog')
    require(summary['original_test_ids_preserved'] is True, 'Original catalog not preserved')
    commit, tree = read_json(a.readback / 'commit.json'), read_json(a.readback / 'tree.json')
    proof = read_json(a.readback / 'proof.json')
    require(proof['method'] == 'NATIVE_AUTHENTICATED_GIT_FETCH_INDEPENDENT_BARE_REPOSITORY', 'No native remote readback')
    require(commit['sha'] == proof['snapshot_commit'] and commit['tree']['sha'] == tree['sha'] and not tree.get('truncated'), 'Readback mismatch')
    remote = {r['path']: r['sha'] for r in tree['tree'] if r['type'] == 'blob'}
    require(all(remote.get(p) == info['git_blob_sha1'] for p, info in current.items()), 'Remote source differs')
    stock_source, stock = read_json(a.stock / 'source.json'), read_json(a.stock / 'summary.json')
    jobs = read_json(a.stock / 'jobs.json')
    require(stock_source['source_manifest'] == current and stock['source_unchanged'] is True, 'Capture source differs')
    require(stock['status'] == 'PASS' and stock['planned'] == stock['completed'] == stock['passed'] == 27, 'Incomplete original GUI captures')
    require(len(jobs) == 27 and all(r['status'] == 'PASS' and r['exit_code'] == 0 and not r['timed_out'] and not r['runtime_flags'] for r in jobs), 'Capture failure')
    workspace = Path(stock_source['workspace'])
    images = read_json(a.stock / 'image-manifest.json')
    require(bool(images), 'No actual capture images')
    require(all((workspace / p).is_file() and digest((workspace / p).read_bytes()) == h for p, h in images.items()), 'Capture image mismatch')
    folder = ROOT / 'docs/evidence/runs' / a.run_id
    folder.mkdir(exist_ok=False)
    for name in ('commit.json', 'tree.json', 'proof.json'):
        shutil.copyfile(a.readback / name, folder / name)
    write_json(folder / 'source-manifest.json', current)
    shutil.copyfile(a.execution / 'tests.json', folder / 'tests.json')
    shutil.copyfile(a.execution / 'summary.json', folder / 'execution-summary.json')
    shutil.copyfile(a.execution / 'source.json', folder / 'execution-source.json')
    module_inputs=[]
    if source.get('qualification_provenance'):
        require(source['qualification_provenance']=='module-revalidation.json','Unknown module qualification provenance')
        selection=read_json(a.execution/'module-revalidation.json')
        require(selection['kind']=='ACTUAL_SAME_SOURCE_MODULE_REVALIDATION_NOT_A_SINGLE_FRESH_FULL_ATTEMPT','Unknown qualification strategy')
        require(len(selection['inputs'])==2 and selection['initial_failed_attempt_preserved'],'Original failed attempt must remain visible')
        input_records={}
        required_files={'source.json','summary.json','tests.json','catalog.json','runtime-errors.json','live/test-modules.json'}
        for index,item in enumerate(selection['inputs']):
            origin=(ROOT/item['path']).resolve()
            require(origin.is_relative_to(ROOT/'docs/dev/releases'),'Module execution input outside release evidence')
            require(set(item['files'])==required_files,'Incomplete original execution files')
            require(read_json(origin/'source.json')['source_manifest']==current,'Module input source differs from current source')
            prefix=folder/'module-inputs'/str(index)
            for name,expected_hash in item['files'].items():
                require(digest((origin/name).read_bytes())==expected_hash,'Original execution input hash mismatch')
                target=prefix/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin/name,target)
            input_records[item['path']]={r['id']:r for r in read_json(origin/'tests.json')}
            module_inputs.append(dict(original=item['path'],archive='module-inputs/'+str(index)))
        for record in records:
            origin=selection['selected_case_origins'].get(record['id'])
            require(origin in input_records and input_records[origin].get(record['id'])==record,'Qualified case was not actually recorded in its declared execution')
        shutil.copyfile(a.execution/'module-revalidation.json',folder/'module-revalidation.json')
        shutil.copyfile(a.execution/'retained-initial-runtime-errors.json',folder/'retained-initial-runtime-errors.json')
    shutil.copyfile(a.stock / 'summary.json', folder / 'capture-summary.json')
    shutil.copyfile(a.stock / 'jobs.json', folder / 'capture-jobs.json')
    shutil.copyfile(a.stock / 'image-manifest.json', folder / 'capture-image-manifest.json')
    # Only authored synthetic capture files, never customer workspaces.
    for image in images:
        target = folder / 'captures' / image
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workspace / image, target)
    status, claims, original_hash = generate_original_claims(folder, commit['sha'], records)
    provenance = dict(kind='ADOPT_ACTUAL_COMPLETED_EXECUTION_NO_TEST_RERUN',
                      command=sys.argv, driver_sha256=digest(Path(__file__).read_bytes()),
                      execution=str(a.execution), captures=str(a.stock),
                      actual_execution_commit=source['commit'], remote_snapshot=commit['sha'],
                      equivalent_source_basis='Exact per-path content/blob manifest equality; documentation-only commit difference allowed.',
                      original_claim_generator_sha256=original_hash,
                      original_overall_status_preserved=status, original_not_verified=sum(c['status'] != 'PASS' for c in claims))
    if module_inputs:
        provenance['module_execution_inputs']=module_inputs
        provenance['qualification_strategy']='Explicit same-source module revalidation; initial timeout retained, not a single fresh full attempt.'
    write_json(folder / 'adoption-provenance.json', provenance)
    attachments = {p.relative_to(folder).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p.read_bytes()), mime=mimetypes.guess_type(p.name)[0] or 'text/plain')
                   for p in folder.rglob('*') if p.is_file()}
    run = dict(schema_version=1, id=a.run_id, created_utc=datetime.now(timezone.utc).isoformat(),
               source_commit=commit['sha'], source_manifest_sha256=manifest_digest(current),
               source_unchanged=current == manifest(ROOT, code_only=True), status=status,
               software_execution_status='PASS', unhandled_runtime_errors=0, test_count=len(records),
               passed=len(records), capture_exit_code=0, tests_sha256=digest((folder / 'tests.json').read_bytes()),
               attachments=attachments, command=' '.join(sys.argv), review_level='SELF_VERIFIED',
               scope='Actual complete synthetic/Linux execution and 27 original GUI captures; repackaged with verified GitHub source proof.',
               not_verified=['Real private corpus quality', 'Windows/reference hardware', 'Physical print', 'Independent novice/independent review'],
               test_execution_strategy='ADOPTED_ACTUAL_OWNED_FRESH_MODULE_PROCESSES',
               test_module_workers=source['workers'], test_module_count=summary['modules'],
               planned_test_count=len(records), not_completed_test_count=0, evidence_adoption=provenance)
    write_json(folder / 'run.json', run)
    from dev_governance import verify_run, execution_passed
    verified, results = verify_run(ROOT, str((folder / 'run.json').relative_to(ROOT)))
    require(execution_passed(verified, results), 'Existing governance rejected execution')
    print(json.dumps(dict(run=a.run_id, status=status, software_execution='PASS', tests=len(records), original_not_verified=provenance['original_not_verified'])))


if __name__ == '__main__':
    main()
