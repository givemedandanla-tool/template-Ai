"""Original unittest IDs in bounded fresh Qt groups; no assertion/timeout changes."""
from collections import OrderedDict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from dev_common import write_json
from evidence_modules import ModuleResults,run_modules

GROUP_SIZE=4

def grouped_modules(expected,live,*,test_root=None,module_timeout=180,workers=1):
    if workers!=1:raise ValueError('Windows desktop GUI groups must run one at a time')
    live=Path(live);live.mkdir(parents=True,exist_ok=False)
    modules=OrderedDict()
    for identity in expected:modules.setdefault(identity.split('.')[0],[]).append(identity)
    result=ModuleResults(expected);errors=[];logs=[];batches=[]
    write_json(live/'test-catalog.json',expected)
    for module,identities in modules.items():
        attempts=[];module_records={};module_logs=[]
        for index in range(0,len(identities),GROUP_SIZE):
            selected=identities[index:index+GROUP_SIZE]
            folder=live/'case-groups'/(module+'-'+str(index//GROUP_SIZE+1).zfill(3))
            child,child_errors,log=run_modules(selected,folder,test_root=test_root,
                module_timeout=module_timeout,workers=1)
            if set(module_records).intersection(child.records):raise ValueError('Duplicate executed test ID')
            module_records.update(child.records);attempts.extend(child.modules)
            errors.extend(child_errors);logs.append(log);module_logs.append(log)
            batches.append(dict(module=module,expected=selected,folder=folder.as_posix(),
                modules=child.modules,runtime_errors=child_errors))
            write_json(live/'case-groups.json',batches)
            write_json(live/'test-progress.json',dict(phase='FRESH_QT_CASE_GROUPS',
                current_test=selected[-1],completed=len(result.records)+len(module_records),
                passed=sum(r['status']=='PASS' for r in [*result.records.values(),*module_records.values()]),
                planned_tests=len(expected),formal_complete=False))
        missing=sorted(set(identities)-set(module_records));unexpected=sorted(set(module_records)-set(identities))
        healthy=not missing and not unexpected and all(a['healthy'] for a in attempts) and all(r['status']=='PASS' for r in module_records.values())
        result.records.update(module_records)
        result.modules.append(dict(module=module,owned_pid=None,
            owned_pids=[a['owned_pid'] for a in attempts],exit_code=0 if healthy else 1,
            seconds=sum(a['seconds'] for a in attempts),expected=len(identities),
            completed=len(module_records),missing_test_ids=missing,unexpected_test_ids=unexpected,
            duplicate_ids=False,parse_error=None,timed_out=any(a['timed_out'] for a in attempts),
            failure=None if healthy else 'OWNED_QT_GROUP_FAILED',remaining_owned_pids=[p for a in attempts for p in a['remaining_owned_pids']],
            healthy=healthy,process_groups=len(attempts),max_cases_per_owned_process=GROUP_SIZE,
            per_process_watchdog_seconds=module_timeout))
        aggregate=live/'modules'/module;aggregate.mkdir(parents=True)
        (aggregate/'unittest.log').write_text('\n'.join(module_logs),encoding='utf-8')
        for name in ['stacks.log','progress.json']:
            paths=sorted((live/'case-groups').glob(module+'-*/modules/'+module+'/'+name))
            if paths:
                if name.endswith('.json'):(aggregate/name).write_bytes(paths[-1].read_bytes())
                else:(aggregate/name).write_text('\n'.join(p.read_text(errors='replace') for p in paths),encoding='utf-8')
        (live/'modules'/(module+'-stdout.log')).write_text('\n'.join(module_logs),encoding='utf-8')
        write_json(live/'test-modules.json',dict(modules=result.modules))
    result.records=OrderedDict((identity,result.records[identity]) for identity in expected if identity in result.records)
    (live/'test-progress.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in result.records.values()),encoding='utf-8')
    write_json(live/'case-group-policy.json',dict(
        strategy='ORIGINAL_CASES_FRESH_QT_PROCESS_GROUPS',logical_modules=len(modules),
        process_groups=len(batches),maximum_cases_per_process=GROUP_SIZE,
        original_case_ids_preserved=list(result.records)==list(expected),
        original_method_assertions_and_wait_limits_unchanged=True,
        per_process_watchdog_seconds=module_timeout,desktop_parallelism=1))
    return result,errors,'\n'.join(logs)

def main():
    spec=importlib.util.spec_from_file_location('original_audit_driver',ROOT/'docs/dev/pre_download_audit/run_local_audit.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    # Only orchestration changes. Original tests, widgets, worker, assertions,
    # intrinsic waits and each owned process's watchdog remain unchanged.
    audit.run_modules=grouped_modules
    status=audit.main()
    output=Path(sys.argv[sys.argv.index('--output')+1])
    policy=json.loads((output/'live/case-group-policy.json').read_text())
    for name in ['source.json','summary.json']:
        path=output/name;value=json.loads(path.read_text())
        value['windows_case_group_policy']=policy
        value['windows_case_group_driver_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        write_json(path,value)
    return status

if __name__=='__main__':
    raise SystemExit(main())
