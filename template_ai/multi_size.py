"""同次輸入、多尺寸獨立計算與明確部分輸出；不保存案件或跨尺寸複製幾何。"""
from copy import deepcopy
import json
from pathlib import Path
import re

from .customers import digest
from .input_graph import InputGraph
from .layout import generate
from .logo_assets import errors
from .logo_store import LogoStore
from .render import export


def size_key(width,height):return json.dumps([float(width),float(height)],separators=(',',':'))


class MultiSizeWorkflow:
    def __init__(self,library,inputs,graph=None,generation=0):
        self.library=library;self.store=LogoStore(library)
        self.people,self.companies,self.original_logos=deepcopy(inputs)
        self.graph=InputGraph(graph) if graph is not None else InputGraph.from_legacy(*inputs)
        # The same graph supplies exact source identity in every physical size.
        # Original per-size Logo choices remain separately resolved below.
        self.people,self.companies,_=self.graph.compile()
        self.generation=generation;self.entries=[]

    def catalog_stamp(self,width,height):
        assets=[a for a in self.library.logos() if abs(a['width_mm']-width)<1e-5 and abs(a['height_mm']-height)<1e-5]
        bindings=[self.library.db.execute('SELECT company_id,confirmed_name FROM logo_entity_bindings WHERE entity_id=?',(c['id'],)).fetchone() for c in self.graph.data['companies']]
        return digest([assets,bindings])

    def calculate(self,sizes,selections=None,allowed_template_ids=None,cancel=None,progress=None):
        if not 1<=len(sizes)<=20:raise ValueError('本次需明確選擇1至20個實體尺寸，未截斷清單')
        if len({size_key(*size) for size in sizes})!=len(sizes):raise ValueError('輸出尺寸重複，請核對方向與毫米值')
        for size in sizes:self.store._size(*size)
        selections=selections or {};templates=self.library.templates(True);assets={a['id']:a for a in self.library.logos()}
        count=sum(1 for width,height in sizes for t in templates if abs(t.width_mm-width)<1e-5 and abs(t.height_mm-height)<1e-5 and t.capacity==len(self.people) and (allowed_template_ids is None or t.id in allowed_template_ids))
        if count>200:raise ValueError('超過當次200候選資源預算；請縮小尺寸／模板集合，未截斷或開始計算')
        self.entries=[]
        for index,(width,height) in enumerate(sizes):
            entry=dict(key=size_key(width,height),size_mm=[width,height],candidates=[],failures=[],
                state='NOT_CHECKED',selected=None,logo_states={},catalog_stamp=self.catalog_stamp(width,height))
            self.entries.append(entry)
            if cancel and cancel.is_set():entry['state']='CANCELLED';continue
            logos={}
            for i,company in enumerate(self.companies):
                port=f'c{i+1}';entity=self.graph.data['companies'][i]['id']
                pin=selections.get(entry['key'],{}).get(entity)
                old=self.original_logos.get(port)
                if not pin and old and abs(old['width_mm']-width)<1e-5 and abs(old['height_mm']-height)<1e-5:pin=old['id']
                if pin:
                    asset=assets.get(pin)
                    if asset and asset.get('approved') and asset['company']==company['name'] and abs(asset['width_mm']-width)<1e-5 and abs(asset['height_mm']-height)<1e-5 and not errors(asset):
                        logos[port]=deepcopy(asset);entry['logo_states'][port]='EXACT_VERSION_PENDING_OUTPUT'
                    else:entry['logo_states'][port]='SELECTION_INVALID_NO_REPLACEMENT'
                else:
                    found=self.store.match(entity,company['name'],width,height)
                    entry['logo_states'][port]=found['state']
                    if found['selected']:logos[port]=deepcopy(found['selected'])
            entry['resolved_logos']=deepcopy(logos)
            matching=[t for t in templates if abs(t.width_mm-width)<1e-5 and abs(t.height_mm-height)<1e-5 and t.capacity==len(self.people) and (allowed_template_ids is None or t.id in allowed_template_ids)]
            for template in matching:
                if cancel and cancel.is_set():break
                try:
                    self.library._template_provenance(template)
                    candidate=generate(deepcopy(template),self.people,self.companies,logos,self.generation)
                    from .candidate_risk import bind_source,verify_original_source
                    try:verify_original_source(candidate,self.library)
                    except (ValueError,OSError):pass
                    bind_source(candidate,self.library,require_registered=True);entry['candidates'].append(candidate)
                except (ValueError,OSError) as error:entry['failures'].append(dict(template_id=template.id,reason=str(error)))
            entry['candidates'].sort(key=lambda c:(not c.formal_eligible,-c.score,c.template.id))
            if entry['candidates']:
                entry['selected']=entry['candidates'][0].template.id
                entry['state']='VALID' if entry['candidates'][0].formal_eligible else 'BLOCKED'
            else:entry['state']='FAILED' if entry['failures'] else 'NO_TEMPLATE'
            if cancel and cancel.is_set():entry['state']='CANCELLED'
            if progress:progress(dict(processed_sizes=index+1,total_sizes=len(sizes),state=entry['state']))
        return self.entries

    def calculate_preserving(self,sizes,previous,selections=None,allowed_template_ids=None,cancel=None,progress=None):
        """Recompute shared source while retaining each explicitly manual instance."""
        from types import SimpleNamespace
        from .candidate_edit import plan_recheck,prepare_edit,calculate_edit
        from .candidate_sync import field_reference
        old_entries={entry['key']:deepcopy(entry) for entry in previous}
        self.calculate(sizes,selections,allowed_template_ids,cancel,progress)
        for entry in self.entries:
            old=old_entries.get(entry['key'])
            if old is None:continue
            for original in old['candidates']:
                if not original.risk_context.get('manual_edit_receipt'):continue
                index=next((i for i,c in enumerate(entry['candidates']) if c.template.id==original.template.id),None)
                try:
                    if cancel and cancel.is_set():raise ValueError('已取消，人工作品保留但未重驗')
                    if index is None:raise ValueError('來源版型／容量不再相容，保留人工作品供比較')
                    # Compare exact field/consumer identities before using new
                    # pN/cN positions; card reorder/deletion is never name-based.
                    current=entry['candidates'][index]
                    for slot in original.template.slots:
                        if field_reference(original,slot)!=field_reference(current,slot):raise ValueError('來源實體／欄位對應已改；人工位置保留待核對，不能按位置套給另一人物')
                    original.risk_context['conditions']=[row for row in original.risk_context.get('conditions',[]) if row['id']!='SHARED_SOURCE_SYNC_REQUIRED']
                    inputs=(self.people,self.companies,entry['resolved_logos']);adapter=SimpleNamespace(library=self.library,candidates=[original],generation=self.generation,input_data=lambda values=inputs:deepcopy(values))
                    preserved=calculate_edit(prepare_edit(adapter,plan_recheck(adapter,0)),self.library)
                except (ValueError,OSError,TypeError,KeyError) as error:
                    preserved=deepcopy(original);preserved.risk_context.setdefault('conditions',[]).append(dict(id='SHARED_SOURCE_SYNC_REQUIRED',status='UNKNOWN',reason=str(error)));preserved.risk_context['edit_state']='MANUAL_SOURCE_CONFLICT'
                if index is None:entry['candidates'].append(preserved)
                else:entry['candidates'][index]=preserved
            if any(c.template.id==old.get('selected') and c.risk_context.get('manual_edit_receipt') for c in entry['candidates']):entry['selected']=old['selected']
            selected=self.selected(entry)
            if selected is not None:entry['state']='VALID' if selected.formal_eligible else 'BLOCKED'
            if cancel and cancel.is_set():entry['state']='CANCELLED'
        return self.entries

    def selected(self,entry):
        return next((c for c in entry['candidates'] if c.template.id==entry['selected']),None)

    def select(self,key,template_id):
        entry=next(e for e in self.entries if e['key']==key)
        candidate=next((c for c in entry['candidates'] if c.template.id==template_id),None)
        if candidate is None:raise ValueError('候選不屬於此尺寸，不替換成其他版型')
        entry['selected']=template_id;entry['state']='VALID' if candidate.formal_eligible else 'BLOCKED'

    def revalidate(self,entry):
        candidate=self.selected(entry)
        if candidate is None or entry['state'] in ('NOT_CHECKED','CANCELLED'):raise ValueError('此尺寸尚未完成計算，不能輸出')
        if self.catalog_stamp(*entry['size_mm'])!=entry['catalog_stamp']:raise ValueError('此尺寸Logo版本／核准／身分已變更，先重新計算')
        template=next((t for t in self.library.templates(True) if t.id==candidate.template.id),None)
        from .training_store import digest as pin_digest
        if template is None or candidate.risk_context.get('source_template_pin')!=dict(id=template.id,version=template.version,digest=pin_digest(template.to_dict())):raise ValueError('確切模板版本已變更／失聯，需重驗')
        self.library._template_provenance(template)
        logos={item.slot.owner:deepcopy(item.logo) for item in candidate.items if item.logo}
        current={a['id']:a for a in self.library.logos()}
        for asset in logos.values():
            if asset['id'] not in current or digest(current[asset['id']])!=digest(asset) or errors(asset):raise ValueError('Logo來源／版本已變更，不輸出舊候選')
        from types import SimpleNamespace
        from .candidate_edit import plan_recheck,prepare_edit,calculate_edit
        adapter=SimpleNamespace(library=self.library,candidates=[candidate],generation=self.generation,input_data=lambda:deepcopy((self.people,self.companies,logos)))
        return calculate_edit(prepare_edit(adapter,plan_recheck(adapter,0)),self.library)

    def plan(self,directory,requests,prefix='layout'):
        directory=Path(directory).resolve()
        if not directory.is_dir():raise ValueError('先選存在的本機輸出資料夾')
        if not isinstance(prefix,str) or not prefix or len(prefix)>80 or re.search(r'[<>:"/\\|?*\x00-\x1f]',prefix) or prefix.endswith((' ','.')):raise ValueError('檔名前綴不符合Windows安全命名')
        if not requests or len({r['key'] for r in requests})!=len(requests):raise ValueError('明確選取不同尺寸的正式／預覽項目')
        entries={e['key']:e for e in self.entries};items=[]
        for request in requests:
            entry=entries.get(request['key']);mode=request.get('mode');formats=request.get('formats',[])
            if entry is None or mode not in ('FINAL','PREVIEW') or not formats or len(set(formats))!=len(formats) or any(f not in ('pdf','png','jpg') for f in formats):raise ValueError('尺寸、輸出類別或格式不合法')
            candidate=self.selected(entry)
            if candidate is None or entry['state'] in ('CANCELLED','NOT_CHECKED'):raise ValueError('此尺寸無已計算候選，不虛構預覽')
            if mode=='FINAL' and not candidate.formal_eligible:raise ValueError('不合格尺寸不能當正式成品，請另選PREVIEW')
            width,height=entry['size_mm']
            for suffix in formats:
                name=f'{prefix}_{width:.10g}x{height:.10g}mm_{mode}.{suffix}'
                items.append(dict(key=entry['key'],template_id=candidate.template.id,mode=mode,
                    path=str(directory/mode/name),issues=list(candidate.issues),status='PLANNED'))
        if len({i['path'] for i in items})!=len(items):raise ValueError('輸出名稱重複，請調整尺寸或前綴')
        omitted=[dict(size_mm=e['size_mm'],state=e['state'],issues=list(self.selected(e).issues) if self.selected(e) else e['failures']) for e in self.entries if e['key'] not in {r['key'] for r in requests}]
        return dict(directory=str(directory),generation=self.generation,items=items,omitted=omitted,
                    partial=bool(omitted) or any(e['state']!='VALID' for e in self.entries),
                    input_digest=digest([self.people,self.companies,self.original_logos,self.graph.data]))

    def execute(self,plan,approved=False,acknowledge_partial=False,current_check=None,dpi=150):
        if not approved or (plan['partial'] and not acknowledge_partial):raise ValueError('需明確確認正式／預覽清單及部分輸出，未寫檔')
        if plan['generation']!=self.generation or plan['input_digest']!=digest([self.people,self.companies,self.original_logos,self.graph.data]):raise ValueError('當次資料版本已變更')
        if current_check and not current_check():raise ValueError('輸入已變更；重新計算後才輸出')
        entries={e['key']:e for e in self.entries};root=Path(plan['directory']).resolve();results=[]
        for item in plan['items']:
            result=dict(item)
            try:
                if current_check and not current_check():raise ValueError('輸入在輸出期間變更，後續項目未輸出')
                entry=entries[item['key']]
                if entry['selected']!=item['template_id']:raise ValueError('候選選擇已改變，需重新確認清單')
                candidate=self.revalidate(entry)
                if item['mode']=='FINAL' and not candidate.formal_eligible:raise ValueError('重新驗證未通過，正式輸出已阻擋')
                target=Path(item['path'])
                if target.parent.parent.resolve()!=root or target.parent.name!=item['mode'] or target.parent.is_symlink():raise ValueError('輸出位置超出確認範圍')
                target.parent.mkdir(exist_ok=True)
                export(candidate,target,dpi=dpi,preview=item['mode']=='PREVIEW',expected_generation=self.generation)
                result.update(status='SUCCESS',issues=list(candidate.issues))
            except (ValueError,KeyError,OSError) as error:result.update(status='FAILED',reason=str(error))
            results.append(result)
        return results
