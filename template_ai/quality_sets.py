"""Immutable quality-only holdout manifests; no training admission or cloud upload."""
import copy
import time
from .quality_gold import QualityGold
from .quality_groups import QualityGroups
from .training_store import TrainingStore,digest,text
from .source_links import verify_source,check_verified,VerifiedSource
from .model import Rect,new_id

SET='QUALITY_SET'


class QualitySets:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library);self.gold=QualityGold(library);self.groups=QualityGroups(library)

    def plan(self,name,gold_ids,inventory_attested=False,independence_reviewed=False,review_reason='',*,verify_bytes=True,declared_paths=None,selected_source_ids=None,evaluation_role='HOLDOUT'):
        text(name,'品質驗收集名稱',120)
        if evaluation_role not in ('HOLDOUT','TRAIN','VALIDATION'):raise ValueError('品質資料角色需明確HOLDOUT或僅診斷TRAIN／VALIDATION')
        if not isinstance(gold_ids,list) or len(gold_ids)>1000 or len(set(gold_ids))!=len(gold_ids) or not gold_ids and not declared_paths:raise ValueError('需明列gold或來源檔案範圍，gold上限1000且不可重複；空集合不當100%')
        if type(inventory_attested) is not bool or type(independence_reviewed) is not bool:raise ValueError('需明確來源作品完整性／群組獨立性核對狀態')
        if inventory_attested or independence_reviewed:text(review_reason,'完整性及近重複／家族核對依據',2000)
        entries=[];errors=[];proofs={};work_ids=set();required_works=set();files={};objects=0;boxes={}
        for gid in sorted(gold_ids):
            validity=self.gold.validity(gid,verify_bytes=False);gold=validity['gold']
            if not validity['valid']:errors += [gid+'：'+e for e in validity['errors']]
            if not gold:continue
            from .quality_gold import USE,DIAGNOSTIC_USE
            expected_use=USE if evaluation_role=='HOLDOUT' else DIAGNOSTIC_USE
            if gold['rights']['use']!=expected_use:errors.append(gid+'：此Gold用途許可不適用所選資料角色，需另行明確核對，不能擴張既有授權')
            if gold['work_id'] in work_ids:raise ValueError('同一作品不能混入不同gold版本重複計分')
            work_ids.add(gold['work_id']);required_works.update(gold['source_inventory_work_ids']);objects+=len(gold['objects'])
            key=(gold['current_path'],gold['source_hash'])
            if validity['valid'] and key not in proofs:
                try:
                    if verify_bytes:
                        proof=verify_source(*key);proofs[key]=dict(path=proof.path,hash=proof.hash,stat=list(proof.stat))
                    else:proofs[key]=copy.deepcopy(gold['source_proof'])
                except (OSError,ValueError) as failure:errors.append(gid+'：'+str(failure))
            file=files.setdefault(gold['original_path'],dict(pages=set(),page_counts=set(),source_ids=set(),source_hashes=set()))
            file['pages'].add(gold['source_page']);file['page_counts'].add(gold['source_page_count']);file['source_ids'].add(gold['source_id']);file['source_hashes'].add(gold['source_hash'])
            page_key=(gold['original_path'],gold['source_page']);crop=Rect(**gold['crop'])
            if any(crop.intersects(other) for other in boxes.get(page_key,[])):errors.append('同頁gold作品切分框重複／跨界，真值仍有爭議')
            boxes.setdefault(page_key,[]).append(crop)
            entries.append(dict(gold_id=gid,gold_revision=gold['revision'],gold_digest=digest(gold),work_id=gold['work_id'],source_id=gold['source_id'],source_hash=gold['source_hash'],role=evaluation_role))
        from .coverage_batches import CoverageBatches
        paths=declared_paths if declared_paths is not None else sorted({p['path'] for p in proofs.values()}|{self.gold.store.get('QUALITY_GOLD',gid)['current_path'] for gid in gold_ids if self.gold.store.get('QUALITY_GOLD',gid)})
        source_scope=CoverageBatches(self.library).plan_source_files(paths,selected_source_ids)
        declared_source_ids=set(source_scope['source_ids']);gold_sources={e['source_id'] for e in entries}
        if not gold_sources<=declared_source_ids:errors.append('有gold不屬明列來源版本；未跨範圍混用')
        source_rows=[];unregistered=[];content_hashes=set();source_unknown_work_count=False
        for member in source_scope['members']:
            pins=member['source_pins'];required_works.update(w['id'] for pin in pins for w in pin['works']);content_hashes.update(member['expected_hashes'])
            if not pins:unregistered.append(member['original_path']);source_unknown_work_count=True
            if any(not pin['works'] for pin in pins):source_unknown_work_count=True
            source_rows.append(dict(logical_file_key=member['logical_file_key'],original_path=member['original_path'],declared_physical_paths=member['declared_physical_paths'],source_ids=[p['source_id'] for p in pins],expected_hashes=member['expected_hashes'],recorded_work_ids=[w['id'] for pin in pins for w in pin['works']],registration_state=member['registration_state']))
            if len(member['expected_hashes'])>1:errors.append('明列來源包含互相矛盾的內容版本，需先選定exact版本')
        missing=sorted(required_works-work_ids);incomplete_pages=[]
        for path,file in files.items():
            if len(file['page_counts'])!=1 or next(iter(file['page_counts'])) is None or file['pages']!=set(range(1,next(iter(file['page_counts']))+1)) or len(file['source_hashes'])!=1:incomplete_pages.append(path)
        assignments=[(sha,evaluation_role) for sha in sorted(content_hashes)];conflicts=self.groups.role_conflicts(assignments) if assignments else []
        errors += [c['reason'] for c in conflicts]
        projection=self.groups.projection(content_hashes);relevant_components=projection['components']
        complete=bool(inventory_attested and entries and not errors and not missing and not incomplete_pages and not unregistered and not source_unknown_work_count and gold_sources==declared_source_ids)
        manifest=dict(schema_version=1,evaluation_role=evaluation_role,name=name,entries=entries,purpose='INDEPENDENT_QUALITY_EVALUATION_LOCAL_ONLY' if evaluation_role=='HOLDOUT' else 'DESCRIPTIVE_FIT_ROLE_DIAGNOSTICS_LOCAL_ONLY',training_admission=False,cloud_upload_allowed=False,inventory_attested=inventory_attested,independence_reviewed=independence_reviewed,review_reason=review_reason,declared_paths=source_scope['declared_paths'],selected_source_ids=selected_source_ids,declared_source_scope_digest=source_scope['scope_digest'],declared_files=source_rows,declared_content_hashes=sorted(content_hashes),physical_path_count=source_scope['physical_path_count'],file_count=source_scope['file_count'],source_page_count=source_scope['source_page_count'],gold_work_count=len(work_ids),gold_object_count=objects,missing_gold_source_ids=sorted(declared_source_ids-gold_sources),unregistered_or_unparsed_files=unregistered,actual_whole_source_work_count=None if source_unknown_work_count else len(required_works),missing_gold_work_ids=missing,incomplete_source_pages=incomplete_pages,whole_source_gold_complete=complete,independent_group_count=len(relevant_components),group_components=relevant_components,group_projection_version=1,group_edges_digest=projection['digest'],unreviewed_near_duplicate_independence_unknown=not independence_reviewed)
        manifest.update(recorded_work_count=len(required_works),actual_whole_source_work_count=len(required_works) if complete else None,independence_scope_ready=bool(evaluation_role=='HOLDOUT' and independence_reviewed and complete and relevant_components),unreviewed_near_duplicate_independence_unknown=not bool(independence_reviewed and complete and relevant_components))
        result=dict(manifest=manifest,manifest_digest=digest(manifest),errors=sorted(set(errors)),source_proofs=list(proofs.values()),quality_pass_claim=False)
        result['digest']=digest(result);return result

    def create(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需核對品質用途／固定gold與獨立群組範圍並明確建立')
        text(actor,'驗收集建立者',120);preview=copy.deepcopy(plan);expected=preview.pop('digest',None)
        if expected!=digest(preview) or plan['errors']:raise ValueError('驗收集預覽已改變或有未解來源／真值／群組角色錯誤')
        manifest=plan['manifest']
        with self.store.transaction():
            for p in plan['source_proofs']:check_verified(VerifiedSource(p['path'],p['hash'],tuple(p['stat'])),p['hash'])
            current=self.plan(manifest['name'],[e['gold_id'] for e in manifest['entries']],manifest['inventory_attested'],manifest['independence_reviewed'],manifest['review_reason'],verify_bytes=False,declared_paths=manifest['declared_paths'],selected_source_ids=manifest['selected_source_ids'],evaluation_role=manifest.get('evaluation_role','HOLDOUT'))
            if current['manifest_digest']!=plan['manifest_digest'] or current['errors']:raise ValueError('來源／真值／角色或家族關聯已變更')
            for sha in manifest['declared_content_hashes']:
                if not self.store.get('GROUP_ROLE',sha):self.store._write('GROUP_ROLE',sha,dict(role=manifest.get('evaluation_role','HOLDOUT'),source_hash=sha,basis='QUALITY_OR_DIAGNOSTIC_ROLE_NOT_TRAINING_ADMISSION',actor=actor),0,'quality_set_source_group_role_locked_not_training')
            return self.store._write(SET,new_id(),dict(state='FROZEN_QUALITY_HOLDOUT' if manifest.get('evaluation_role','HOLDOUT')=='HOLDOUT' else 'FROZEN_FIT_ROLE_DIAGNOSTICS',manifest=copy.deepcopy(manifest),manifest_digest=plan['manifest_digest'],entries=copy.deepcopy(manifest['entries']),actor=actor,created=time.time(),quality_pass=False),0,'independent_quality_set_frozen_not_training')

    def validity(self,identity,verify_bytes=True,*,exposure_policy='REJECT'):
        if exposure_policy not in ('REJECT','DESCRIPTIVE_REPAIR_ONLY'):raise ValueError('未知答案曝露處理政策')
        record=self.store.get(SET,identity)
        if not record:return dict(valid=False,errors=['品質驗收集不存在'],dataset=None)
        manifest=record['manifest'];errors=[]
        if digest(manifest)!=record['manifest_digest'] or record['entries']!=manifest['entries']:errors.append('固定驗收集manifest不符')
        if exposure_policy=='REJECT' and manifest.get('evaluation_role','HOLDOUT')=='HOLDOUT' and self.store.get('HOLDOUT_EXPOSED',identity):errors.append('此holdout已揭露答案／角色洩漏；需真正獨立新來源，不可當全新驗收集')
        for entry in record['entries']:
            current=self.gold.validity(entry['gold_id'],verify_bytes)
            if not current['valid'] or digest(current['gold'])!=entry['gold_digest']:errors.append(entry['gold_id']+'gold／來源／用途許可已失效')
        try:
            from .coverage_batches import CoverageBatches
            current_scope=CoverageBatches(self.library).plan_source_files(manifest['declared_paths'],manifest['selected_source_ids'])
            if current_scope['scope_digest']!=manifest['declared_source_scope_digest']:errors.append('明列來源身分／登錄／作品版本或範圍已改變，不能沿用舊分母')
            projection=self.groups.projection(manifest['declared_content_hashes'])
            if manifest.get('group_projection_version')!=1 or projection['digest']!=manifest['group_edges_digest']:errors.append('此明列來源的客戶／家族相關群組版本已變更或舊快照缺少投影範圍，需核對後新版本')
            if manifest['declared_content_hashes']:errors += [r['reason'] for r in self.groups.role_conflicts([(sha,manifest.get('evaluation_role','HOLDOUT')) for sha in manifest['declared_content_hashes']])]
        except ValueError as error:errors.append(str(error))
        return dict(valid=not errors,errors=sorted(set(errors)),dataset=record)
