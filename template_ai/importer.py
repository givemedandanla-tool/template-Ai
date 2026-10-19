"""只讀匯入：Inkscape 轉換在背景執行；原檔雜湊与來源各自保存。"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QImageReader, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtSvg import QSvgRenderer
from .background import file_digest

IMPORT_VERSION = "visual-import-0.2.0-dual-recovery"
MAX_PIXELS = 12_000_000


def metadata_checksum(payload: dict) -> str:
    values = {key: value for key, value in payload.items() if key != "metadata_sha256"}
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def cache_matches(payload: dict, folder: Path, source_hash: str, page: int) -> bool:
    """只重用完整同來源／同頁快取；JSON 和檔案不可信時重建，不把存在當完成。"""
    try:
        if not isinstance(payload, dict) or payload.get("cache_version") != IMPORT_VERSION:
            return False
        if payload.get("hash") != source_hash or payload.get("page") != page or payload.get("metadata_sha256") != metadata_checksum(payload):
            return False
        if type(payload["page_count"]) is not int or not page <= payload["page_count"]:
            return False
        preview_height(payload["width_mm"], payload["height_mm"])
        names = {"image": "preview.png"}
        if payload.get("svg"):
            names["svg"] = "source.svg"
        if payload.get("semantic_svg"):
            names["semantic_svg"] = "semantic.svg"
        hashes = payload["file_hashes"]
        if set(hashes) != set(names):
            return False
        for key, name in names.items():
            path = Path(payload[key])
            if path.resolve() != (folder / name).resolve() or path.is_symlink() or not path.is_file() or file_digest(path) != hashes[key]:
                return False
        return True
    except (KeyError, TypeError, ValueError, OSError, OverflowError):
        return False


def preview_height(width: float, height: float, width_px: int = 1600) -> int:
    """先看幾何預算再建立畫面，防止極端長圖在轉換前耗盡低配記憶體。"""
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError("來源畫布尺寸不合法")
    pixels = width_px * height / width
    if not math.isfinite(pixels) or pixels > MAX_PIXELS / width_px:
        raise ValueError("來源比例超出本版預覽像素預算")
    return max(1, round(pixels))


def inkscape_path() -> str | None:
    configured = os.environ.get("TEMPLATE_AI_INKSCAPE", "")
    options = [configured, shutil.which("inkscape") or "", r"C:\Program Files\Inkscape\bin\inkscape.exe", r"C:\Program Files\Inkscape\inkscape.exe"]
    return next((p for p in options if p and Path(p).is_file()), None)


def _run(executable: str, arguments: list[str], directory: Path) -> str:
    env = os.environ.copy()
    env["INKSCAPE_PROFILE_DIR"] = str(directory / "inkscape-profile")
    result = subprocess.run([executable, *arguments], cwd=directory, env=env, capture_output=True, text=True,
                            errors="replace", timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise ValueError("Inkscape 轉換失敗：" + result.stderr[-1500:])
    return result.stdout


def svg_size(path: Path) -> tuple[float, float]:
    import re
    root = ET.parse(path).getroot()
    units = {"mm": 1, "cm": 10, "in": 25.4, "pt": 25.4 / 72, "px": 25.4 / 96, "": 25.4 / 96}
    def dimension(value: str) -> float:
        m = re.fullmatch(r"\s*([0-9.eE+-]+)\s*(mm|cm|in|pt|px)?\s*", value)
        return float(m[1]) * units[m[2] or ""] if m else 0
    w, h = dimension(root.get("width", "")), dimension(root.get("height", ""))
    if w <= 0 or h <= 0:
        box = [float(x) for x in root.get("viewBox", "").replace(",", " ").split()]
        if len(box) != 4 or box[2] <= 0 or box[3] <= 0:
            raise ValueError("SVG 未提供可用畫布尺寸")
        w, h = box[2] * 25.4 / 96, box[3] * 25.4 / 96
    preview_height(w, h)
    return w, h


def render_svg(path: Path, target: Path, width_px: int = 1600) -> None:
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        raise ValueError("SVG 無法由 Qt 正確讀取")
    bounds = renderer.viewBoxF()
    h = preview_height(bounds.width(), bounds.height(), width_px)
    image = QImage(width_px, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    if not image.save(str(target), "PNG"):
        raise ValueError("來源預覽寫入失敗")


def import_file(path: str | Path, assets: str | Path, page: int = 1) -> dict:
    """已知 PDF 相容 AI 可用 Qt PDF；其他 AI 優先嘗試 Inkscape，失敗不偽造結果。"""
    path, assets = Path(path).resolve(), Path(assets).resolve()
    if type(page) is not int or not 1 <= page <= 999:
        raise ValueError("頁碼必須是 1～999 的整數")
    if not path.is_file() or path.stat().st_size > 200_000_000:
        raise ValueError("檔案不存在或超過本版單檔 200 MB 支援範圍")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        signature = f.read(8)
        digest.update(signature)
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()
    is_pdf = signature.startswith(b"%PDF-")
    page_count = 1
    if is_pdf:
        document = QPdfDocument()
        try:
            if document.load(str(path)) != QPdfDocument.Error.None_:
                raise ValueError("PDF 相容層無法讀取；請先輸出未加密的可信 PDF／SVG")
            page_count = document.pageCount()
            if not 1 <= page <= page_count:
                raise ValueError(f"來源只有 {page_count} 頁，無法匯入第 {page} 頁")
        finally:
            document.close()
    elif page != 1:
        raise ValueError("此非 PDF 來源本版只支援第 1 頁，請另存目標畫板後匯入")
    folder = assets / f"{sha}-p{page}-{IMPORT_VERSION}"
    metadata = folder / "metadata.json"
    if folder.is_symlink() or any((folder / name).is_symlink() for name in ("metadata.json", "preview.png", "source.svg", "semantic.svg")):
        raise ValueError("快取位置含符號連結，無法安全重建；請改用正常本機資產目錄")
    if metadata.exists():
        try:
            cached = json.loads(metadata.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeError):
            cached = None
        if cache_matches(cached, folder, sha, page):
            return {**cached, "reused": True}
    folder.mkdir(parents=True, exist_ok=True)
    image_path, svg_path = folder / "preview.png", folder / "source.svg"
    converter = inkscape_path()
    suffix = path.suffix.lower()
    svg = ""
    calibrated = True
    from .recovery_diagnostics import issue
    from .source_recovery import recover_semantics, compare_images, original_pdf_reference
    recovery = dict(source_kind='RASTER', semantic_status='NO_TEXT', fidelity_status='UNKNOWN',
                    counts={}, issues=[issue('NO_EDITABLE_TEXT')])
    semantic_svg = ''
    converted = conversion_failed = False
    if suffix in (".ai", ".eps", ".svg", ".pdf") and converter:
        try:
            args = [str(path), "--export-text-to-path", "--export-plain-svg", "--export-type=svg", "--export-filename=" + str(svg_path)]
            if is_pdf:
                args.extend([f"--pages={page}", "--pdf-poppler"])
            _run(converter, args, folder)
            if not svg_path.is_file():
                raise ValueError("Inkscape 未建立可用 SVG")
            width, height = svg_size(svg_path)
            _run(converter, [str(svg_path), "--export-type=png", "--export-width=1600", "--export-background=white", "--export-background-opacity=1", "--export-filename=" + str(image_path)], folder)
            converted = True
        except (ValueError, OSError, subprocess.TimeoutExpired):
            if not is_pdf and suffix != '.svg':
                error = ValueError('Inkscape 無法還原此來源；需要 PDF 相容內容或本地可信外觀參考。')
                error.recovery_report = dict(source_kind='OTHER', semantic_status='FAILED', fidelity_status='UNKNOWN', issues=[issue('CONVERSION_FAILED')])
                raise error from None
            conversion_failed = True
            svg_path.unlink(missing_ok=True);image_path.unlink(missing_ok=True)
    if converted:
        svg, engine = str(svg_path), "Inkscape " + IMPORT_VERSION
        semantic_svg, recovery = recover_semantics(path, folder, page, is_pdf, converter, run=_run)
    elif is_pdf:
        document = QPdfDocument()
        if document.load(str(path)) != QPdfDocument.Error.None_ or not 1 <= page <= document.pageCount():
            raise ValueError("PDF 相容內容或頁碼無法讀取")
        page_count = document.pageCount()
        size = document.pagePointSize(page - 1)
        width, height = size.width() * 25.4 / 72, size.height() * 25.4 / 72
        target_size = QSize(1600, preview_height(width, height))
        image = document.render(page - 1, target_size)
        document.close()
        if not image.save(str(image_path), "PNG"):
            raise ValueError("PDF 預覽失敗")
        engine = "Qt PDF／PDF 相容層（點陣訓練參考）"
        semantic_svg, recovery = recover_semantics(path, folder, page, is_pdf, None, run=_run)
        # Original PDF text/glyph extraction is independent of Inkscape.
        recovery['source_kind'] = 'PDF'
    elif suffix == ".svg":
        svg_path.write_bytes(path.read_bytes())
        width, height = svg_size(svg_path)
        render_svg(svg_path, image_path)
        svg, engine = str(svg_path), "Qt SVG（待與可信原稿比對）"
        semantic_svg, recovery = recover_semantics(path, folder, page, False, None, run=_run)
    elif suffix in (".png", ".jpg", ".jpeg"):
        reader = QImageReader(str(path))
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > MAX_PIXELS:
            raise ValueError("圖片無法讀取或超出本版 1200 萬像素預算")
        image = reader.read()
        if image.isNull():
            raise ValueError("圖片解碼失敗：" + reader.errorString())
        # 點陣圖片未標定毫米時，以比例顯示；使用者必須確認作品尺寸。
        width, height = 100.0, 100.0 * image.height() / image.width()
        calibrated = False
        if not image.save(str(image_path), "PNG"):
            raise ValueError("圖片保存失敗")
        engine = "點陣來源；毫米尺寸待使用者標定"
    else:
        raise ValueError("此來源需 Inkscape 或 PDF 相容內容；可改提供 PDF／SVG／PNG／JPG")
    if conversion_failed:
        recovery['issues'].append(issue('CONVERSION_FAILED'))
    image = QImage(str(image_path))
    if image.isNull() or image.width() * image.height() > MAX_PIXELS:
        raise ValueError("轉換未產生可用預覽")
    if is_pdf:
        try:
            reference = original_pdf_reference(path, page, (image.width(), image.height()))
            comparison = compare_images(reference, image)
            recovery['visual_comparison'] = comparison
            recovery['fidelity_status'] = comparison['status']
            if comparison['status'] != 'WITHIN_POLICY':
                recovery['issues'].append(issue('VISUAL_MISMATCH'))
        except (ValueError, OSError):
            recovery['issues'].append(issue('FIDELITY_UNKNOWN'))
    else:
        recovery['issues'].append(issue('FIDELITY_UNKNOWN'))
    payload = {"hash": sha, "image": str(image_path), "svg": svg, "width_mm": width,
               "height_mm": height, "page": page, "page_count": page_count, "engine": engine,
               "calibrated": calibrated, "visual_confirmed": False, "reused": False,
               "semantic_svg": semantic_svg, "recovery": recovery}
    payload["cache_version"] = IMPORT_VERSION
    payload["file_hashes"] = {"image": file_digest(image_path)}
    if svg:
        payload["file_hashes"]["svg"] = file_digest(svg_path)
    if semantic_svg:
        payload["file_hashes"]["semantic_svg"] = file_digest(semantic_svg)
    payload["metadata_sha256"] = metadata_checksum(payload)
    temporary = folder / "metadata.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, metadata)
    return payload
