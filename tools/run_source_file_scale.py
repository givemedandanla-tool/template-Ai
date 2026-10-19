"""Actual owned .ai-source workload with durable pause/reopen and measured RSS."""
import argparse
import json
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def run(directory,count,font=None,pause_after=17):
    import psutil
    from PySide6.QtWidgets import QApplication
    from template_ai.storage import Library
    from template_ai.fonts import FontManager
    from template_ai.design_jobs import DesignJobs,run_design_job
    from template_ai.training_store import digest
    from tools.local_learning_selftest import choose_font
    app=QApplication.instance() or QApplication([])
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    stop=threading.Event();rss=[0];process=psutil.Process();start=time.perf_counter()
    def sample():
        while not stop.is_set():
            total=0
            for child in [process]+process.children(recursive=True):
                try:total+=child.memory_info().rss
                except psutil.Error:pass
            rss[0]=max(rss[0],total);stop.wait(.05)
    sampler=threading.Thread(target=sample,daemon=True);sampler.start()
    library=Library(directory/'isolated-data');manager=FontManager(library)
    try:
        asset=manager.import_font(font or choose_font(),True);jobs=DesignJobs(library)
        job=jobs.create('OWNED_SOURCE_FILE_BENCHMARK',dict(font_asset=asset,items=list(range(count))),
            'OWNED_SYNTHETIC_BENCHMARK',True);claimed=jobs.claim(job['id'],job['revision']);state={'done':0}
        def progress(value):
            state['done']=value['done']
            if value['done']%25==0:print(json.dumps(value),flush=True)
        paused=run_design_job(library.root,job['id'],claimed['owner']['token'],
            cancel=lambda:state['done']>=min(pause_after,count-1),progress=progress)
        prefix_digest=digest(jobs.results(job['id']));prefix_count=paused['next_index'];identity=job['id']
        manager.close();library.close();library=Library(directory/'isolated-data');manager=FontManager(library);jobs=DesignJobs(library)
        if digest(jobs.results(identity))!=prefix_digest:raise AssertionError('Durable prefix changed after reopen')
        job=jobs.current(identity);claimed=jobs.claim(identity,job['revision'])
        completed=run_design_job(library.root,identity,claimed['owner']['token'],progress=progress)
        if completed['phase']!='COMPLETE' or digest(jobs.results(identity)[:prefix_count])!=prefix_digest:
            raise AssertionError('Source-file batch or exact durable prefix failed')
        result=dict(completed['summary'],status='PASS',wall_seconds=time.perf_counter()-start,
            paused_at=prefix_count,reopened_prefix_unchanged=True,peak_process_tree_rss_sampled_bytes=rss[0],
            rss_scope='50MS_SAMPLED_PARENT_AND_CHILDREN_NOT_EXACT_PEAK_OR_VIVOBOOK_QUALIFICATION')
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result
    finally:stop.set();sampler.join();manager.close();library.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True);parser.add_argument('--count',type=int,choices=(6,1000,3000),required=True);parser.add_argument('--font')
    args=parser.parse_args();print(json.dumps(run(args.directory,args.count,args.font),ensure_ascii=False))
