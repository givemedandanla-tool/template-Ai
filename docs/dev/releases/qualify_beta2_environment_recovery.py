"""Select actual healthy same-source modules after confirmed disk exhaustion.

Keeps the failed full attempt verbatim. Does not change results, assertions,
timeouts, product code, or governance. The existing formal adopter independently
checks every selected record against its declared archived execution input.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from dev_common import read_json,write_json,manifest
from dev_governance import test_ids

FULL=ROOT/'docs/evidence/runs/RUN-BUNDLED-INKSCAPE-BETA2-003'
LIVE=ROOT/'.checkpoints/formal-live/RUN-BUNDLED-INKSCAPE-BETA2-003'
RETRY=ROOT/'docs/dev/releases/v0.2.0-beta.2/linux-environment-retry-001'
ORIGINAL=ROOT/'docs/dev/releases/v0.2.0-beta.2/linux-full-003-input'
OUT=ROOT/'docs/dev/releases/v0.2.0-beta.2/linux-qualified-001'
REQUIRED=['source.json','summary.json','tests.json','catalog.json','runtime-errors.json','live/test-modules.json']


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    current=manifest(ROOT,code_only=True)
    initial=read_json(FULL/'run.json');records=read_json(FULL/'tests.json')
    require(sha(FULL/'tests.json')==initial['tests_sha256'] and len(records)==initial['test_count'],'Raw initial records were altered')
    require(initial['source_unchanged'] and read_json(FULL/'source-manifest.json')==current,'Initial source changed')
    require(initial['planned_test_count']==1986,'Unexpected initial catalog')
    modules=read_json(FULL/'test-modules.json')['modules']
    blocked={m['module'] for m in modules if not m['healthy']}
    require(len(blocked)==14,'Review a changed infrastructure scope before qualification')
    failures=[r for r in records if r['status']!='PASS']
    require(len(failures)==46 and all(r['status']=='ERROR' and 'No space left on device' in str(r['details']) for r in failures),
            'Only the specifically confirmed ENOSPC errors may be revalidated here; no assertion failures')
    errors=read_json(FULL/'runtime-errors.json')
    require(len(errors)==3,'Unexpected initial runtime errors')
    for error in errors:
        require((error['type']=='KeyError' and 'No space left on device' in str(error)) or
                (error['type']=='OWNED_TEST_MODULE_PROCESS_FAILURE' and error.get('module')=='test_font_candidates'
                 and error.get('timed_out') and error.get('failure')=='MODULE_DEADLINE_EXCEEDED'),
                'Unexplained runtime failure must be investigated, never silently retried')
    catalog=[]
    for module in modules:
        ids=read_json(LIVE/'parallel-parts'/module['module']/'modules'/(module['module']+'-expected.json'))
        require(len(ids)==module['expected'],'Original per-module expected manifest differs')
        catalog.extend(ids)
    require(len(catalog)==len(set(catalog))==1986,'Incomplete/duplicate original planned catalog')
    require(set(catalog)==test_ids(ROOT),'Original expected index differs from current immutable test source')
    retry_source=read_json(RETRY/'source.json');retry_summary=read_json(RETRY/'summary.json')
    retry_records=read_json(RETRY/'tests.json');retry_modules=read_json(RETRY/'live/test-modules.json')['modules']
    require(retry_source['source_manifest']==current and retry_summary['source_unchanged_during_run'],'Retry source differs')
    require(retry_summary['software_execution']=='PASS' and retry_summary['runtime_errors']==0 and not read_json(RETRY/'runtime-errors.json'),
            'Actual complete retry must pass before selecting any results')
    require({m['module'] for m in retry_modules}==blocked and all(m['healthy'] for m in retry_modules),'Retry must contain every blocked whole module, all healthy')
    require(read_json(RETRY/'live/test-modules.json')['module_timeout_seconds']==180,'Do not extend module deadlines')
    expected_retry={identity for identity in catalog if identity.split('.')[0] in blocked}
    require({r['id'] for r in retry_records}==expected_retry and len(retry_records)==len(expected_retry)==139,'Retry catalog incomplete')
    require(all(r['status']=='PASS' for r in retry_records),'Retry contains failed/skipped cases')
    selected=[r for r in records if r['id'].split('.')[0] not in blocked]+retry_records
    require(len(selected)==1986 and {r['id'] for r in selected}==set(catalog) and all(r['status']=='PASS' for r in selected),'Selected execution is incomplete or not PASS')
    prior={r['id'] for r in read_json(ROOT/'docs/evidence/runs/RUN-WINDOWS-BETA-FINAL-LINUX-001/tests.json')}
    require(len(prior)==1963 and prior<=set(catalog),'Original1963 cases lost')
    ORIGINAL.mkdir(exist_ok=False);OUT.mkdir(exist_ok=False)
    # Lossless schema adapter: raw result/module/error bytes are copied verbatim.
    source=dict(qualification='ADAPTER_OF_FAILED_RAW_FULL_RUN_NOT_QUALIFIED',commit=initial['source_commit'],
                source_manifest=current,expected=1986,workers=3,manifest_sha256=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest(),
                raw_full_run=str((FULL/'run.json').relative_to(ROOT)),raw_full_run_sha256=sha(FULL/'run.json'))
    write_json(ORIGINAL/'source.json',source);write_json(ORIGINAL/'catalog.json',catalog)
    write_json(ORIGINAL/'summary.json',dict(software_execution='FAIL',planned=1986,completed=len(records),statuses=dict(Counter(r['status'] for r in records)),
               modules=len(modules),healthy_modules=sum(m['healthy'] for m in modules),runtime_errors=len(errors),source_unchanged_during_run=True,
               original_test_ids_preserved=False,kind='LOSSLESS_METADATA_ADAPTER_OF_RETAINED_RAW_FAILED_RUN'))
    for src,dst in [('tests.json','tests.json'),('runtime-errors.json','runtime-errors.json'),('test-modules.json','live/test-modules.json')]:
        target=ORIGINAL/dst;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(FULL/src,target)
    inputs=[]
    for folder in [ORIGINAL,RETRY]:
        inputs.append(dict(path=folder.relative_to(ROOT).as_posix(),source_commit=read_json(folder/'source.json')['commit'],
                           files={name:sha(folder/name) for name in REQUIRED}))
    origins={r['id']:(RETRY if r['id'].split('.')[0] in blocked else ORIGINAL).relative_to(ROOT).as_posix() for r in selected}
    provenance=dict(kind='ACTUAL_SAME_SOURCE_MODULE_REVALIDATION_NOT_A_SINGLE_FRESH_FULL_ATTEMPT',
         inputs=inputs,initial_failed_attempt_preserved=True,affected_modules=sorted(blocked),
         reason='46 ENOSPC setup errors, two ENOSPC class-setup error chains and one font-candidate deadline; restore disk capacity by reversible auxiliary metadata compression, then actually rerun all139 cases in the14 blocked whole modules alone.',
         original_module_deadline_seconds=180,repeat_module_deadline_seconds=180,original_workers=3,repeat_workers=1,
         selected_case_origins=origins,product_changes=False,assertion_changes=False,test_skips=False,
         original_raw_run=str((FULL/'run.json').relative_to(ROOT)),original_raw_run_sha256=sha(FULL/'run.json'),
         disk_recovery_manifest='docs/dev/maintenance/READBACK_METADATA_COMPRESSION_20261022.json')
    lookup={r['id']:r for r in selected};write_json(OUT/'tests.json',[lookup[key] for key in catalog]);write_json(OUT/'catalog.json',catalog)
    new_source=dict(retry_source,expected=1986,workers=3,qualification='ACTUAL_SAME_SOURCE_HEALTHY_MODULE_SELECTION',
                   original_catalog_size=1963,new_ids=sorted(set(catalog)-prior),
                   command=[sys.executable,str(Path(__file__).relative_to(ROOT))],runner_sha256=sha(Path(__file__)),
                   qualification_provenance='module-revalidation.json')
    write_json(OUT/'source.json',new_source)
    write_json(OUT/'summary.json',dict(qualification='LOCAL_ONLY_NOT_REMOTE_VERIFIED',source_commit=new_source['commit'],software_execution='PASS',
         planned=1986,completed=1986,statuses=dict(PASS=1986),modules=len(modules),healthy_modules=len(modules),runtime_errors=0,
         source_unchanged_during_run=True,original_test_ids_preserved=True,retained_prior_failed_attempt=True,retained_prior_runtime_errors=3,
         actual_attempt_records=len(records)+len(retry_records),qualification_is_single_fresh_full_run=False))
    write_json(OUT/'runtime-errors.json',[]);write_json(OUT/'retained-initial-runtime-errors.json',errors)
    write_json(OUT/'module-revalidation.json',provenance)
    replacement={m['module']:m for m in retry_modules}
    write_json(OUT/'live/test-modules.json',dict(strategy='HEALTHY_SAME_SOURCE_WHOLE_MODULE_SELECTION_WITH_RETAINED_FAILED_ATTEMPT',
         modules=[replacement.get(m['module'],m) for m in modules],module_timeout_seconds=180,planned_tests=1986,completed_tests=1986))
    require(manifest(ROOT,code_only=True)==current,'Source changed during qualification assembly')
    print(json.dumps(dict(status='ACTUAL_SELECTED_MODULES_PASS_PENDING_ORIGINAL_GUI_AND_FORMAL_ADOPTER',tests=1986,revalidated=139,blocked_modules=14)))


if __name__=='__main__':main()
