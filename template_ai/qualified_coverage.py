"""Bounded, purpose-aware sample distributions; counts never imply quality or supplementation."""
import copy,time
from collections import Counter,defaultdict
from pathlib import Path
from .training_store import TrainingStore,digest
from .datasets import exact_label_signature
from .quality_groups import QualityGroups
from .quality_gold import QualityGold
from .trusted_samples import cache_stamps
from .model import new_id
from .source_links import fingerprint

COLLECTIONS=('APPROVED_TRAINABLE','CANDIDATE_PENDING','EXCLUDED','VALIDATION','QUALITY_HOLDOUT','EXACT_DATASET')


class QualifiedCoverage:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library);self.db=library.db

    def roster(self,collection,dataset_id,offset):
        if collection=='EXACT_DATASET':
            dataset=self.store.get('DATASET',dataset_id)
            if not dataset or digest(dataset['manifest'])!=dataset['manifest_digest'] or dataset['entries']!=dataset['manifest']['entries']:raise ValueError('明確選取可核對的精確資料集版本')
            if len(dataset['entries'])>200:raise ValueError('資料集超過既有200筆預算，不截斷')
            return [dict(kind='SAMPLE',id=e['sample_id'],entry=e,dataset_id=dataset_id) for e in dataset['entries'][offset:offset+50]],len(dataset['entries']),dataset['manifest']['name']
        if collection=='QUALITY_HOLDOUT':
            where="q.kind='QUALITY_SET' AND COALESCE(json_extract(q.payload,'$.manifest.evaluation_role'),'HOLDOUT')='HOLDOUT'";args=[]
            if dataset_id:where+=' AND q.id=?';args.append(dataset_id)
            base=" FROM training_records q,json_each(q.payload,'$.entries') e WHERE "+where;total=self.db.execute('SELECT count(*)'+base,args).fetchone()[0]
            rows=self.db.execute("SELECT q.id,json_extract(e.value,'$.gold_id'),json_extract(e.value,'$.gold_revision')"+base+' ORDER BY q.id,CAST(e.key AS INTEGER) LIMIT 50 OFFSET ?',(*args,offset))
            return [dict(kind='QUALITY_GOLD',id=r[1],entry=dict(gold_revision=r[2]),dataset_id=r[0]) for r in rows],total,'獨立品質保留集的精確成員出現次數'
        kind='SAMPLE_CANDIDATE' if collection=='CANDIDATE_PENDING' else 'SAMPLE';where='kind=?';args=[kind]
        if kind=='SAMPLE_CANDIDATE':where+=" AND json_extract(payload,'$.state') IN ('COLLECTED','DEFERRED')"
        total=self.db.execute('SELECT count(*) FROM training_records WHERE '+where,args).fetchone()[0]
        return [dict(kind=kind,id=r[0]) for r in self.db.execute('SELECT id FROM training_records WHERE '+where+' ORDER BY id LIMIT 50 OFFSET ?',(*args,offset))],total,'目前保存的'+('待審修正候選' if kind=='SAMPLE_CANDIDATE' else '樣本')+'；有效資格逐筆核對'

    def stamp(self,work_id):
        work=self.library.artwork(work_id);source=self.library.source(work['source_id'])
        try:raw=list(fingerprint(Path(source['current_path']).stat()));cache=cache_stamps(source)
        except OSError:raw='MISSING_OR_INACCESSIBLE';cache='MISSING_OR_INACCESSIBLE'
        return digest([self.store.pins(work_id),raw,cache])

    def row(self,reference,collection,groups,graph):
        record=self.store.get(reference['kind'],reference['id'])
        if not record:return dict(id=reference['id'],state='MISSING',matches=collection in ('EXCLUDED','EXACT_DATASET','QUALITY_HOLDOUT'),known=False,facets={},reason='精確版本的來源記錄失聯')
        work_id=record['work_id'];work=self.library.artwork(work_id);source=self.library.source(work['source_id']);facts_state=self.store.facts_state(work_id);role_row=self.store.get('GROUP_ROLE',source['hash']);role=role_row['role'] if role_row else 'UNASSIGNED';entry=reference.get('entry') or {};state=record.get('state','UNKNOWN');known=False;matches=True;signature=None;reason=[];gold=None
        if reference['kind']=='SAMPLE':
            state=self.store.sample_state(record['id']);known=state=='APPROVED' and record.get('source_byte_size')==source['byte_size'];signature=exact_label_signature(record)
            if not known:reason.append('目前准入／來源／長度釘選無效或未知')
            if entry and (record['revision']!=entry['sample_revision'] or record['scope_digest']!=entry['scope_digest']):known=False;reason.append('保存資料集的exact樣本版本已失效')
            if collection=='APPROVED_TRAINABLE':matches=known and role not in ('VALIDATION','HOLDOUT') and not groups.role_conflicts([(source['hash'],'TRAIN')],graph=graph)
            elif collection=='VALIDATION':matches=known and role=='VALIDATION' and not groups.role_conflicts([(source['hash'],'VALIDATION')],graph=graph)
            elif collection=='EXCLUDED':matches=not known
            if entry:role=entry['role']
        elif reference['kind']=='QUALITY_GOLD':
            checked=QualityGold(self.library).validity(record['id'],verify_bytes=False);known=checked['valid'] and record['revision']==entry.get('gold_revision');state='VALID_QUALITY_GOLD' if known else 'INVALID_QUALITY_GOLD';role='HOLDOUT';reason+=checked['errors'];gold=record
            signature=digest([source['hash'],source['byte_size'],record['width_mm'],record['height_mm'],[{k:o.get(k) for k in ('kind','owner','text','rect')} for o in record['objects']]])
        else:
            state='PENDING_CANDIDATE';reason.append('候選未獲訓練准入，不混入可訓練樣本')
        known=known and facts_state=='CONFIRMED' and work['payload'].get('visual_confirmed') is True
        facets=self.facets(work,source,known,gold)
        return dict(id=record['id'],record_kind=reference['kind'],record_revision=record['revision'],work_id=work_id,work_revision=work['revision'],source_id=source['id'],source_hash=source['hash'],source_byte_size=source['byte_size'],source_name=Path(source.get('original_path') or source['current_path']).name,work_name=work['name'],role=role,state=state,known=known,matches=matches,facets=facets,exact_label_signature=signature,scope_stamp=self.stamp(work_id),dataset_id=reference.get('dataset_id'),reasons=reason,facts_state=facts_state)

    def facets(self,work,source,known,gold=None):
        if not known:return {axis:'UNKNOWN' for axis in ('size','people','companies','logo','native_text','special_effect','ocr','multi_work')}
        slots=work['payload']['slots'];people=len({s['owner'] for s in slots if s['owner'].startswith('p')});companies=len({s['owner'] for s in slots if s['owner'].startswith('c')});logo='UNKNOWN'
        if gold:
            from .quality_facets import describe
            described=describe([gold],dict(group_components=[],whole_source_gold_complete=False,evaluation_role='HOLDOUT'));values=described['logo'];logo=values[0] if len(values)==1 else 'MULTIPLE_VERIFIED_TYPES'
        count=self.db.execute("SELECT count(*) FROM artworks WHERE source_id=? AND COALESCE(json_extract(payload,'$.segmentation_state'),'')!='SUPERSEDED'",(source['id'],)).fetchone()[0]
        return dict(size=f"{work['payload']['work_width']:g}×{work['payload']['work_height']:g}mm",people='3+' if people>=3 else str(people),companies=str(companies),logo=logo,native_text='UNKNOWN',special_effect='UNKNOWN',ocr='UNKNOWN',multi_work='SOURCE_HAS_MULTIPLE_REGISTERED_WORKS_COMPLETENESS_UNKNOWN' if count>1 else 'SOURCE_HAS_ONE_REGISTERED_WORK_COMPLETENESS_UNKNOWN')
