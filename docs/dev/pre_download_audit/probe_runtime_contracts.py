"""Observe selected existing tests through the unchanged owned-module executor."""
import argparse,collections,hashlib,json,os,subprocess,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from dev_common import manifest
import evidence_modules


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--observer',choices=['monitor','ast'],default='monitor')
    parser.add_argument('--case',action='append',default=[])
    parser.add_argument('--catalog',type=Path,default=ROOT/'docs/dev/pre_download_audit/full-regression-004/catalog.json')
    parser.add_argument('--all-tests',action='store_true')
    parser.add_argument('--exclude-cases',type=Path)
    parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    parser.add_argument('--points',type=Path,default=Path(__file__).with_name('runtime-points.json'))
    args=parser.parse_args();args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    original_points=args.points.resolve();frozen_folder=args.output/'frozen-runner';frozen_folder.mkdir()
    frozen_worker=frozen_folder/('ast_type_worker.py' if args.observer=='ast' else 'runtime_type_worker.py')
    original_worker=ROOT/'docs/dev/pre_download_audit'/frozen_worker.name
    frozen_worker.write_bytes(original_worker.read_bytes());frozen_worker.chmod(0o444)
    frozen_sha256=hashlib.sha256(frozen_worker.read_bytes()).hexdigest()
    frozen_points=frozen_folder/'points.json';frozen_points.write_bytes(original_points.read_bytes());frozen_points.chmod(0o444);args.points=frozen_points
    points=json.loads(args.points.read_text());catalog=json.loads(args.catalog.read_text())
    if len(catalog)!=len(set(catalog)):raise ValueError('Catalog must contain unique exact test IDs')
    proposed={p['test_id'] for p in points['points'] if p['test_id']}
    selected=[identity for identity in catalog if args.all_tests or identity in proposed]
    if args.exclude_cases:
        exclude=json.loads(args.exclude_cases.read_text())
        if set(exclude)-set(catalog):raise ValueError('Excluded IDs missing from full catalog')
        selected=[identity for identity in selected if identity not in exclude]
    if args.case:
        if set(args.case)-set(selected):raise ValueError('Requested case is not an exact proposed original test')
        selected=[identity for identity in selected if identity in args.case]
    if not selected:raise RuntimeError('No real existing test selected')
    before=manifest(code_only=True)
    (args.output/'source.json').write_text(json.dumps({'qualification':'LOCAL_ONLY_TYPE_OBSERVATION_NOT_PRIVATE_CORPUS','observer_mode':args.observer,'runtime_instrumented':args.observer=='ast','frozen_worker_sha256':frozen_sha256,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_manifest':before,'points_sha256':hashlib.sha256(args.points.read_bytes()).hexdigest(),'observer_helper_sha256':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['runtime_type_worker.py','ast_type_worker.py','probe_runtime_contracts.py','build_runtime_points.py','coordinate_contract.py']},'selected_tests':selected,'unmatched_proposed_test_ids':sorted(proposed-set(catalog))},indent=2)+'\n')
    original_subprocess=evidence_modules.subprocess;commands=[]
    def owned_observer(command,**kwargs):
        if Path(command[1]).resolve()!=ROOT/'tools/evidence_test_worker.py':raise RuntimeError('Refuse unexpected subprocess wrapping')
        out=Path(command[command.index('--output')+1]);typed=out.parent/(out.name+'-types.json')
        wrapped=[command[0],str(frozen_worker),'--points',str(args.points.resolve()),'--type-output',str(typed),'--',*command[2:]]
        commands.append(wrapped)
        kwargs['env']=dict(kwargs.get('env') or os.environ);kwargs['env']['TEMPLATE_AI_AUDIT_ROOT']=str(ROOT)
        return original_subprocess.Popen(wrapped,**kwargs)
    evidence_modules.subprocess=types.SimpleNamespace(Popen=owned_observer,TimeoutExpired=original_subprocess.TimeoutExpired,DEVNULL=original_subprocess.DEVNULL,STDOUT=original_subprocess.STDOUT)
    try:result,errors,log=evidence_modules.run_modules(selected,args.output/'live',module_timeout=180,workers=args.workers)
    finally:evidence_modules.subprocess=original_subprocess
    combined={};observer_errors=collections.Counter();module_proofs=[]
    for path in (args.output/'live').rglob('*-types.json'):
        data=json.loads(path.read_text());observer_errors.update(data['observer_errors'])
        if args.observer=='ast' and (data.get('worker_sha256')!=frozen_sha256 or not data.get('worker_source_unchanged')):observer_errors['WORKER_VERSION_MISMATCH']+=1
        if args.observer=='ast':
            module_proofs.extend(dict(path=p,**v) for p,v in data.get('modules',{}).items())
        for identity,row in data['rows'].items():
            target=combined.setdefault(identity,{'visits':0,'values':{},'returns':{},'normal_calls':{},'raised_calls':{},'member_checks':{},'test_contexts':[]})
            target['visits']+=row['visits']
            for field in ['returns','normal_calls','raised_calls','member_checks']:
                for key,n in row[field].items():target[field][key]=target[field].get(key,0)+n
            for label,kinds in row['values'].items():
                values=target['values'].setdefault(label,{})
                for key,n in kinds.items():values[key]=values.get(key,0)+n
            target['test_contexts']=sorted(set(target['test_contexts']+row['test_contexts']))
    statuses=collections.Counter(v['status'] for v in result.records.values());unchanged=manifest(code_only=True)==before
    report={'scope':'AUTHORED_EXISTING_TESTS_TYPE_NAMES_ONLY','observer_mode':args.observer,'runtime_instrumented':args.observer=='ast','frozen_worker_sha256':frozen_sha256,'module_equivalence_proofs':module_proofs,'business_ast_equivalence_verified':bool(module_proofs) and all(p['business_ast_identical_after_unwrapping'] for p in module_proofs),'selected':len(selected),'statuses':dict(statuses),'modules':len(result.modules),'healthy_modules':sum(m['healthy'] for m in result.modules),'runtime_errors':errors,'observer_errors':dict(observer_errors),'source_unchanged':unchanged,'observed_rows':len(combined),'rows':combined,'actual_commands':commands,'not_asserted':'Observed cases do not prove arbitrary inputs safe; original static warnings and source contracts remain recorded'}
    (args.output/'observations.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (args.output/'unittest.log').write_text(log)
    (args.output/'tests.json').write_text(json.dumps(list(result.records.values()),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['selected','statuses','modules','healthy_modules','observer_errors','source_unchanged','observed_rows']}))
    return 0 if statuses=={'PASS':len(selected)} and unchanged and not errors and not observer_errors and (args.observer!='ast' or report['business_ast_equivalence_verified']) else 1


if __name__=='__main__':raise SystemExit(main())
