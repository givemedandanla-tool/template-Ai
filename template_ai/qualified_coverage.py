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
        historical_roles=getattr(self,'historical_roles',{}).get(source['hash'],set())
        combined=historical_roles|({role} if role!='UNASSIGNED' else set())
        if len(combined)==1:role=next(iter(combined))
        elif len(combined)>1:role='ROLE_CONFLICT'
        holdout_state=None
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
            from .quality_protocol import CONSUMED
            holdout_state='EXPOSED_NOT_FRESH' if self.store.get('HOLDOUT_EXPOSED',reference['dataset_id']) else 'CONSUMED_EXISTING_PROTOCOL_ONLY' if self.store.get(CONSUMED,source['hash']) else 'REGISTERED_GOLD_FRESHNESS_NOT_GRANTED'
            signature=digest([source['hash'],source['byte_size'],record['width_mm'],record['height_mm'],[{k:o.get(k) for k in ('kind','owner','text','rect')} for o in record['objects']]])
        else:
            state='PENDING_CANDIDATE';reason.append('候選未獲訓練准入，不混入可訓練樣本')
        known=known and facts_state=='CONFIRMED' and work['payload'].get('visual_confirmed') is True
        if collection in ('APPROVED_TRAINABLE','VALIDATION'):matches=matches and known
        facets=self.facets(work,source,known,gold)
        return dict(holdout_state=holdout_state,id=record['id'],record_kind=reference['kind'],record_revision=record['revision'],work_id=work_id,work_revision=work['revision'],source_id=source['id'],source_hash=source['hash'],source_byte_size=source['byte_size'],source_name=Path(source.get('original_path') or source['current_path']).name,work_name=work['name'],role=role,state=state,known=known,matches=matches,facets=facets,exact_label_signature=signature,scope_stamp=self.stamp(work_id),dataset_id=reference.get('dataset_id'),reasons=reason,facts_state=facts_state)

    def facets(self,work,source,known,gold=None):
        if not known:return {axis:'UNKNOWN' for axis in ('size','people','companies','logo','native_text','special_effect','ocr','multi_work')}
        slots=work['payload']['slots'];people=len({s['owner'] for s in slots if s['owner'].startswith('p')});companies=len({s['owner'] for s in slots if s['owner'].startswith('c')});logo='UNKNOWN'
        if gold:
            from .quality_facets import describe
            described=describe([gold],dict(group_components=[],whole_source_gold_complete=False,evaluation_role='HOLDOUT'));values=described['logo'];logo=values[0] if len(values)==1 else 'MULTIPLE_VERIFIED_TYPES'
        evidence=work['payload'].get('analysis_evidence',{});proofs=[p for p in evidence.get('text_object_evidence',{}).values() if p.get('source_hash')==source['hash'] and p.get('derivative_hash')==source.get('file_hashes',{}).get('svg') and p.get('evidence_channel')=='INKSCAPE_SVG_DERIVATIVE']
        native='DERIVATIVE_TEXT_NATIVE_UNVERIFIED' if any(p.get('classification')=='DERIVATIVE_TEXT' for p in proofs) else 'UNKNOWN'
        effects='DERIVATIVE_EFFECT_ATTRIBUTES_NATIVE_TYPE_UNKNOWN' if any(p.get('observed_effect_attributes') for p in proofs) else 'UNKNOWN'
        ocr=evidence.get('ocr',{});ocr_class='LOCAL_OCR_EXECUTION_RECORDED_NATIVE_UNKNOWN' if ocr.get('executed') is True and ocr.get('algorithm_version') and ocr.get('model_hashes') and work['payload'].get('analysis_key') else 'UNKNOWN'
        count=self.db.execute("SELECT count(*) FROM artworks WHERE source_id=? AND COALESCE(json_extract(payload,'$.segmentation_state'),'')!='SUPERSEDED'",(source['id'],)).fetchone()[0]
        return dict(size=f"{work['payload']['work_width']:g}×{work['payload']['work_height']:g}mm",people='3+' if people>=3 else str(people),companies=str(companies),logo=logo,native_text=native,special_effect=effects,ocr=ocr_class,multi_work='SOURCE_HAS_MULTIPLE_REGISTERED_WORKS_COMPLETENESS_UNKNOWN' if count>1 else 'SOURCE_HAS_ONE_REGISTERED_WORK_COMPLETENESS_UNKNOWN')

    def report(self,collection='APPROVED_TRAINABLE',dataset_id=None,offset=0,save_snapshot=True):
        if collection not in COLLECTIONS or type(offset) is not int or offset<0 or type(save_snapshot) is not bool:raise ValueError('覆蓋統計需明確集合與50筆分頁')
        epoch=self.store.epoch;version=self.db.execute('PRAGMA data_version').fetchone()[0];groups=QualityGroups(self.library);graph,state,_=groups.graph_state();references,total,label=self.roster(collection,dataset_id,offset)
        self.historical_roles=defaultdict(set)
        for sha,role in groups.model_exposure_roles():self.historical_roles[sha].add(role)
        inspected=[self.row(ref,collection,groups,graph) for ref in references];matched=[r for r in inspected if r['matches']];qualified=[r for r in matched if r['known']];facets=defaultdict(lambda:defaultdict(set));signature_sets=defaultdict(lambda:defaultdict(set));representatives={}
        for row in matched:
            signature=row.get('exact_label_signature') or 'UNKNOWN:'+row['id']
            for axis,value in row['facets'].items():
                facets[axis][value].add(row['work_id'])
                if row['known']:signature_sets[axis][value].add(signature)
            if row['known']:representatives.setdefault(signature,row)
        hashes={r['source_hash'] for r in qualified};projection=groups.projection(sorted(hashes),graph=graph,state=state)
        counts=dict(scanned_record_occurrences=len(references),matching_record_occurrences=len(matched),currently_verified_occurrences=len(qualified),distinct_source_files=len({r['source_id'] for r in qualified}),distinct_artworks=len({r['work_id'] for r in qualified}),exact_content_groups=len({(r['source_hash'],r['source_byte_size']) for r in qualified}),deduplicated_approved_label_weights=len(representatives),declared_related_groups=len(projection['components']))
        counts['exposed_or_consumed_holdout_members']=sum(r.get('holdout_state') in ('EXPOSED_NOT_FRESH','CONSUMED_EXISTING_PROTOCOL_ONLY') for r in matched)
        roles=dict(Counter(r.get('role','UNKNOWN') for r in matched));statuses=dict(Counter(r['state'] for r in inspected));notices=[]
        if not qualified:notices.append('本掃描範圍沒有可列入此集合的當前有效資料；不代表模型不合格或正式無解')
        if offset or total>50:notices.append('目前僅此50筆掃描頁；全庫有效數與代表性尚未由本頁決定')
        if any('UNKNOWN' in values for values in facets.values()):notices.append('部分分類缺可靠核實依據，顯示未知，不猜原生效果／Logo類型／代表性')
        if collection=='QUALITY_HOLDOUT':notices.append('保留集此頁只描述已登錄成員與真值資格；使用／曝光另列，不授予新的獨立驗收資格')
        notices.append('各分類可重疊；不能加總不同軸件數當獨立樣本，也不設定任意最少數量／比例或補樣任務')
        result=dict(collection=collection,collection_label=label,dataset_id=dataset_id,offset=offset,limit=50,roster_total=total,scan_complete=offset==0 and total<=50,counts=counts,roles=roles,scanned_states=statuses,rows=matched,artworks=[dict(work_id=r['work_id'],work_revision=r['work_revision'],facts_state=r['facts_state']) for r in matched if r.get('work_id')],facets={axis:{value:sorted(wids) for value,wids in sorted(values.items())} for axis,values in sorted(facets.items())},facet_label_weights={axis:{value:len(signatures) for value,signatures in sorted(values.items())} for axis,values in sorted(signature_sets.items())},facet_denominator='MATCHED_ROWS_IN_THIS_SCANNED_COLLECTION; WORK_IDS_DISTINCT_WITHIN_CATEGORY, AXES_OVERLAP',related_group_basis='EXISTING_DECLARED_RELATION_COMPONENTS; NOT_PROVEN_INDEPENDENT_QUALITY_GROUPS',independence_unknown=True,source_epoch=epoch,created=time.time(),notices=notices,supplementation=False,quality_pass_claim=False,automatic_training=False,images_loaded=False,model_weights_loaded=False)
        if self.store.epoch!=epoch or self.db.execute('PRAGMA data_version').fetchone()[0]!=version:raise ValueError('統計期間版本變更，未混用不同版本計數；請重算')
        for row in matched:
            if row.get('work_id') and self.stamp(row['work_id'])!=row['scope_stamp']:raise ValueError('統計期間來源／作品改變；請重新計數')
        result['snapshot_digest']=digest(result)
        if save_snapshot:
            payload=copy.deepcopy(result);payload['collection_label']=collection
            for row in payload['rows']:
                row.pop('work_name',None);row.pop('source_name',None);row.pop('reasons',None)
            with self.store.transaction():
                if self.store.epoch!=epoch or self.db.execute('PRAGMA data_version').fetchone()[0]!=version:raise ValueError('計數保存前資料版本改變，舊數值未冒稱目前有效')
                payload['source_epoch_after_snapshot']=epoch+1
                saved=self.store._write('COVERAGE_SNAPSHOT',new_id(),payload,0,'descriptive_coverage_snapshot_saved_not_quality_gate')
            result.update(snapshot_id=saved['id'],source_epoch_after_snapshot=epoch+1)
        return result

    def snapshots(self,offset=0):
        if type(offset) is not int or offset<0:raise ValueError('快照目錄需有效分頁')
        rows=self.db.execute("SELECT id,revision,json_extract(payload,'$.collection'),json_extract(payload,'$.created'),json_extract(payload,'$.source_epoch') FROM training_records WHERE kind='COVERAGE_SNAPSHOT' ORDER BY rowid DESC LIMIT 50 OFFSET ?",(offset,))
        return dict(rows=[dict(id=r[0],revision=r[1],collection=r[2],created=r[3],source_epoch=r[4]) for r in rows],offset=offset,total=self.store.count('COVERAGE_SNAPSHOT'))

    def historical(self,identity):
        row=self.store.get('COVERAGE_SNAPSHOT',identity)
        if not row:raise ValueError('統計快照不存在')
        return dict(snapshot=row,current_eligibility_claim=False,requires_recalculation=True,scope='HISTORICAL_COUNTS_ONLY_NOT_CURRENT_QUALITY_OR_INDEPENDENCE')
