"""只讀匯入：Inkscape 轉換在背景執行；原檔雜湊与來源各自保存。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPdf import QPdfDocument
from PySide6.QtSvg import QSvgRenderer

IMPORT_VERSION = "visual-import-0.1"
MAX_PIXELS = 12_000_000


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
    return w, h


def render_svg(path: Path, target: Path, width_px: int = 1600) -> None:
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        raise ValueError("SVG 無法由 Qt 正確讀取")
    bounds = renderer.viewBoxF()
    h = max(1, round(width_px * bounds.height() / bounds.width()))
    if width_px * h > MAX_PIXELS:
        raise ValueError("來源比例超出本版預覽像素預算")
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
    if not path.is_file() or path.stat().st_size > 200_000_000:
        raise ValueError("檔案不存在或超過本版單檔 200 MB 支援範圍")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        signature = f.read(8)
        digest.update(signature)
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()
    folder = assets / f"{sha}-p{page}-{IMPORT_VERSION}"
    metadata = folder / "metadata.json"
    if metadata.exists():
        cached = json.loads(metadata.read_text(encoding="utf-8"))
        if Path(cached["image"]).is_file() and (not cached["svg"] or Path(cached["svg"]).is_file()):
            return {**cached, "reused": True}
    folder.mkdir(parents=True, exist_ok=True)
    image_path, svg_path = folder / "preview.png", folder / "source.svg"
    converter = inkscape_path()
    is_pdf = signature.startswith(b"%PDF-")
    suffix = path.suffix.lower()
    svg = ""
    page_count = 1
    calibrated = True
    if suffix in (".ai", ".eps", ".svg", ".pdf") and converter:
        args = [str(path), "--export-text-to-path", "--export-plain-svg", "--export-type=svg", "--export-filename=" + str(svg_path)]
        if is_pdf:
            args.extend([f"--pages={page}", "--pdf-poppler"])
        _run(converter, args, folder)
        if not svg_path.is_file():
            raise ValueError("Inkscape 未建立可用 SVG，請提供可信 PDF／SVG／圖片參考")
        width, height = svg_size(svg_path)
        _run(converter, [str(svg_path), "--export-type=png", "--export-width=1600", "--export-background=white", "--export-background-opacity=1", "--export-filename=" + str(image_path)], folder)
        svg, engine = str(svg_path), "Inkscape " + IMPORT_VERSION
        if is_pdf:
            document = QPdfDocument()
            if document.load(str(path)) == QPdfDocument.Error.None_:
                page_count = document.pageCount()
            document.close()
    elif is_pdf:
        document = QPdfDocument()
        if document.load(str(path)) != QPdfDocument.Error.None_ or not 1 <= page <= document.pageCount():
            raise ValueError("PDF 相容內容或頁碼無法讀取")
        page_count = document.pageCount()
        size = document.pagePointSize(page - 1)
        width, height = size.width() * 25.4 / 72, size.height() * 25.4 / 72
        target_size = QSize(1600, max(1, round(1600 * height / width)))
        if target_size.width() * target_size.height() > MAX_PIXELS:
            raise ValueError("頁面超出預覽像素預算")
        image = document.render(page - 1, target_size)
        document.close()
        if not image.save(str(image_path), "PNG"):
            raise ValueError("PDF 預覽失敗")
        engine = "Qt PDF／PDF 相容層（點陣訓練參考）"
    elif suffix == ".svg":
        svg_path.write_bytes(path.read_bytes())
        width, height = svg_size(svg_path)
        render_svg(svg_path, image_path)
        svg, engine = str(svg_path), "Qt SVG（待與可信原稿比對）"
    elif suffix in (".png", ".jpg", ".jpeg"):
        image = QImage(str(path))
        if image.isNull() or image.width() * image.height() > MAX_PIXELS:
            raise ValueError("圖片無法讀取或超出本版 1200 萬像素預算")
        # 點陣圖片未標定毫米時，以比例顯示；使用者必須確認作品尺寸。
        width, height = 100.0, 100.0 * image.height() / image.width()
        calibrated = False
        if not image.save(str(image_path), "PNG"):
            raise ValueError("圖片保存失敗")
        engine = "點陣來源；毫米尺寸待使用者標定"
    else:
        raise ValueError("此來源需 Inkscape 或 PDF 相容內容；可改提供 PDF／SVG／PNG／JPG")
    image = QImage(str(image_path))
    if image.isNull() or image.width() * image.height() > MAX_PIXELS:
        raise ValueError("轉換未產生可用預覽")
    payload = {"hash": sha, "image": str(image_path), "svg": svg, "width_mm": width,
               "height_mm": height, "page": page, "page_count": page_count, "engine": engine,
               "calibrated": calibrated, "visual_confirmed": False, "reused": False}
    temporary = folder / "metadata.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, metadata)
    return payload
