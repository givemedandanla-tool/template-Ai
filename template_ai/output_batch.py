"""Ephemeral per-file delivery with no-clobber publication and bounded safe retries.

Overwrite explicitly preserves the old file in a recovery directory, checks the
moved bytes again and publishes exclusively. It is not a transactional replace:
conflicts retain both versions and expose the recovery path. No customer history.
"""
from copy import deepcopy
from pathlib import Path
import os,re,shutil,tempfile,uuid
from .background import file_digest
from .customers import digest
from .render import export
from .safe_publish import publish_complete
from .source_links import hash_source

class OutputBlocked(ValueError):pass


def pin(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('不覆寫符號連結')
    proof=hash_source(path,byte_limit=50*1024*1024);st=path.stat()
    return dict(sha256=proof.hash,size=st.st_size,mtime_ns=st.st_mtime_ns,inode=st.st_ino,device=st.st_dev)


def safe_name(name,mode,suffix):
    if not isinstance(name,str) or not name or len(name)>180 or name in ('.','..') or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.endswith((' ','.')):raise ValueError('檔名不符合Windows安全命名或過長')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'{p}{i}' for p in ('COM','LPT') for i in range(1,10)]}:raise ValueError('Windows保留檔名不可使用')
    if Path(name).suffix.lower()!=suffix or mode not in Path(name).stem.upper():raise ValueError('檔名須保留已選格式及FINAL／PREVIEW用途標記')
    return name

class OutputBatch:
    def __init__(self,workflow,plan):
        self.workflow=workflow;self.plan=deepcopy(plan);self.id=uuid.uuid4().hex;self.items=[]
        for index,item in enumerate(plan['items']):self.items.append(dict(deepcopy(item),id=str(index),action='CREATE',attempts=0,reason='',retryable=False,stage_path=None,recovery_path=None))
        self.scope=None

    def configure(self,choices):
        if self.scope is not None:raise ValueError('已凍結輸出清單；更名／改目的地需建立新清單')
        if set(choices)!={row['id'] for row in self.items}:raise ValueError('請完整核對每筆檔案')
        used=set();configured=deepcopy(self.items)
        for row in configured:
            choice=choices[row['id']];action=choice.get('action','CREATE');original=Path(row['path']);name=safe_name(choice.get('name',original.name),row['mode'],original.suffix.lower())
            target=original.with_name(name)
            if action not in ('CREATE','SKIP','OVERWRITE'):raise ValueError('輸出動作不合法')
            key=str(target).casefold()
            if key in used:raise ValueError('同批Windows不分大小寫的檔名重複')
            used.add(key);row.update(path=str(target),action=action,expected_target=None,status='SKIPPED' if action=='SKIP' else 'PLANNED')
            if action=='OVERWRITE':
                if not target.is_file():raise ValueError('覆寫對象不存在；請選新增或更名')
                row['expected_target']=pin(target)
            elif action=='CREATE' and (target.exists() or target.is_symlink()):raise FileExistsError('目的檔已存在：請更名、略過或明確覆寫 '+str(target))
        self.items=configured;self.scope=digest(self.authorized());return self.items

    def authorized(self):return dict(plan=self.plan,items=[{k:row[k] for k in ('id','path','key','template_id','mode','action','expected_target')} for row in self.items])

    def _check(self,row,current_check,cancel):
        if cancel and cancel.is_set():raise OutputBlocked('使用者安全停止；尚未輸出的項目維持未完成')
        if current_check and not current_check():raise OutputBlocked('當次輸入已變更，先重新試排及確認清單')
        workflow=self.workflow
        if self.plan['generation']!=workflow.generation or self.plan['input_digest']!=digest([workflow.people,workflow.companies,workflow.original_logos,workflow.graph.data]):raise OutputBlocked('當次輸入／版本已變更')
        entry=next((e for e in workflow.entries if e['key']==row['key']),None)
        if not entry or entry['selected']!=row['template_id']:raise OutputBlocked('所選尺寸／候選版本已變更')
        try:candidate=workflow.revalidate(entry)
        except (ValueError,KeyError) as error:raise OutputBlocked(str(error)) from error
        if row['mode']=='FINAL' and not candidate.valid:raise OutputBlocked('正式印前未通過：'+'；'.join(candidate.issues))
        target=Path(row['path']);root=Path(self.plan['directory']).resolve()
        if target.parent.parent.resolve()!=root or target.parent.name!=row['mode'] or target.parent.is_symlink():raise OutputBlocked('目的地超出已確認範圍或目錄為符號連結')
        return candidate

    def execute(self,ids=None,approved=False,acknowledge_partial=False,current_check=None,cancel=None,progress=None,dpi=150,retry=False):
        if not approved or not self.scope or self.scope!=digest(self.authorized()) or (self.plan['partial'] and not acknowledge_partial):raise ValueError('需明確核對未變更的每筆清單與部分輸出範圍')
        selected=set(ids if ids is not None else [row['id'] for row in self.items if row['status']=='PLANNED'])
        if not selected and ids is None:return deepcopy(self.items)
        if not selected or not selected<={row['id'] for row in self.items}:raise ValueError('需明列確切待輸出／重試檔案')
        for row in self.items:
            if row['id'] not in selected:continue
            if retry and not (row['status']=='FAILED' and row['retryable'] and row['attempts']<3):raise ValueError('僅可重試確切可恢復失敗，最多3次；成功、略過、品質阻擋不重做')
            if not retry and row['status']!='PLANNED':raise ValueError('只執行尚未輸出的已確認項目')
        for row in self.items:
            if row['id'] not in selected:continue
            row.update(status='WRITING',retryable=False,reason='',attempts=row['attempts']+1)
            if progress:progress(deepcopy(row))
            stage=None;backup=None
            try:
                candidate=self._check(row,current_check,cancel);target=Path(row['path']);target.parent.mkdir(exist_ok=True)
                if row['action']=='OVERWRITE' and pin(target)!=row['expected_target']:raise OutputBlocked('既存檔案已變更，覆寫確認過期，請重建清單')
                if row['action']=='CREATE' and (target.exists() or target.is_symlink()):raise FileExistsError('目的檔案在確認後出現，未覆寫')
                # Conservative encoding workspace estimate, not a promised file size.
                estimate=max(1024*1024,int(candidate.template.width_mm*candidate.template.height_mm*(dpi/25.4)**2*8))
                if shutil.disk_usage(target.parent).free<estimate:raise OSError('可用空間不足以容納保守編碼工作預算；釋放空間後可重試')
                stage=target.with_name('.template-ai-STAGING_NOT_FINAL-'+uuid.uuid4().hex+'-'+row['mode']+target.suffix)
                export(candidate,stage,dpi=dpi,preview=row['mode']=='PREVIEW',expected_generation=self.workflow.generation)
                row.update(stage_path=str(stage),stage_pin=pin(stage))
                fresh=self._check(row,current_check,cancel)
                if fresh.dependency_stamp!=candidate.dependency_stamp:raise OutputBlocked('編碼期間字型／素材依賴變更，請重新試排')
                if row['action']=='OVERWRITE':
                    folder=Path(tempfile.mkdtemp(prefix='.template-ai-recovery-',dir=target.parent));backup=folder/target.name
                    os.rename(target,backup);row.update(recovery_path=str(backup),recovery_pin=pin(backup))
                    if row['recovery_pin']!=row['expected_target']:raise OutputBlocked('覆寫前的檔案版本已變更；已保留並嘗試恢復，請核對恢復路徑')
                publish_complete(stage,target,check=lambda:self._check(row,current_check,cancel));row.update(status='SUCCESS',sha256=file_digest(target),bytes=target.stat().st_size,issues=list(fresh.issues))
                try:stage.unlink();row['stage_path']=None
                except OSError:row['reason']='正式檔已完成；暫存清理未完成，可另行確認清理'
            except Exception as error:
                row.update(status='BLOCKED' if isinstance(error,OutputBlocked) else 'FAILED',reason=str(error),retryable=isinstance(error,OSError))
                if backup and backup.exists():
                    try:
                        os.link(backup,Path(row['path']));row['reason']+='；原檔已恢復（恢復副本保留）'
                    except OSError:row['reason']+='；恢復副本保留於 '+str(backup)+'，目的地有衝突，需核對'
                if stage and stage.exists():row.update(stage_path=str(stage),stage_pin=pin(stage))
            if progress:progress(deepcopy(row))
            if cancel and cancel.is_set():break
        return deepcopy(self.items)

    def cleanup_stage(self,identity,approved=False):
        row=next((r for r in self.items if r['id']==identity),None)
        if not approved or not row or not row.get('stage_path'):raise ValueError('需明確確認確切暫存檔清理；成功檔／恢復原檔不在範圍')
        path=Path(row['stage_path'])
        if '.template-ai-STAGING_NOT_FINAL-' not in path.name or path.parent!=Path(row['path']).parent or pin(path)!=row['stage_pin']:raise ValueError('暫存身分已變更，拒絕清理')
        path.unlink();row['stage_path']=None;return deepcopy(row)
