"""One resumable pipeline in the existing TrainingStore; never auto-approve facts.

Each source/work unit is pinned and committed independently. Retry does not rerun
unrelated valid units. A SQLite/audit integrity failure stops the shared worker.
"""
from copy import deepcopy
import os
from pathlib import Path
import sqlite3
import time
from .batch_import import preflight,convert_item,healthy_source
from .model import new_id
from .source_links import verify_source
from .training_pipeline import LIVE_OWNERS,owner_alive
from .training_quality import analyse_work
from .training_store import TrainingStore,digest,text


class AutomaticTraining:
    def __init__(self,library):
        self.library=library;self.store=TrainingStore(library);self.db=library.db

    def preflight(self,paths,page=1):
        report=preflight(paths,self.library.list_sources(),page)
        for item in report['items']:
            matching=[s for s in self.library.list_sources() if s['hash']==item.get('expected_hash') and s['page']==page and Path(s['current_path']).resolve()==Path(item['path']).resolve()]
            item['existing_source_id']=matching[0]['id'] if matching else None
        report['scope']='來源／作品／候選標記／品質／已授權幾何學習一鍵管線；人工事實、樣本准入及發布不自動核准'
        return report

    def create(self,report,actor,approved=False):
        if approved is not True:raise ValueError('需先核對預檢並明確開始訓練')
        text(actor,'啟動者',120)
        fresh=self.preflight([i['path'] for i in report['items']],report['page'])
        identity=lambda r:[(i['path'],i.get('expected_hash'),i['page'],i['status'],i.get('existing_source_id')) for i in r['items']]
        if identity(fresh)!=identity(report):raise ValueError('預檢來源已變更，請重新核對')
        # Duplicate bytes keep separate source identities / customer-code evidence.
        rows=[dict(path=i['path'],page=i['page'],source_hash=i.get('expected_hash'),state='READY' if i['status'] in ('READY','SKIPPED') else 'FAILED',
            source_id=i.get('existing_source_id'),error=None if i['status'] in ('READY','SKIPPED') else i['reason'],unit_ids=[],attempts=0) for i in fresh['items']]
        with self.store.transaction():return self.store._write('AUTO_JOB',new_id(),dict(phase='READY',items=rows,actor=actor,created=time.time(),owner=None,cancel_requested=False),0,'automatic_pipeline_preflight_confirmed')

    def get(self,identity):
        row=self.store.get('AUTO_JOB',identity)
        if row is None:raise ValueError('自動分析工作不存在')
        return row

    def retry_plan(self,work_ids):
        if not work_ids or len(work_ids)>200 or len(set(work_ids))!=len(work_ids):raise ValueError('請明確選取1～200個不同作品')
        return dict(items=[dict(work_id=wid,pins=self.store.pins(wid),signature=self.work_signature(self.library.artwork(wid))) for wid in sorted(work_ids)])

    def create_retry(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需明確確認此作品修正／重分析範圍')
        text(actor,'操作者',120)
        with self.store.transaction():
            if self.retry_plan([r['work_id'] for r in plan['items']])!=plan:raise ValueError('修正或來源在確認期間變更，請重新核對')
            items=[]
            for row in plan['items']:
                source=self.library.source(row['pins']['source_id'])
                items.append(dict(path=source['current_path'],page=source['page'],source_hash=source['hash'],source_id=source['id'],state='READY',unit_ids=[],attempts=0,error=None,work_scope=[row['work_id']],expected_pins=row['pins']))
            return self.store._write('AUTO_JOB',new_id(),dict(phase='READY',items=items,actor=actor,created=time.time(),owner=None,cancel_requested=False,scope='EXACT_CHANGED_WORKS_ONLY'),0,'affected_work_retry_confirmed')

    def phase(self,row):
        return 'INTERRUPTED' if row['phase']=='RUNNING' and not owner_alive(row.get('owner')) else row['phase']

    def claim(self,identity,revision,approved=False,retry=False):
        if approved is not True:raise ValueError('需明確啟動／接續確切工作')
        with self.store.transaction():
            row=self.get(identity)
            if row['revision']!=revision:raise ValueError('工作版本已更新')
            for worker in ('geometry-worker','automatic-worker'):
                lease=self.store.get('WORKER',worker)
                if lease and lease.get('active') and owner_alive(lease.get('owner')):raise ValueError('已有訓練worker執行，不重複啟動')
            if self.phase(row)=='RUNNING':raise ValueError('已有執行者，不接管')
            for item in row['items']:
                if item['state'] in ('RUNNING','WAITING_REVIEW','STALE') or retry and item['state']=='FAILED':item['state']='READY'
            owner=dict(pid=os.getpid(),token=new_id());row.update(phase='RUNNING',owner=owner,cancel_requested=False)
            lease=self.store.get('WORKER','automatic-worker')
            self.store._write('WORKER','automatic-worker',dict(active=True,owner=owner,job_id=identity),lease['revision'] if lease else 0,'automatic_worker_claimed')
            result=self.store._write('AUTO_JOB',identity,row,revision,'automatic_job_started')
        LIVE_OWNERS.add(owner['token']);return result

    def owned(self,identity,token):
        row=self.get(identity)
        if row['phase']!='RUNNING' or (row.get('owner') or {}).get('token')!=token or not owner_alive(row['owner']):raise ValueError('自動工作執行者已失效')
        return row

    def finish(self,identity,token,phase,error=None):
        with self.store.transaction():
            row=self.owned(identity,token);row.update(phase=phase,finished=time.time(),system_error=error)
            result=self.store._write('AUTO_JOB',identity,row,row['revision'],'automatic_job_'+phase.lower())
            lease=self.store.get('WORKER','automatic-worker');lease['active']=False
            self.store._write('WORKER','automatic-worker',lease,lease['revision'],'automatic_worker_released')
            return result

    def work_signature(self,work):
        facts=self.store.facts(work['id']);source=self.library.source(work['source_id'])
        samples=list(self.db.execute("SELECT id,revision FROM training_records WHERE kind='SAMPLE' AND json_extract(payload,'$.work_id')=? ORDER BY id",(work['id'],)))
        return digest([self.store.pins(work['id']),facts,self.store.noise_signature(work['id']),samples,source['file_hashes']])

    def process_work(self,work,job):
        from .source_analysis import ANALYSER_VERSION
        identity=digest([work['id'],ANALYSER_VERSION]);before=self.store.get('AUTO_UNIT',identity);signature=self.work_signature(work)
        if before and (before['state']=='EXCLUDED' or before['input_signature']==signature and before['state'] in ('WAITING_REVIEW','DRAFT_READY')):
            return before,True
        proof=self.store.source_proof(work['id']);self.store.checked(work['id'],proof)
        quality=analyse_work(work,self.library.source(work['source_id']));facts=self.store.facts(work['id'])
        noise=self.store.noise_decisions(work['id']);issues=[r for r in quality if r['severity'] in ('BLOCK','REVIEW')]
        templates=[];state='WAITING_REVIEW'
        approved=[self.store.get('SAMPLE',sid) for sid, in self.db.execute("SELECT id FROM training_records WHERE kind='SAMPLE' AND json_extract(payload,'$.work_id')=? ORDER BY id LIMIT 201",(work['id'],))]
        if len(approved)>200:raise ValueError('單作品樣本超過200，需縮小已授權學習範圍')
        for sample in approved:
            if self.store.sample_state(sample['id'])!='APPROVED':continue
            entries=list(self.db.execute("SELECT DISTINCT d.id FROM training_records d,json_each(d.payload,'$.entries') e WHERE d.kind='DATASET' AND json_extract(e.value,'$.sample_id')=? AND json_extract(e.value,'$.role')='TRAIN' ORDER BY d.id LIMIT 201",(sample['id'],)))
            if len(entries)>200:raise ValueError('單樣本資料集超過200，需明確縮小學習範圍')
            for dataset_id, in entries:
                if not self.store.dataset_validity(dataset_id,[sample['id']])['valid']:continue
                existing=self.store.existing_geometry_result(dataset_id,sample['id'])
                if existing:templates.append(existing)
                else:
                    plan=self.store.geometry_learning_plan(dataset_id,sample['id'],'自動分析幾何候選')
                    templates.append(self.store.learn_dataset_sample(plan,proof,job['actor'],True).id)
        if templates:state='DRAFT_READY'
        payload=dict(work_id=work['id'],source_id=work['source_id'],input_signature=self.work_signature(work),state=state,
            pins=self.store.pins(work['id']),facts_state=self.store.facts_state(work['id']),issues=issues,
            noise=noise,template_ids=sorted(set(templates)),analysis_version=ANALYSER_VERSION,
            stages=dict(geometry='CHECKED',facts='CONFIRMED' if self.store.facts_state(work['id'])=='CONFIRMED' else 'NEEDS_REVIEW',noise='EVALUATED',learning='DRAFT_ONLY' if templates else 'WAITING_SAMPLE_AND_TRAIN_AUTHORIZATION'),
            reason='只使用有效已准入TRAIN與已核對事實；候選結果從不自動發布',created=time.time())
        with self.store.transaction():return self.store._write('AUTO_UNIT',identity,payload,before['revision'] if before else 0,'automatic_work_analysed'),False

    def run_source(self,item,job,cancel=None):
        from .source_analysis import analyse_source
        path=Path(item['path']);verify_source(path,item['source_hash'])
        source=self.library.source(item['source_id']) if item.get('source_id') else None
        if source is None:
            source=next((s for s in self.library.list_sources() if s['hash']==item['source_hash'] and s['page']==item['page'] and Path(s['current_path']).resolve()==path.resolve()),None)
        if source is None:
            reuse=next((s for s in self.library.list_sources() if s['hash']==item['source_hash'] and s['page']==item['page'] and healthy_source(s)),None)
            result=convert_item(dict(path=str(path),page=item['page'],expected_hash=item['source_hash'],reuse_source=reuse),self.library.assets)
            source=self.library.add_source(path,result['payload']);source=self.library.source(source['id'])
        if not healthy_source(source):raise ValueError('來源或衍生快取失效，需重新核對')
        works=self.library.artworks(source['id'])
        works=[w for w in works if w['payload'].get('segmentation_state')!='SUPERSEDED']
        if item.get('work_scope'):
            if self.store.pins(item['work_scope'][0])!=item['expected_pins']:raise ValueError('選定作品在啟動前又變更，未套用舊分析')
            works=[w for w in works if w['id'] in item['work_scope']]
            if {w['id'] for w in works}!=set(item['work_scope']):raise ValueError('作品不屬確認來源')
        if not item.get('work_scope') and (not works or all(w['payload'].get('analysis_key') for w in works)):
            hypotheses=analyse_source(source,self.library.assets)
            for number,hypothesis in enumerate(hypotheses,1):
                if cancel and cancel.is_set():break
                if any(w['payload'].get('analysis_key')==hypothesis['key'] for w in works):continue
                # Atomically save the source-derived work and unconfirmed observations.
                with self.store.transaction():
                    payload={k:deepcopy(hypothesis[k]) for k in ('crop','work_width','work_height','slots','visual_confirmed','company_bindings')}
                    payload['analysis_evidence']=hypothesis['evidence']
                    payload['analysis_key']=hypothesis['key']
                    encoded=self.library._artwork_payload(source['id'],payload);wid=new_id()
                    self.db.execute('INSERT INTO artworks VALUES(?,?,?,1,?)',(wid,source['id'],'AI候選作品 '+str(number),encoded))
                    self.db.execute('INSERT INTO artwork_revisions VALUES(?,1,?,?)',(wid,encoded,time.time()))
                    self.library.event(wid,'automatic_source_work_proposed_not_confirmed')
                    work=self.library.artwork(wid)
                    if hypothesis['observations']:
                        observations=self.store.validate_observations(wid,hypothesis['observations'])
                        for observation in observations:observation['evidence']='AI_SOURCE_HYPOTHESIS'
                        self.store._write('FACTS',wid,dict(observations=observations,confirmation=None,state='PENDING',pins=self.store.pins(wid)),0,'source_observations_proposed_not_confirmed')
                        self.store._refresh_noise(wid)
                works.append(work)
        units=[];reused=0
        for work in works:
            if cancel and cancel.is_set():break
            try:
                unit,was_reused=self.process_work(work,job);units.append(unit);reused+=int(was_reused)
            except (ValueError,OSError) as error:
                identity=digest([work['id'],'source-hypotheses-1']);old=self.store.get('AUTO_UNIT',identity)
                with self.store.transaction():unit=self.store._write('AUTO_UNIT',identity,dict(work_id=work['id'],source_id=source['id'],state='FAILED',issues=[dict(severity='BLOCK',code='WORK_ANALYSIS',reason=str(error),slot_ids=[],work_id=work['id'])],input_signature=None,template_ids=[],pins=self.store.pins(work['id'])),old['revision'] if old else 0,'automatic_work_isolated')
                units.append(unit)
        return dict(source_id=source['id'],unit_ids=[u['id'] for u in units],state='WAITING_REVIEW' if not units or any(u['state'] in ('FAILED','WAITING_REVIEW') for u in units) else 'SUCCESS',
            analysed_units=len(units)-reused,reused_units=reused,stages_complete=not(cancel and cancel.is_set()))


def run_automatic(root,identity,token,cancel=None,progress=None):
    from .storage import Library
    library=Library(root);service=AutomaticTraining(library)
    try:
        job=service.owned(identity,token)
        for index in range(len(job['items'])):
            job=service.owned(identity,token);item=job['items'][index]
            if cancel and cancel.is_set():return service.finish(identity,token,'CANCELLED')
            if item['state'] not in ('READY','SUCCESS'):continue
            try:
                result=service.run_source(item,job,cancel)
                with service.store.transaction():
                    current=service.owned(identity,token);current['items'][index].update(result,error=None,attempts=item['attempts']+1)
                    job=service.store._write('AUTO_JOB',identity,current,current['revision'],'automatic_source_result_saved')
            except (ValueError,OSError,ET_PARSE_ERROR) as error:
                with service.store.transaction():
                    current=service.owned(identity,token);current['items'][index].update(state='FAILED',error=str(error),attempts=item['attempts']+1)
                    job=service.store._write('AUTO_JOB',identity,current,current['revision'],'automatic_source_isolated')
            if progress:progress(job)
        if cancel and cancel.is_set():return service.finish(identity,token,'CANCELLED')
        return service.finish(identity,token,'COMPLETED_WITH_EXCEPTIONS' if any(i['state'] in ('FAILED','WAITING_REVIEW') for i in job['items']) else 'COMPLETED')
    except BaseException as error:
        try:service.finish(identity,token,'FAILED_SYSTEM',str(error))
        except BaseException:pass
        raise
    finally:LIVE_OWNERS.discard(token);library.close()


from xml.etree.ElementTree import ParseError as ET_PARSE_ERROR
