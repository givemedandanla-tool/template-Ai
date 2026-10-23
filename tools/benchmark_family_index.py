"""Owned metadata-only scale probe; deliberately missing sources remain STALE."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def benchmark(count=3000):
    from template_ai.storage import Library
    from template_ai.training_store import TrainingStore,digest
    from template_ai.family_workspace import FamilyWorkspace
    import psutil
    if type(count) is not int or not 1<=count<=10000:raise ValueError('Bounded descriptor count required')
    started=time.perf_counter();process=psutil.Process();before=process.memory_info().rss
    with tempfile.TemporaryDirectory() as directory:
        library=Library(Path(directory)/'owned-descriptors')
        try:
            store=TrainingStore(library)
            with store.transaction():
                for block in range(0,count,10):
                    families=[]
                    for i in range(block,min(count,block+10)):
                        roles=[dict(key='p1:name:0',kind='name',owner_port='p1',present_examples=0),dict(key='p1:email:0',kind='email',owner_port='p1',present_examples=0)]
                        if i%3==0:roles.append(dict(key='p2:name:0',kind='name',owner_port='p2',present_examples=0))
                        pattern={r['owner_port']+':'+r['kind']:1 for r in roles}
                        families.append(dict(family_id='owned-family-'+str(i).zfill(5),independent_support=5,
                            observed_dimensions_mm=[[90 if i%2==0 else 100,54]],roles=roles,
                            data_requirement_profiles=[dict(semantic_type='name'),dict(semantic_type='email')],source_members=[],
                            grammar=dict(observed_joint_counts=[dict(pattern=pattern)])))
                    artifact=dict(profile_model=dict(families=families),family_model=dict(families=[]))
                    store._write('DESIGN_MODEL','owned-model-'+str(block).zfill(5),dict(state='UNTRUSTED_BENCHMARK',
                        dataset_id='INTENTIONALLY_MISSING_SOURCE_DATASET',manifest_digest='not-source-evidence',
                        weights_digest=digest(artifact),artifact=artifact,formal_qualification='NOT_EVALUATED'),0,'owned_metadata_only_probe')
            workspace=FamilyWorkspace(library);times={}
            for name,query,page in [('first_page',{},0),('last_page',{},(count-1)//48),('filtered',dict(size=[100,54],semantic='email'),0)]:
                start=time.perf_counter();result=workspace.index(query,page=page);times[name]=time.perf_counter()-start
                assert all(row['health']=='STALE' for row in result['rows'])
                if name=='first_page':assert result['total']==count;first=result
                if name=='last_page':assert len(result['rows'])==(count-1)%48+1
                if name=='filtered':assert result['total']==count//2
            view=workspace.save_view('Owned unavailable-source descriptors',{},'OWNED_BENCHMARK')
            assert workspace.open_view(view['id'])['total']==count
            assert len(library.templates())==0
            return dict(scope='METADATA_QUERY_PAGINATION_ONLY_NOT_AI_IMPORT_TRAINING_OR_SOURCE_VALIDATION',
                descriptor_rows=count,models=(count+9)//10,all_source_states='STALE_INTENTIONALLY',page_size=48,
                timings_seconds=times,total_seconds=time.perf_counter()-started,
                process_rss_before_bytes=before,process_rss_after_bytes=process.memory_info().rss,
                saved_query_reopened=True,global_templates=0,production_qualification=False)
        finally:library.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,default=3000);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=benchmark(args.count)
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
