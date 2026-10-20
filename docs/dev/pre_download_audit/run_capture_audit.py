"""Reuse original ordered capture commands and deadlines with local type evidence.

No formal remote/publication gate is altered. Private business workspaces remain
in an owned ignored cache; this folder stores only local results/type metadata.
"""
import argparse,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from dev_common import manifest

def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--points',type=Path,required=True);args=parser.parse_args()
 args.output=args.output.resolve();args.workspace=args.workspace.resolve();args.workspace.relative_to(ROOT/'.cache');args.output.mkdir(parents=True,exist_ok=False);args.workspace.mkdir(parents=True,exist_ok=False)
 frozen=args.output/'frozen-runner';frozen.mkdir();worker=frozen/'ast_type_worker.py';worker.write_bytes(Path(__file__).with_name('ast_type_worker.py').read_bytes());worker.chmod(0o444);worker_sha=hashlib.sha256(worker.read_bytes()).hexdigest();points=frozen/'points.json';points.write_bytes(args.points.read_bytes());points.chmod(0o444)
 before=manifest(code_only=True);jobs=json.loads(Path(__file__).with_name('capture-job-registry.json').read_text())['ordered_original_jobs'];rows=[];env=dict(os.environ,QT_QPA_PLATFORM='offscreen',TEMPLATE_AI_AUDIT_ROOT=str(ROOT))
 save(args.output/'source.json',dict(qualification='LOCAL_ONLY_CAPTURE_AND_INSTRUMENTED_TYPE_EVIDENCE',head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_manifest=before,frozen_worker_sha256=worker_sha,points_sha256=hashlib.sha256(points.read_bytes()).hexdigest(),workspace=str(args.workspace),stock_tests='full0051886PASS plus root7 related33PASS; final stock1889 still pending',registry='capture-job-registry.json',no_formal_remote_qualification=True))
 for index,job in enumerate(jobs):
  script=ROOT/job['script'];options=[str(args.workspace) if v=='<OWNED_OUTPUT>' else str(v) for v in job['arguments']];typed=args.output/f'{index+1:02}-{script.stem}-types.json';log=args.output/f'{index+1:02}-{script.stem}.log';command=[sys.executable,str(worker),'--points',str(points),'--type-output',str(typed),'--script',str(script),'--',*options];started=time.monotonic();process=None;timed_out=False
  save(args.output/'progress.json',dict(status='RUNNING',index=index+1,total=len(jobs),current_script=job['script'],completed=len(rows)))
  try:
   with log.open('wb') as output:
    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=process.wait(timeout=job['timeout'])
    except subprocess.TimeoutExpired:
     timed_out=True;os.killpg(process.pid,signal.SIGKILL);code=process.wait(timeout=5)
  except BaseException:
   if process and process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
   raise
  data=json.loads(typed.read_text()) if typed.exists() else None
  markers=[dict(line=i+1,kind='UNHANDLED_TRACEBACK_OR_QT_OVERRIDE') for i,line in enumerate(log.read_text(errors='replace').splitlines()) if line.strip().startswith('Traceback (most recent call last):') or 'Error calling Python override' in line]
  proved=(data is not None and not data['observer_errors'] and data.get('worker_sha256')==worker_sha and data.get('worker_source_unchanged') and all(p['business_ast_identical_after_unwrapping'] for p in data['modules'].values()))
  row=dict(id=f'CAPTURE-{index+1:02}',script=job['script'],command=command,deadline_seconds=job['timeout'],seconds=time.monotonic()-started,exit_code=code,timed_out=timed_out,observer_proof=bool(proved),type_rows=len(data['rows']) if data else 0,log=log.name,runtime_log_flags=markers,status='PASS' if code==0 and not timed_out and proved and not markers else 'FAIL')
  rows.append(row);save(args.output/'jobs.json',rows);print(json.dumps({k:row[k] for k in ['id','script','status','exit_code','seconds','type_rows']}),flush=True)
  if row['status']!='PASS':break
 unchanged=manifest(code_only=True)==before;summary=dict(qualification='LOCAL_ONLY_NOT_REMOTE_VERIFIED',planned=len(jobs),completed=len(rows),passed=sum(r['status']=='PASS' for r in rows),failed=[r['id'] for r in rows if r['status']!='PASS'],source_unchanged=unchanged,stock_product_qualification=False,workspace_private_and_not_for_git=str(args.workspace),not_executed=[j['script'] for j in jobs[len(rows):]],status='PASS' if len(rows)==len(jobs) and all(r['status']=='PASS' for r in rows) and unchanged else 'FAIL_OR_BLOCKED')
 save(args.output/'summary.json',summary);print(json.dumps(summary),flush=True);return 0 if summary['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
