"""SQLite 持久模板、來源、標記及 Logo；寫入採交易並保存核准事件。"""
from __future__ import annotations

import hashlib
import copy
import json
from pathlib import Path
import sqlite3
import time

from .model import Template, new_id, template_errors

MAX_RELINK_AUDIT_BYTES=8*1024*1024


class Library:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if self.root.name=='restored-library' and (self.root.parent/'RESTORE_STAGING_NOT_ACTIVE').exists():
            raise ValueError('隔離還原尚未完成，保留現行環境；請檢查還原狀態後重新還原至新目錄')
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets = self.root / "assets"
        self.assets.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / "library.sqlite3")
        self.closed=False
        self._close_listeners=[]
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS contents(hash TEXT PRIMARY KEY, bytes INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, hash TEXT REFERENCES contents(hash), original_path TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS labels(source_id TEXT PRIMARY KEY REFERENCES sources(id), payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS templates(id TEXT PRIMARY KEY, family_id TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(family_id, version));
        CREATE TABLE IF NOT EXISTS logos(id TEXT PRIMARY KEY, company TEXT NOT NULL, width REAL NOT NULL, height REAL NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, entity TEXT NOT NULL, action TEXT NOT NULL, timestamp REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS artworks(id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), name TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS artwork_revisions(artwork_id TEXT NOT NULL REFERENCES artworks(id), revision INTEGER NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(artwork_id,revision));
        CREATE TABLE IF NOT EXISTS active_artworks(source_id TEXT PRIMARY KEY REFERENCES sources(id), artwork_id TEXT NOT NULL REFERENCES artworks(id));
        CREATE TABLE IF NOT EXISTS font_assets(hash TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS font_repairs(id TEXT PRIMARY KEY, hash TEXT NOT NULL REFERENCES font_assets(hash), phase TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS source_links(source_id TEXT PRIMARY KEY REFERENCES sources(id), current_path TEXT NOT NULL, revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS source_relinks(id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), revision INTEGER NOT NULL, previous_path TEXT NOT NULL, current_path TEXT NOT NULL, hash TEXT NOT NULL, timestamp REAL NOT NULL, UNIQUE(source_id,revision));
        CREATE TABLE IF NOT EXISTS relink_batches(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS template_edit_clocks(template_id TEXT PRIMARY KEY REFERENCES templates(id), revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS font_changes(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS object_edits(id TEXT PRIMARY KEY, entity_kind TEXT NOT NULL, entity_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runtime_requests(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,revision INTEGER NOT NULL,payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS runtime_requests_state ON runtime_requests(json_extract(payload,'$.state'),seq);
        INSERT OR IGNORE INTO template_edit_clocks SELECT id,0 FROM templates;
        """)
        self.db.commit()

    def event(self, entity: str, action: str) -> None:
        self.db.execute("INSERT INTO reviews VALUES(?,?,?,?)", (new_id(), entity, action, time.time()))

    def add_source(self, original: Path, payload: dict, *, before_write=None, commit_hook=None) -> dict:
        """同內容共用分析資產，但每條原名／路徑登錄獨立保留。"""
        sha = payload["hash"]
        source_id = new_id()
        original_path=str(original.resolve());byte_size=original.stat().st_size
        data = {**payload, "id": source_id, "original_path": original_path}
        try:
            with self.db:
                if before_write or commit_hook:
                    self.db.execute('BEGIN IMMEDIATE')
                    if before_write:before_write()
                self.db.execute("INSERT OR IGNORE INTO contents VALUES(?,?)", (sha, byte_size))
                self.db.execute("INSERT INTO sources VALUES(?,?,?,?)", (source_id, sha, original_path, json.dumps(data, ensure_ascii=False)))
                if commit_hook:commit_hook(data)
        except Exception as error:
            if before_write or commit_hook:raise RuntimeError('來源登錄與工作連結未一起提交，已停止：'+str(error)) from error
            raise
        return data

    def list_sources(self) -> list[dict]:
        return [{**json.loads(r[0]), "current_path": r[1], "link_revision": r[2], "byte_size": r[3]}
                for r in self.db.execute("SELECT s.payload,COALESCE(l.current_path,s.original_path),COALESCE(l.revision,0),c.bytes FROM sources s JOIN contents c ON c.hash=s.hash LEFT JOIN source_links l ON l.source_id=s.id ORDER BY s.rowid DESC")]

    def source(self, source_id: str) -> dict:
        r = self.db.execute("SELECT s.payload,COALESCE(l.current_path,s.original_path),COALESCE(l.revision,0),c.bytes FROM sources s JOIN contents c ON c.hash=s.hash LEFT JOIN source_links l ON l.source_id=s.id WHERE s.id=?", (source_id,)).fetchone()
        if r is None:
            raise ValueError("來源不存在")
        return {**json.loads(r[0]), "current_path": r[1], "link_revision": r[2], "byte_size": r[3]}

    def sources_for_content(self,content_hash,page,path=None,limit=100):
        """Bounded reuse candidates; never the denominator of registered sources."""
        if content_hash is None:return []
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('單次來源快取候選最多100')
        where=['s.hash=?',"json_extract(s.payload,'$.page')=?"];args=[content_hash,page]
        if path is not None:
            import os
            self.db.create_function('runtime_normpath',1,lambda value:os.path.normcase(os.path.normpath(value)),deterministic=True)
            where.append('runtime_normpath(COALESCE(l.current_path,s.original_path))=runtime_normpath(?)');args.append(str(Path(path).absolute()))
        ids=[row[0] for row in self.db.execute('SELECT s.id FROM sources s LEFT JOIN source_links l ON l.source_id=s.id WHERE '+' AND '.join(where)+' ORDER BY s.rowid DESC LIMIT ?',(*args,limit))]
        from .startup_catalog import payload
        for identity in ids:payload(self,'sources',identity)
        return [self.source(identity) for identity in ids]

    def relink_source(self, source_id: str, proof, expected_revision: int) -> dict:
        """背景驗證完成後於 SQLite 所屬執行緒提交；原來源與作品模板保持不變。"""
        from .source_links import check_verified
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("來源位置版次不合法")
        # The legacy single-source API shares the same transaction and mapping audit.
        self.relink_sources([dict(source_id=source_id,proof=proof,expected_revision=expected_revision)],approved=True)
        return self.source(source_id)

    def _write_source_link(self, source_id, proof, expected_revision, expected_context=None):
        from .source_links import check_verified
        source = self.source(source_id)
        if type(expected_revision) is not int or expected_revision < 0 or source["link_revision"] != expected_revision:
            raise ValueError("來源已由另一工作階段重連，請重新載入")
        check_verified(proof, source["hash"])
        if proof.stat[2] != source["byte_size"]:
            raise ValueError("來源長度不符，不重新連結")
        impact=self.source_impacts(source_id)
        if expected_context is not None and expected_context!=impact['context_sha256']:
            raise ValueError('來源客戶／版型／訓練／資產關聯已變更，請重新核對完整影響')
        if source["current_path"] == proof.path:
            return None
        revision = expected_revision + 1
        self.db.execute("INSERT INTO source_links VALUES(?,?,?) ON CONFLICT(source_id) DO UPDATE SET current_path=excluded.current_path,revision=excluded.revision", (source_id, proof.path, revision))
        self.db.execute("INSERT INTO source_relinks VALUES(?,?,?,?,?,?,?)", (new_id(), source_id, revision, source["current_path"], proof.path, source["hash"], time.time()))
        self.event(source_id, "source_relinked_same_content")
        return {"source_id": source_id, "hash": source["hash"], "previous_path": source["current_path"], "current_path": proof.path,
                "before_revision": expected_revision, "after_revision": revision,
                "impact_snapshot":impact['context'],"impact_sha256":impact['context_sha256'],
                "verified_source_stat":list(proof.stat),"verification":"EXACT_SHA256_AND_BYTE_LENGTH"}

    def relink_sources(self, requests, approved=False, undo_of=None):
        if approved is not True or not requests:
            raise ValueError("請明列勾選並確認來源身份與重連影響")
        ids = [r["source_id"] for r in requests]
        if len(ids) != len(set(ids)) or len(ids) > 2000:
            raise ValueError("批次來源重複或超過支援數量")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if undo_of:
                prior = self.relink_batch(undo_of)
                expected = {r["source_id"]: r for r in prior["items"]}
                if set(ids) != set(expected):
                    raise ValueError("復原必須對應原批次全體來源")
                for request in requests:
                    item = expected[request["source_id"]]
                    if request["expected_revision"] != item["after_revision"] or request["proof"].path != item["previous_path"]:
                        raise ValueError("復原位置或版次與原批次不符")
            changes=[];audit_bytes=0
            for request in requests:
                item=self._write_source_link(request['source_id'],request['proof'],request['expected_revision'],request.get('expected_context'))
                if item:
                    audit_bytes+=len(json.dumps(item,ensure_ascii=False).encode())
                    if audit_bytes>MAX_RELINK_AUDIT_BYTES:raise ValueError('整批重連稽核超過8MiB；本批未套用，請分組核對')
                    changes.append(item)
            if not changes:
                self.db.commit()
                return {"id": None, "kind": "NO_CHANGE", "items": []}
            record = {"id": new_id(), "kind": "UNDO" if undo_of else "APPLY", "undo_of": undo_of, "items": changes,
                      "approved": True, "timestamp": time.time()}
            self.db.execute("INSERT INTO relink_batches VALUES(?,?)", (record["id"], json.dumps(record, ensure_ascii=False)))
            self.event(record["id"], "source_batch_undo_approved" if undo_of else "source_batch_relink_approved")
            self.db.commit()
            return record
        except BaseException:
            self.db.rollback()
            raise

    def relink_batch(self, batch_id):
        row = self.db.execute("SELECT payload FROM relink_batches WHERE id=?", (batch_id,)).fetchone()
        if not row:
            raise ValueError("重連批次不存在")
        return json.loads(row[0])

    def relink_batches(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM relink_batches ORDER BY rowid DESC")]

    def source_impacts(self, source_id):
        from .source_context import source_context
        return source_context(self,source_id)

    def source_link_history(self, source_id: str) -> list[dict]:
        return [dict(revision=r[0], previous_path=r[1], current_path=r[2], hash=r[3], timestamp=r[4])
                for r in self.db.execute("SELECT revision,previous_path,current_path,hash,timestamp FROM source_relinks WHERE source_id=? ORDER BY revision DESC", (source_id,))]

    def active_source_id(self) -> str | None:
        row = self.db.execute("SELECT value FROM preferences WHERE key='active_source'").fetchone()
        return row[0] if row and self.db.execute("SELECT 1 FROM sources WHERE id=?", (row[0],)).fetchone() else None

    def select_source(self, source_id: str) -> None:
        if not self.db.execute("SELECT 1 FROM sources WHERE id=?", (source_id,)).fetchone():
            raise ValueError("來源不存在，不能恢復此工作上下文")
        with self.db:
            self.db.execute("INSERT INTO preferences VALUES('active_source',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (source_id,))

    def save_labels(self, source_id: str, payload: dict) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO labels VALUES(?,?)", (source_id, json.dumps(payload, ensure_ascii=False)))
            self.event(source_id, "save_labels")

    def get_labels(self, source_id: str) -> dict | None:
        row = self.db.execute("SELECT payload FROM labels WHERE source_id=?", (source_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def _artwork_payload(self, source_id: str, payload: dict) -> str:
        """草稿可保留未修好的欄位，但作品範圍與毫米必須有效，才可安全恢復畫布。"""
        from .model import Rect
        import math
        row = self.db.execute("SELECT payload FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise ValueError("作品來源不存在")
        source = json.loads(row[0])
        try:
            crop = Rect(**payload["crop"])
            if not crop.inside(source["width_mm"], source["height_mm"]):
                raise ValueError()
            if not all(math.isfinite(payload[k]) and 0 < payload[k] <= 2000 for k in ("work_width", "work_height")):
                raise ValueError()
            if not isinstance(payload["slots"], list):
                raise ValueError()
            return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        except (KeyError, TypeError, ValueError):
            raise ValueError("作品範圍或毫米尺寸不合法，標記尚未保存") from None

    def _decode_artwork(self, row) -> dict | None:
        return {"id": row[0], "source_id": row[1], "name": row[2], "revision": row[3], "payload": json.loads(row[4])} if row else None

    def artworks(self, source_id: str) -> list[dict]:
        return [self._decode_artwork(row) for row in self.db.execute("SELECT id,source_id,name,revision,payload FROM artworks WHERE source_id=? ORDER BY rowid", (source_id,))]

    def artwork(self, artwork_id: str) -> dict:
        row = self.db.execute("SELECT id,source_id,name,revision,payload FROM artworks WHERE id=?", (artwork_id,)).fetchone()
        if not row:
            raise ValueError("作品不存在")
        return self._decode_artwork(row)

    def active_artwork(self, source_id: str) -> dict | None:
        row = self.db.execute("SELECT a.id,a.source_id,a.name,a.revision,a.payload FROM artworks a JOIN active_artworks s ON s.artwork_id=a.id WHERE s.source_id=? AND a.source_id=s.source_id", (source_id,)).fetchone()
        return self._decode_artwork(row)

    def create_artwork(self, source_id: str, name: str, payload: dict) -> dict:
        if not name.strip() or len(name.strip()) > 120:
            raise ValueError("作品名稱需為 1～120 個字")
        data = self._artwork_payload(source_id, payload)
        artwork_id = new_id()
        with self.db:
            self.db.execute("INSERT INTO artworks VALUES(?,?,?,?,?)", (artwork_id, source_id, name.strip(), 1, data))
            self.db.execute("INSERT INTO artwork_revisions VALUES(?,?,?,?)", (artwork_id, 1, data, time.time()))
            self.db.execute("INSERT INTO active_artworks VALUES(?,?) ON CONFLICT(source_id) DO UPDATE SET artwork_id=excluded.artwork_id", (source_id, artwork_id))
            self.event(artwork_id, "create_artwork")
        return self.artwork(artwork_id)

    def select_artwork(self, source_id: str, artwork_id: str) -> dict:
        artwork = self.artwork(artwork_id)
        if artwork["source_id"] != source_id:
            raise ValueError("作品不屬於目前來源，不能跨來源混配")
        with self.db:
            self.db.execute("INSERT INTO active_artworks VALUES(?,?) ON CONFLICT(source_id) DO UPDATE SET artwork_id=excluded.artwork_id", (source_id, artwork_id))
        return artwork

    def rename_artwork(self, artwork_id: str, name: str) -> None:
        if not name.strip() or len(name.strip()) > 120:
            raise ValueError("作品名稱需為 1～120 個字")
        self.artwork(artwork_id)
        with self.db:
            self.db.execute("UPDATE artworks SET name=? WHERE id=?", (name.strip(), artwork_id))
            self.event(artwork_id, "rename_artwork")

    def save_artwork(self, artwork_id: str, payload: dict, expected_revision: int) -> dict:
        artwork = self.artwork(artwork_id)
        if artwork["revision"] != expected_revision:
            raise ValueError("作品已由另一工作階段更新，請重新載入；本次修改未覆蓋新標記")
        from .object_tools import protect_locked
        protect_locked(artwork['payload'],payload)
        data = self._artwork_payload(artwork["source_id"], payload)
        previous = json.dumps(artwork["payload"], ensure_ascii=False, sort_keys=True, allow_nan=False)
        if data == previous:
            return artwork
        revision = expected_revision + 1
        with self.db:
            cursor = self.db.execute("UPDATE artworks SET revision=?,payload=? WHERE id=? AND revision=?", (revision, data, artwork_id, expected_revision))
            if cursor.rowcount != 1:
                raise ValueError("作品版次已變更，標記尚未保存")
            self.db.execute("INSERT INTO artwork_revisions VALUES(?,?,?,?)", (artwork_id, revision, data, time.time()))
            self.event(artwork_id, "save_artwork_revision")
        return self.artwork(artwork_id)

    def artwork_history(self, artwork_id: str) -> list[dict]:
        return [{"revision": r[0], "created": r[1]} for r in self.db.execute("SELECT revision,created FROM artwork_revisions WHERE artwork_id=? ORDER BY revision DESC LIMIT 100", (artwork_id,))]

    def restore_artwork(self, artwork_id: str, revision: int, expected_revision: int) -> dict:
        row = self.db.execute("SELECT payload FROM artwork_revisions WHERE artwork_id=? AND revision=?", (artwork_id, revision)).fetchone()
        if not row:
            raise ValueError("此標記歷史版次不存在")
        return self.save_artwork(artwork_id, json.loads(row[0]), expected_revision)

    def initialize_artwork(self, source_id: str, default_payload: dict) -> dict:
        active = self.active_artwork(source_id)
        if active:
            return active
        works = self.artworks(source_id)
        if works:
            return self.select_artwork(source_id, works[0]["id"])
        # 舊版單作品記錄保留原表；只在首次開啟來源時建立新工作區，不刪除舊資料。
        legacy = self.get_labels(source_id)
        payload = legacy if legacy and all(k in legacy for k in ("crop", "work_width", "work_height", "slots")) else default_payload
        return self.create_artwork(source_id, "作品 1（舊標記）" if payload is legacy else "作品 1", payload)

    def save_template(self,t:Template,expected_revision=None) -> None:
        if expected_revision is None:return self._save_template_data(t)
        if self.db.in_transaction:raise ValueError('已有交易，不能巢狀草稿保存')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            current=self.object_snapshot('TEMPLATE',t.id)
            if type(expected_revision) is not int or current['revision']!=expected_revision:raise ValueError('模板已由其他工作階段變更／ABA，未保存手工內容')
            self._save_template_data(t);self.db.commit()
        except BaseException:self.db.rollback();raise

    def _save_template_data(self,t):
        self._template_provenance(t,allow_quarantined_draft=True)
        row = self.db.execute("SELECT state,family_id,version,payload FROM templates WHERE id=?", (t.id,)).fetchone()
        if row and row[0] == "published":
            raise ValueError("已發布版本不可覆寫，請建立新版本草稿")
        if row and (row[1],row[2])!=(t.family_id,t.version):
            raise ValueError("已有模板的family／版次識別不可改写")
        if row:
            from .object_tools import protect_locked
            protect_locked(json.loads(row[3]),t.to_dict())
        collision = self.db.execute("SELECT id FROM templates WHERE family_id=? AND version=?", (t.family_id, t.version)).fetchone()
        if collision and collision[0] != t.id:
            raise ValueError("此模板版次已存在，請取得下一個新版本，不可覆蓋歷史")
        serialized=json.dumps(t.to_dict(),ensure_ascii=False)
        if row and row[3]==serialized: return
        with self.db:
            self.db.execute("INSERT INTO templates VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,payload=excluded.payload", (t.id, t.family_id, t.version, t.state, serialized))
            self._bump_template_clock(t.id)
            self.event(t.id, "save_draft")

    def publish(self, t: Template) -> None:
        self._template_provenance(t,for_publication=True)
        errors = template_errors(t)
        from PySide6.QtGui import QFontDatabase,QGuiApplication
        if QGuiApplication.instance() is None:errors.append('字型系統未初始化，不能核驗發布')
        else:
            families=set(QFontDatabase.families())
            for slot in t.slots:
                if slot.kind!='logo' and slot.font_asset is None:
                    if slot.font not in families:errors.append(slot.id+'：指定字型未安裝，不可發布')
                    elif slot.font_style and slot.font_style not in QFontDatabase.styles(slot.font):errors.append(slot.id+'：指定款式未安裝，不可借用其他款式發布')
        from .background import background_errors
        errors.extend(background_errors(t.background, t.width_mm, t.height_mm))
        if errors:
            raise ValueError("\n".join(errors))
        published = copy.deepcopy(t)
        published.state = "published"
        with self.db:
            # 發布與審核事件同一交易；失敗不讓畫面物件誤變成已發布。
            row = self.db.execute("SELECT state FROM templates WHERE id=?", (t.id,)).fetchone()
            if row and row[0] == "published":
                raise ValueError("已發布版本不可覆寫，請建立新版本草稿")
            old=self.db.execute('SELECT payload FROM templates WHERE id=?',(t.id,)).fetchone()
            if old:
                from .object_tools import protect_locked
                protect_locked(json.loads(old[0]),t.to_dict())
            collision = self.db.execute("SELECT id FROM templates WHERE family_id=? AND version=?", (t.family_id, t.version)).fetchone()
            if collision and collision[0] != t.id:
                raise ValueError("此模板版次已存在，不可覆蓋歷史")
            self.db.execute("INSERT INTO templates VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,payload=excluded.payload", (t.id, t.family_id, t.version, published.state, json.dumps(published.to_dict(), ensure_ascii=False)))
            self._bump_template_clock(t.id)
            self.event(t.id, "publish_user_confirmed")
        t.state = "published"

    def _template_provenance(self, t: Template,*,allow_quarantined_draft=False,for_publication=False) -> None:
        if t.generation_reference is not None:
            raise ValueError('當次學習實例保存在DESIGN_INSTANCE，不能當成已發布全域模板')
        registered=self.db.execute('SELECT family_id,version FROM templates WHERE id=?',(t.id,)).fetchone()
        if registered and (registered[0],registered[1])!=(t.family_id,t.version):
            raise ValueError('同一模板ID的系列與版次不可改寫；請建立具新ID的明確版本草稿')
        from .quality_source_rechecks import source_or_template_blocked
        if not (allow_quarantined_draft is True and t.state=='draft') and source_or_template_blocked(self,t,exact_content=for_publication):raise ValueError('重大共通錯誤重審尚未核准此來源／模板版本，暫停可信使用')
        if t.training_reference is not None:
            from .training_store import TrainingStore
            try: TrainingStore.bind(self).validate_training_reference(t)
            except (sqlite3.Error, KeyError, TypeError) as error: raise ValueError('訓練資料來源／准入無法核對，不能使用此模板') from error
        if not t.source_work_id:
            if t.source_work_revision != 0:
                raise ValueError("模板缺少來源作品識別，不能只填版次")
            return
        row = self.db.execute("SELECT a.source_id,r.payload FROM artworks a JOIN artwork_revisions r ON r.artwork_id=a.id WHERE a.id=? AND r.revision=?", (t.source_work_id, t.source_work_revision)).fetchone()
        if not row or row[0] != t.source_id:
            raise ValueError("模板的來源作品／標記版次不符，不可混配來源")
        if json.loads(row[1]).get('analysis_evidence',{}).get('oversized_text'):raise ValueError('來源文字超出觀察資源預算且未完整核實，不能發布衍生模板')

    def next_version(self, family_id: str) -> int:
        return self.db.execute("SELECT COALESCE(MAX(version),0)+1 FROM templates WHERE family_id=?", (family_id,)).fetchone()[0]

    def _bump_template_clock(self, template_id):
        self.db.execute("INSERT INTO template_edit_clocks VALUES(?,1) ON CONFLICT(template_id) DO UPDATE SET revision=revision+1",(template_id,))

    def template_snapshots(self):
        return [{"template":json.loads(payload),"revision":revision} for payload,revision in self.db.execute("SELECT t.payload,c.revision FROM templates t JOIN template_edit_clocks c ON c.template_id=t.id ORDER BY t.rowid DESC")]

    def object_snapshot(self,kind,entity_id):
        if kind=='TEMPLATE':
            row=self.db.execute('SELECT t.payload,c.revision FROM templates t JOIN template_edit_clocks c ON c.template_id=t.id WHERE t.id=?',(entity_id,)).fetchone()
            if not row:raise ValueError('模板不存在')
            return {'kind':kind,'id':entity_id,'payload':json.loads(row[0]),'revision':row[1]}
        if kind=='ARTWORK':
            w=self.artwork(entity_id)
            return {'kind':kind,'id':entity_id,'payload':w['payload'],'revision':w['revision']}
        raise ValueError('物件上下文不合法')

    def object_edit_history(self,kind,entity_id):
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM object_edits WHERE entity_kind=? AND entity_id=? ORDER BY rowid DESC LIMIT 50',(kind,entity_id))]

    def _object_write(self,kind,entity_id,payload,revision):
        if kind=='TEMPLATE':
            t=Template.from_dict(payload);self._template_provenance(t,allow_quarantined_draft=True)
            if t.state!='draft' or t.id!=entity_id:raise ValueError('發布版本唯讀／模板身份不符')
            self.db.execute('UPDATE templates SET payload=? WHERE id=? AND state=?',(json.dumps(payload,ensure_ascii=False),entity_id,'draft'))
            self._bump_template_clock(entity_id)
        else:
            w=self.artwork(entity_id);data=self._artwork_payload(w['source_id'],payload)
            self.db.execute('UPDATE artworks SET revision=?,payload=? WHERE id=?',(revision+1,data,entity_id))
            self.db.execute('INSERT INTO artwork_revisions VALUES(?,?,?,?)',(entity_id,revision+1,data,time.time()))

    def apply_object_edit(self,snapshot,request,confirmed=False,operation_id=None):
        from .object_tools import propose
        from .font_review import fingerprint
        if confirmed is not True:raise ValueError('需明確核准精確範圍與差異')
        if self.db.in_transaction:raise ValueError('已有交易，不能巢狀物件編輯')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if operation_id is not None:
                if not isinstance(operation_id,str) or not operation_id.startswith('batch:') or len(operation_id)!=70:raise ValueError('批次操作ID不合法')
                old=self.db.execute('SELECT payload FROM object_edits WHERE id=?',(operation_id,)).fetchone()
                if old:
                    record=json.loads(old[0])
                    if record['kind']!=snapshot['kind'] or record['entity_id']!=snapshot['id'] or record['plan']['request']!=request or record['before']!=snapshot['payload'] or record['before_revision']!=snapshot['revision'] or record['phase']!='APPLIED':raise ValueError('操作ID已用於不同範圍或已復原；不能盲目重試')
                    self.db.commit();return {**record,'reused':True}
            current=self.object_snapshot(snapshot['kind'],snapshot['id'])
            if current['revision']!=snapshot['revision'] or fingerprint(current['payload'])!=fingerprint(snapshot['payload']):raise ValueError('物件資料已變更／ABA，請重新載入與預覽')
            # Recompute under write lock; caller-supplied after/eligibility is never trusted.
            plan=propose(current['payload'],current['kind'],request)
            if request.get('operation')=='PATCH' and 'font_asset' in request.get('patch',{}):self._assert_font_registered({'asset':request['patch']['font_asset']})
            self._object_write(current['kind'],current['id'],plan['after'],current['revision'])
            record={'id':operation_id or new_id(),'kind':current['kind'],'entity_id':current['id'],'phase':'APPLIED','sequence':1,'created':time.time(),
                    'before':copy.deepcopy(current['payload']),'after':copy.deepcopy(plan['after']),'expected_revision':current['revision']+1,
                    'plan':plan,'before_revision':current['revision']}
            self.db.execute('INSERT INTO object_edits VALUES(?,?,?,?)',(record['id'],current['kind'],current['id'],json.dumps(record,ensure_ascii=False)))
            self.event(current['id'],'object_edit_'+request['operation'].lower());self.db.commit()
            return record
        except BaseException:self.db.rollback();raise

    def object_history_action(self,record_id,action,confirmed=False):
        from .font_review import fingerprint
        if confirmed is not True or action not in ('UNDO','REDO'):raise ValueError('需明確核對歷史範圍／復原或重做')
        if self.db.in_transaction:raise ValueError('已有交易，不能巢狀歷史編輯')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT payload FROM object_edits WHERE id=?',(record_id,)).fetchone()
            if not row:raise ValueError('歷史不存在')
            r=json.loads(row[0]);expected_phase='APPLIED' if action=='UNDO' else 'UNDONE'
            if r['phase']!=expected_phase:raise ValueError('歷史階段已變更')
            current=self.object_snapshot(r['kind'],r['entity_id']);expected=r['after'] if action=='UNDO' else r['before'];target=r['before'] if action=='UNDO' else r['after']
            if current['revision']!=r['expected_revision'] or fingerprint(current['payload'])!=fingerprint(expected):raise ValueError('歷史後已有編輯／ABA，不能覆蓋；請重新核對')
            if current['kind']=='TEMPLATE' and current['payload']['state']!='draft':raise ValueError('發布版本唯讀')
            # Undo lock operation is an explicit, separately confirmed scope; no automatic unlock.
            if r['plan']['request']['operation']!='LOCK':
                from .object_tools import protect_locked
                protect_locked(current['payload'],target)
            from .object_tools import warnings_for
            r['current_warnings']=warnings_for(target,r['kind'])
            self._object_write(r['kind'],r['entity_id'],target,current['revision'])
            r['phase']='UNDONE' if action=='UNDO' else 'APPLIED';r['sequence']+=1;r['expected_revision']=current['revision']+1
            self.db.execute('UPDATE object_edits SET payload=? WHERE id=?',(json.dumps(r,ensure_ascii=False),r['id']))
            self.event(r['entity_id'],'object_edit_'+action.lower());self.db.commit();return r
        except BaseException:self.db.rollback();raise

    def comparison_source(self, template: dict) -> dict:
        """GUI thread only: copy exact pinned historical geometry for a read-only worker."""
        t = Template.from_dict(template)
        if not t.source_work_id:
            return {"status": "UNKNOWN", "reason": "模板未綁定來源作品／歷史版次"}
        row = self.db.execute("SELECT a.source_id,r.payload FROM artworks a JOIN artwork_revisions r ON r.artwork_id=a.id WHERE a.id=? AND r.revision=?", (t.source_work_id, t.source_work_revision)).fetchone()
        if not row or row[0] != t.source_id:
            raise ValueError("對照來源作品／歷史版次不符")
        return {"status": "PINNED", "work_id": t.source_work_id, "revision": t.source_work_revision,
                "work": json.loads(row[1]), "source": self.source(row[0])}

    def font_change_history(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM font_changes ORDER BY rowid DESC')]

    def _assert_font_registered(self,target):
        from .font_catalog import asset_health
        asset=target['asset']
        row=self.db.execute('SELECT payload FROM font_assets WHERE hash=?',(asset['hash'],)).fetchone()
        if not row or json.loads(row[0])!=asset or asset_health(asset)[0]!='HEALTHY':
            raise ValueError('目標字型登錄／核准內容已變更，請重新審核')

    def _template_cas(self,template_id,expected_hash,expected_revision,draft_only=False):
        from .font_review import fingerprint
        row=self.db.execute('SELECT t.payload,c.revision,t.state FROM templates t JOIN template_edit_clocks c ON c.template_id=t.id WHERE t.id=?',(template_id,)).fetchone()
        if not row or row[1]!=expected_revision or fingerprint(json.loads(row[0]))!=expected_hash or (draft_only and row[2]!='draft'):
            raise ValueError('模板在審核後已變更或發布，不能覆蓋；請重新審核')
        return Template.from_dict(json.loads(row[0]))

    def _commit_font_change(self,data):
        from .font_review import fingerprint
        if self.db.in_transaction:raise ValueError('已有交易未完成，不能巢狀套用')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self._assert_font_registered(data['target'])
            groups={}
            for row in data['rows']:groups.setdefault(row['template_id'],[]).append(row)
            record={'id':new_id(),'phase':'APPLIED','sequence':1,'timestamp':time.time(),'target':copy.deepcopy(data['target']),
                    'target_face':data['rows'][0]['proposed']['face_fingerprint'],'drafts':[],
                    'scope':'僅此選取新草稿；未發布／未核准正式輸出，歷史不保存樣本文字'}
            for template_id,rows in groups.items():
                first=rows[0]
                original=self._template_cas(template_id,first['template_hash'],first['revision'])
                self._template_provenance(original)
                draft=copy.deepcopy(original);draft.id=new_id();draft.version=self.next_version(original.family_id);draft.state='draft'
                before=draft.to_dict();selected={r['slot_id']:r for r in rows}
                for slot in draft.slots:
                    if slot.id not in selected:continue
                    if slot.kind=='logo':raise ValueError('Logo不可套用字型替代')
                    if slot.locked:raise ValueError('物件已鎖定；不能以新草稿替代繞過')
                    after=selected[slot.id]['after']
                    slot.font=after['font'];slot.font_style=after['font_style'];slot.font_asset=copy.deepcopy(after['font_asset'])
                payload=draft.to_dict()
                self.db.execute('INSERT INTO templates VALUES(?,?,?,?,?)',(draft.id,draft.family_id,draft.version,draft.state,json.dumps(payload,ensure_ascii=False)))
                self._bump_template_clock(draft.id)
                self.event(draft.id,'font_replacement_new_draft_reviewed')
                record['drafts'].append({'template_id':draft.id,'base_template_id':original.id,'family_id':draft.family_id,'version':draft.version,
                    'before':before,'after':payload,'current_hash':fingerprint(payload),'revision':1,
                    'fields':[{k:r[k] for k in ('slot_id','risk','before','after','text_sha256','original','proposed','reasons')} for r in rows]})
                # 原字面缺字資訊含字元，不將臨時姓名／聯絡文字字元集合持久保存。
                for field in record['drafts'][-1]['fields']:
                    for side in ('original','proposed'):
                        if field[side]:
                            field[side]=copy.deepcopy(field[side])
                            field[side]['missing_count']=len(field[side].get('missing',[]));field[side].pop('missing',None)
            self.db.execute('INSERT INTO font_changes VALUES(?,?)',(record['id'],json.dumps(record,ensure_ascii=False)))
            self.event(record['id'],'font_replacement_batch_scope_confirmed')
            self.db.commit();return record
        except BaseException:self.db.rollback();raise

    def _commit_font_history(self,data):
        from .font_review import fingerprint
        if self.db.in_transaction:raise ValueError('已有交易未完成，不能巢狀復原')
        expected=data['record'];action=data['kind']
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT payload FROM font_changes WHERE id=?',(expected['id'],)).fetchone()
            if not row or json.loads(row[0])!=expected:raise ValueError('替代歷史已變更，請刷新')
            record=copy.deepcopy(expected)
            if action=='REDO':self._assert_font_registered(record['target'])
            for item in record['drafts']:
                self._template_cas(item['template_id'],item['current_hash'],item['revision'],draft_only=True)
                payload=copy.deepcopy(item['before'] if action=='UNDO' else item['after'])
                self.db.execute('UPDATE templates SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),item['template_id']))
                self._bump_template_clock(item['template_id']);item['revision']+=1;item['current_hash']=fingerprint(payload)
                self.event(item['template_id'],'font_replacement_'+action.lower())
            record['phase']='UNDONE' if action=='UNDO' else 'APPLIED';record['sequence']+=1
            self.db.execute('UPDATE font_changes SET payload=? WHERE id=?',(json.dumps(record,ensure_ascii=False),record['id']))
            self.event(record['id'],'font_replacement_'+action.lower()+'_scope_confirmed')
            self.db.commit();return record
        except BaseException:self.db.rollback();raise

    def templates(self, published_only: bool = False) -> list[Template]:
        sql = "SELECT payload FROM templates" + (" WHERE state='published'" if published_only else "") + " ORDER BY rowid DESC"
        return [Template.from_dict(json.loads(r[0])) for r in self.db.execute(sql)]

    def add_logo(self, company: str, width: float, height: float, payload: dict) -> dict:
        if not company.strip() or width <= 0 or height <= 0:
            raise ValueError("公司名稱與矩形尺寸不可為空")
        logo = {**payload, "id": new_id(), "company": company.strip(), "width_mm": width, "height_mm": height, "approved": True}
        with self.db:
            self.db.execute("INSERT INTO logos VALUES(?,?,?,?,?)", (logo["id"], company.strip(), width, height, json.dumps(logo, ensure_ascii=False)))
            self.event(logo["id"], "logo_user_approved")
        return logo

    def logos(self) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM logos ORDER BY rowid DESC")]

    def fonts(self) -> list[dict]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM font_assets ORDER BY rowid")]

    def register_font(self, asset: dict) -> None:
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO font_assets VALUES(?,?)", (asset["hash"], json.dumps(asset, ensure_ascii=False)))
            self.event(asset["hash"], "font_local_use_approved")

    def prepare_font_repair(self, record: dict) -> None:
        with self.db:
            self.db.execute("INSERT INTO font_repairs VALUES(?,?,?,?)", (record["id"], record["hash"], "PREPARED", json.dumps(record, ensure_ascii=False)))

    def finish_font_repair(self, repair_id: str, phase: str, action: str) -> None:
        if phase not in ("COMPLETED", "FAILED"):
            raise ValueError("修復狀態不合法")
        owns_transaction = not self.db.in_transaction
        if owns_transaction:
            self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("SAVEPOINT font_repair_finish")
        try:
            row = self.db.execute("SELECT hash,phase FROM font_repairs WHERE id=?", (repair_id,)).fetchone()
            if not row or row[1] != "PREPARED":
                raise ValueError("修復意圖不存在或已結案")
            self.db.execute("UPDATE font_repairs SET phase=? WHERE id=?", (phase, repair_id))
            self.event(row[0], action)
            self.db.execute("RELEASE font_repair_finish")
            if owns_transaction:
                self.db.commit()
        except BaseException:
            self.db.execute("ROLLBACK TO font_repair_finish")
            self.db.execute("RELEASE font_repair_finish")
            if owns_transaction:
                self.db.rollback()
            raise

    def font_repairs(self) -> list[dict]:
        return [{**json.loads(row[0]), "phase": row[1]} for row in self.db.execute("SELECT payload,phase FROM font_repairs ORDER BY rowid")]

    def backup(self, target: Path) -> None:
        """第一版提供數據庫一致性快照；完整資產加密備份留後期。"""
        if target.exists():
            raise FileExistsError("預設不覆寫既有備份")
        with sqlite3.connect(target) as other:
            self.db.backup(other)

    def observe_close(self,callback):
        """Weak lifecycle subscription; listeners stop producers before SQLite is closed."""
        import weakref
        if self.closed:raise ValueError('資料庫已關閉，不能登錄背景工作')
        try:reference=weakref.WeakMethod(callback)
        except TypeError:reference=weakref.ref(callback)
        self._close_listeners.append(reference)
        return reference

    def close(self) -> None:
        if getattr(self,'closed',False):return
        self.closed=True;errors=[]
        for reference in getattr(self,'_close_listeners',[]):
            callback=reference()
            if callback is not None:
                try:callback()
                except Exception as error:errors.append(error)
        self._close_listeners=[]
        from .batch_import import end_session
        try:end_session(self)
        finally:self.db.close()
        if errors:raise errors[0]
