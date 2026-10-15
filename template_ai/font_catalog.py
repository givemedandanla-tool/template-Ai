"""字型來源／引用只讀快照；QRawFont 留在建立它的執行緒，結果只有普通資料。"""
from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
import re
import unicodedata

from PySide6.QtGui import QFont, QFontDatabase, QRawFont, QTextLayout
from .background import file_digest
from .fonts import font_errors

MM_PER_POINT = 25.4 / 72
STATUS_NAMES = {"HEALTHY":"核准複本正常", "MISSING":"複本失聯", "MODIFIED":"複本內容異動", "UNAPPROVED":"未核准",
                "INVALID":"記錄／綁定不完整", "UNREADABLE":"無法讀取／解析", "QT_AVAILABLE":"Qt 可用，來源未核實",
                "REFERENCE_MISSING":"模板字型不可用", "REFERENCE_UNKNOWN":"模板引用未登錄", "NOT_CHECKED":"本輪預算內未核驗"}


def asset_health(asset):
    if not isinstance(asset, dict) or not isinstance(asset.get("hash"), str) or not re.fullmatch(r"[0-9a-f]{64}", asset["hash"]) or not isinstance(asset.get("families"), list) or not asset["families"] or not isinstance(asset.get("path"), str):
        return "INVALID", ["字型資產記錄不完整"]
    if asset.get("approved") is not True: return "UNAPPROVED", ["本機使用未核准"]
    try:
        path = Path(asset["path"])
        if path.is_symlink(): return "INVALID", ["字型複本位置含符號連結"]
        if not path.is_file(): return "MISSING", ["核准複本失聯，系統同名字型不能代替"]
        if path.stat().st_size > 50_000_000: return "UNREADABLE", ["單檔超過50 MB"]
        if file_digest(path) != asset["hash"]: return "MODIFIED", ["複本內容異動，不沿用核准"]
        return "HEALTHY", []
    except OSError: return "UNREADABLE", ["核准複本不可讀"]


def raw_asset(asset):
    status, issues = asset_health(asset)
    if status != "HEALTHY": raise ValueError("；".join(issues))
    raw = QRawFont(asset["path"], 1000, QFont.PreferNoHinting)
    if not raw.isValid() or raw.familyName() not in asset["families"]:
        raise ValueError("字型無法解析或實際字面家族與核准記錄不同")
    # 解析後再讀 bytes hash，不能把讀取期間改版冒稱同一核准身份。
    status, issues = asset_health(asset)
    if status != "HEALTHY": raise ValueError("；".join(issues))
    return raw


def host_candidates(limit=1000):
    families = QFontDatabase.families()
    return [{"family": f, "styles": QFontDatabase.styles(f)} for f in families[:limit]], len(families) > limit


def build_inventory(assets, templates, hosts, hosts_partial=False, max_assets=256, max_bytes=256*1024*1024):
    asset_refs, family_refs = defaultdict(list), defaultdict(list)
    for template in templates:
        for slot in template.slots:
            if slot.kind == "logo": continue
            ref = {"template_id":template.id, "template_name":template.name, "version":template.version, "state":template.state,
                   "slot_id":slot.id, "owner":slot.owner, "kind":slot.kind, "family":slot.font}
            if isinstance(slot.font_asset, dict):
                asset_refs[(str(slot.font_asset.get("hash")), str(slot.font_asset.get("path")))].append(ref)
            else: family_refs[slot.font].append(ref)
    rows, budget = [], 0
    report = {"status":"PARTIAL" if hosts_partial or len(assets)>max_assets else "COMPLETE", "rows":rows,
              "omitted_assets":max(0,len(assets)-max_assets), "notes":[], "bytes_budgeted":0}
    keys = set()
    for asset in assets[:max_assets]:
        if not isinstance(asset, dict): asset = {}
        key = (str(asset.get("hash")), str(asset.get("path"))); keys.add(key)
        families = asset.get("families", [])
        families = [f for f in families if isinstance(f,str)] if isinstance(families,list) else []
        row = {"id":"asset:"+key[0]+":"+key[1], "kind":"ASSET", "families":families,
               "styles":[], "asset":asset, "references":asset_refs.get(key, []), "source":"程式核准複本", "notes":[],
               "identity":"SHA-256 核准身份；不代表原稿字型或嵌入授權"}
        face=asset.get('font_evidence',{}); rights=asset.get('usage_rights',{})
        row['identity']+=f" · 字面{face.get('index','未知')} · 嵌入{face.get('embedding','UNKNOWN')} · 印製授權{'已明確記錄' if rights.get('print_export') else '未核實'}"
        try: length = Path(asset["path"]).stat().st_size
        except (KeyError,OSError,TypeError): length = 0
        if budget+length > max_bytes:
            status, issues = "NOT_CHECKED", ["本輪驗證預算不足，不能當正常"]
            report["status"] = "PARTIAL"
        else:
            budget += min(length, 50_000_000)
            status, issues = asset_health(asset)
            if status == "HEALTHY":
                try:
                    raw = raw_asset(asset)
                    row.update(parsed_family=raw.familyName(), styles=[raw.styleName()], byte_size=length)
                except ValueError as error: status, issues = "UNREADABLE", [str(error)]
        row.update(status=status, notes=issues)
        for ref in row["references"]: ref["binding_valid"] = ref["family"] in families
        rows.append(row)
    unknown_count = 0
    for (digest,path),refs in asset_refs.items():
        if (digest,path) in keys: continue
        if unknown_count >= 2000:
            report["status"] = "PARTIAL"; report["notes"].append("引用超出本輪預算"); break
        unknown_count += 1
        rows.append({"id":"reference:"+digest+":"+path, "kind":"REFERENCE", "families":sorted({r["family"] for r in refs}), "styles":[],
                     "status":"REFERENCE_UNKNOWN", "source":"模板指定複本未登錄", "references":refs,
                     "notes":["引用身份／位置未對應本機字型登錄，需核對；不借用系統同名字型"], "identity":digest+" · "+path})
    host_families = set()
    for host in hosts:
        family = host["family"]; host_families.add(family)
        rows.append({"id":"qt:"+family, "kind":"QT", "families":[family], "styles":host["styles"], "status":"QT_AVAILABLE",
                     "source":"Qt 可用候選", "references":family_refs.get(family, []), "notes":["可用不等於已證實原稿字型或使用授權"], "identity":"未取得字型檔案身份"})
    for family,refs in family_refs.items():
        if family not in host_families:
            if unknown_count >= 2000:
                report["status"] = "PARTIAL"; report["notes"].append("未知家族引用超出本輪預算"); break
            unknown_count += 1
            rows.append({"id":"missing:"+family, "kind":"REFERENCE", "families":[family], "styles":[], "status":"REFERENCE_MISSING",
                         "source":"模板指定家族不可用", "references":refs, "notes":["指定字型無可用 Qt 家族，原稿身份未知"], "identity":"未知"})
    report["bytes_budgeted"] = budget
    return report


def filter_inventory(rows, query="", kind=None, status=None):
    needle = query.casefold().strip()
    return [r for r in rows if (not kind or r["kind"]==kind) and (not status or r["status"]==status)
            and (not needle or needle in " ".join([*r["families"],*r["styles"],r["source"],r["identity"],STATUS_NAMES[r["status"]],
                     *[v["template_name"] for v in r["references"]]]).casefold())]


TABLE_TAGS = ("head","hhea","hmtx","maxp","cmap","name","glyf","loca","CFF ","CFF2","GSUB","GPOS","GDEF","kern","fvar","avar","gvar","HVAR","MVAR","COLR","CPAL","SVG ")


def face_fingerprint(raw):
    import hashlib
    digest = hashlib.sha256()
    for tag in TABLE_TAGS:
        data = bytes(raw.fontTable(tag))
        digest.update(tag.encode()); digest.update(len(data).to_bytes(8,"big")); digest.update(data)
    return digest.hexdigest()


def validate_inputs(text, size_pt, width_mm, min_scale):
    if not isinstance(text,str) or len(text)>4096 or any(unicodedata.category(c) in ("Cc","Cs","Zl","Zp") for c in text):
        raise ValueError("診斷支援最多4096字元的單行文字，不接受控制字元")
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (size_pt,width_mm,min_scale)) or not 1<=size_pt<=200 or not 0<width_mm<=2000 or not .05<=min_scale<=1:
        raise ValueError("字級／框宽／水平比例超出合法範圍")


def analyze_font(row, text, size_pt=10.0, width_mm=80.0, min_scale=0.85, style=None, tracking_mm=0.0):
    validate_inputs(text, size_pt, width_mm, min_scale)
    if type(tracking_mm) not in (int,float) or not math.isfinite(tracking_mm) or not 0<=tracking_mm<=2:raise ValueError("字距需0～2mm")
    result = {"status":"BLOCKED", "issues":[], "size_pt":size_pt, "width_mm":None, "scale":None, "missing":[], "coverage":None, "measurement_verified":False,
              "scope":"所選字面的單行字形與宽度，不代表原稿身份／授權／完整模板合格"}
    if row["kind"] == "ASSET":
        try: raw = raw_asset(row["asset"])
        except ValueError as error: result["issues"]=[str(error)]; return result
        family, actual_style = raw.familyName(), raw.styleName()
        if style and style != actual_style:
            result["issues"]=["指定款式不是此核准複本的已解析字面"]; return result
    elif row["kind"] == "QT":
        family = row["families"][0]
        if family not in QFontDatabase.families():
            result["issues"]=["主機候選已不可用"]; return result
        actual_style = style or (row["styles"][0] if row["styles"] else "")
        font = QFontDatabase.font(family,actual_style,1000); font.setPixelSize(1000); font.setHintingPreference(QFont.PreferNoHinting)
        font.setStyleStrategy(QFont.NoFontMerging)
        raw = QRawFont.fromFont(font)
        if not raw.isValid(): result["issues"]=["主機字面無法解析"]; return result
    else:
        result["issues"]=["引用未證實可用，不能用同名字型算通過"]; return result
    result.update(family=raw.familyName(), style=raw.styleName(), face_fingerprint=face_fingerprint(raw))
    required = sorted({ord(c) for c in text if not c.isspace()})
    if not required:
        result["status"]="NO_TEXT"; result["issues"]=["沒有實際非空白文字，不宣稱覆蓋率100%"]; return result
    missing = []
    for cp in required:
        indexes = raw.glyphIndexesForString(chr(cp))
        if not indexes or any(glyph == 0 for glyph in indexes): missing.append(cp)
    result.update(missing=[f"U+{cp:04X} {chr(cp)}" for cp in missing], coverage=(len(required)-len(missing))/len(required))
    if missing:
        result["issues"]=["所選字面缺少必要字形，不計算替代字型宽度"]; return result
    font = QFontDatabase.font(family,actual_style,1000); font.setPixelSize(1000)
    font.setHintingPreference(QFont.PreferNoHinting); font.setStyleStrategy(QFont.NoFontMerging)
    font.setLetterSpacing(QFont.AbsoluteSpacing,tracking_mm/(size_pt*MM_PER_POINT/1000))
    layout = QTextLayout(text,font)
    layout.beginLayout(); line = layout.createLine()
    if line.isValid(): line.setLineWidth(1e9)
    layout.endLayout()
    runs = layout.glyphRuns()
    if not line.isValid() or line.textLength() != len(text.encode("utf-16-le"))//2 or not runs or any(face_fingerprint(run.rawFont()) != result["face_fingerprint"] for run in runs):
        result["issues"]=["實際排版字面與所選字面未核對一致，拒絕替代／混用量測"]; return result
    width = line.naturalTextWidth()*size_pt*MM_PER_POINT/1000
    height = line.height()*size_pt*MM_PER_POINT/1000
    if not math.isfinite(width) or not width>0:
        result["issues"]=["實際文字寬度無法驗證"]; return result
    from .text_metrics import ink_metrics
    ink=ink_metrics(font,text);fit_width=ink['width']*size_pt*MM_PER_POINT/1000;height=max(height,ink['height']*size_pt*MM_PER_POINT/1000)
    result.update(fit_width_mm=fit_width,advance_width_mm=width,ink_left_mm=ink['left']*size_pt*MM_PER_POINT/1000)
    scale = min(1.0,width_mm/fit_width)
    result.update(width_mm=width, height_mm=height, scale=scale)
    if row["kind"]=="ASSET":
        status,issues=asset_health(row["asset"])
        if status!="HEALTHY": result["issues"]=issues; return result
    result["measurement_verified"] = True
    if scale+1e-12 < min_scale:
        result["issues"]=["固定字級下所需水平縮放低於設定下限，不截字或縮小字級"]; return result
    result["status"]="FEASIBLE_WIDTH"
    return result
