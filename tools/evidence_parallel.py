"""Bounded parallel orchestration; each module retains its own owned subprocess."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from datetime import datetime,timezone
from pathlib import Path
import json,shutil
from dev_common import write_json


def run_parallel(expected,groups,live,*,test_root,module_timeout,workers):
    from evidence_modules import run_modules,ModuleResults,read_bounded
    live=Path(live);live.mkdir(parents=True,exist_ok=True)
    workspace=live/'modules';workspace.mkdir(exist_ok=False)
    parts=live/'parallel-parts';parts.mkdir(exist_ok=False)
    result=ModuleResults(expected);finished={};errors=[]
    write_json(live/'test-catalog.json',expected)
    def progress():
        snapshots=[]
        for module in groups:
            raw=read_bounded(parts/module/'test-progress.json')
            if raw:snapshots.append(json.loads(raw))
        write_json(live/'test-progress.json',dict(phase='RUNNING_OWNED_TEST_MODULES',
            current_test=', '.join(s.get('current_test') or '' for s in snapshots if s.get('current_test'))[:1500],
            started=sum(s.get('started',0) for s in snapshots),completed=sum(s.get('completed',0) for s in snapshots),
            passed=sum(s.get('passed',0) for s in snapshots),
            failed_ids=[i for s in snapshots for i in s.get('failed_ids',[])][:20],
            planned_tests=len(expected),formal_complete=False,updated_at=datetime.now(timezone.utc).isoformat()))
    def metadata():
        modules=[item for module in groups if module in finished for item in finished[module][0].modules]
        write_json(live/'test-modules.json',dict(strategy='PARALLEL_OWNED_FRESH_MODULE_PROCESSES',
            workers=workers,module_timeout_seconds=module_timeout,planned_tests=len(expected),
            completed_tests=sum(len(item[0].records) for item in finished.values()),modules=modules))
    with ThreadPoolExecutor(max_workers=min(workers,len(groups)),thread_name_prefix='owned-test-module') as pool:
        pending={pool.submit(run_modules,identities,parts/module,test_root=test_root,module_timeout=module_timeout):module
            for module,identities in groups.items()}
        while pending:
            done,_=wait(pending,timeout=.25,return_when=FIRST_COMPLETED)
            for future in done:
                module=pending.pop(future)
                try:finished[module]=future.result()
                except Exception as error:
                    failed=ModuleResults(groups[module]);failed.modules=[dict(module=module,healthy=False,
                        expected=len(groups[module]),completed=0,missing_test_ids=groups[module],failure='ORCHESTRATION_ERROR')]
                    finished[module]=(failed,[dict(type='PARALLEL_MODULE_ORCHESTRATION_ERROR',module=module,message=str(error)[:2000])],'Orchestration failed: '+module)
                metadata()
            progress()
    logs=[];stacks=[]
    for module in groups:
        child,child_errors,log=finished[module];result.records.update(child.records)
        result.modules.extend(child.modules);errors.extend(child_errors);logs.append(log)
        child_workspace=parts/module/'modules'
        if child_workspace.exists():
            for path in child_workspace.iterdir():
                target=workspace/path.name
                if path.is_dir():shutil.copytree(path,target)
                else:shutil.copy2(path,target)
        raw=read_bounded(parts/module/'timeout-stacks.log')
        if raw:stacks.append(raw)
    # Completion order never changes the canonical test record or module order.
    result.records=type(result.records)((identity,result.records[identity]) for identity in expected if identity in result.records)
    (live/'test-progress.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in result.records.values()))
    (live/'timeout-stacks.log').write_text('\n'.join(stacks))
    metadata();progress()
    return result,errors,'\n'.join(logs)
