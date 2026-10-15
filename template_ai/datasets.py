"""Immutable role-pinned manifests, exact identity groups and explicit geometry-only learning."""
import copy
import json
import time
from .model import Slot,Rect,learn_from_labels,new_id
from .batch_import import healthy_source


def exact_label_signature(sample):
    from .training_store import digest
    slots=[{k:v for k,v in s.items() if k!='id'} for s in sample['label_slots']]
    slots.sort(key=lambda s:(s['owner'],s['kind'],s['index']))
    texts=sorted((p['owner'],p['kind'],p['index'],p['text']) for p in sample['positive_labels'])
    return digest({'source_hash':sample['pins']['source_hash'],'page':sample['pins']['page'],'crop':sample['crop'],'dimensions':[sample['width_mm'],sample['height_mm']],'bindings':sample['bindings'],'slots':slots,'positive_text':texts})


class DatasetMixin:
    def dataset_plan(self,name,assignments):
        from .training_store import text,digest
        text(name,'資料集名稱',120)
        if not isinstance(assignments,list) or not 1<=len(assignments)<=200 or any(not isinstance(a,dict) or set(a)!={'sample_id','role'} for a in assignments) or len({a['sample_id'] for a in assignments})!=len(assignments):raise ValueError('資料集需1～200個明列且不重複的sample／role')
        errors=[];entries=[];groups={};dedup={}
        for assignment in sorted(assignments,key=lambda a:a['sample_id']):
            sid=assignment['sample_id'];role=assignment['role'];sample=self.get('SAMPLE',sid)
            if role not in ('TRAIN','VALIDATION','HOLDOUT','UNASSIGNED') or not sample:raise ValueError('樣本或角色不合法')
            if self.sample_state(sid)!='APPROVED':errors.append(sid+'：樣本未准入或已過期／隔離／撤銷')
            group=sample['pins']['source_hash'];prior=self.get('GROUP_ROLE',group)
            if role!='UNASSIGNED':
                if prior and prior['role']!=role:errors.append('同內容／同源整檔group已有不同角色：'+group)
                groups.setdefault(group,set()).add(role)
            signature=exact_label_signature(sample);dedup.setdefault(signature,[]).append(sid)
            entries.append({'sample_id':sid,'sample_revision':sample['revision'],'scope_digest':sample['scope_digest'],'facts_revision':sample['facts_revision'],'source_id':sample['pins']['source_id'],'source_hash':group,'source_group':group,'page':sample['pins']['page'],'crop':sample['crop'],'width_mm':sample['width_mm'],'height_mm':sample['height_mm'],'role':role,'exact_label_signature':signature,'rule_dependencies':sample['rule_dependencies'],'noise_signature':sample['noise_signature'],'use':sample['rights']['use']})
        if any(len(roles)>1 for roles in groups.values()):errors.append('同源不同作品／同內容異名不能跨TRAIN/VALIDATION/HOLDOUT')
        from .quality_groups import QualityGroups
        try:
            errors += [row['reason'] for row in QualityGroups(self.library).role_conflicts([(entry['source_hash'],entry['role']) for entry in entries])]
        except ValueError as error:errors.append('群組獨立性尚未核實：'+str(error))
        manifest={'schema_version':1,'name':name,'entries':entries,'purpose':'GEOMETRY_TRAINING_LOCAL','whole_source_groups':sorted(groups),'exact_duplicates':{sig:ids for sig,ids in sorted(dedup.items()) if len(ids)>1},'near_similarity':'UNKNOWN','customer_identity':'UNKNOWN','source_identities_merged':False}
        plan={'epoch':self.epoch,'manifest':manifest,'manifest_digest':digest(manifest),'errors':sorted(set(errors))};plan['digest']=digest(plan);return plan

    def create_dataset(self,plan,actor,approved=False):
        from .training_store import text
        if approved is not True:raise ValueError('明確確認資料集用途、角色與source group')
        text(actor,'建立者',120)
        with self.transaction():
            current=self.dataset_plan(plan['manifest']['name'],[{'sample_id':e['sample_id'],'role':e['role']} for e in plan['manifest']['entries']])
            if current['digest']!=plan.get('digest') or current['errors']:raise ValueError('資料集範圍已變更或角色／樣本不合法：'+'；'.join(current['errors']))
            for entry in current['manifest']['entries']:
                if entry['role']=='UNASSIGNED':continue
                group=self.get('GROUP_ROLE',entry['source_group'])
                if not group:self._write('GROUP_ROLE',entry['source_group'],{'role':entry['role'],'source_hash':entry['source_group'],'basis':'WHOLE_SOURCE_EXACT_HASH','actor':actor},0,'dataset_group_role_assigned')
            return self._write('DATASET',new_id(),{'state':'FROZEN','manifest':current['manifest'],'entries':current['manifest']['entries'],'manifest_digest':current['manifest_digest'],'actor':actor,'created':time.time(),'training_started':False,'training_started_scope':'AT_MANIFEST_FREEZE; current exact uses in USE_LEDGER'},0,'dataset_frozen')

    def dataset_validity(self,dataset_id,selected_sample_ids=None):
        from .training_store import digest
        dataset=self.get('DATASET',dataset_id);errors=[]
        if not dataset:return {'valid':False,'errors':['資料集不存在']}
        from .quality_groups import QualityGroups
        try:
            errors += [row['reason'] for row in QualityGroups(self.library).role_conflicts([(entry['source_hash'],entry['role']) for entry in dataset.get('entries',[])])]
        except ValueError as error:errors.append('群組獨立性尚未核實：'+str(error))
        if digest(dataset.get('manifest'))!=dataset.get('manifest_digest') or dataset.get('entries')!=dataset.get('manifest',{}).get('entries'):errors.append('資料集不可變manifest不符')
        for entry in dataset.get('entries',[]):
            sample=self.get('SAMPLE',entry['sample_id'])
            if (selected_sample_ids is None or entry['sample_id'] in selected_sample_ids) and (not sample or self.sample_state(entry['sample_id'])!='APPROVED' or sample['revision']!=entry['sample_revision'] or sample.get('scope_digest')!=entry['scope_digest']):errors.append(entry['sample_id']+'樣本已過期／撤銷／版次變更')
            role=self.get('GROUP_ROLE',entry['source_group'])
            if entry['role']!='UNASSIGNED' and (not role or role['role']!=entry['role']):errors.append('來源group角色不符')
        return {'valid':not errors,'errors':sorted(set(errors)),'dataset':dataset}

    def geometry_learning_plan(self,dataset_id,sample_id,name):
        from .training_store import text,digest
        text(name,'模板草稿名稱',120);validity=self.dataset_validity(dataset_id,[sample_id])
        if not validity['valid']:raise ValueError('資料集目前不可用：'+'；'.join(validity['errors']))
        dataset=validity['dataset'];entry=next((e for e in dataset['entries'] if e['sample_id']==sample_id),None)
        if not entry or entry['role']!='TRAIN':raise ValueError('只有本資料集的有效TRAIN樣本可明確啟動幾何學習')
        existing=self.existing_geometry_result(dataset_id,sample_id)
        if existing:raise ValueError('此資料集／樣本版已有幾何成果，復用或編輯既有版本：'+existing)
        duplicates=dataset['manifest']['exact_duplicates'].get(entry['exact_label_signature'],[])
        if duplicates and sample_id!=min(duplicates):raise ValueError('同資料集exact duplicate只學代表項；所有來源身份仍保留')
        sample=self.get('SAMPLE',sample_id);plan={'epoch':self.epoch,'dataset_id':dataset_id,'dataset_revision':dataset['revision'],'manifest_digest':dataset['manifest_digest'],'entry':entry,'name':name,'source_pins':sample['pins'],'sample_revision':sample['revision'],'purpose':'GEOMETRY_DRAFT_ONLY'};plan['digest']=digest(plan);return plan

    def existing_geometry_result(self,dataset_id,sample_id):
        sample=self.get('SAMPLE',sample_id)
        if not sample:return None
        row=self.db.execute("SELECT json_extract(payload,'$.template_id') FROM training_records WHERE kind='USE' AND json_extract(payload,'$.dataset_id')=? AND json_extract(payload,'$.sample_id')=? AND json_extract(payload,'$.sample_revision')=? ORDER BY id LIMIT 1",(dataset_id,sample_id,sample['revision'])).fetchone()
        return row[0] if row else None

    def validate_training_reference(self,template):
        ref=template.training_reference
        if not isinstance(ref,dict) or set(ref)!= {'dataset_id','manifest_digest','sample_id','sample_revision','purpose'} or ref['purpose']!='GEOMETRY_DRAFT_ONLY':raise ValueError('模板訓練來源不完整')
        validity=self.dataset_validity(ref['dataset_id'],[ref['sample_id']])
        if not validity['valid'] or validity['dataset']['manifest_digest']!=ref['manifest_digest']:raise ValueError('模板訓練資料集／样本已不可用')
        entry=next((e for e in validity['dataset']['entries'] if e['sample_id']==ref['sample_id'] and e['role']=='TRAIN'),None);sample=self.get('SAMPLE',ref['sample_id'])
        if not entry or not sample or entry['sample_revision']!=ref['sample_revision'] or sample['revision']!=ref['sample_revision'] or template.source_work_id!=sample['work_id'] or template.source_work_revision!=sample['pins']['work_revision'] or template.source_id!=sample['pins']['source_id'] or (template.width_mm,template.height_mm)!=(sample['width_mm'],sample['height_mm']) or template.artwork!=Rect(**sample['crop']):raise ValueError('模板來源／尺寸／TRAIN版次不符')

    def _write_geometry_draft(self,plan,proof,job_id=None,actor=''):
        # Caller owns BEGIN IMMEDIATE. Never call Library.save_template's nested commit here.
        current=self.geometry_learning_plan(plan['dataset_id'],plan['entry']['sample_id'],plan['name'])
        if current['digest']!=plan.get('digest'):raise ValueError('學習範圍已變更')
        sample=self.get('SAMPLE',plan['entry']['sample_id']);self.checked(sample['work_id'],proof)
        if not healthy_source(self.library.source(sample['pins']['source_id'])):raise ValueError('來源／分析快取不健康')
        slots=[Slot(**{**s,'rect':Rect(**s['rect'])}) for s in sample['label_slots']]
        template=learn_from_labels(plan['name'],sample['width_mm'],sample['height_mm'],slots,sample['pins']['source_id'],Rect(**sample['crop']),sample['bindings'],sample['work_id'],sample['pins']['work_revision'])
        template.training_reference={'dataset_id':plan['dataset_id'],'manifest_digest':plan['manifest_digest'],'sample_id':sample['id'],'sample_revision':sample['revision'],'purpose':'GEOMETRY_DRAFT_ONLY'}
        self.library._template_provenance(template);self.db.execute('INSERT INTO templates VALUES(?,?,?,?,?)',(template.id,template.family_id,template.version,template.state,json.dumps(template.to_dict(),ensure_ascii=False)));self.library._bump_template_clock(template.id);self.library.event(template.id,'trusted_sample_geometry_draft_created')
        self._write('USE',new_id(),{'dataset_id':plan['dataset_id'],'manifest_digest':plan['manifest_digest'],'sample_id':sample['id'],'sample_revision':sample['revision'],'template_id':template.id,'job_id':job_id,'actor':actor,'purpose':'GEOMETRY_DRAFT_ONLY','created':time.time()},0,'sample_geometry_use_recorded');return template

    def learn_dataset_sample(self,plan,proof,actor,approved=False):
        from .training_store import text
        if approved is not True:raise ValueError('明確啟動單一TRAIN樣本的幾何草稿學習')
        text(actor,'啟動者',120)
        with self.transaction():return self._write_geometry_draft(plan,proof,actor=actor)
