"""Fresh owned processes isolate native Qt; optional bounded module concurrency."""
from collections import OrderedDict
from datetime import datetime,timezone
import hashlib,json,os,re,signal,subprocess,sys,time
from pathlib import Path
from dev_common import ROOT,write_json,digest

MAX_FILE=32*1024*1024


class ModuleResults:
    def __init__(self,expected):self.expected=expected;self.records=OrderedDict();self.modules=[]
    def wasSuccessful(self):
        return bool(self.expected) and set(self.records)==set(self.expected) and all(r['status']=='PASS' for r in self.records.values()) and all(m['healthy'] for m in self.modules)


def read_bounded(path):
    if not path.exists():return None
    if path.stat().st_size>MAX_FILE:raise ValueError('Test metadata exceeds32MiB; not silently truncated')
    return path.read_text(encoding='utf-8')


def stop_owned(process):
    if getattr(process,'_evidence_stopped',False):return
    process._evidence_stopped=True
    from template_ai.runtime_worker import stop_tree
    if process.poll() is None:stop_tree(process)
    # Every POSIX worker starts a unique session. Its remaining descendants keep
    # that owned process group even when the native Python parent has crashed.
    if os.name=='posix':
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:raise RuntimeError('Owned test process did not terminate')


def request_deadline_stack(process):
    """Only after the deadline is already failed; never a periodic valid-work signal."""
    if os.name=='posix' and process.poll() is None:
        try:os.kill(process.pid,signal.SIGUSR1)
        except OSError:return
        time.sleep(.1)  # bounded diagnostic grace; timed_out remains a failure


def owned_descendants(process):
    if os.name!='posix':return []
    import psutil
    found=[]
    for item in psutil.process_iter(['pid','status']):
        try:
            if item.pid!=process.pid and item.info['status']!=psutil.STATUS_ZOMBIE and os.getpgid(item.pid)==process.pid:found.append(item.pid)
        except (ProcessLookupError,PermissionError,psutil.NoSuchProcess):pass
    return found


def file_hash(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def run_modules(expected,live,*,test_root=None,module_timeout=120,workers=1):
    if not expected or len(expected)!=len(set(expected)):raise ValueError('Need a nonempty unique exact test catalog')
    if not 0<module_timeout<=600:raise ValueError('Test module deadline must be bounded')
    if type(workers) is not int or not 1<=workers<=4:raise ValueError('Owned module workers must be1..4')
    groups=OrderedDict()
    for identity in expected:
        if not re.fullmatch(r'test_[A-Za-z0-9_]+(?:\.[A-Za-z_][A-Za-z0-9_]*){2,}',identity):raise ValueError('Invalid exact unittest ID')
        groups.setdefault(identity.split('.')[0],[]).append(identity)
    if workers>1:
        from evidence_parallel import run_parallel
        return run_parallel(expected,groups,live,test_root=test_root,module_timeout=module_timeout,workers=workers)
    live=Path(live);live.mkdir(parents=True,exist_ok=True);workspace=live/'modules';workspace.mkdir(exist_ok=False)
    test_root=Path(test_root or ROOT/'tests');result=ModuleResults(expected);errors=[];log=[]
    write_json(live/'test-catalog.json',expected)
    def progress(current=None,child=None):
        child=child or {};records=list(result.records.values())
        write_json(live/'test-progress.json',dict(phase='RUNNING_OWNED_TEST_MODULE' if current else 'TEST_MODULES_FINISHED',current_test=child.get('current_test') or current,started=len(records)+child.get('started',0),completed=len(records)+child.get('completed',0),passed=sum(r['status']=='PASS' for r in records)+child.get('passed',0),failed_ids=[r['id'] for r in records if r['status']!='PASS'][:20],planned_tests=len(expected),formal_complete=False,updated_at=datetime.now(timezone.utc).isoformat()))
    for module,identities in groups.items():
        requested=workspace/(module+'-expected.json');write_json(requested,identities);output=workspace/module;stdout=workspace/(module+'-stdout.log')
        started=time.monotonic();timed_out=False;failure=None;last_child=None;remaining=[];progress(module)
        command=[sys.executable,str(ROOT/'tools/evidence_test_worker.py'),'--expected',str(requested),'--test-root',str(test_root),'--output',str(output),'--deadline-at',str(started+module_timeout)]
        with stdout.open('wb') as stream:
            process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=os.name=='posix')
            try:
                while process.poll() is None:
                    raw=read_bounded(output/'progress.json')
                    if raw and raw!=last_child:
                        progress(module,json.loads(raw));last_child=raw
                    if time.monotonic()-started>module_timeout:
                        timed_out=True;failure='MODULE_DEADLINE_EXCEEDED'
                        request_deadline_stack(process);stop_owned(process);break
                    if stdout.stat().st_size>MAX_FILE:failure='MODULE_STDOUT_BUDGET_EXCEEDED';stop_owned(process);break
                    time.sleep(.05)
                if process.returncode==0:
                    grace=time.monotonic()+.5
                    remaining=owned_descendants(process)
                    while remaining and time.monotonic()<grace:
                        time.sleep(.05);remaining=owned_descendants(process)
                    if remaining:failure='MODULE_LEFT_OWNED_CHILDREN'
            except BaseException:
                stop_owned(process);raise
            finally:
                # Cleanup is restricted to this newly created session, never a
                # global process-name kill or another project's worker.
                stop_owned(process)
        runtime=[];records=[];parse_error=None
        try:
            raw=read_bounded(output/'results.json')
            if raw:
                payload=json.loads(raw);records=payload['records'];runtime=payload['runtime_errors']
            else:
                raw=read_bounded(output/'progress.jsonl') or ''
                records=[json.loads(line) for line in raw.splitlines() if line]
        except (ValueError,KeyError,TypeError) as error:parse_error=str(error)
        ids=[r.get('id') for r in records];unexpected=sorted(set(ids)-set(identities));missing=sorted(set(identities)-set(ids));duplicate=len(ids)!=len(set(ids))
        valid_records=not unexpected and not duplicate and not parse_error and all('seconds' in r and r.get('status') in ('PASS','FAIL','ERROR','SKIP','EXPECTED_FAILURE','UNEXPECTED_SUCCESS') for r in records)
        if valid_records:
            for record in records:
                result.records[record['id']]=record
                with (live/'test-progress.jsonl').open('a',encoding='utf-8') as journal:journal.write(json.dumps(record,ensure_ascii=False)+'\n')
        healthy=process.returncode==0 and not timed_out and not failure and valid_records and not missing and not runtime
        item=dict(module=module,owned_pid=process.pid,exit_code=process.returncode,seconds=round(time.monotonic()-started,6),expected=len(identities),completed=len(records) if valid_records else 0,missing_test_ids=missing,unexpected_test_ids=unexpected,duplicate_ids=duplicate,parse_error=parse_error,timed_out=timed_out,failure=failure,remaining_owned_pids=remaining,healthy=healthy,stdout_bytes=stdout.stat().st_size,stdout_sha256=file_hash(stdout))
        result.modules.append(item);errors.extend(runtime)
        if process.returncode not in (0,1) or timed_out or failure:errors.append(dict(type='OWNED_TEST_MODULE_PROCESS_FAILURE',module=module,exit_code=process.returncode,timed_out=timed_out,failure=failure))
        if stdout.stat().st_size>MAX_FILE:
            with stdout.open('rb') as stream:text=stream.read(8192).decode('utf-8','replace')+'\nSTDOUT_BUDGET_EXCEEDED; only first8192bytes shown; module failed.\n'
        else:text=read_bounded(stdout) or ''
        unittest_log=read_bounded(output/'unittest.log') or ''
        log.append(f'Owned module {module}: exit={process.returncode}; completed={item["completed"]}/{len(identities)}; healthy={healthy}\n'+unittest_log+text)
        stacks=read_bounded(output/'stacks.log') or ''
        if stacks:
            with (live/'timeout-stacks.log').open('a',encoding='utf-8') as stream:stream.write('Owned module '+module+'\n'+stacks)
        write_json(live/'test-modules.json',dict(strategy='SERIAL_OWNED_FRESH_MODULE_PROCESSES',module_timeout_seconds=module_timeout,planned_tests=len(expected),completed_tests=len(result.records),modules=result.modules))
        progress()
    (live/'timeout-stacks.log').touch(exist_ok=True)
    return result,errors,'\n'.join(log)
