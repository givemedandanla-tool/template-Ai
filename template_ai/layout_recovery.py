"""Opt-in encrypted short-lived local layout recovery; no customer/history database."""
import copy,json,os,tempfile,time
from pathlib import Path
from dataclasses import asdict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .secure_backup import key
from .safe_publish import publish_complete
from .training_store import digest
from .background import file_digest
from .model import Template
from .layout import Candidate,Placed
from .candidate_risk import bind_source,placement_digest

MAGIC=b'TALR1';LIMIT=4*1024*1024;TTL_SECONDS=24*3600


def engine_pins():
    from PySide6.QtCore import qVersion
    root=Path(__file__).parent
    names=('layout.py','render.py','model.py','candidate_risk.py','layout_recovery.py','text_policy.py','text_metrics.py','font_catalog.py','font_evidence.py','logo_assets.py','background.py')
    return dict(qt=qVersion(),files={name:file_digest(root/name) for name in names})


def encode_candidate(candidate):
    return dict(template=candidate.template.to_dict(),items=[asdict(i) for i in candidate.items],issues=copy.deepcopy(candidate.issues),score=candidate.score,generation=candidate.generation,reasons=copy.deepcopy(candidate.reasons),diagnostics=copy.deepcopy(candidate.diagnostics),measurements=copy.deepcopy(candidate.measurements),dependency_stamp=candidate.dependency_stamp,risk_context=copy.deepcopy(candidate.risk_context))


def decode_candidate(value):
    value=copy.deepcopy(value);template=Template.from_dict(value.pop('template'));slots={s.id:s for s in template.slots};items=[]
    for row in value.pop('items'):
        slot=row.pop('slot')
        if slot['id'] not in slots or asdict(slots[slot['id']])!=slot:raise ValueError('恢復框位與模板不符')
        items.append(Placed(slots[slot['id']],**row))
    return Candidate(template,items,**value)


class LayoutRecovery:
    def __init__(self,root,clock=time.time):
        self.root=Path(root)/'private-layout-recovery';self.path=self.root/'session.talr';self.clock=clock
    def pending(self):
        if not self.path.exists():return False
        if self.path.is_symlink() or self.path.stat().st_size>LIMIT+128:raise ValueError('恢復暫存格式／大小不安全，請清除')
        if self.clock()-self.path.stat().st_mtime>TTL_SECONDS:self.clear();return False
        return True
    def clear(self):
        self.path.unlink(missing_ok=True)
        return dict(cleared=True,scope='LOCAL_RECOVERY_ONLY',secure_erase=False)
    def save(self,payload,password):
        if self.path.exists():raise FileExistsError('已有加密暫存；先明確放棄並清除，不覆寫')
        if payload.get('state') not in ('CANCELLED','PAUSED_SAFE'):raise ValueError('僅可保存安全停止的當次階段；正常完成不保留私人暫存')
        now=self.clock();record=dict(schema=1,created=now,expires=now+TTL_SECONDS,root_digest=digest(str(self.root.parent.resolve())),engine=engine_pins(),payload=copy.deepcopy(payload))
        plain=json.dumps(record,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
        if len(plain)>LIMIT:raise ValueError('恢復資訊超過4MiB預算；未保存，原稿與圖片不放入恢復暫存')
        salt=os.urandom(16);nonce=os.urandom(12);cipher=AESGCM(key(password,salt));blob=MAGIC+salt+nonce+cipher.encrypt(nonce,plain,MAGIC)
        if cipher.decrypt(nonce,blob[33:],MAGIC)!=plain:raise ValueError('加密自我核對失敗')
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.root.is_symlink():raise ValueError('恢復目錄不可為符號連結')
        descriptor,path=tempfile.mkstemp(prefix='.saving-',dir=self.root)
        try:
            with os.fdopen(descriptor,'wb') as stream:stream.write(blob);stream.flush();os.fsync(stream.fileno())
            publish_complete(path,self.path)
        finally:Path(path).unlink(missing_ok=True)
        return dict(saved=True,encrypted=True,authenticated=True,expires=record['expires'],scope='ONE_LOCAL_SHORT_LIVED_LAYOUT',unsaved_progress_recoverable=False)
    def load(self,password):
        if not self.pending():raise ValueError('沒有有效的已落盤恢復資訊；未保存進度無法承諾恢復')
        blob=self.path.read_bytes()
        if not blob.startswith(MAGIC) or len(blob)<49:raise ValueError('恢復格式不支援，請放棄並清除')
        try:plain=AESGCM(key(password,blob[5:21])).decrypt(blob[21:33],blob[33:],MAGIC);record=json.loads(plain)
        except Exception as error:raise ValueError('密碼錯誤或恢復暫存損壞；未修改目前工作') from error
        if record.get('schema')!=1 or record.get('root_digest')!=digest(str(self.root.parent.resolve())) or record.get('expires',0)<=self.clock() or record.get('created',0)>self.clock()+60 or record.get('expires',0)-record.get('created',0)>TTL_SECONDS:
            self.clear();raise ValueError('恢復版本／Library／有效期不符，已清除暫存')
        if record.get('engine')!=engine_pins():self.clear();raise ValueError('計算引擎／規則版本已變更，暫存需重新計算且已清除')
        return record['payload']
    def validate(self,library,payload):
        if len(payload.get('rows',[]))>200 or len(payload.get('templates',[]))>200:raise ValueError('恢復候選範圍超過200上限')
        current={t.id:t for t in library.templates(True)};rows=[]
        for row in payload.get('rows',[]):
            restored=copy.deepcopy(row)
            if row.get('candidate'):
                candidate=decode_candidate(row['candidate']);template=current.get(candidate.template.id)
                if not template or digest(template.to_dict())!=digest(candidate.template.to_dict()):restored.update(candidate=None,state='STALE_RECALCULATE',reason='模板版本已改變／失聯')
                else:
                    bind_source(candidate,library)
                    freshness=[c for c in candidate.risk['conditions'] if c['id']=='SNAPSHOT_FRESHNESS']
                    if any(c['status']!='PASS' for c in freshness):restored.update(candidate=None,state='STALE_RECALCULATE',reason='輸入／資產／框位指紋已變更')
                    else:restored.update(candidate=candidate,state='RESTORED_CURRENT_PENDING_ADOPTION')
            rows.append(restored)
        return rows
