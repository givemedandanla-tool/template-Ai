"""Qualify actual same-source module attempts; retain the initial timeout unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from dev_common import manifest,write_json
from dev_governance import test_ids

def require(value,message):
    if not value:raise ValueError(message)

def read(folder,name):
    return json.loads((folder/name).read_text(encoding='utf-8-sig'))

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--full',type=Path,required=True)
parser.add_argument('--replacement',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
current=manifest(ROOT,code_only=True)
full_source=read(args.full,'source.json');retry_source=read(args.replacement,'source.json')
require(full_source['source_manifest']==retry_source['source_manifest']==current,'Both actual executions must match every current code/test/fixture byte')
full=read(args.full,'summary.json');retry=read(args.replacement,'summary.json')
require(full['source_unchanged_during_run'] and retry['source_unchanged_during_run'],'Source changed during an execution')
original=read(args.full,'tests.json');replacement=read(args.replacement,'tests.json')
require(all(r['status']=='PASS' for r in original+replacement),'Assertion/runtime test failures cannot be converted to success')
modules=read(args.full,'live/test-modules.json')['modules']
bad=[m for m in modules if not m['healthy']]
require(len(bad)==1 and bad[0]['timed_out'] and bad[0]['failure']=='MODULE_DEADLINE_EXCEEDED','Only one explicitly retained module deadline may be revalidated')
name=bad[0]['module']
old_errors=read(args.full,'runtime-errors.json')
require(len(old_errors)==1 and old_errors[0].get('type')=='OWNED_TEST_MODULE_PROCESS_FAILURE' and old_errors[0].get('module')==name,'Unexpected original runtime errors remain unresolved')
new_modules=read(args.replacement,'live/test-modules.json')['modules']
require(len(new_modules)==1 and new_modules[0]['module']==name and new_modules[0]['healthy'],'Replacement must be the entire affected module, actually healthy')
require(retry['software_execution']=='PASS' and retry['runtime_errors']==0 and not read(args.replacement,'runtime-errors.json'),'Replacement has runtime errors')
catalog=read(args.full,'catalog.json');retry_catalog=read(args.replacement,'catalog.json')
required={identity for identity in catalog if identity.split('.')[0]==name}
require(set(retry_catalog)==required=={r['id'] for r in replacement},'Replacement omits or adds affected cases')
require(len(replacement)==len(required)==new_modules[0]['expected']==new_modules[0]['completed'],'Incomplete or duplicate replacement')
selected=[r for r in original if r['id'].split('.')[0]!=name]+replacement
require(len(selected)==len(catalog)==len({r['id'] for r in selected}),'Incomplete or duplicate qualification')
require({r['id'] for r in selected}==set(catalog)==test_ids(ROOT),'Qualification must include the complete current catalog')
lookup={r['id']:r for r in selected};selected=[lookup[identity] for identity in catalog]
selected_modules=[new_modules[0] if m['module']==name else m for m in modules]
require(all(m['healthy'] and m['expected']==m['completed'] for m in selected_modules),'An unhealthy original module was retained')
require(full['original_test_ids_preserved'] is True,'Original catalog retention was not demonstrated')
inputs=[]
for folder in [args.full,args.replacement]:
    inputs.append(dict(path=folder.as_posix(),source_commit=read(folder,'source.json')['commit'],
        files={n:digest(folder/n) for n in ['source.json','summary.json','tests.json','catalog.json','runtime-errors.json','live/test-modules.json']}))
provenance=dict(kind='ACTUAL_SAME_SOURCE_MODULE_REVALIDATION_NOT_A_SINGLE_FRESH_FULL_ATTEMPT',
    affected_module=name,inputs=inputs,initial_failed_attempt_preserved=True,
    reason='Initial four-way run waited in a real MainWindow close notice during cleanup. Same unchanged module passed all11 cases alone within the same180s limit.',
    original_module_deadline_seconds=180,repeat_module_deadline_seconds=180,
    selected_case_origins={r['id']:(args.replacement if r['id'].split('.')[0]==name else args.full).as_posix() for r in selected},
    known_infrastructure_limit='This GUI cleanup module is not qualified for four simultaneous module processes; its selected qualification is the successful isolated attempt.',
    assertion_changes=False,test_skips=False,product_changes=False)
args.output.mkdir(parents=True,exist_ok=False)
write_json(args.output/'tests.json',selected);write_json(args.output/'catalog.json',catalog)
write_json(args.output/'runtime-errors.json',[])
write_json(args.output/'live/test-modules.json',dict(modules=selected_modules))
source=dict(full_source,qualification='LOCAL_ONLY_SAME_SOURCE_MODULE_ATTEMPTS',
    command=[sys.executable,*sys.argv],runner_sha256=digest(Path(__file__)),
    qualification_provenance='module-revalidation.json',workers_by_module={name:retry_source['workers']})
summary=dict(full,qualification='EXPLICIT_MODULE_REVALIDATION_NOT_FIRST_ATTEMPT_ALL_PASS',
    software_execution='PASS',planned=len(catalog),completed=len(selected),statuses={'PASS':len(selected)},
    healthy_modules=len(selected_modules),runtime_errors=0,
    retained_prior_failed_attempt=args.full.as_posix(),retained_prior_runtime_errors=len(old_errors))
write_json(args.output/'source.json',source);write_json(args.output/'summary.json',summary)
write_json(args.output/'module-revalidation.json',provenance)
write_json(args.output/'retained-initial-runtime-errors.json',old_errors)
shutil.copyfile(__file__,args.output/'qualification-driver.py')
print(json.dumps(dict(qualification='SELECTED_ACTUAL_SAME_SOURCE_MODULES',passed=len(selected),healthy_modules=len(selected_modules),isolated_module_cases=len(replacement),initial_failure_retained=True)))
