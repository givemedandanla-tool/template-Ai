"""Admit closed healthy modules without declaring the parent suite complete."""
import argparse,collections,json,sys
from pathlib import Path
F=Path(__file__).resolve().parent
sys.path.insert(0,str(F.parents[2]/'tools'))
from dev_common import manifest
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=F/a.run;a.output.mkdir(parents=True,exist_ok=False)
source=json.loads((run/'source.json').read_text());assert source['source_manifest']==manifest(code_only=True);receipt=json.loads((run/'live/test-modules.json').read_text());rows={};tests=[];modules=[];equivalence=[]
for module in receipt['modules']:
 if not module['healthy'] or module['exit_code']!=0 or module['timed_out'] or module['failure'] or module['remaining_owned_pids']:continue
 folder=run/'live/modules';name=module['module'];result=json.loads((folder/name/'results.json').read_text());assert not result['runtime_errors'];assert len(result['records'])==module['expected'] and all(r['status']=='PASS' for r in result['records'])
 typed=json.loads((folder/(name+'-types.json')).read_text());assert not typed['observer_errors'] and typed['worker_sha256']==source['frozen_worker_sha256'] and typed['worker_source_unchanged'];assert all(v['business_ast_identical_after_unwrapping'] for v in typed['modules'].values())
 tests.extend(result['records']);modules.append(module);equivalence.extend(typed['modules'].values())
 for key,row in typed['rows'].items():
  dst=rows.setdefault(key,dict(visits=0,values={},returns={},normal_calls={},raised_calls={},member_checks={},test_contexts=[]));dst['visits']+=row['visits']
  for label,types in row['values'].items():
   bucket=dst['values'].setdefault(label,{})
   for name,count in types.items():bucket[name]=bucket.get(name,0)+count
  for name,count in row['member_checks'].items():dst['member_checks'][name]=dst['member_checks'].get(name,0)+count
  for context in row['test_contexts']:
   if context not in dst['test_contexts']:dst['test_contexts'].append(context)
assert len(tests)==len({t['id'] for t in tests}) and tests
report=dict(scope='COMPLETED_HEALTHY_MODULES_ONLY_PARENT_SUITE_STILL_RUNNING',parent_suite_complete=False,selected=len(tests),statuses=dict(PASS=len(tests)),modules=len(modules),runtime_errors=[],observer_errors={},source_unchanged=True,business_ast_equivalence_verified=True,observed_rows=len(rows),rows=rows,frozen_worker_sha256=source['frozen_worker_sha256'],not_claimed='Parent full-suite success, failed/incomplete modules, arbitrary inputs or deferred external qualification')
(a.output/'observations.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(a.output/'source.json').write_text(json.dumps({**source,'qualification':report['scope'],'parent_run':a.run},indent=2)+'\n');(a.output/'tests.json').write_text(json.dumps(tests,indent=2)+'\n');(a.output/'module-receipts.json').write_text(json.dumps(modules,indent=2)+'\n');print('closed healthy modules',len(modules),'PASS cases',len(tests),'original type rows',len(rows))
