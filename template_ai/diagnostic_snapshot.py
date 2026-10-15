"""Adapters over existing validators; raw values and exact references remain local."""
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid
from PySide6.QtGui import QFontDatabase
from . import __version__
from .diagnostic_bundle import encoded, sha, validate, MAX_ISSUES, save_bundle
from .diagnostic_schema import issue, public_issue
from .model import KINDS

TTL_SECONDS = 7*24*60*60


def table_data(table):
    if table.rowCount()>200:raise ValueError('報告單次最多200列，請縮小範圍')
    rows=[[table.item(i,j).text() if table.item(i,j) else '' for j in range(table.columnCount())] for i in range(table.rowCount())]
    if sum(len(v) for r in rows for v in r)>200_000:raise ValueError('輸入超過報告預算，請縮小範圍')
    return rows


def file_stamp(path):
    try:
        s=Path(path).stat()
        return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
    except (OSError,ValueError,TypeError):return None


def selected_templates(window):
    rows=window.library.db.execute("SELECT payload FROM templates WHERE state='published' AND abs(json_extract(payload,'$.width_mm')-?)<0.00001 AND abs(json_extract(payload,'$.height_mm')-?)<0.00001 LIMIT 201",(window.out_w.value(),window.out_h.value())).fetchall()
    if len(rows)>200:raise ValueError('單次報告同尺寸模板超過200件，請縮小Library範圍')
    from .model import Template
    return [Template.from_dict(json.loads(row[0])) for row in rows]


def context(window,kind,work_id=None,session=None):
    """Local dependency digest, never written into the public report."""
    values={'kind':kind,'work':None,'templates':[]};paths=set()
    def paths_in(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if isinstance(v,str) and ('path' in k or k in ('svg','png','file')):paths.add(v)
                else:paths_in(v)
        elif isinstance(value,list):
            for v in value:paths_in(v)
    if kind=='evaluation':
        from .training_store import TrainingStore
        store=TrainingStore(window.library);record=store.get('EVALUATION',work_id)
        if not record:raise ValueError('先選取已保存的分類評估紀錄')
        values['evaluation']=record;values['dataset_validity']=store.dataset_validity(record['dataset_id'])
        for entry in values['dataset_validity'].get('dataset',{}).get('entries',[])[:200]:
            sample=store.get('SAMPLE',entry['sample_id'])
            if sample:paths_in(window.library.source(sample['pins']['source_id']))
    if work_id and kind!='evaluation':
        work=window.library.artwork(work_id);values['work']=work
        try:values['source']=window.library.source(work['source_id'])
        except (ValueError,KeyError):values['source']=None
        if values['source']:paths_in(values['source'])
        paths_in(work['payload'])
    if kind in ('input','candidate','session'):
        values['input_graph']=getattr(getattr(window,'active_input_graph',None),'data',None)
        values.update(generation=window.generation,people=table_data(window.people),companies=table_data(window.companies),size=[window.out_w.value(),window.out_h.value()],filter=getattr(window,'reorder_template_id',None))
        templates=selected_templates(window)
        eligible=[t for t in templates if (t.width_mm,t.height_mm)==tuple(values['size'])]
        if len(eligible)>200:raise ValueError('報告單次最多200模板，請縮小範圍')
        values['templates']=[t.to_dict() for t in eligible]
        selected=window.candidate_list.currentRow()
        candidates=window.candidates[selected:selected+1] if kind=='candidate' and selected>=0 else []
        values['selected_candidate']=selected if kind=='candidate' else None
        values['provenance']=[]
        for c in candidates:
            try:window.library._template_provenance(c.template);values['provenance'].append(True)
            except ValueError:values['provenance'].append(False)
        values['candidates']=[{'template':c.template.to_dict(),'generation':c.generation,'issues':c.issues,
                                'diagnostics':c.diagnostics,'measurements':c.measurements,
                                'items':[(p.slot.id,p.text,p.scale,p.logo) for p in c.items]} for c in candidates]
        paths_in(values['candidates']);paths_in(values['templates'])
    if kind=='template':
        t=window.template
        if not t:raise ValueError('先選取模板，未檢查其餘模板')
        values['template']=t.to_dict();paths_in(values['template'])
        try:values['stored_template']=window.library.object_snapshot('TEMPLATE',t.id)
        except ValueError:values['stored_template']=None
    if session is not None:
        values['session']={'running':session.running,'state':getattr(session,'report_state','NOT_CHECKED'),
                           'rows':[(r.get('template_id'),r['state'],r['candidate'].issues if r.get('candidate') else None) for r in session.rows],
                           'generation':getattr(session,'generation',None),'total':len(getattr(getattr(session,'worker',None),'templates',[]))}
    for template in values.get('templates',[])+([values['template']] if 'template' in values else []):
        if template.get('source_id'):
            try:paths_in(window.library.source(template['source_id']))
            except (ValueError,KeyError):pass
    if len(paths)>400:raise ValueError('依賴檔案超出單次報告預算，請縮小範圍')
    values['files']={p:file_stamp(p) for p in sorted(paths)}
    values['font_environment']=[(f,list(QFontDatabase.styles(f))) for f in sorted({s.get('font','') for t in values.get('templates',[])+[values.get('template',{})] for s in t.get('slots',[])})]
    return sha(json.dumps(values,ensure_ascii=False,sort_keys=True,default=str).encode())


@dataclass
class Snapshot:
    data: dict
    targets: list
    stamp: str
    kind: str
    work_id: str | None = None
    session: object = None

    def check(self,window):
        if context(window,self.kind,self.work_id,self.session)!=self.stamp:
            raise ValueError('資料／來源／字型／模板或背景結果已異動，請重新產生報告')


def make_snapshot(window,kind,work_id=None,session=None):
    if kind not in ('input','candidate','training','template','session','evaluation'):raise ValueError('不支援此報告範圍')
    if kind=='training' and not work_id:raise ValueError('先選取一個確切作品')
    before=context(window,kind,work_id,session)
    stage='DATA_PROCESSING' if kind in ('training','evaluation') else 'TEMPLATE_GENERATION' if kind=='template' else 'INPUT_OUTPUT'
    data={'schema_version':1,'report_id':uuid.uuid4().hex,
          'created_utc':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
          'app_version':__version__,'historical':True,'nonformal':True,'stage':stage,
          'stages':{k:'NOT_CHECKED' for k in ('DATA_PROCESSING','TEMPLATE_GENERATION','INPUT_OUTPUT')},
          'status':'LOCAL_SCOPE_CHECKED','source_health':'NOT_CHECKED','model_quality':'NOT_VERIFIED','physical_print':'NOT_VERIFIED',
          'scope':{'sources':0,'works':0,'candidates':0,'fields':0,'width_mm':None,'height_mm':None},
          'progress':{'state':'LOCAL_SCOPE_CHECKED','total':None,'checked':None,'calculated':None,'failed':None,'unstarted':None,'global_unsolvable':False},
          'issues':[],'measurements':[],'omitted_issues':0,'privacy':'SAFE_ALLOWLIST_NO_SOURCE_ATTACHMENTS','object_revision':None,'classification':None}
    targets=[];aliases={};field_aliases={}
    def add(row,target='範圍1',locator=None,measurement=False):
        ids=row.get('slot_ids',[])
        fields=[]
        for sid in ids[:200]:
            if sid not in field_aliases:field_aliases[sid]='欄位'+str(len(field_aliases)+1)
            fields.append(field_aliases[sid])
        public=public_issue(row,target,fields,stage)
        public['locatable']=bool(locator and row.get('locatable'))
        group='measurements' if measurement else 'issues'
        if len(data[group])>=MAX_ISSUES:
            data['omitted_issues']+=1;return
        data[group].append(public)
        if not measurement:targets.append(locator if public['locatable'] else None)
    def check_source(source_id):
        if not source_id:return
        from .source_links import source_status
        try:health=source_status(window.library.source(source_id))['status']
        except (KeyError,ValueError,OSError):health='UNREADABLE'
        data['source_health']=health;data['scope']['sources']=1
        add(issue('SOURCE_'+health,'INFO' if health=='OK' else 'REVIEW'),'來源1')
    if kind=='input':
        from .input_diagnostics import diagnose, KINDS as INPUT_KINDS
        data['scope'].update(width_mm=window.out_w.value(),height_mm=window.out_h.value())
        try:
            people,companies,_=window.input_data()
            if sum(len(p.get(k,[])) for p in people for k in INPUT_KINDS)>2000:raise RuntimeError('輸入欄位超出2000項報告預算，請縮小範圍，尚未檢查')
            result=diagnose(people,companies,selected_templates(window),window.out_w.value(),window.out_h.value())
            for row in result['issues']:
                row=dict(row);row.update(severity='REVIEW',kind=row.get('field_kind','company' if row['table']=='companies' else INPUT_KINDS[row['col']] if row['col']<7 else 'company'),locatable=True)
                add(row,('公司' if row['table']=='companies' else '人物')+str(row['row']+1),{'kind':'input','table':row['table'],'row':row['row'],'col':row['col']})
            data['scope']['fields']=len(window.active_input_graph.data['fields']) if getattr(window,'active_input_graph',None) is not None else sum(len(p.get(k,[])) for p in people for k in INPUT_KINDS)
            data['progress']['total']=result['templates_checked']
        except (ValueError,TypeError,KeyError):add(issue('INVALID_INPUT','REVIEW'))
        data['status']='PENDING_LAYOUT'
    elif kind=='candidate':
        index=window.candidate_list.currentRow()
        if not 0<=index<len(window.candidates):
            add(issue('NO_CANDIDATE','REVIEW'));data['status']='PENDING_LAYOUT'
            data['scope'].update(width_mm=window.out_w.value(),height_mm=window.out_h.value())
        else:
            c=window.candidates[index];check_source(c.template.source_id)
            data['scope'].update(candidates=1,fields=len(c.template.slots),width_mm=c.template.width_mm,height_mm=c.template.height_mm)
            data['object_revision']=c.template.version
            data['status']='STALE_RESULT' if c.generation!=window.generation or data['source_health'] not in ('NOT_CHECKED','OK') else 'DIGITAL_VALID' if c.valid else 'BLOCKED'
            from .layout import layout_dependency
            _,_,logos=window.input_data()
            dependency_changed=bool(c.dependency_stamp and c.dependency_stamp!=layout_dependency(c.template,logos))
            try:window.library._template_provenance(c.template)
            except ValueError:dependency_changed=True
            if dependency_changed:data['status']='STALE_RESULT'
            typed=list(c.diagnostics)
            typed.extend(issue('UNCLASSIFIED','REVIEW') for _ in range(max(0,len(c.issues)-len(typed))))
            if dependency_changed:typed.append(issue('DEPENDENCY_CHANGED','REVIEW'))
            for row in typed:
                locator={'kind':'candidate','index':index,'template_id':c.template.id,'slot_ids':row.get('slot_ids',[])} if data['status']!='STALE_RESULT' else None
                add(row,'候選1',locator)
            for row in c.measurements:add(row,'候選1',measurement=True)
            data['progress']=copy.deepcopy(getattr(window,'last_layout_summary',data['progress']))
    elif kind=='training':
        from .training_quality import analyse_work
        work=window.library.artwork(work_id)
        try:source=window.library.source(work['source_id'])
        except (ValueError,KeyError):source=None
        check_source(work['source_id'])
        p=work['payload'];data['scope'].update(works=1,fields=len(p.get('slots',[])),width_mm=p.get('work_width'),height_mm=p.get('work_height'))
        data['object_revision']=work['revision']
        for row in analyse_work(work,source):
            add(row,'作品1',{'kind':'training','work_id':work_id,'slot_ids':row['slot_ids']} if data['source_health']=='OK' else None)
        data['status']='BLOCKED' if any(i['severity']=='BLOCK' for i in data['issues']) else 'LOCAL_SCOPE_CHECKED'
    elif kind=='template':
        from .model import template_errors
        t=window.template;check_source(t.source_id)
        data['scope'].update(fields=len(t.slots),width_mm=t.width_mm,height_mm=t.height_mm)
        data['object_revision']=t.version
        for _ in template_errors(t):add(issue('TEMPLATE_CHECK'),'模板1')
        data['status']='BLOCKED' if data['issues'] and any(i['severity']=='BLOCK' for i in data['issues']) else 'LOCAL_SCOPE_CHECKED'
    elif kind=='evaluation':
        from .training_store import TrainingStore
        record=TrainingStore(window.library).get('EVALUATION',work_id)
        if not record:raise ValueError('找不到確切分類評估紀錄')
        c={k:copy.deepcopy(record[k]) for k in ('gold_count','predicted_count','critical_owner_errors','gate','prediction_origin','metrics')}
        c['versions']='USER_SUPPLIED_LABELS_NOT_VERIFIED_LOCAL_ONLY';data['classification']=c;data['object_revision']=record['revision']
        data['status']='BLOCKED' if c['gate']=='FAILED_CRITICAL' else 'LOCAL_SCOPE_CHECKED'
        add(issue('QUALITY_CRITICAL' if c['gate']=='FAILED_CRITICAL' else 'QUALITY_EVIDENCE_INSUFFICIENT','BLOCK' if c['gate']=='FAILED_CRITICAL' else 'REVIEW'))
    else:
        if session is None:raise ValueError('找不到當次背景工作')
        total=len(getattr(getattr(session,'worker',None),'templates',[]));checked=sum('template_id' in r for r in session.rows)
        failed=sum('template_id' in r and r.get('candidate') is None for r in session.rows)
        state=getattr(session,'report_state','NOT_CHECKED')
        if session.running:state='RUNNING'
        data['status']=state;data['scope']['candidates']=checked
        data['progress'].update(state=state,total=total,checked=checked,calculated=max(0,checked-failed),failed=failed,unstarted=max(0,total-checked))
        for i,r in enumerate(session.rows):
            if not r.get('candidate'):add(issue('WORKER_FAILED','REVIEW'),'候選'+str(i+1))
            else:
                for row in r['candidate'].diagnostics:add(row,'候選'+str(i+1))
        if getattr(session,'size',None):data['scope'].update(width_mm=session.size[0],height_mm=session.size[1])
    data['stages'][stage]=data['status']
    if data['omitted_issues']:data['progress']['state']='PARTIAL'
    import math
    for key in ('width_mm','height_mm'):
        value=data['scope'][key]
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:data['scope'][key]=None
    validate(data)
    snapshot=Snapshot(data,targets,before,kind,work_id,session)
    snapshot.check(window)
    return snapshot


class LocatorStore:
    """Only exact IDs/revisions and a dependency digest; never included in the shared ZIP."""
    def __init__(self,library):
        self.root=library.root/'diagnostic-locators'
        if self.root.is_symlink():raise ValueError('定位索引目錄不能是連結')
        self.root.mkdir(mode=0o700,exist_ok=True)
        self.cleanup()
    def cleanup(self,now=None):
        now=time.time() if now is None else now
        for p in self.root.glob('*.json'):
            try:
                if p.is_symlink() or p.stat().st_size>500_000 or json.loads(p.read_text())['expires']<=now:p.unlink()
            except (OSError,ValueError,KeyError,TypeError):p.unlink(missing_ok=True)
    def clear(self):
        for p in self.root.glob('*.json'):p.unlink(missing_ok=True)
    def remember(self,snapshot):
        data={'report_sha256':sha(encoded(snapshot.data)),'expires':time.time()+TTL_SECONDS,
              'stamp':snapshot.stamp,'kind':snapshot.kind,'work_id':snapshot.work_id,
              'targets':snapshot.targets,'session_only':snapshot.session is not None}
        # User-saved report files are never deleted by this index cleanup.
        save_private(self.root/(snapshot.data['report_id']+'.json'),encoded(data))
    def get(self,data):
        self.cleanup();p=self.root/(validate(data)['report_id']+'.json')
        if not p.is_file() or p.is_symlink():raise ValueError('無本機定位索引／已到期；仍可閱讀歷史報告')
        row=json.loads(p.read_text())
        if row['report_sha256']!=sha(encoded(data)):raise ValueError('報告內容不符合本機索引')
        if row['session_only']:raise ValueError('背景工作報告只能歷史閱讀；需在原當次工作核對')
        return row


def save_private(path,body):
    import tempfile
    fd,name=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)


def locate(window,data,index,snapshot=None):
    if snapshot is not None:
        snapshot.check(window);targets=snapshot.targets
    else:
        row=LocatorStore(window.library).get(data)
        if context(window,row['kind'],row['work_id'])!=row['stamp']:raise ValueError('版本已變／來源異動，不能定位歷史問題')
        targets=row['targets']
    if not 0<=index<len(targets) or not targets[index]:raise ValueError('此問題無可靠本機定位；請人工核對')
    target=targets[index]
    from .training_navigation import require_clean_navigation,locate_work
    require_clean_navigation(window)
    if target['kind']=='training':return locate_work(window,target['work_id'],target['slot_ids'])
    window.tabs.setCurrentIndex(2)
    if target['kind']=='input':
        if getattr(window,'active_input_graph',None) is not None:
            window.edit_input_graph();return
        table=getattr(window,target['table']);table.setCurrentCell(target['row'],target['col']);table.setFocus()
    else:
        i=target['index'];c=window.candidates[i]
        if c.template.id!=target['template_id']:raise ValueError('候選已變更')
        old=window.export_button.isEnabled();old_preview=window.preview_button.isEnabled()
        window.candidate_list.setCurrentRow(i);window.choose_candidate(i)
        window.export_button.setEnabled(old and window.export_button.isEnabled())
        window.preview_button.setEnabled(old_preview and window.preview_button.isEnabled())
        if target['slot_ids']:
            from PySide6.QtCore import QRectF,Qt
            ids=set(target['slot_ids']);slots=[s for s in c.template.slots if s.id in ids]
            if len(slots)!=len(ids):raise ValueError('欄位已變更')
            if slots:
                r=slots[0].rect;window.output_canvas.fitInView(QRectF(r.x,r.y,r.w,r.h),Qt.KeepAspectRatio)
        window.issues.setFocus()
    return target
