"""SQLite 持久模板、來源、標記及 Logo；寫入採交易並保存核准事件。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .model import Template, new_id, template_errors


class Library:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets = self.root / "assets"
        self.assets.mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.root / "library.sqlite3")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS contents(hash TEXT PRIMARY KEY, bytes INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, hash TEXT REFERENCES contents(hash), original_path TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS labels(source_id TEXT PRIMARY KEY REFERENCES sources(id), payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS templates(id TEXT PRIMARY KEY, family_id TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(family_id, version));
        CREATE TABLE IF NOT EXISTS logos(id TEXT PRIMARY KEY, company TEXT NOT NULL, width REAL NOT NULL, height REAL NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, entity TEXT NOT NULL, action TEXT NOT NULL, timestamp REAL NOT NULL);
        """)
        self.db.commit()

    def event(self, entity: str, action: str) -> None:
        self.db.execute("INSERT INTO reviews VALUES(?,?,?,?)", (new_id(), entity, action, time.time()))

    def add_source(self, original: Path, payload: dict) -> dict:
        """同內容共用分析資產，但每條原名／路徑登錄獨立保留。"""
        sha = payload["hash"]
        source_id = new_id()
        data = {**payload, "id": source_id, "original_path": str(original.resolve())}
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO contents VALUES(?,?)", (sha, original.stat().st_size))
            self.db.execute("INSERT INTO sources VALUES(?,?,?,?)", (source_id, sha, str(original.resolve()), json.dumps(data, ensure_ascii=False)))
        return data

    def list_sources(self) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM sources ORDER BY rowid DESC")]

    def save_labels(self, source_id: str, payload: dict) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO labels VALUES(?,?)", (source_id, json.dumps(payload, ensure_ascii=False)))
            self.event(source_id, "save_labels")

    def get_labels(self, source_id: str) -> dict | None:
        row = self.db.execute("SELECT payload FROM labels WHERE source_id=?", (source_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_template(self, t: Template) -> None:
        row = self.db.execute("SELECT state FROM templates WHERE id=?", (t.id,)).fetchone()
        if row and row[0] == "published":
            raise ValueError("已發布版本不可覆寫，請建立新版本草稿")
        collision = self.db.execute("SELECT id FROM templates WHERE family_id=? AND version=?", (t.family_id, t.version)).fetchone()
        if collision and collision[0] != t.id:
            raise ValueError("此模板版次已存在，請取得下一個新版本，不可覆蓋歷史")
        with self.db:
            self.db.execute("INSERT INTO templates VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,payload=excluded.payload", (t.id, t.family_id, t.version, t.state, json.dumps(t.to_dict(), ensure_ascii=False)))
            self.event(t.id, "save_draft")

    def publish(self, t: Template) -> None:
        errors = template_errors(t)
        from .background import background_errors
        errors.extend(background_errors(t.background, t.width_mm, t.height_mm))
        if errors:
            raise ValueError("\n".join(errors))
        t.state = "published"
        self.save_template(t)
        with self.db:
            self.event(t.id, "publish_user_confirmed")

    def next_version(self, family_id: str) -> int:
        return self.db.execute("SELECT COALESCE(MAX(version),0)+1 FROM templates WHERE family_id=?", (family_id,)).fetchone()[0]

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

    def backup(self, target: Path) -> None:
        """第一版提供數據庫一致性快照；完整資產加密備份留後期。"""
        if target.exists():
            raise FileExistsError("預設不覆寫既有備份")
        with sqlite3.connect(target) as other:
            self.db.backup(other)

    def close(self) -> None:
        self.db.close()
