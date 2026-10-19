"""Measure durable 1000/3000 authored descriptor workloads; never real AI proof."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')

from template_ai.storage import Library
from template_ai.design_jobs import DesignJobs,run_design_job


def hashes():
    names=['design_jobs','design_evaluation','design_family','design_profiles','design_joint',
           'training_store','storage','model','datasets','quality_groups','training_pipeline']
    return {name:hashlib.sha256((ROOT/'template_ai'/f'{name}.py').read_bytes()).hexdigest() for name in names}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,choices=[1000,3000],required=True)
    parser.add_argument('--data-root',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():raise ValueError('Scale report IDs are immutable;choose a new path')
    before=hashes();started=time.perf_counter();library=Library(args.data_root);jobs=DesignJobs(library)
    try:
        job=jobs.create('OWNED_DESCRIPTOR_BENCHMARK',dict(items=list(range(args.count)),
            origin='AUTHORED_SYNTHETIC',purpose='DESCRIPTOR_EXTRACTION_AND_SHARED_FAMILY_PROFILE_FIT'),
            'Owned anonymous workload measurement',True)
        claimed=jobs.claim(job['id'],job['revision']);progress=[]
        paused=run_design_job(args.data_root,job['id'],claimed['owner']['token'],
            cancel=lambda:len(progress)>=17,progress=lambda row:progress.append(row))
        if paused['phase']!='PAUSED' or paused['next_index']!=17:raise ValueError('Actual cancellation boundary not observed')
        first=jobs.results(job['id']);library.close();library=Library(args.data_root);jobs=DesignJobs(library)
        current=jobs.current(job['id']);claimed=jobs.claim(job['id'],current['revision'])
        completed=run_design_job(args.data_root,job['id'],claimed['owner']['token'])
        if completed['phase']!='COMPLETE' or jobs.results(job['id'])[:17]!=first:
            raise ValueError('Restart did not preserve committed evidence')
        rows=[]
        for index in range(args.count):
            item=jobs.store.get('DESIGN_JOB_ITEM',jobs.item_key(job['id'],index))
            rows.append(dict(index=index,input_digest=item['input_digest'],result_digest=item['result_digest'],
                             latency_ms=item['elapsed_seconds']*1000))
        import numpy as np
        after=hashes();report=dict(schema=1,origin='AUTHORED_SYNTHETIC',count=args.count,job_id=job['id'],
            actual_pause_after=17,reopened_database=True,retained_prefix_unchanged=True,
            ledger_item_count=jobs.store.count('DESIGN_JOB_ITEM'),source_hashes_before=before,source_hashes_after=after,
            source_unchanged=before==after,wall_seconds=time.perf_counter()-started,
            latency_percentiles_ms=dict(zip(['p50','p95','p99'],np.percentile([row['latency_ms'] for row in rows],[50,95,99]).tolist())),
            summary=completed['summary'],items=rows,
            limits=['not real .ai parsing','not actual font/Logo fidelity','not Windows/VivoBook timing',
                    'not aesthetics or production qualification','per-item latency excludes ledger commit;wall time includes it'])
        if before!=after:raise ValueError('Measured implementation changed during workload')
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({key:report[key] for key in ('count','wall_seconds','actual_pause_after','source_unchanged','latency_percentiles_ms')}))
    finally:library.close()


if __name__=='__main__':main()
