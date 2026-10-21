"""Bounded subprocess commands for coverage; uses the existing process isolation helper."""
import json
import subprocess
import sys
import time
from .runtime_worker import stop_tree

MAX_BYTES=32*1024*1024


def execute(root,command,payload):
    from .storage import Library
    from .training_store import TrainingStore
    from .coverage_batches import CoverageBatches
    from .metadata_snapshot import read_snapshot
    library=Library(root)
    try:
        TrainingStore(library);service=CoverageBatches(library)
        if command=='BATCHES':
            with read_snapshot(library.db):
                offset=payload.get('offset',0);query=payload.get('query','')
                if type(offset) is not int or offset<0 or not isinstance(query,str) or len(query)>500:raise ValueError('查詢範圍無效')
                args=['COVERAGE_BATCH'];where="kind=?"
                for token in query.casefold().split():where+=" AND instr(training_casefold(id||' '||payload),?)>0";args.append(token)
                total=library.db.execute('SELECT count(*) FROM training_records WHERE '+where,args).fetchone()[0]
                rows=[service.batch(row[0]) for row in library.db.execute('SELECT id FROM training_records WHERE '+where+" ORDER BY json_extract(payload,'$.created') DESC,id LIMIT 50 OFFSET ?",(*args,offset))]
                return dict(rows=[{key:row[key] for key in ('id','revision','state','file_count','source_page_count','created')} for row in rows],total=total,offset=offset)
        if command=='PLAN_FILES':return service.plan_source_files(payload['paths'],payload.get('selected_source_ids'))
        if command=='PLAN_ROOT':return service.plan_directory(payload['root'],payload.get('recursive',True),payload.get('extensions'),payload.get('selected_source_ids'))
        if command=='MEMBERS':return dict(batch=service.batch(payload['batch_id']),page=service.members(payload['batch_id'],payload.get('offset',0),50,payload.get('query',''),payload.get('group_by','file')),summary=service.boundary_summary(payload['batch_id']))
        if command=='DETAIL':return service.refresh_assessment(payload['member_id'])
        if command=='PLAN_GROUP_RULE':return service.group_rule_plan(payload['member_ids'],payload['rule_id'],payload['rule_revision'])
        if command=='CHECK':return service.check_member_sources(payload['member_id'],payload['revision'])
        if command=='PLAN_SEGMENTATION':return service.segmentation_plan(payload['member_id'],payload['work_ids'],payload['reason'])
        if command=='PLAN_LAYER':return service.layer_plan(payload['member_id'],payload['work_id'],payload['layer'],payload['decision'],payload['reason'],payload['evidence'])
        if command=='PLAN_EXCLUSION':return service.exclusion_plan(payload['member_id'],payload['reason'],payload['evidence'])
        if command=='PLAN_CLOSE':return service.closure_plan(payload['batch_id'])
        if command=='CLOSURE_STATUS':return service.closure_status(payload['batch_id'])
        if command=='PLAN_REOPEN':
            batch=service.batch(payload['batch_id']);details=batch.get('scope_details',{});snapshot=details.get('root_snapshot')
            if snapshot:scope=service.plan_directory(snapshot['root'],snapshot['recursive'],snapshot['extensions'],payload.get('selected_source_ids'))
            elif details.get('declared_paths'):scope=service.plan_source_files(details['declared_paths'],payload.get('selected_source_ids'))
            else:scope=service.plan_registered_sources(batch['source_ids'])
            return dict(batch_id=batch['id'],expected_revision=batch['revision'],new_scope_plan=scope,reason=payload['reason'])
        if command=='CONFIRM':
            action=payload['action'];plan=payload['plan'];actor=payload['actor'];approved=payload.get('approved',False)
            methods={'CREATE':service.create,'SEGMENTATION':service.confirm_segmentation,'LAYER':service.confirm_layer,'EXCLUSION':service.confirm_exclusion,'CLOSE':service.close,'GROUP_RULE':service.confirm_group_rule}
            if action in methods:return methods[action](plan,actor,approved)
            if action=='REOPEN':return service.reopen(plan['batch_id'],plan['expected_revision'],plan['new_scope_plan'],actor,plan['reason'],approved)
        raise ValueError('不支援此覆蓋審核命令')
    finally:library.close()


def run_command(root,command,payload,*,cancel=None,timeout=120,module='template_ai.coverage_command'):
    if module not in ('template_ai.coverage_command','template_ai.quality_command'):raise ValueError('不支援的核對程序')
    data=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
    if len(data)>MAX_BYTES:raise ValueError('命令metadata超過32MiB，需明確分組')
    if cancel and cancel.is_set():raise ValueError('已取消，尚未開始')
    from .launch import worker_command
    process=subprocess.Popen(worker_command(module,root,command),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    start=time.monotonic();first=True
    try:
        while True:
            if cancel and cancel.is_set() or time.monotonic()-start>timeout:
                stop_tree(process);raise ValueError('核對程序已隔離停止；結果尚未確認，請刷新讀回持久資料，不自動重試')
            try:
                stdout,stderr=process.communicate(data if first else None,timeout=.25);break
            except subprocess.TimeoutExpired:first=False
        if len(stdout)>MAX_BYTES:raise ValueError('結果超過32MiB，未當完整快照')
        if process.returncode:raise ValueError(stderr[-4096:].decode('utf-8','replace') or '核對程序未完成，請刷新持久資料')
        result=json.loads(stdout)
        if 'error' in result:raise ValueError(result['error'])
        return result['result']
    finally:
        if process.poll() is None:stop_tree(process)
        process.wait()
        for stream in (process.stdin,process.stdout,process.stderr):
            if stream:stream.close()


def main(executor=execute):
    from .offline_runtime import enable_offline_guard
    enable_offline_guard()
    try:
        raw=sys.stdin.buffer.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('命令超過有界metadata')
        result=dict(result=executor(sys.argv[1],sys.argv[2],json.loads(raw)))
        encoded=json.dumps(result,ensure_ascii=False,allow_nan=False).encode()
        if len(encoded)>MAX_BYTES:raise ValueError('結果超過有界metadata，請縮小範圍')
    except Exception as error:encoded=json.dumps(dict(error=str(error)[:4000]),ensure_ascii=False).encode()
    sys.stdout.buffer.write(encoded);sys.stdout.buffer.flush()


if __name__=='__main__':main()
