"""固定背景與可變資料分開保存；核准的是指定內容，不是可隨時變動的路徑。"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET


def file_digest(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_embedded_svg(path: str | Path) -> None:
    """外連圖片可在核准後變動，故向量背景只接受內嵌圖片和文件內部引用。"""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        raise ValueError("固定背景 SVG 不可讀") from e
    for node in root.iter():
        values = list(node.attrib.values())
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1] == "href" and not value.startswith(("#", "data:")):
                raise ValueError("固定背景含外連資源，請在 Inkscape 內嵌圖片後重新匯出")
        if node.text:
            values.append(node.text)
        for value in values:
            if "@import" in value.lower():
                raise ValueError("固定背景含外連樣式，請先整理為自足 SVG")
            for reference in re.findall(r"url\(\s*['\"]?([^)'\"]+)", value, flags=re.IGNORECASE):
                if not reference.strip().startswith(("#", "data:")):
                    raise ValueError("固定背景含外連資源，請在 Inkscape 內嵌後重新匯出")


def make_background(source: dict, width: float, height: float, approved: bool = False) -> dict:
    """只接收獨立的乾淨背景；不自動覆蓋原稿文字，也不假稱已識別全部個資。"""
    sw, sh = source["width_mm"], source["height_mm"]
    if not all(math.isfinite(v) and 0 < v <= 2000 for v in (sw, sh, width, height)):
        raise ValueError("固定背景與模板尺寸必須有效")
    if source.get("calibrated"):
        if abs(sw - width) > 0.05 or abs(sh - height) > 0.05:
            raise ValueError("固定背景必須與模板為同一毫米尺寸，請先在設計工具調整頁面")
    elif abs((sw / sh) / (width / height) - 1) > 0.002:
        raise ValueError("背景圖片比例與模板不符；不會拉伸或自動裁掉圖案")
    asset = {"image": source["image"], "svg": source.get("svg", ""),
             "source_width_mm": sw, "source_height_mm": sh,
             "width_mm": width, "height_mm": height, "source_hash": source["hash"],
             "page": source.get("page", 1), "engine": source.get("engine", ""),
             "render_mode": "vector" if source.get("svg") else "raster",
             "approved": bool(approved), "crop": None,
             "files": {"image": file_digest(source["image"])}}
    if asset["svg"]:
        ensure_embedded_svg(asset["svg"])
        asset["files"]["svg"] = file_digest(asset["svg"])
    return asset


def background_errors(asset: dict | None, width: float, height: float, verify_files: bool = True) -> list[str]:
    if asset is None:
        return []
    if not isinstance(asset, dict):
        return ["固定背景記錄格式不合法，需重新匯入"]
    errors = []
    try:
        if asset.get('restore_revalidation_required'):
            errors.append('固定背景從備份恢復，需在此環境重新檢視／核准，不沿用舊主機渲染品質通過')
        if asset.get("approved") is not True:
            errors.append("固定背景尚未人工核准；需確認沒有舊人物資料及待替換 Logo")
        dimensions = [asset[k] for k in ("width_mm", "height_mm", "source_width_mm", "source_height_mm")]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and 0 < v <= 2000 for v in dimensions):
            raise ValueError()
        if abs(dimensions[0] - width) > 1e-5 or abs(dimensions[1] - height) > 1e-5:
            errors.append("固定背景與模板毫米尺寸不符，不能跨尺寸借用")
        if asset.get("crop") is not None:
            errors.append("本版固定背景需完整同尺寸頁面，不接受未知裁切")
        if asset.get("render_mode") not in ("vector", "raster") or (asset.get("render_mode") == "vector" and not asset.get("svg")):
            errors.append("固定背景呈現方式不合法，需重新匯入")
        files = asset["files"]
        for kind in ("image", "svg") if asset.get("svg") else ("image",):
            expected = files[kind]
            path = Path(asset[kind])
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError()
            if verify_files:
                if not path.is_file():
                    errors.append("固定背景來源失聯：" + kind)
                elif file_digest(path) != expected:
                    errors.append("固定背景內容已變更，需重新匯入與核准：" + kind)
    except (KeyError, TypeError, ValueError, OSError):
        errors.append("固定背景記錄不完整或檔案不可讀，需重新匯入")
    return errors
