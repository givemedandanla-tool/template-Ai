"""Bounded child-process protocol around the existing analysis/training engines.

Stdout carries small control metadata, never original files or whole job payloads.
Actual progress is read back from committed SQLite rows. A stalled child can be
stopped without killing the GUI or claiming its uncommitted unit was saved.
"""
from collections import deque
from contextlib import closing
import json,os,queue,sqlite3,subprocess,sys,threading,time
from pathlib import Path

PREFIX=b'TEMPLATE_AI_RUNTIME_V1 '
MAX_LINE=16384


class WorkerTimeout(RuntimeError):
    pass


def read_job(root,kind,identity):
    if kind not in ('JOB','AUTO_JOB'):raise ValueError('未知持久工作種類')
    with closing(sqlite3.connect((Path(root)/'library.sqlite3').resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        row=db.execute('SELECT revision,payload FROM training_records WHERE kind=? AND id=?',(kind,identity)).fetchone()
        if not row or len(row[1].encode())>1048576:raise ValueError('工作失聯／超過持久metadata上限')
        return dict(json.loads(row[1]),id=identity,revision=row[0])


def stop_tree(process):
    """Only descendants of our live Popen child; process identities checked by psutil."""
    if process.poll() is not None:return
    import psutil
    try:
        parent=psutil.Process(process.pid);children=parent.children(recursive=True)
    except psutil.NoSuchProcess:return
    targets=list(reversed(children))+[parent]
    for target in targets:
        try:target.terminate()
        except psutil.NoSuchProcess:pass
    _,alive=psutil.wait_procs(targets,timeout=1)
    for target in alive:
        try:target.kill()
        except psutil.NoSuchProcess:pass
    try:process.wait(timeout=2)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)


def run_isolated(root,kind,identity,token,*,cancel=None,progress=None,admission=None,unit_timeout=120,cancel_grace=10,process_factory=subprocess.Popen):
    if unit_timeout<=0 or cancel_grace<=0:raise ValueError('worker timeout需正值')
    command=[sys.executable,'-m','template_ai.runtime_worker','--root',str(root),'--kind',kind,'--job',identity,'--token',token]
    process=process_factory(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=str(Path(__file__).resolve().parents[1]),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    events=queue.Queue(maxsize=32);commands=queue.Queue(maxsize=1);errors=deque(maxlen=8);reader_error=threading.Event();stopped=threading.Event()
    def read_stdout():
        try:
            while not stopped.is_set():
                line=process.stdout.readline(MAX_LINE+1)
                if not line:return
                if len(line)>MAX_LINE or not line.endswith(b'\n'):reader_error.set();return
                if not line.startswith(PREFIX):continue
                value=json.loads(line[len(PREFIX):])
                if not isinstance(value,dict) or value.get('type') not in ('BOUNDARY','PROGRESS','RESULT','ERROR'):reader_error.set();return
                while not stopped.is_set():
                    try:events.put(value,timeout=.1);break
                    except queue.Full:continue
        except Exception:reader_error.set()
    def read_stderr():
        try:
            while not stopped.is_set():
                data=process.stderr.read(2048)
                if not data:return
                errors.append(data.decode('utf-8','replace'))
        except OSError:pass
    def write_commands():
        while not stopped.is_set():
            try:packet=commands.get(timeout=.1)
            except queue.Empty:continue
            try:process.stdin.write(packet);process.stdin.flush()
            except (BrokenPipeError,OSError):return
    readers=[threading.Thread(target=read_stdout,daemon=True),threading.Thread(target=read_stderr,daemon=True),threading.Thread(target=write_commands,daemon=True)]
    for reader in readers:reader.start()
    last_boundary=time.monotonic();cancel_at=None;next_control=0;result=None;failure=None
    try:
        while True:
            now=time.monotonic()
            if now>=next_control and process.poll() is None:
                decision=admission() if admission else None;cancelled=bool(cancel and cancel.is_set())
                if cancelled and cancel_at is None:cancel_at=now
                control=dict(cancel=cancelled,allowed=decision.allowed if decision else True,reasons=[str(reason)[:120] for reason in decision.reasons[:10]] if decision else [])
                packet=(json.dumps(control)+'\n').encode()
                try:commands.put_nowait(packet)
                except queue.Full:
                    try:commands.get_nowait()
                    except queue.Empty:pass
                    commands.put_nowait(packet)
                next_control=now+.25
            if reader_error.is_set():raise RuntimeError('worker回傳超出協定範圍，已隔離停止')
            if cancel_at is not None and now-cancel_at>cancel_grace:raise RuntimeError('安全取消超時，已停止worker；已提交單位保留，未提交部分需明確恢復')
            if now-last_boundary>unit_timeout:raise WorkerTimeout('工作長時間未達安全邊界，已隔離停止；保留已提交單位，未完成項列為例外')
            try:event=events.get(timeout=.05)
            except queue.Empty:event=None
            if event:
                if event.get('job_id')!=identity:raise RuntimeError('worker結果不屬目前工作')
                if event['type']=='ERROR':failure=str(event.get('message','worker失敗'))[:4000]
                else:last_boundary=now
                if event['type']=='BOUNDARY':next_control=0
                if event['type']=='PROGRESS' and progress:progress(read_job(root,kind,identity))
                if event['type']=='RESULT':result=event
            if process.poll() is not None and not any(reader.is_alive() for reader in readers[:2]) and events.empty():break
        if failure:raise RuntimeError(failure)
        if process.returncode!=0 or not result:raise RuntimeError('worker未完成已核實結果；'+''.join(errors)[-4000:])
        saved=read_job(root,kind,identity)
        if saved['phase']=='RUNNING' or saved['revision']!=result.get('revision') or saved['phase']!=result.get('phase') or (saved.get('owner') or {}).get('token')!=token:raise RuntimeError('worker退出與已提交工作不一致，未宣稱完成')
        return saved
    finally:
        if process.poll() is None:stop_tree(process)
        stopped.set()
        for reader in readers:reader.join(timeout=.2)
        for stream in (process.stdin,process.stdout,process.stderr):
            if stream:stream.close()
        from .training_pipeline import LIVE_OWNERS
        LIVE_OWNERS.discard(token)


def child_main(arguments=None):
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--kind',choices=('JOB','AUTO_JOB'),required=True);parser.add_argument('--job',required=True);parser.add_argument('--token',required=True);args=parser.parse_args(arguments)
    def emit(kind,**value):
        raw=PREFIX+json.dumps(dict(type=kind,job_id=args.job,**value),ensure_ascii=False).encode()+b'\n'
        if len(raw)>MAX_LINE:raise ValueError('worker協定行超額')
        sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
    control=dict(cancel=False,allowed=False,reasons=['PARENT_ADMISSION_PENDING'],at=0);cancel=threading.Event();lock=threading.Lock()
    input_fd=sys.stdin.fileno()
    def commands():
        buffer=bytearray()
        try:
            while True:
                data=os.read(input_fd,2048)
                if not data:cancel.set();return
                buffer.extend(data)
                while b'\n' in buffer:
                    line,_,rest=buffer.partition(b'\n');buffer=bytearray(rest)
                    if len(line)>2048:cancel.set();return
                    value=json.loads(line)
                    if not isinstance(value,dict) or type(value.get('cancel')) is not bool or type(value.get('allowed')) is not bool or not isinstance(value.get('reasons'),list):cancel.set();return
                    with lock:control.update(value,at=time.monotonic())
                    if value['cancel']:cancel.set()
                if len(buffer)>2048:cancel.set();return
        except Exception:cancel.set()
    thread=threading.Thread(target=commands,daemon=True);thread.start()
    # Wait only for the first parent decision, bounded; heavy engines remain unloaded.
    deadline=time.monotonic()+3
    while control['at']==0 and time.monotonic()<deadline and not cancel.is_set():cancel.wait(.01)
    def admission():
        from .runtime_resources import ResourceDecision
        with lock:previous=control['at']
        emit('BOUNDARY')
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and not cancel.is_set():
            with lock:fresh=control['at']>previous
            if fresh:break
            cancel.wait(.01)
        with lock:value=dict(control)
        allowed=value['allowed'] and time.monotonic()-value['at']<=3 and not cancel.is_set()
        reasons=('CANCEL_REQUESTED',) if cancel.is_set() else tuple(value['reasons']) or ('PARENT_RESOURCE_DECISION_STALE',)
        return ResourceDecision(allowed,'READY' if allowed else 'PAUSED_RESOURCES',reasons if not allowed else (),0,0,None)
    try:
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        if args.kind=='JOB':
            from .training_pipeline import run_training_job
            result=run_training_job(args.root,args.job,args.token,cancel,lambda row:emit('PROGRESS',revision=row['revision']),admission=admission)
        else:
            from .automatic_training import run_automatic
            result=run_automatic(args.root,args.job,args.token,cancel,lambda row:emit('PROGRESS',revision=row['revision']),admission=admission)
        emit('RESULT',revision=result['revision'],phase=result['phase']);return 0
    except BaseException as error:emit('ERROR',message=str(error)[:4000]);return 1


if __name__=='__main__':raise SystemExit(child_main())
