"""Versioned source-marking drafts and transactional work segmentation.

These operations edit learning metadata, never source pixels or published
templates. Split/merge retains original work revisions and requires unambiguous
assignment of every existing field; no silent person/company deduplication.
"""
from copy import deepcopy
from dataclasses import asdict
import json
import time
from .model import Rect,Slot,new_id,company_ports
from .object_tools import propose,protect_locked
from .training_store import TrainingStore,digest,text


class AnnotationSession:
    def __init__(self,library,work_id):
        self.library=library;self.store=TrainingStore(library);self.base=library.artwork(work_id)
        if self.base['payload'].get('segmentation_state')=='SUPERSEDED':raise ValueError('此作品切分已被新版本取代；保留歷史，不當現行可學習作品')
        self.payload=deepcopy(self.base['payload']);self.facts=self.store.facts(work_id);self.observations=deepcopy(self.facts['observations'])
        self.undo_stack=[];self.redo_stack=[]

    def checkpoint(self):self.undo_stack.append(deepcopy([self.payload,self.observations]));self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:self.redo_stack.append(deepcopy([self.payload,self.observations]));self.payload,self.observations=self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:self.undo_stack.append(deepcopy([self.payload,self.observations]));self.payload,self.observations=self.redo_stack.pop()

    def change(self,request):
        if request.get('operation')=='LOCK':raise ValueError('鎖定／解鎖請使用既有安全物件工具，重新載入後再校正')
        plan=propose(self.payload,'ARTWORK',request);self.checkpoint();self.payload=plan['after'];self.sync_observations();return plan

    def add(self,rect,kind='name',owner='p1',value='待來源核對'):
        from .model import KINDS
        import re
        if kind not in KINDS or not isinstance(owner,str) or not re.fullmatch(r'[pc][1-9]\d*',owner):raise ValueError('先指定有效欄位類型與人物／公司歸屬')
        if len(self.payload['slots'])>=200 or not rect.inside(self.payload['work_width'],self.payload['work_height']):raise ValueError('新框需位於作品範圍且不超過200框')
        text(value,'候選來源內容',512);self.checkpoint()
        index=sum(s['kind']==kind and s['owner']==owner for s in self.payload['slots'])
        slot=Slot(kind,owner,rect,index=index);self.payload['slots'].append(asdict(slot));self.payload['visual_confirmed']=False
        self.observations.append(dict(id=new_id(),slot_id=slot.id,text=value,object_type='LOGO_PART' if kind=='logo' else 'TEXT',classification='LOGO' if kind=='logo' else 'FIELD',region=self.source_rect(rect)))
        return slot.id

    def bind_observation(self,observation_id,kind,owner):
        observation=next((o for o in self.observations if o['id']==observation_id and o.get('slot_id') is None),None)
        if observation is None:raise ValueError('待審來源觀察已更新，請重新核對')
        crop=self.payload['crop'];region=observation['region'];sx=self.payload['work_width']/crop['w'];sy=self.payload['work_height']/crop['h']
        rect=Rect((region['x']-crop['x'])*sx,(region['y']-crop['y'])*sy,region['w']*sx,region['h']*sy)
        identity=self.add(rect,kind,owner,observation['text'])
        # Keep the source observation's stable identity and original prediction.
        self.observations.pop();observation['slot_id']=identity;observation['classification']='LOGO' if kind=='logo' else 'FIELD'
        return identity

    def source_rect(self,rect):
        crop=self.payload['crop'];sx=crop['w']/self.payload['work_width'];sy=crop['h']/self.payload['work_height']
        return dict(x=crop['x']+rect.x*sx,y=crop['y']+rect.y*sy,w=rect.w*sx,h=rect.h*sy)

    def sync_observations(self):
        slots={s['id']:s for s in self.payload['slots']};self.observations=[o for o in self.observations if o.get('slot_id') is None or o['slot_id'] in slots]
        for observation in self.observations:
            slot=slots.get(observation.get('slot_id'))
            if slot:
                observation['region']=self.source_rect(Rect(**slot['rect']))
                observation['classification']='LOGO' if slot['kind']=='logo' else 'FIELD'
                observation['object_type']='LOGO_PART' if slot['kind']=='logo' else 'TEXT'
            original=next((o for o in self.facts['observations'] if o['id']==observation['id']),None)
            if original is None or any(observation.get(k)!=original.get(k) for k in ('slot_id','text','region','classification')):
                observation['evidence']='USER_OBSERVATION_DRAFT'

    def save(self):
        self.sync_observations();identity=self.base['id']
        with self.store.transaction():
            current=self.library.artwork(identity)
            if digest(current)!=digest(self.base) or self.store.facts(identity)['revision']!=self.facts['revision']:raise ValueError('作品／事實已更新，保留本次草稿，不覆寫')
            protect_locked(self.base['payload'],self.payload)
            encoded=self.library._artwork_payload(current['source_id'],self.payload);changed=digest(self.base['payload'])!=digest(self.payload)
            revision=current['revision']+int(changed)
            if changed:
                self.library.db.execute('UPDATE artworks SET revision=?,payload=? WHERE id=? AND revision=?',(revision,encoded,identity,current['revision']))
                self.library.db.execute('INSERT INTO artwork_revisions VALUES(?,?,?,?)',(identity,revision,encoded,time.time()));self.library.event(identity,'annotation_draft_saved_source_unchanged')
            if changed or digest(self.observations)!=digest(self.facts['observations']):
                checked=self.store.validate_observations(identity,self.observations) if self.observations else []
                self.store._write('FACTS',identity,dict(observations=checked,confirmation=None,state='PENDING',pins=self.store.pins(identity)),self.facts['revision'],'annotation_facts_pending')
                self.store._refresh_noise(identity)
        self.base=self.library.artwork(identity);self.facts=self.store.facts(identity);self.observations=deepcopy(self.facts['observations']);return self.base


def resegment(library,snapshots,regions,actor,reason,approved=False):
    from .source_analysis import contains
    if approved is not True or not snapshots or not 1<=len(regions)<=20 or len({w['id'] for w in snapshots})!=len(snapshots):raise ValueError('需明確確認作品範圍與1～20個新區域')
    text(actor,'操作者',120);text(reason,'切分／合併理由')
    if len({w['source_id'] for w in snapshots})!=1:raise ValueError('不能把不同來源／頁次作品合併')
    store=TrainingStore(library);source=library.source(snapshots[0]['source_id']);proof=store.source_proof(snapshots[0]['id'])
    for region in regions:
        if not region.inside(source['width_mm'],source['height_mm']):raise ValueError('新區域超出原來源')
    placements=[];people={};companies={};bindings={};seen=set()
    for work in snapshots:
        crop=work['payload']['crop'];sx=crop['w']/work['payload']['work_width'];sy=crop['h']/work['payload']['work_height']
        for raw in work['payload']['slots']:
            if raw['id'] in seen:raise ValueError('來源框stable ID重複，需逐筆核對，不自動合併')
            seen.add(raw['id']);slot=deepcopy(raw);r=slot['rect'];global_rect=Rect(crop['x']+r['x']*sx,crop['y']+r['y']*sy,r['w']*sx,r['h']*sy)
            destination=[i for i,region in enumerate(regions) if contains(region,global_rect,1e-5)]
            if len(destination)!=1:raise ValueError('既有欄位會遺失或跨多作品，先調整邊界；不得靜默捨棄')
            prefix='p' if slot['owner'].startswith('p') else 'c';mapping=people if prefix=='p' else companies
            mapping.setdefault((work['id'],slot['owner']),prefix+str(len(mapping)+1))
            slot['owner']=mapping[(work['id'],slot['owner'])];region=regions[destination[0]]
            slot['rect']=dict(x=global_rect.x-region.x,y=global_rect.y-region.y,w=global_rect.w,h=global_rect.h)
            placements.append((destination[0],slot))
        for person,ports in work['payload'].get('company_bindings',{}).items():
            pk=(work['id'],person)
            if pk in people:bindings[people[pk]]=[companies[(work['id'],c)] for c in company_ports(ports) if (work['id'],c) in companies]
    with store.transaction():
        for snapshot in snapshots:
            if digest(library.artwork(snapshot['id']))!=digest(snapshot):raise ValueError('作品在確認期間變更，整組不套用')
            store.checked(snapshot['id'],proof)
        result=[]
        for i,region in enumerate(regions):
            slots=[slot for index,slot in placements if index==i];owners={s['owner'] for s in slots}
            payload=dict(crop=asdict(region),work_width=region.w,work_height=region.h,slots=slots,visual_confirmed=False,
                company_bindings={p:[c for c in cs if c in owners] for p,cs in bindings.items() if p in owners},
                segmentation_origin=[dict(work_id=w['id'],revision=w['revision']) for w in snapshots],segmentation_actor=actor,segmentation_reason=reason)
            identity=new_id();encoded=library._artwork_payload(source['id'],payload)
            library.db.execute('INSERT INTO artworks VALUES(?,?,?,1,?)',(identity,source['id'],'人工校正作品 '+str(i+1),encoded))
            library.db.execute('INSERT INTO artwork_revisions VALUES(?,1,?,?)',(identity,encoded,time.time()));library.event(identity,'work_segmentation_candidate_created')
            slot_ids={s['id'] for s in slots};observations=[]
            for old in snapshots:
                for observation in store.facts(old['id'])['observations']:
                    if observation.get('slot_id') in slot_ids or observation.get('slot_id') is None and contains(region,Rect(**observation['region']),1e-5):
                        o=deepcopy(observation);o['prior_prediction']='RESEGMENTED_REQUIRES_CONFIRMATION';observations.append(o)
            if observations:
                checked=store.validate_observations(identity,observations)
                store._write('FACTS',identity,dict(observations=checked,confirmation=None,state='PENDING',pins=store.pins(identity)),0,'segmented_observations_preserved_pending')
                store._refresh_noise(identity)
            result.append(library.artwork(identity))
        for old in snapshots:
            payload=deepcopy(old['payload']);payload.update(segmentation_state='SUPERSEDED',superseded_by=[w['id'] for w in result]);encoded=library._artwork_payload(source['id'],payload)
            library.db.execute('UPDATE artworks SET revision=revision+1,payload=? WHERE id=?',(encoded,old['id']))
            library.db.execute('INSERT INTO artwork_revisions VALUES(?,?,?,?)',(old['id'],old['revision']+1,encoded,time.time()));library.event(old['id'],'old_work_segmentation_retained_as_history')
        return result
