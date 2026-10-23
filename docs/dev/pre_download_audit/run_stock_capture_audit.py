"""Run all original ordered capture jobs, without expression instrumentation."""
import argparse,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools'))
from dev_common import manifest
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();a.workspace=a.workspace.resolve();a.workspace.relative_to(ROOT/'.cache');a.workspace.mkdir(parents=True,exist_ok=False);a.output.mkdir(parents=True,exist_ok=False)
def save(name,value):(a.output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
before=manifest(code_only=True);jobs=json.loads(Path(__file__).with_name('capture-job-registry.json').read_text())['ordered_original_jobs'];save('source.json',dict(qualification='LOCAL_ONLY_STOCK_CAPTURES',head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_manifest=before,runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),workspace=str(a.workspace),instrumented=False));rows=[]
for i,job in enumerate(jobs,1):
 command=[sys.executable,job['script'],*[str(a.workspace) if v=='<OWNED_OUTPUT>' else str(v) for v in job['arguments']]];started=time.monotonic();log=a.output/f'{i:02}-{Path(job["script"]).stem}.log';save('progress.json',dict(current=i,total=len(jobs),script=job['script'],completed=len(rows)));timed_out=False
 with log.open('wb') as stream:
  child=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=child.wait(timeout=job['timeout'])
  except subprocess.TimeoutExpired:timed_out=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait(timeout=5)
  except BaseException:
   if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
   raise
 markers=[dict(line=n+1,kind='TRACEBACK_OR_QT_OVERRIDE') for n,l in enumerate(log.read_text(errors='replace').splitlines()) if l.strip().startswith('Traceback (most recent call last):') or 'Error calling Python override' in l]
 row=dict(id=f'STOCK-CAPTURE-{i:02}',script=job['script'],command=command,deadline_seconds=job['timeout'],seconds=time.monotonic()-started,exit_code=code,timed_out=timed_out,runtime_flags=markers,log=log.name,status='PASS' if code==0 and not timed_out and not markers else 'FAIL');rows.append(row);save('jobs.json',rows)
 if row['status']!='PASS':break
unchanged=before==manifest(code_only=True);summary=dict(planned=len(jobs),completed=len(rows),passed=sum(r['status']=='PASS' for r in rows),failed=[r['id'] for r in rows if r['status']!='PASS'],source_unchanged=unchanged,instrumented=False,qualification='LOCAL_ONLY_NOT_REMOTE_VERIFIED',not_executed=[j['script'] for j in jobs[len(rows):]],status='PASS' if len(rows)==len(jobs) and all(r['status']=='PASS' for r in rows) and unchanged else 'FAIL_OR_BLOCKED');save('summary.json',summary);save('image-manifest.json',{f.relative_to(a.workspace).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in a.workspace.rglob('*.png')});print(json.dumps(summary));raise SystemExit(summary['status']!='PASS')
