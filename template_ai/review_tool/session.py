"""Private, versioned review sessions; observations never grant training admission.

This module owns no parser and does not open the original application's database.
Images/fonts remain local references. Diagnostic output is a separate allowlist.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid

SCHEMA_VERSION = 1
FORMAT = "template-ai-artwork-review"
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
REVIEW_STATES = {"UNCHECKED", "REVIEWED", "UNKNOWN"}
SOURCE_STATES = {"ADDED", "READY", "ANALYSING", "ANALYZING", "ANALYSED", "ANALYZED",
                 "PARTIAL", "FAILED", "MISSING", "PAUSED", "WAITING", "PROCESSING"}


class SessionCorruptError(ValueError):
    """No verified snapshot is available; never silently replace it with empty data."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix):
    return prefix + "-" + uuid.uuid4().hex


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _local(value):
    from ..offline_runtime import assert_local_path
    assert_local_path(value)
    return Path(value).expanduser().resolve()


def _rect(value):
    if not isinstance(value, dict):
        raise ValueError("標記範圍需要位置與寬高。")
    result = {key: value[key] for key in ("x", "y", "w", "h")}
    if (any(type(v) not in (int, float) or not math.isfinite(v) for v in result.values())
            or result["w"] <= 0 or result["h"] <= 0):
        raise ValueError("標記位置需為有限數值，寬高必須大於零。")
    return result


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = None
    temporary = None
    try:
        handle = tempfile.NamedTemporaryFile(prefix="." + path.name + "-", suffix=".tmp",
                                             dir=path.parent, delete=False)
        temporary = Path(handle.name)
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        # Persist the rename on platforms supporting directory fsync.
        if os.name != "nt":
            descriptor = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _read_verified(path):
    if path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("本機核對資料超出本版讀取預算，原資料已保留。")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(envelope, dict) or envelope.get("format") != FORMAT
            or envelope.get("schema_version") != SCHEMA_VERSION
            or not isinstance(envelope.get("payload"), dict)
            or _digest(envelope["payload"]) != envelope.get("sha256")):
        raise ValueError("本機核對資料的版本或完整性無法驗證。")
    _validate(envelope["payload"])
    return envelope


def _validate(data):
    if (data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("sources"), list)
            or not isinstance(data.get("owners"), list) or not isinstance(data.get("history"), list)
            or type(data.get("revision")) is not int or data["revision"] < 0):
        raise ValueError("本機核對資料結構不正確。")
    source_ids, work_ids = set(), set()
    owner_ids = {owner["id"] for owner in data["owners"]}
    if len(owner_ids) != len(data["owners"]):
        raise ValueError("人物或公司識別碼重複。")
    for source in data["sources"]:
        if not source.get("id") or source["id"] in source_ids:
            raise ValueError("來源識別碼缺失或重複。")
        source_ids.add(source["id"])
        for version in source.get("analysis_versions", []):
            if _digest(version["result"]) != version["sha256"]:
                raise ValueError("原判讀版本已變更，不能冒充原始結果。")
        for work in source.get("works", []):
            if not work.get("id") or work["id"] in work_ids:
                raise ValueError("作品識別碼缺失或重複。")
            work_ids.add(work["id"])
            _rect(work["crop"])
            field_ids = set()
            for field in work.get("fields", []):
                if not field.get("id") or field["id"] in field_ids:
                    raise ValueError("欄位識別碼缺失或重複。")
                field_ids.add(field["id"])
                _rect(field["rect"])
                if field.get("review_state") not in REVIEW_STATES:
                    raise ValueError("欄位核對狀態不正確。")
                if _digest(field.get("prediction", {})) != field.get("prediction_sha256"):
                    raise ValueError("欄位原判讀已被修改。")
                if field.get("owner") is not None and field["owner"] not in owner_ids:
                    raise ValueError("欄位參照了尚未建立的歸屬對象。")
                if any(key not in owner_ids for key in field.get("shared_with", [])):
                    raise ValueError("欄位參照了尚未建立的共享對象。")
                font_review = field.get("human_font_annotation")
                if font_review is not None:
                    if (not isinstance(font_review, dict) or font_review.get("source") != "HUMAN_VISUAL_REVIEW"
                            or font_review.get("status") not in {"ANNOTATED", "ANNOTATED_FAMILY_ONLY"}
                            or not isinstance(font_review.get("family"), str) or not font_review["family"]
                            or font_review.get("pt_confirmed") is not False
                            or font_review.get("horizontal_scale_confirmed") is not False):
                        raise ValueError("人工字型核對記錄不完整，不能冒稱已確認其他文字參數。")
                    sha = font_review.get("file_sha256")
                    if font_review["status"] == "ANNOTATED_FAMILY_ONLY":
                        if sha is not None or font_review.get("font_file_identity") != "UNKNOWN":
                            raise ValueError("只有字型名稱的記錄不能冒稱已核對字型檔。")
                    elif (not isinstance(sha, str) or len(sha) != 64
                          or any(c not in "0123456789abcdef" for c in sha)
                          or type(font_review.get("face_index")) is not int
                          or font_review["face_index"] < 0):
                        raise ValueError("已核對字型檔的記錄需要真實雜湊與字面索引。")
            for relation in work.get("relations", []):
                if any(key not in field_ids for key in relation.get("field_ids", [])):
                    raise ValueError("關係參照了不存在的欄位。")
    _canonical(data)  # Reject NaN and non-JSON objects before writing a snapshot.


class SessionStore:
    """Single-user local store, with bounded per-work undo and verified backup."""

    def __init__(self, root):
        self.root = _local(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "review-session.json"
        self.backup_path = self.root / "review-session.backup.json"
        self.data = {"schema_version": SCHEMA_VERSION, "id": _id("session"), "revision": 0,
                     "created_utc": _now(), "sources": [], "owners": [], "history": [],
                     "selection": {"source_id": None, "work_id": None, "field_id": None}}
        self.dirty = False
        self.saved_utc = None
        self.recovery_notice = None
        self.interrupted_sources = []
        self._undo = []
        if self.path.exists() or self.backup_path.exists():
            self.load()

    def load(self):
        errors = []
        for candidate in (self.path, self.backup_path):
            if not candidate.is_file():
                continue
            try:
                envelope = _read_verified(candidate)
            except (ValueError, OSError, KeyError, TypeError, UnicodeError) as error:
                errors.append(type(error).__name__)
                continue
            self.data = envelope["payload"]
            self.saved_utc = envelope.get("saved_utc")
            self._undo = []
            self.dirty = candidate == self.backup_path
            self.recovery_notice = ("上次資料無法驗證，已恢復最近的完整備份；原檔保留，請保存恢復結果。"
                                    if self.dirty else None)
            self.interrupted_sources = []
            for source in self.sources():
                if source.get("status") in {"ANALYSING", "ANALYZING", "PROCESSING"}:
                    source["status"] = "PAUSED"
                    source["stage_message"] = "上次判讀未完成，已保留結果，等待明確接續"
                    self.interrupted_sources.append(source["id"])
            if self.interrupted_sources:
                self._record("RECOVER_INTERRUPTED_ANALYSIS", source_ids=self.interrupted_sources)
            return self.data
        raise SessionCorruptError("本機資料與備份皆無法驗證，原檔已保留，請改用資料副本或匯出安全報告。")

    def mark_dirty(self):
        self.data["revision"] += 1
        self.dirty = True

    def _record(self, operation, **details):
        self.mark_dirty()
        record = {"id": _id("revision"), "operation": operation, "time": _now(),
                  "revision": self.data["revision"], **deepcopy(details)}
        self.data["history"].append(record)
        return record

    def _remember(self, source, work=None):
        entry = {"source_id": source["id"]}
        if work is None:
            entry.update(scope="works", before=deepcopy(source.get("works", [])))
        else:
            entry.update(scope="work", work_id=work["id"], before=deepcopy(work))
        self._undo.append(entry)
        self._undo = self._undo[-100:]

    def sources(self):
        return self.data["sources"]

    def get_source(self, source_id):
        for source in self.sources():
            if source["id"] == source_id:
                return source
        raise KeyError("找不到指定來源。")

    def works(self, source_id=None):
        sources = [self.get_source(source_id)] if source_id else self.sources()
        return [work for source in sources for work in source.get("works", [])]

    def get_work(self, work_id):
        for work in self.works():
            if work["id"] == work_id:
                return work
        raise KeyError("找不到指定作品。")

    def _source_for_work(self, work_id):
        for source in self.sources():
            if any(work["id"] == work_id for work in source.get("works", [])):
                return source
        raise KeyError("找不到作品的來源。")

    def get_field(self, work_id, field_id):
        for field in self.get_work(work_id).get("fields", []):
            if field["id"] == field_id:
                return field
        raise KeyError("找不到指定標記。")

    def add_files(self, paths):
        prepared = []
        for value in paths:
            path = _local(value)
            if not path.is_file():
                raise FileNotFoundError("選取的來源檔案不存在。")
            if path.suffix.lower() not in {".ai", ".svg", ".pdf"}:
                raise ValueError("請選擇 AI、PDF 或 SVG 來源檔案。")
            prepared.append(path)
        known = {os.path.normcase(item["path"]): item for item in self.sources()}
        added = []
        for path in prepared:
            key = os.path.normcase(str(path))
            if key in known:
                continue
            source = {"id": _id("source"), "path": str(path), "name": path.name,
                      "status": "ADDED", "stage_message": "已加入，尚未判讀", "works": [],
                      "analysis": None, "analysis_versions": [], "issues": [], "added_utc": _now()}
            self.sources().append(source)
            known[key] = source
            added.append(source)
        if added:
            self._record("ADD_FILES", source_ids=[item["id"] for item in added])
        return added

    def stage_status(self, source_id, status, message=""):
        if status not in SOURCE_STATES:
            raise ValueError("來源處理狀態不正確。")
        source = self.get_source(source_id)
        source["status"], source["stage_message"] = status, str(message)
        self.mark_dirty()

    def select(self, source_id=None, work_id=None, field_id=None):
        if field_id and not work_id:
            raise ValueError("選取欄位時需要作品。")
        if work_id:
            work = self.get_work(work_id)
            source_id = self._source_for_work(work_id)["id"]
            if field_id:
                self.get_field(work_id, field_id)
        if source_id:
            self.get_source(source_id)
        selection = {"source_id": source_id, "work_id": work_id, "field_id": field_id}
        if selection != self.data["selection"]:
            self.data["selection"] = selection
            self.mark_dirty()
        return selection

    @staticmethod
    def _prepare_field(raw):
        field = deepcopy(raw)
        field.setdefault("id", _id("field"))
        field["rect"] = _rect(field["rect"])
        field.setdefault("text", "")
        field.setdefault("kind", "UNKNOWN")
        field.setdefault("owner", None)
        field.setdefault("shared_with", [])
        field.setdefault("review_state", "REVIEWED" if field.get("reviewed") else "UNCHECKED")
        field.setdefault("revisions", [])
        field.setdefault("evidence", {})
        field.setdefault("measurements", {})
        field.setdefault("prediction", {key: deepcopy(field.get(key)) for key in
                      ("rect", "source_rect", "text", "kind", "owner", "evidence", "measurements")})
        if not isinstance(field["prediction"], dict) or field["review_state"] not in REVIEW_STATES:
            raise ValueError("欄位原判讀或核對狀態的格式不正確。")
        field["prediction_sha256"] = _digest(field["prediction"])
        return field

    @staticmethod
    def _annotated_geometry(field, revision_ref):
        rect = deepcopy(field["rect"])
        values = {key + "_mm": {"value": value, "unit": "mm", "status": "ANNOTATED",
                                 "basis": "HUMAN_REGION_CORRECTION", "evidence_refs": [revision_ref]}
                  for key, value in rect.items()}
        values["width_mm"], values["height_mm"] = deepcopy(values["w_mm"]), deepcopy(values["h_mm"])
        values["frame"] = {"rect": rect, "coordinate": "WORK_LOCAL_MM", "status": "ANNOTATED",
                           "basis": "HUMAN_REGION_CORRECTION", "evidence_refs": [revision_ref]}
        field["annotation_measurements"] = values
        field["measurement_geometry_stale"] = True

    def _prepare_analysis_records(self, source, original, version_id):
        """Namespace only colliding IDs; original analysis/evidence stays unchanged."""
        maps = source.setdefault("identity_map", {"works": {}, "fields": {}, "pages": {}})
        for key in ("works", "fields", "pages"):
            maps.setdefault(key, {})
        other_sources = [row for row in self.sources() if row["id"] != source["id"]]
        occupied_works = {w["id"] for row in other_sources for w in row.get("works", [])}
        occupied_pages = {p["id"] for row in other_sources
                          for p in (row.get("analysis") or {}).get("pages", []) if p.get("id")}
        field_owners = {}
        for row in self.sources():
            for work in row.get("works", []):
                for field in work.get("fields", []):
                    field_owners.setdefault(field["id"], set()).add((row["id"], work["id"]))

        def allocate(group, key, raw_id, occupied):
            if key not in maps[group]:
                candidate = raw_id
                if candidate in occupied:
                    candidate = "review-" + group[:-1] + "-" + _digest([source["id"], key])[:24]
                maps[group][key] = candidate
            return maps[group][key]

        pages, page_ids = [], {}
        for index, raw in enumerate(original.get("pages", [])):
            page = deepcopy(raw)
            raw_id = page.get("id") or "page-" + str(page.get("page", index + 1))
            page_id = allocate("pages", raw_id, raw_id, occupied_pages)
            page.update(id=page_id, source_page_id=raw_id, analysis_version_ref=version_id)
            page_ids[raw_id] = page_id
            pages.append(page)
        works, raw_work_ids = [], set()
        for index, raw in enumerate(original.get("works", [])):
            work = deepcopy(raw)
            raw_id = work.get("id") or "inferred-work-" + _digest([work.get("page"), work.get("crop"), index])[:24]
            if raw_id in raw_work_ids:
                raise ValueError("判讀結果含有重複作品識別碼。")
            raw_work_ids.add(raw_id)
            work_id = allocate("works", raw_id, raw_id, occupied_works)
            work.update(id=work_id, source_work_id=raw_id, source_id=source["id"],
                        analysis_version_ref=version_id)
            if work.get("page_id") in page_ids:
                work["source_page_id"] = work["page_id"]
                work["page_id"] = page_ids[work["page_id"]]
            work["crop"] = _rect(work.get("crop", work.get("rect")))
            work.setdefault("name", "作品 " + str(len(works) + 1))
            work.setdefault("review_state", "UNCHECKED")
            work.setdefault("manual_revision", 0)
            fields, field_ids, raw_field_ids = [], {}, set()
            for number, raw_field in enumerate(work.get("fields", [])):
                field = self._prepare_field(raw_field)
                raw_field_id = raw_field.get("id") or "inferred-field-" + _digest([raw_id, number, field["rect"]])[:24]
                if raw_field_id in raw_field_ids:
                    raise ValueError("判讀結果含有重複欄位識別碼。")
                raw_field_ids.add(raw_field_id)
                occupied = {fid for fid, owners in field_owners.items()
                            if owners - {(source["id"], work_id)}}
                key = _canonical([raw_id, raw_field_id]).decode("utf-8")
                field_id = allocate("fields", key, raw_field_id, occupied)
                field.update(id=field_id, source_field_id=raw_field_id,
                             analysis_version_ref=version_id)
                field_ids[raw_field_id] = field_id
                field_owners.setdefault(field_id, set()).add((source["id"], work_id))
                fields.append(field)
            for field in fields:
                for key in ("label_for", "icon_for"):
                    if field.get(key) in field_ids:
                        field[key] = field_ids[field[key]]
            work["fields"] = fields
            for key in ("relations", "geometry_relations"):
                relationships = []
                for raw_relation in work.get(key, []):
                    relation = deepcopy(raw_relation)
                    for endpoint in ("source", "target"):
                        if relation.get(endpoint) in field_ids:
                            relation[endpoint] = field_ids[relation[endpoint]]
                    if "field_ids" in relation:
                        relation["field_ids"] = [field_ids.get(fid, fid) for fid in relation["field_ids"]]
                    if relation.get("id") and (work_id != raw_id or any(a != b for a, b in field_ids.items())):
                        relation["source_relation_id"] = relation["id"]
                        relation["id"] = "review-relation-" + _digest([source["id"], raw_id, relation["id"]])[:24]
                    relationships.append(relation)
                work[key] = relationships
            work.setdefault("issues", [])
            works.append(work)
        return works, pages

    @staticmethod
    def _continuation_problem(source, original):
        active = source.get("analysis") or {}
        old_hash = (active.get("source") or {}).get("hash")
        new_hash = (original.get("source") or {}).get("hash")
        if (not isinstance(old_hash, str) or len(old_hash) != 64
                or any(c not in "0123456789abcdef" for c in old_hash) or old_hash != new_hash):
            return "來源內容雜湊不同或缺少可信雜湊，不能自動合併判讀。"
        if (not active.get("analysis_version") or active.get("analysis_version") != original.get("analysis_version")
                or active.get("schema_version") != original.get("schema_version")):
            return "分析器或資料口徑不同，請保留成獨立版本核對。"
        old_cap, new_cap = active.get("capabilities") or {}, original.get("capabilities") or {}
        if old_cap.get("ocr_requested") != new_cap.get("ocr_requested"):
            return "文字辨識策略不同，請保留成獨立版本核對。"
        old_engine = old_cap.get("inkscape_runtime") or {}
        new_engine = new_cap.get("inkscape_runtime") or {}
        for key in ("version", "executable_sha256", "manifest_sha256"):
            if old_engine.get(key) != new_engine.get(key):
                return "實際轉換引擎的版本或身分不同，不能合併判讀。"
        old_pages = {page.get("page"): page for page in active.get("pages", [])}
        for page in original.get("pages", []):
            prior = old_pages.get(page.get("page"))
            if prior:
                for key in ("width_mm", "height_mm", "calibrated", "image_hash"):
                    if prior.get(key) != page.get(key):
                        return "既有頁面的尺寸或外觀依據不同，不能合併判讀。"
        return None

    @staticmethod
    def _append_unseen(source, works, pages, version_id, *, new_pages_only):
        active = source["analysis"]
        existing_pages = active.setdefault("pages", [])
        old_page_numbers = {p.get("page") for p in existing_pages}
        old_page_ids = {p["id"] for p in existing_pages if p.get("id")}
        old_work_ids = {work["id"] for work in source["works"]}
        new_pages = [page for page in pages if page["id"] not in old_page_ids
                     and (not new_pages_only or page.get("page") not in old_page_numbers)]
        allowed_pages = {page["id"] for page in new_pages}
        if not new_pages_only:
            allowed_pages |= old_page_ids
        additions = [work for work in works if work["id"] not in old_work_ids
                     and work.get("page_id") in allowed_pages]
        if not additions and not new_pages:
            return {"work_ids": [], "page_ids": []}
        existing_pages.extend(deepcopy(new_pages))
        source["works"].extend(deepcopy(additions))
        ref = {"analysis_version_id": version_id, "base_analysis_version_id": active.get("version_id"),
               "source_hash": active["source"]["hash"], "analysis_version": active["analysis_version"],
               "work_ids": [work["id"] for work in additions], "page_ids": [page["id"] for page in new_pages],
               "adoption": "AUTOMATIC_NEW_PAGE_ONLY" if new_pages_only else "EXPLICIT_UNSEEN_WORKS", "time": _now()}
        source.setdefault("continuation_refs", []).append(ref)
        return {"work_ids": ref["work_ids"], "page_ids": ref["page_ids"]}

    def apply_analysis(self, source_id, result):
        original_source = self.get_source(source_id)
        source = deepcopy(original_source)
        original = deepcopy(result)
        _canonical(original)
        version = {"id": _id("analysis"), "created_utc": _now(), "sha256": _digest(original),
                   "result": original}
        works, pages = self._prepare_analysis_records(source, original, version["id"])
        version["candidate_work_ids"] = [work["id"] for work in works]
        source["analysis_versions"].append(version)
        modified = any(work.get("manual_revision", 0) or work.get("review_state") != "UNCHECKED"
                       or any(field.get("revisions") or field.get("review_state") != "UNCHECKED"
                              for field in work.get("fields", [])) for work in source.get("works", []))
        if modified:
            source["pending_analysis_version"] = version["id"]
            source["analysis_update_pending"] = True
            if self._continuation_problem(source, original) is None:
                added = self._append_unseen(source, works, pages, version["id"], new_pages_only=True)
                source["last_continuation"] = dict(analysis_version_id=version["id"], **added)
        else:
            source["works"] = works
            source["analysis"] = {key: deepcopy(value) for key, value in original.items() if key != "works"}
            source["analysis"]["version_id"] = version["id"]
            source["analysis"]["pages"] = pages
            source.pop("pending_analysis_version", None)
            source["analysis_update_pending"] = False
        source["status"] = original.get("status", "ANALYSED")
        if source["status"] not in SOURCE_STATES:
            raise ValueError("判讀結果的狀態不正確。")
        source["issues"] = deepcopy(original.get("issues", []))
        source["stage_message"] = ("新判讀版本已保留，人工修正維持原樣" if modified else "判讀完成，等待核對")
        candidate = dict(self.data, sources=[source if row["id"] == source_id else row
                                            for row in self.sources()])
        _validate(candidate)
        self.data["sources"] = candidate["sources"]
        if not modified:
            self._undo = [entry for entry in self._undo if entry["source_id"] != source_id]
            selection = self.data["selection"]
            if selection.get("source_id") == source_id:
                active = next((work for work in works if work["id"] == selection.get("work_id")), None)
                if active is None:
                    selection["work_id"] = selection["field_id"] = None
                elif not any(field["id"] == selection.get("field_id") for field in active["fields"]):
                    selection["field_id"] = None
        self._record("ANALYSIS_ADDED", source_id=source_id, analysis_id=version["id"],
                     active_records_preserved=modified)
        return source

    def adopt_new_unseen_works(self, source_id, analysis_version_id):
        """Explicitly append new IDs from a verified compatible version, never replace."""
        source = deepcopy(self.get_source(source_id))
        version = next((v for v in source.get("analysis_versions", []) if v["id"] == analysis_version_id), None)
        if version is None:
            raise KeyError("找不到指定判讀版本。")
        if _digest(version["result"]) != version["sha256"]:
            raise ValueError("判讀版本完整性無法驗證。")
        problem = self._continuation_problem(source, version["result"])
        if problem:
            raise ValueError(problem)
        works, pages = self._prepare_analysis_records(source, version["result"], version["id"])
        before = {key: deepcopy(source.get(key)) for key in ("works", "analysis", "continuation_refs", "stage_message")}
        absent = [key for key in before if key not in source]
        additions = self._append_unseen(source, works, pages, version["id"], new_pages_only=False)
        if not additions["work_ids"] and not additions["page_ids"]:
            return additions
        candidate = dict(self.data, sources=[source if row["id"] == source_id else row for row in self.sources()])
        _validate(candidate)
        self._undo.append({"scope": "continuation", "source_id": source_id, "before": before, "absent": absent})
        self._undo = self._undo[-100:]
        self.data["sources"] = candidate["sources"]
        self._record("UNSEEN_WORKS_ADOPTED", source_id=source_id, analysis_version_id=analysis_version_id, **additions)
        return additions

    def add_owner(self, label, kind="PERSON"):
        if kind not in {"PERSON", "COMPANY"} or not str(label).strip():
            raise ValueError("請填寫人物或公司名稱。")
        owner = {"id": _id("owner"), "label": str(label).strip(), "kind": kind}
        self.data["owners"].append(owner)
        self._record("OWNER_ADDED", owner_id=owner["id"])
        return owner

    def update_field(self, work_id, field_id, changes=None, **keywords):
        changes = {**(changes or {}), **keywords}
        allowed = {"text", "kind", "owner", "shared_with", "review_state", "rect", "role",
                   "annotation_type", "notes", "label_for", "icon_for"}
        if set(changes) - allowed:
            raise ValueError("這個操作只能修改判讀記錄，不能改寫原判讀或來源依據。")
        if "rect" in changes:
            changes["rect"] = _rect(changes["rect"])
        if "review_state" in changes and changes["review_state"] not in REVIEW_STATES:
            raise ValueError("核對狀態不正確。")
        if "text" in changes and not isinstance(changes["text"], str):
            raise ValueError("文字內容需為字串。")
        if "shared_with" in changes and (not isinstance(changes["shared_with"], list)
                                         or not all(isinstance(v, str) for v in changes["shared_with"])):
            raise ValueError("共享對象需要穩定識別碼清單。")
        owner_ids = {owner["id"] for owner in self.data["owners"]}
        if "owner" in changes and changes["owner"] is not None and changes["owner"] not in owner_ids:
            raise ValueError("請從已建立的人物或公司中指定歸屬。")
        if any(value not in owner_ids for value in changes.get("shared_with", [])):
            raise ValueError("共享對象尚未建立。")
        work = self.get_work(work_id)
        field = self.get_field(work_id, field_id)
        before = {key: deepcopy(field.get(key)) for key in changes}
        if before == changes:
            return field
        _canonical(changes)
        self._remember(self._source_for_work(work_id), work)
        record = self._record("FIELD_UPDATED", work_id=work_id, field_id=field_id,
                              before=before, after=changes)
        field.update(deepcopy(changes))
        if "rect" in changes:
            crop = work["crop"]
            field["current_source_rect"] = dict(field["rect"], x=crop["x"] + field["rect"]["x"],
                                                y=crop["y"] + field["rect"]["y"])
            field["geometry_status"] = "MANUALLY_ANNOTATED_SOURCE_MEASUREMENTS_PRESERVED"
            self._annotated_geometry(field, record["id"])
        field["reviewed"] = field["review_state"] == "REVIEWED"
        field["revisions"].append(record)
        work["manual_revision"] += 1
        work["review_state"] = "UNCHECKED"
        return field

    def add_annotation(self, work_id, kind, rect, text="", **properties):
        work = self.get_work(work_id)
        if set(properties) - {"owner", "shared_with", "review_state", "role", "notes", "annotation_type"}:
            raise ValueError("新增標記不能改寫原判讀或識別碼。")
        field = self._prepare_field({"id": _id("field"), "rect": _rect(rect), "text": str(text),
                                     "kind": str(kind), "prediction": {},
                                     "evidence": {"status": "ANNOTATED", "basis": "MANUAL_REGION"},
                                     **properties})
        owner_ids = {owner["id"] for owner in self.data["owners"]}
        if (field["owner"] is not None and field["owner"] not in owner_ids
                or any(key not in owner_ids for key in field["shared_with"])):
            raise ValueError("請先建立標記的人物、公司或共享對象。")
        self._remember(self._source_for_work(work_id), work)
        record = self._record("ANNOTATION_ADDED", work_id=work_id, field_id=field["id"])
        field["revisions"].append(record)
        self._annotated_geometry(field, record["id"])
        work["fields"].append(field)
        work["manual_revision"] += 1
        work["review_state"] = "UNCHECKED"
        return field

    def resize_annotation(self, work_id, field_id, rect):
        return self.update_field(work_id, field_id, rect=rect)

    def annotate_font(self, work_id, field_id, record):
        """Record human visual choice without upgrading source typography evidence.

        A family-only choice is useful annotation, not verified file identity.
        With a local file, verify its actual bytes and collection face first.
        Original measurements, evidence and prediction are never changed here.
        """
        work = self.get_work(work_id)
        field = self.get_field(work_id, field_id)
        if not isinstance(record, dict):
            raise ValueError("字型核對需要候選記錄。")
        family = record.get("family")
        style = record.get("style", "")
        if not isinstance(family, str) or not family.strip() or not isinstance(style, str):
            raise ValueError("請選擇要記錄的字型名稱。")
        annotation = {"id": _id("font-review"), "family": family.strip(), "style": style,
                      "selected_family": family.strip(), "source": "HUMAN_VISUAL_REVIEW",
                      "reviewed_utc": _now(), "status": "ANNOTATED_FAMILY_ONLY",
                      "font_file_identity": "UNKNOWN", "file_path": None,
                      "file_sha256": None, "face_index": None, "pt_confirmed": False,
                      "horizontal_scale_confirmed": False, "scale_x_confirmed": False,
                      "native_source_font_identity_confirmed": False}
        file_value = record.get("file_path") or record.get("path") or record.get("font_path")
        if file_value:
            from fontTools.ttLib import TTFont, TTLibError
            path = _local(file_value)
            if not path.is_file():
                raise FileNotFoundError("所選本機字型檔已不存在；可重新選擇，或只保留字型名稱候選。")
            if path.stat().st_size > 50_000_000:
                raise ValueError("這個字型檔超出單次核對預算，未改動目前記錄。")
            face = record.get("face_index", record.get("face", 0))
            if type(face) is not int or face < 0:
                raise ValueError("字型字面索引需為非負整數。")
            def file_hash():
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                return digest.hexdigest()
            sha = file_hash()
            expected = (record.get("file_sha256") or record.get("sha256")
                        or record.get("file_hash") or record.get("hash"))
            if expected is not None and expected != sha:
                raise ValueError("字型檔內容已變更，不能沿用原候選的確認。")
            try:
                with path.open("rb") as stream:
                    is_collection = stream.read(4) == b"ttcf"
                if not is_collection and face != 0:
                    raise ValueError("這個字型不是多字面集合，不能指定其他字面。")
                with TTFont(str(path), fontNumber=face, lazy=True) as font:
                    actual_family = font["name"].getBestFamilyName()
                    actual_style = font["name"].getBestSubFamilyName() or ""
                    aliases = {name.toUnicode().strip().casefold() for name in font["name"].names
                               if name.nameID in {1, 16} and name.toUnicode().strip()}
            except (TTLibError, KeyError, IndexError, UnicodeError) as error:
                raise ValueError("字型檔或指定字面無法驗證，未改動目前記錄。") from error
            if not actual_family or file_hash() != sha:
                raise ValueError("字型讀取期間發生變更，請重新核對。")
            annotation.update(status="ANNOTATED", font_file_identity="VERIFIED_LOCAL_FILE_FACE",
                              file_path=str(path), file_sha256=sha, face_index=face,
                              family=actual_family, style=actual_style,
                              selected_family_matches_face=family.strip().casefold() in aliases)
        _canonical(annotation)
        self._remember(self._source_for_work(work_id), work)
        revision = self._record("FONT_ANNOTATED", work_id=work_id, field_id=field_id,
                                before=field.get("human_font_annotation"), after=annotation)
        field["human_font_annotation"] = annotation
        field["revisions"].append(revision)
        work["manual_revision"] += 1
        work["review_state"] = "UNCHECKED"
        return annotation

    def remove_annotation(self, work_id, field_id):
        work = self.get_work(work_id)
        self.get_field(work_id, field_id)
        self._remember(self._source_for_work(work_id), work)
        work["fields"] = [field for field in work["fields"] if field["id"] != field_id]
        removed_relations = [r for r in work["relations"] if field_id in r.get("field_ids", [])]
        work["relations"] = [r for r in work["relations"] if field_id not in r.get("field_ids", [])]
        work["manual_revision"] += 1
        work["review_state"] = "UNCHECKED"
        self._record("ANNOTATION_REMOVED", work_id=work_id, field_id=field_id,
                     removed_relation_ids=[r.get("id") for r in removed_relations])
        if self.data["selection"].get("field_id") == field_id:
            self.data["selection"]["field_id"] = None

    def add_relation(self, work_id, field_ids, kind="group", **properties):
        if set(properties) & {"id", "kind", "field_ids", "source", "target", "status"}:
            raise ValueError("關係識別碼與端點由所選標記決定。")
        if isinstance(field_ids, str) and isinstance(kind, (list, tuple)):
            field_ids, kind = kind, field_ids
        ids = list(dict.fromkeys(field_ids))
        if len(ids) < 2 or not isinstance(kind, str) or not kind:
            raise ValueError("請至少選取兩個欄位並指定關係。")
        work = self.get_work(work_id)
        for field_id in ids:
            self.get_field(work_id, field_id)
        relation = {"id": _id("relation"), "kind": kind, "field_ids": ids,
                    "source": ids[0], "target": ids[1], "status": "ANNOTATED", **deepcopy(properties)}
        _canonical(relation)
        self._remember(self._source_for_work(work_id), work)
        work["relations"].append(relation)
        work["manual_revision"] += 1
        work["review_state"] = "UNCHECKED"
        self._record("RELATION_ADDED", work_id=work_id, relation_id=relation["id"])
        return relation

    def remove_relation(self, work_id, relation_id):
        work = self.get_work(work_id)
        if not any(r["id"] == relation_id for r in work["relations"]):
            raise KeyError("找不到指定關係。")
        self._remember(self._source_for_work(work_id), work)
        work["relations"] = [r for r in work["relations"] if r["id"] != relation_id]
        work["manual_revision"] += 1
        work["review_state"] = "UNCHECKED"
        self._record("RELATION_REMOVED", work_id=work_id, relation_id=relation_id)

    def add_work(self, source_id, page_id, crop, name=None):
        source = self.get_source(source_id)
        pages = (source.get("analysis") or {}).get("pages", [])
        page = next((p for p in pages if p.get("id") == page_id or p.get("page") == page_id), None)
        if page is None:
            raise ValueError("請先選擇已取得預覽的來源頁。")
        self._remember(source)
        work = {"id": _id("work"), "source_id": source_id, "page_id": page.get("id"),
                "page": page.get("page", 1), "image": page.get("image"), "crop": _rect(crop),
                "name": name or "作品 " + str(len(source["works"]) + 1), "fields": [],
                "relations": [], "issues": [], "review_state": "UNCHECKED", "manual_revision": 1,
                "evidence": {"status": "ANNOTATED", "basis": "MANUAL_WORK_REGION"}}
        work["rect"] = dict(work["crop"])
        self._undo[-1].update(action="add_work", work_id=work["id"])
        source["works"].append(work)
        self._record("WORK_ADDED", source_id=source_id, work_id=work["id"])
        return work

    def resize_work(self, work_id, crop):
        crop = _rect(crop)
        source = self._source_for_work(work_id)
        work = self.get_work(work_id)
        self._remember(source, work)
        old = work["crop"]
        dx, dy = old["x"] - crop["x"], old["y"] - crop["y"]
        for field in work["fields"]:
            rect = field["rect"]
            field["rect"] = dict(rect, x=rect["x"] + dx, y=rect["y"] + dy)
            field["current_source_rect"] = dict(field["rect"], x=crop["x"] + field["rect"]["x"],
                                                y=crop["y"] + field["rect"]["y"])
            field["out_of_work"] = (field["rect"]["x"] < 0 or field["rect"]["y"] < 0
                                    or field["rect"]["x"] + rect["w"] > crop["w"]
                                    or field["rect"]["y"] + rect["h"] > crop["h"])
        work["crop"] = crop
        work["rect"] = dict(crop)
        if "width_mm" in work:
            work["width_mm"] = crop["w"]
        if "height_mm" in work:
            work["height_mm"] = crop["h"]
        work["geometry_status"] = "MANUALLY_ANNOTATED_SOURCE_MEASUREMENTS_PRESERVED"
        work["manual_revision"] += 1
        work["review_state"] = "UNCHECKED"
        record = self._record("WORK_RESIZED", work_id=work_id, before=old, after=crop)
        for field in work["fields"]:
            self._annotated_geometry(field, record["id"])
        return work

    def remove_work(self, work_id):
        source = self._source_for_work(work_id)
        self._remember(source)
        self._undo[-1].update(action="remove_work", work_id=work_id,
                              index=next(i for i, w in enumerate(source["works"]) if w["id"] == work_id),
                              removed=deepcopy(self.get_work(work_id)))
        source["works"] = [work for work in source["works"] if work["id"] != work_id]
        self._record("WORK_REMOVED", source_id=source["id"], work_id=work_id)
        if self.data["selection"].get("work_id") == work_id:
            self.data["selection"] = {"source_id": source["id"], "work_id": None, "field_id": None}

    def undo(self):
        if not self._undo:
            return False
        entry = self._undo.pop()
        source = self.get_source(entry["source_id"])
        if entry["scope"] == "continuation":
            for key, value in entry["before"].items():
                if key in entry["absent"]:
                    source.pop(key, None)
                else:
                    source[key] = value
        elif entry["scope"] == "works":
            if entry.get("action") == "add_work":
                source["works"] = [work for work in source["works"] if work["id"] != entry["work_id"]]
            elif entry.get("action") == "remove_work":
                if not any(w["id"] == entry["work_id"] for w in source["works"]):
                    source["works"].insert(min(entry["index"], len(source["works"])), entry["removed"])
            else:
                source["works"] = entry["before"]
        else:
            source["works"] = [entry["before"] if work["id"] == entry["work_id"] else work
                               for work in source["works"]]
        self._record("UNDO", work_id=entry.get("work_id"), source_id=source["id"])
        selection = self.data["selection"]
        if selection.get("work_id"):
            try:
                work = self.get_work(selection["work_id"])
                if not any(f["id"] == selection.get("field_id") for f in work["fields"]):
                    selection["field_id"] = None
            except KeyError:
                selection["work_id"] = selection["field_id"] = None
        return True

    def complete_work(self, work_id):
        work = self.get_work(work_id)
        counts = {state: sum(f["review_state"] == state for f in work["fields"])
                  for state in REVIEW_STATES}
        # An empty candidate still needs an explicit human decision; never call zero fields complete.
        incomplete = counts["UNCHECKED"] or not work["fields"]
        status = ("INCOMPLETE" if incomplete else
                  "REVIEWED_WITH_UNKNOWNS" if counts["UNKNOWN"] else "REVIEWED")
        if status != "INCOMPLETE":
            self._remember(self._source_for_work(work_id), work)
            work["review_state"] = status
            self._record("WORK_REVIEW_COMPLETED", work_id=work_id, status=status)
        return {"status": status, "unchecked": counts["UNCHECKED"], "unknown": counts["UNKNOWN"],
                "reviewed": counts["REVIEWED"], "total": len(work["fields"]),
                "training_admission": "NOT_GRANTED_BY_REVIEW"}

    def save(self):
        _validate(self.data)
        saved_utc = _now()
        payload = deepcopy(self.data)
        revision = payload["revision"]
        envelope = {"format": FORMAT, "schema_version": SCHEMA_VERSION, "saved_utc": saved_utc,
                    "sha256": _digest(payload), "payload": payload}
        raw = json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ValueError("核對資料超出本版保存預算；修改仍保留，請先處理資料量。")
        if self.path.is_file():
            try:
                _read_verified(self.path)
            except (ValueError, OSError, KeyError, TypeError, UnicodeError):
                pass  # Never replace a good backup with a damaged main snapshot.
            else:
                _atomic_write(self.backup_path, self.path.read_bytes())
        _atomic_write(self.path, raw)
        self.saved_utc = saved_utc
        self.dirty = self.data["revision"] != revision
        return {"saved_utc": saved_utc, "revision": revision, "path": str(self.path)}

    def observation_package(self):
        _validate(self.data)
        return {"format": "template-ai-private-observations", "schema_version": SCHEMA_VERSION,
                "created_utc": _now(), "qualification": "OBSERVATION_AND_MANUAL_REVIEW_ONLY",
                "training_admission": "NOT_GRANTED_BY_REVIEW", "private_data_included": True,
                "payload": deepcopy(self.data), "payload_sha256": _digest(self.data)}

    def export_observation_package(self, path):
        target = _local(path)
        package = self.observation_package()
        _atomic_write(target, json.dumps(package, ensure_ascii=False, indent=2,
                                        allow_nan=False).encode("utf-8"))
        return target

    def safe_report(self):
        """No names, paths, text, raw errors, font identities, IDs, or source hashes."""
        states = {}
        ocr_identities, ocr_errors = {}, {}
        safe_errors = {'BUNDLED_OCR_RUNTIME_INVALID', 'BUNDLED_OCR_LANGUAGES_INVALID',
                       'OCR_EXECUTION_UNAVAILABLE', 'OCR_LANGUAGES_UNAVAILABLE',
                       'LOCAL_OCR_UNAVAILABLE', 'OCR_RUNTIME_UNAVAILABLE', 'OCR_FAILED',
                       'OCR_MODEL_STAGE_UNAVAILABLE', 'OCR_MODEL_INITIALIZATION_FAILED',
                       'OCR_IMAGE_INPUT_FAILED', 'OCR_PROCESS_FAILED'}
        for source in self.sources():
            key = source.get("status")
            key = key if key in SOURCE_STATES else "OTHER"
            states[key] = states.get(key, 0) + 1
            versions = source.get('analysis_versions') or []
            latest = versions[-1].get('result') if versions else source.get('analysis')
            capabilities = latest.get('capabilities', {}) if isinstance(latest, dict) else {}
            runtime = capabilities.get('ocr_runtime', {}) if isinstance(capabilities, dict) else {}
            safe = {}
            if isinstance(runtime, dict) and runtime:
                for name, allowed in {'state': {'READY', 'UNAVAILABLE'},
                                      'origin': {'BUNDLED', 'ENV_LOCAL', 'SYSTEM_PATH', 'UNKNOWN'},
                                      'policy': {'BUNDLED_ONLY', 'SOURCE_LOCAL'},
                                      'error_code': safe_errors}.items():
                    if isinstance(runtime.get(name), str) and runtime[name] in allowed:
                        safe[name] = runtime[name]
                version = runtime.get('version')
                if isinstance(version, str) and re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{1,12}){1,4}', version):
                    safe['version'] = version
                for name in ('executable_sha256', 'runtime_manifest_sha256'):
                    value = runtime.get(name)
                    if isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value):
                        safe[name] = value
                count = runtime.get('verified_files')
                if type(count) is int and 0 < count <= 4096:
                    safe['verified_files'] = count
                if safe:
                    identity = _canonical(safe).decode('utf-8')
                    row = ocr_identities.setdefault(identity, dict(safe, source_count=0))
                    row['source_count'] += 1
            source_errors = {safe['error_code']} if safe.get('error_code') else set()
            for issue in source.get('issues', []):
                if isinstance(issue, dict):
                    code = (issue.get('detail') if issue.get('code') in ('OCR_UNAVAILABLE', 'OCR_FAILED')
                            and isinstance(issue.get('detail'), str)
                            and issue['detail'] in safe_errors else issue.get('code'))
                    if isinstance(code, str) and code in safe_errors:
                        source_errors.add(code)
            for code in source_errors:
                ocr_errors[code] = ocr_errors.get(code, 0) + 1
        works = self.works()
        fields = [field for work in works for field in work.get("fields", [])]
        return {"schema_version": 1, "tool": "TemplateAIReview", "session_schema": SCHEMA_VERSION,
                "privacy": "SAFE_ALLOWLIST_NO_CONTENT_NO_PATHS_NO_ATTACHMENTS",
                "source_count": len(self.sources()), "work_count": len(works), "field_count": len(fields),
                "source_status_counts": states,
                "field_review_counts": {state: sum(f.get("review_state") == state for f in fields)
                                        for state in sorted(REVIEW_STATES)},
                "has_unsaved_changes": self.dirty, "backup_recovered": self.recovery_notice is not None,
                "interrupted_source_count": len(self.interrupted_sources),
                "ocr_runtime_summaries": [ocr_identities[key] for key in sorted(ocr_identities)],
                "ocr_error_counts": ocr_errors,
                "ocr_summary": ("文字辨識配套需要處理；原稿及人工標記仍可使用。請保留本機資料，將這份報告交給維護者。"
                                if ocr_errors or any(row.get('state') == 'UNAVAILABLE' for row in ocr_identities.values())
                                else "已記錄文字辨識配套資訊；判讀結果仍需人工核對。"
                                if ocr_identities else "尚無文字辨識配套紀錄；有原始向量文字時不一定需要文字辨識。"),
                "training_admission": "NOT_GRANTED_BY_REVIEW"}
