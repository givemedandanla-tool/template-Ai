"""Cassowary repair in explicitly bounded geometry; drafts require manual publication.

Fixed font sizes and ownership are constants. Existing non-overlap topology is
preserved. This searches an approved bounded problem, not all possible designs.
"""
from copy import deepcopy
from dataclasses import asdict
import math
import kiwisolver as kiwi
from .layout import generate,text_geometry
from .model import Template,Rect,template_errors
from .text_policy import tracking_geometry
from .training_store import TrainingStore,digest,text
from .template_versions import TemplateVersions,differences

VERSION='cassowary-bounded-geometry-1'

class CustomLayout:
    def __init__(self,library):self.library=library;self.versions=TemplateVersions(library)
    def plan(self,template_id,people,companies,logos,policy,generation=0):
        if not isinstance(policy,dict) or set(policy)!={'move_mm','expand_mm','gap_mm'}:raise ValueError('須明定本次位移／擴框／間距範圍')
        for key,maximum in [('move_mm',50),('expand_mm',50),('gap_mm',5)]:
            if type(policy[key]) not in (int,float) or not math.isfinite(policy[key]) or not 0<=policy[key]<=maximum:raise ValueError('特製範圍不合法')
        base_plan=self.versions.plan(template_id);base=Template.from_dict(base_plan['source']['payload'])
        if base.state!='published' or len(base.slots)>64:raise ValueError('基準須為已核准模板且最多64物件；不靜默截斷')
        self.library._template_provenance(base)
        eligible=[t for t in self.library.templates(True) if (t.width_mm,t.height_mm,t.capacity)==(base.width_mm,base.height_mm,len(people))]
        for template in eligible:
            try:self.library._template_provenance(template)
            except ValueError:continue
            if generate(template,people,companies,logos,generation).valid:raise ValueError('已有同尺寸／容量合格現成模板，先使用既有合格候選')
        if len(people)!=base.capacity:raise ValueError('人物容量不同；不改歸屬或虛構人物框位')
        candidate=generate(base,people,companies,logos,generation);draft=deepcopy(base);draft.state='draft';bounds=policy;solver=kiwi.Solver();variables={};measurements=[]
        result=dict(version=VERSION,solver='kiwisolver '+kiwi.__version__,base_plan=base_plan,policy=deepcopy(policy),generation=generation,input_digest=digest([people,companies,logos]),status='UNVERIFIED',issues=[],measurements=measurements,changes=[],scope='CURRENT_INPUT_BOUNDED_GEOMETRY_DRAFT; NO_FONT_OR_OWNER_CHANGE; NOT_PUBLISHED')
        by_slot={item.slot.id:item for item in candidate.items}
        try:
            for slot in sorted(draft.slots,key=lambda s:s.id):
                variables[slot.id]=tuple(kiwi.Variable(slot.id+'-'+axis) for axis in ('x','y','w','h'));x,y,w,h=variables[slot.id];r=slot.rect;m=draft.safe_margin_mm
                for constraint in [x>=m,y>=m,w>=.01,h>=.01,x+w<=draft.width_mm-m,y+h<=draft.height_mm-m]:solver.addConstraint(constraint)
                if slot.locked:
                    for var,value in zip((x,y,w,h),(r.x,r.y,r.w,r.h)):solver.addConstraint(var==value)
                else:
                    for var,value in zip((x,y),(r.x,r.y)):
                        solver.addConstraint(var>=value-bounds['move_mm']);solver.addConstraint(var<=value+bounds['move_mm'])
                    for var,value in zip((w,h),(r.w,r.h)):
                        solver.addConstraint(var>=value);solver.addConstraint(var<=value+(0 if slot.kind=='logo' else bounds['expand_mm']))
                for var,value in zip((x,y,w,h),(r.x,r.y,r.w,r.h)):solver.addConstraint((var==value)|kiwi.strength.weak)
                item=by_slot.get(slot.id)
                if item and item.text and slot.kind!='logo':
                    minimum=deepcopy(slot);minimum.tracking_mm=minimum.tracking_min_mm;minimum.tracking_max_mm=minimum.tracking_min_mm
                    tw,th,errors,tracking,strategy=tracking_geometry(minimum,item.text,text_geometry)
                    if errors:result['issues']+=errors;return self._finish(result,draft,candidate)
                    solver.addConstraint(w>=tw*slot.min_scale);solver.addConstraint(h>=th)
                    measurements.append(dict(slot_id=slot.id,size_pt=slot.size_pt,text_width_mm=tw,min_scale=slot.min_scale,min_width_mm=tw*slot.min_scale,text_height_mm=th,tracking_min_mm=tracking))
            slots=sorted(draft.slots,key=lambda s:s.id)
            for i,a in enumerate(slots):
                for b in slots[i+1:]:
                    ar,br=a.rect,b.rect;choices=[]
                    if ar.x+ar.w<=br.x+1e-8:choices.append((br.x-ar.x-ar.w,variables[a.id][0]+variables[a.id][2]+bounds['gap_mm']<=variables[b.id][0]))
                    if br.x+br.w<=ar.x+1e-8:choices.append((ar.x-br.x-br.w,variables[b.id][0]+variables[b.id][2]+bounds['gap_mm']<=variables[a.id][0]))
                    if ar.y+ar.h<=br.y+1e-8:choices.append((br.y-ar.y-ar.h,variables[a.id][1]+variables[a.id][3]+bounds['gap_mm']<=variables[b.id][1]))
                    if br.y+br.h<=ar.y+1e-8:choices.append((ar.y-br.y-br.h,variables[b.id][1]+variables[b.id][3]+bounds['gap_mm']<=variables[a.id][1]))
                    if not choices:raise ValueError('基準拓撲有重疊；不推測可移除的物件')
                    solver.addConstraint(max(choices,key=lambda pair:pair[0])[1])
            solver.updateVariables()
            for slot in draft.slots:
                values=[var.value() for var in variables[slot.id]];slot.rect=Rect(*(round(v,8) for v in values))
            repaired=generate(draft,people,companies,logos,generation)
            remaining=[d for d in repaired.diagnostics if d.get('code')!='UNPUBLISHED'];errors=template_errors(draft)
            if remaining or errors:result.update(status='BLOCKED_INPUT_OR_QUALITY',issues=errors+[str(d) for d in remaining])
            else:result.update(status='FEASIBLE_DRAFT',issues=['特製草稿已通過目前輸入的幾何／語意／字型檢查；仍未發布，不能正式輸出'])
            return self._finish(result,draft,repaired)
        except kiwi.UnsatisfiableConstraint:
            result.update(status='NO_SOLUTION_WITHIN_BOUNDS',issues=['在本次明定的位移／擴框／安全區／固定字級及原拓撲條件下無解；不是所有設計均無解'])
            return self._finish(result,draft,candidate)
        except ValueError as error:
            result.update(issues=[str(error)]);return self._finish(result,draft,candidate)
    def _finish(self,result,draft,candidate):
        result['draft']=draft.to_dict();result['changes']=differences(result['base_plan']['source']['payload'],result['draft']);result['digest']=digest(result);result['preview_candidate']=candidate;return result
    def create_draft(self,plan,people,companies,logos,actor,reason,approved=False):
        if digest({k:v for k,v in plan.items() if k not in ('digest','preview_candidate')})!=plan.get('digest'):raise ValueError('特製計畫內容已變更，請重新預覽')
        if approved is not True or plan['status']!='FEASIBLE_DRAFT':raise ValueError('須核對可行候選、變動清單，明確建立草稿；未發布')
        text(actor,'特製核准者',120);text(reason,'特製核准理由')
        fresh=self.plan(plan['base_plan']['source']['id'],people,companies,logos,plan['policy'],plan['generation'])
        if fresh['status']!='FEASIBLE_DRAFT' or fresh['digest']!=plan.get('digest'):raise ValueError('模板／輸入／規則依賴已變更，請重新預覽特製範圍')
        before={s['id']:s for s in fresh['base_plan']['source']['payload']['slots']}
        geometry={s['id']:s['rect'] for s in fresh['draft']['slots'] if s['rect']!=before[s['id']]['rect']}
        return self.versions.clone(fresh['base_plan'],actor,reason,True,geometry=geometry,custom_evidence=dict(algorithm=VERSION,solver=fresh['solver'],policy=fresh['policy'],input_digest=fresh['input_digest'],measurements=fresh['measurements']))
