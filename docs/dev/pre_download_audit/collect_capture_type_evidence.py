"""Combine only successful capture commands; never call them unittest passes."""
import argparse,collections,json
from pathlib import Path
F=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--input',action='append',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
rows={};contexts=[];sources=[]
for name in args.input:
 folder=F/name;assert json.loads((folder/'summary.json').read_text())['source_unchanged'];source=json.loads((folder/'source.json').read_text());sources.append(source)
 if len(sources)>1:assert source['source_manifest']==sources[0]['source_manifest']
 for job in json.loads((folder/'jobs.json').read_text()):
  if job['status']!='PASS':continue
  typed=Path(job['command'][job['command'].index('--type-output')+1]);data=json.loads(typed.read_text());assert not data['observer_errors'] and data['worker_source_unchanged'] and data['worker_sha256']==source['frozen_worker_sha256'];assert all(m['business_ast_identical_after_unwrapping'] for m in data['modules'].values())
  context='capture:'+job['script'];contexts.append(dict(id=context,status='PASS',command=job['command'],source_folder=name,deadline=job['deadline_seconds'],exit_code=job['exit_code'],unittest=False,assertions_or_window_replaced=False,worker_sha256=data['worker_sha256']))
  for key,row in data['rows'].items():
   if context not in row['test_contexts']:continue
   target=rows.setdefault(key,dict(visits=0,values={},member_checks={},test_contexts=[],returns={},normal_calls={},raised_calls={}))
   target['visits']+=row['visits']
   if context not in target['test_contexts']:target['test_contexts'].append(context)
   for label,types in row['values'].items():
    bucket=target['values'].setdefault(label,{})
    for type_name,count in types.items():bucket[type_name]=bucket.get(type_name,0)+count
   for member,count in row['member_checks'].items():target['member_checks'][member]=target['member_checks'].get(member,0)+count
summary=dict(scope='AUTHORED_REAL_GUI_CAPTURES_WITH_ASSERTIONS_NOT_UNITTESTS',execution_kind='CAPTURE_NOT_STOCK_QUALIFICATION',selected=len(contexts),statuses=dict(PASS=len(contexts)),runtime_errors=[],observer_errors={},source_unchanged=True,business_ast_equivalence_verified=True,rows=rows,observed_rows=len(rows),excluded_failed_jobs=True,qualification='Individual successful commands only; incomplete overall capture chain is not marked complete')
(args.output/'observations.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(args.output/'capture-contexts.json').write_text(json.dumps(contexts,ensure_ascii=False,indent=2)+'\n');(args.output/'source.json').write_text(json.dumps(dict(source_manifest=sources[0]['source_manifest'],input_runs=args.input,qualification=summary['qualification']),indent=2)+'\n');print('capture contexts',len(contexts),'observed original occurrences',len(rows))
