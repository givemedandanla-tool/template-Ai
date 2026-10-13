"""受限單根唯讀搜尋；候選只證明內容，不自動核准來源／客戶身份。"""
from collections import defaultdict
import os
from pathlib import Path
import re

from .source_links import hash_source, ScanCancelled, MAX_SOURCE_BYTES


def availability(source):
    path = Path(source.get("current_path", source["original_path"]))
    try:
        value = path.stat()
        if not path.is_file():
            return "非一般檔案"
        if value.st_size != source.get("byte_size"):
            return "大小異動，內容待重審"
        return "在場，原位置內容未核驗"
    except FileNotFoundError:
        return "失聯"
    except OSError:
        return "不可讀"


def discover_sources(sources, root, cancel=None, max_entries=5000, max_bytes=256 * 1024 * 1024):
    if len(sources) > 2000 or type(max_entries) is not int or max_entries < 1 or type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("搜尋來源或資源預算不合法／超過支援範圍")
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("請選取正常本機資料夾，不使用符號連結根目錄")
    root = root.resolve()
    root_device = root.stat().st_dev
    rows, by_content, by_name = [], defaultdict(list), defaultdict(list)
    for source in sources:
        row = {"source": source, "availability": availability(source), "candidates": [], "same_name_different": []}
        rows.append(row)
        length = source.get("byte_size")
        if type(length) is int and 0 <= length <= MAX_SOURCE_BYTES and re.fullmatch(r"[0-9a-f]{64}", source.get("hash", "")):
            by_content[(source["hash"], length)].append(row)
            by_name[Path(source["original_path"]).name.casefold()].append(row)
        else:
            row["availability"] = "內容指紋資料不足，待審"
    lengths = {key[1] for key in by_content}
    report = {"root": str(root), "status": "COMPLETE", "entries": 0, "bytes_budgeted": 0, "hashed_files": 0, "errors": [], "rows": rows}
    # Depth-first iterators keep directory memory bounded by entries; do not follow links/mounts.
    stack = []
    try:
        stack.append(os.scandir(root))
        while stack:
            if cancel and cancel.is_set():
                report["status"] = "CANCELLED"; break
            try:
                entry = next(stack[-1])
            except StopIteration:
                stack.pop().close(); continue
            if report["entries"] >= max_entries:
                report["status"] = "PARTIAL"; break
            report["entries"] += 1
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    report["errors"].append({"path": str(path), "reason": "符號連結未搜尋"}); continue
                value = entry.stat(follow_symlinks=False)
                if value.st_dev != root_device:
                    report["errors"].append({"path": str(path), "reason": "跨檔案系統未搜尋"}); continue
                if entry.is_dir(follow_symlinks=False):
                    if len(stack) >= 32:
                        report["errors"].append({"path": str(path), "reason": "目錄深度超過 32，請縮小範圍"}); continue
                    stack.append(os.scandir(path)); continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                names = by_name.get(path.name.casefold(), [])
                if value.st_size not in lengths:
                    for row in names: row["same_name_different"].append(str(path))
                    continue
                remaining = max_bytes - report["bytes_budgeted"]
                if value.st_size > remaining:
                    report["status"] = "PARTIAL"; break
                report["bytes_budgeted"] += value.st_size
                if not path.resolve().is_relative_to(root):
                    raise ValueError("來源位置移到指定搜尋範圍之外")
                proof = hash_source(path, cancel, byte_limit=min(MAX_SOURCE_BYTES, remaining))
                report["hashed_files"] += 1
                matching = by_content.get((proof.hash, proof.stat[2]), [])
                for row in matching:
                    if len(row["candidates"]) < 32: row["candidates"].append(proof)
                    else: row["candidate_limit"] = True; report["status"] = "PARTIAL"
                for row in names:
                    if row not in matching: row["same_name_different"].append(str(path))
            except ScanCancelled:
                report["status"] = "CANCELLED"; break
            except (OSError, ValueError) as error:
                report["errors"].append({"path": str(path), "reason": str(error)})
                if isinstance(error, ValueError):
                    # 內容在讀取中增長可能消耗原大小以外預算；停止，不累積未計數讀取。
                    report["status"] = "PARTIAL"; break
    except OSError as error:
        report["errors"].append({"path": str(root), "reason": str(error)})
    finally:
        for iterator in stack: iterator.close()
    if report["status"] == "COMPLETE" and report["errors"]:
        report["status"] = "PARTIAL"
    for row in rows:
        row["candidates"].sort(key=lambda p: p.path)
    return report
