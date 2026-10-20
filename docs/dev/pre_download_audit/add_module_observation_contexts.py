"""Bind background-thread type witnesses to their healthy owned module.

A module context is not invented as a test ID. The corresponding real test IDs
and all-PASS/process/runtime receipts remain explicit and separate.
"""
import argparse,json,shutil
from pathlib import Path
F=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=F/a.run;a.output.mkdir(parents=True,exist_ok=False)
o=json.loads((run/'observations.json').read_text());assert not o['observer_errors'] and not o['runtime_errors'] and o['statuses']=={'PASS':o['selected']} and o['business_ast_equivalence_verified'];receipts=json.loads((run/'live/test-modules.json').read_text());modules={m['module']:m for m in receipts['modules']};tests=json.loads((run/'tests.json').read_text());assert all(m['healthy'] and m['exit_code']==0 for m in modules.values());contexts={}
for name,m in modules.items():
 records=[r for r in tests if r['id'].split('.')[0]==name];assert len(records)==m['expected'] and all(r['status']=='PASS' for r in records)
 contexts[name]=dict(scope='OWNED_MODULE_CONTEXT_NOT_A_TEST_ID',tests=[r['id'] for r in records],receipt=m)
 raw=json.loads((run/'live/modules'/(name+'-types.json')).read_text());assert not raw['observer_errors']
 for key in raw['rows']:
  if key in o['rows']:
   bucket=o['rows'][key].setdefault('module_contexts',[])
   if name not in bucket:bucket.append(name)
o['background_context_binding']='Healthy owned module only; no attribution to an individual case without a testcase stack';(a.output/'observations.json').write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n');(a.output/'module-contexts.json').write_text(json.dumps(contexts,indent=2)+'\n')
for name in ['source.json','tests.json']:shutil.copyfile(run/name,a.output/name)
print('qualified real module contexts',len(contexts))
