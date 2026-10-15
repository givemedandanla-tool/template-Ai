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
                if not path.resolve().is_relative_to(root):
                    report["errors"].append({"path": str(path), "reason": "實際位置在指定搜尋範圍之外，未進入"}); continue
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


def discover_source_roots(sources, roots, cancel=None, max_entries=5000, max_bytes=256 * 1024 * 1024):
    """Multiple explicit roots share one budget; overlap is searched once, never chosen as identity."""
    if not isinstance(roots, (list, tuple)) or not 1 <= len(roots) <= 16:
        raise ValueError('請明列1～16個已授權搜尋根目錄')
    if len(sources)>2000 or type(max_entries) is not int or max_entries<1 or type(max_bytes) is not int or max_bytes<1:
        raise ValueError('搜尋來源或資源預算不合法／超過支援範圍')
    valid=[];errors=[]
    for value in roots:
        path=Path(value)
        try:
            if path.is_symlink() or not path.is_dir():raise ValueError('根目錄離線／不是正常資料夾，未搜尋')
            path=path.resolve(strict=True)
            if path not in valid:valid.append(path)
        except (OSError,ValueError) as error:errors.append(dict(path=str(path),reason=str(error)))
    selected=[];overlaps=[]
    for path in sorted(valid,key=lambda p:(len(p.parts),str(p))):
        if any(path.is_relative_to(parent) for parent in selected):overlaps.append(str(path))
        else:selected.append(path)
    result=dict(root='；'.join(str(x) for x in selected),roots=[str(x) for x in selected],overlapping_roots=overlaps,
                status='PARTIAL' if errors else 'COMPLETE',entries=0,bytes_budgeted=0,hashed_files=0,errors=errors,
                rows=[dict(source=s,availability=availability(s),candidates=[],same_name_different=[]) for s in sources],unsearched_roots=[])
    for index,path in enumerate(selected):
        if cancel and cancel.is_set():result['status']='CANCELLED';result['unsearched_roots']=[str(p) for p in selected[index:]];break
        if result['entries']>=max_entries or result['bytes_budgeted']>=max_bytes:
            result['status']='PARTIAL';result['unsearched_roots']=[str(p) for p in selected[index:]];break
        report=discover_sources(sources,path,cancel,max_entries-result['entries'],max_bytes-result['bytes_budgeted'])
        for key in ('entries','bytes_budgeted','hashed_files'):result[key]+=report[key]
        result['errors'].extend(report['errors'])
        for output,row in zip(result['rows'],report['rows']):
            if '不足' in row['availability']:output['availability']=row['availability']
            seen={proof.path for proof in output['candidates']}
            for proof in row['candidates']:
                if proof.path not in seen and len(output['candidates'])<32:output['candidates'].append(proof);seen.add(proof.path)
                elif proof.path not in seen:output['candidate_limit']=True;result['status']='PARTIAL'
            output['same_name_different']=list(dict.fromkeys(output['same_name_different']+row['same_name_different']))
            if row.get('candidate_limit'):output['candidate_limit']=True;result['status']='PARTIAL'
            for proof in row['candidates']:
                if proof.path==str(Path(output['source'].get('current_path',output['source']['original_path'])).resolve()):output['availability']='在場，內容指紋與長度已核驗'
            if str(Path(output['source'].get('current_path',output['source']['original_path'])).resolve()) in row['same_name_different']:output['availability']='目前位置內容已改變，不能沿用舊來源'
        if report['status']=='CANCELLED':result['status']='CANCELLED';result['unsearched_roots']=[str(p) for p in selected[index+1:]];break
        if report['status']=='PARTIAL':result['status']='PARTIAL'
    for row in result['rows']:row['candidates'].sort(key=lambda proof:proof.path)
    return result
