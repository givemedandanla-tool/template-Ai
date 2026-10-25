"""Synthetic Windows cancellation/death controls; no artwork or network traffic."""
import argparse,json,os,subprocess,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from template_ai.review_tool.native_isolation import WindowsIsolation,worker_environment,IsolationError

def parent(root,folder):
    c=WindowsIsolation(root)
    try:
        c.grant(root/'python');c.grant(folder,writable=True)
        return c.run([root/'python/pythonw.exe',folder/'sleep.py',folder/'started.json'],worker_environment(folder,root/'python'),cwd=folder,timeout=30)
    finally:c.close()

def verify(root,output):
    import psutil
    output.mkdir(exist_ok=False);results=[]
    for mode in ('timeout','cancel','verification-failure','parent-death'):
        folder=root/'jobs'/('lifetime-'+uuid.uuid4().hex);folder.mkdir(parents=True)
        (folder/'sleep.py').write_text('import json,os,sys,time\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps({"pid":os.getpid()}))\ntime.sleep(30)\n')
        if mode=='parent-death':
            process=subprocess.Popen([sys.executable,__file__,'--parent','--root',str(root),'--output',str(folder)],creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                for _ in range(150):
                    if (folder/'started.json').is_file():break
                    if process.poll() is not None:raise RuntimeError('Parent exited before child')
                    time.sleep(.1)
                child=psutil.Process(json.loads((folder/'started.json').read_text())['pid']);created=child.create_time()
                process.kill();process.wait(timeout=5)
                for _ in range(50):
                    if not child.is_running():break
                    time.sleep(.1)
                assert not child.is_running()
                results.append(dict(case=mode,passed=True))
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=5)
        else:
            c=WindowsIsolation(root)
            try:
                c.grant(root/'python');c.grant(folder,writable=True)
                if mode=='verification-failure':
                    def reject(_):raise IsolationError('Synthetic token verification failure')
                    c._verify=reject
                    try:c.run([root/'python/pythonw.exe',folder/'sleep.py',folder/'started.json'],worker_environment(folder,root/'python'),cwd=folder,timeout=2)
                    except IsolationError:pass
                    else:raise AssertionError('Verification failure did not fail closed')
                    assert not (folder/'started.json').exists()
                else:
                    start=time.monotonic()
                    proof=c.run([root/'python/pythonw.exe',folder/'sleep.py',folder/'started.json'],worker_environment(folder,root/'python'),cwd=folder,timeout=.5 if mode=='timeout' else 10,cancelled=(lambda:time.monotonic()-start>.5) if mode=='cancel' else None)
                    assert proof['stop_reason']==('cancelled' if mode=='cancel' else 'timeout')
                    assert not psutil.pid_exists(proof['pid'])
                results.append(dict(case=mode,passed=True))
            finally:c.close()
        (output/'summary.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--parent',action='store_true');a=p.parse_args()
    if a.parent:parent(a.root,a.output)
    else:verify(a.root,a.output)
