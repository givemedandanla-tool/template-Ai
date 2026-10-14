"""同一繪圖核心用於預覽與 PDF／PNG／JPG，字級與毫米不受螢幕 DPI 影響。"""
from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgRenderer

from .layout import Candidate, MM_PER_POINT
from .background import background_errors
from .model import Template


def draw_text(p: QPainter, rect: QRectF, text: str, family: str, pt: float, scale: float, align: str, color: str = "#111827", style: str = "", asset: dict | None = None) -> None:
    font = QFontDatabase.font(family,style,1000) if style else QFont(family)
    font.setPixelSize(1000)
    if style or asset:
        from .font_catalog import analyze_font
        row={"kind":"ASSET","asset":asset} if asset else {"kind":"QT","families":[family],"styles":[style]}
        result=analyze_font(row,text,pt,2000,.05,style or None)
        if not result.get("measurement_verified") or result.get("family")!=family: raise ValueError("渲染字面未核驗："+"；".join(result["issues"] or ["指定家族與實際字面不符"]))
        font=QFontDatabase.font(family,result["style"],1000);font.setPixelSize(1000)
        font.setStyleStrategy(QFont.NoFontMerging); font.setHintingPreference(QFont.PreferNoHinting)
    metrics = QFontMetricsF(font)
    factor = pt * MM_PER_POINT / 1000
    text_w = metrics.horizontalAdvance(text) * factor * scale
    text_h = metrics.height() * factor
    x = rect.x()
    if align == "center":
        x += (rect.width() - text_w) / 2
    elif align == "right":
        x += rect.width() - text_w
    p.save()
    p.setClipRect(rect)
    p.translate(x, rect.y() + (rect.height() - text_h) / 2 + metrics.ascent() * factor)
    p.scale(factor * scale, factor)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(0, 0, text)
    p.restore()


def draw_logo(p: QPainter, target: QRectF, asset: dict) -> None:
    crop = asset.get("crop")
    full_w, full_h = asset["source_width_mm"], asset["source_height_mm"]
    x, y, w, h = (crop[k] for k in ("x", "y", "w", "h")) if crop else (0, 0, full_w, full_h)
    ratio = min(target.width() / w, target.height() / h)
    actual = QRectF(target.x() + (target.width() - w * ratio) / 2, target.y() + (target.height() - h * ratio) / 2, w * ratio, h * ratio)
    p.save()
    p.setClipRect(actual)
    full = QRectF(actual.x() - x * ratio, actual.y() - y * ratio, full_w * ratio, full_h * ratio)
    if asset.get("svg"):
        renderer = QSvgRenderer(asset["svg"])
        if not renderer.isValid():
            p.restore()
            raise ValueError("Logo 向量來源不可讀")
        renderer.render(p, full)
    else:
        image = QImage(asset["image"])
        if image.isNull():
            p.restore()
            raise ValueError("Logo 圖片來源失聯")
        p.drawImage(full, image)
    p.restore()


def paint_background(p: QPainter, t: Template) -> None:
    p.fillRect(QRectF(0, 0, t.width_mm, t.height_mm), Qt.white)
    errors = background_errors(t.background, t.width_mm, t.height_mm)
    if errors:
        raise ValueError("；".join(errors))
    if t.background:
        # 頁面映射一致，背景先畫；不以白色遮罩消除未知原稿資料。
        asset = t.background if t.background["render_mode"] == "vector" else {**t.background, "svg": ""}
        draw_logo(p, QRectF(0, 0, t.width_mm, t.height_mm), asset)


def render_background(t: Template, dpi: int = 150) -> QImage:
    if not 72 <= dpi <= 600:
        raise ValueError("背景預覽 DPI 超出支援範圍")
    w, h = max(1, round(t.width_mm * dpi / 25.4)), max(1, round(t.height_mm * dpi / 25.4))
    if w * h > 24_000_000:
        raise ValueError("背景預覽超過像素預算")
    image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.white)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(dpi / 25.4, dpi / 25.4)
    try:
        paint_background(p, t)
    finally:
        p.end()
    return image


def paint_candidate(p: QPainter, candidate: Candidate, preview: bool = False) -> None:
    t = candidate.template
    from .fonts import font_asset_errors
    font_issues = font_asset_errors(item.slot for item in candidate.items)
    if font_issues:
        raise ValueError("；".join(font_issues))
    paint_background(p, t)
    for item in candidate.items:
        s = item.slot
        rect = QRectF(s.rect.x, s.rect.y, s.rect.w, s.rect.h)
        if s.kind == "logo":
            if item.logo:
                draw_logo(p, rect, item.logo)
            else:
                p.fillRect(rect, QColor("#111827"))
                p.save()
                p.translate(rect.x(), rect.y())
                p.setPen(Qt.white)
                font = QFont(s.font)
                font.setPixelSize(1000)
                factor = min(rect.width() / max(1, QFontMetricsF(font).horizontalAdvance(item.text or "Logo")), rect.height() / 1500)
                p.scale(factor, factor)
                p.setFont(font)
                p.drawText(QRectF(0, 0, rect.width() / factor, rect.height() / factor), Qt.AlignCenter, item.text or "Logo")
                p.restore()
        elif item.text:
            draw_text(p, rect, item.text, s.font, s.size_pt, item.scale, s.align, s.color, s.font_style, s.font_asset)
    if preview:
        # 附註位於矩形本體外，矩形內的幾何與比例不改動。
        note = QRectF(0, t.height_mm + 2, t.width_mm, 10)
        draw_text(p, note, "PREVIEW / 非正式 / Logo 占位或待驗證", "Noto Sans CJK TC" if "Noto" in t.slots[0].font else t.slots[0].font, 6, 1, "left")


def render_image(candidate: Candidate, dpi: int = 150, preview: bool = False) -> QImage:
    if not 72 <= dpi <= 600:
        raise ValueError("本版數位輸出 DPI 設定支援 72～600，非印刷品質保證")
    w, h = candidate.template.width_mm, candidate.template.height_mm + (14 if preview else 0)
    px_w, px_h = max(1, round(w * dpi / 25.4)), max(1, round(h * dpi / 25.4))
    if px_w * px_h > 24_000_000:
        raise ValueError("輸出超過本版 2400 萬像素預算，請降低 DPI 或分批")
    image = QImage(px_w, px_h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.white)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(dpi / 25.4, dpi / 25.4)
    try:
        paint_candidate(p, candidate, preview)
    finally:
        p.end()
    return image


def export(candidate: Candidate, target: str | Path, dpi: int = 300, preview: bool = False, expected_generation: int | None = None) -> Path:
    """同目錄暫存與排他建立；任何錯誤不留下冒充成功的半成品，也不覆寫既有檔。"""
    target = Path(target)
    from .fonts import font_asset_errors
    font_issues = font_asset_errors(item.slot for item in candidate.items)
    if font_issues:
        raise ValueError("；".join(font_issues))
    errors = background_errors(candidate.template.background, candidate.template.width_mm, candidate.template.height_mm)
    if errors:
        raise ValueError("；".join(errors))
    if expected_generation is not None and candidate.generation != expected_generation:
        raise ValueError("候選版本已過期，請重新排版")
    if not preview and not candidate.valid:
        raise ValueError("正式數位輸出被阻擋：" + "；".join(candidate.issues))
    if preview and "PREVIEW" not in target.stem.upper():
        raise ValueError("非正式預覽檔名必須包含 PREVIEW")
    if not target.parent.is_dir():
        raise ValueError("輸出資料夾不存在")
    if target.exists():
        raise FileExistsError("預設不覆寫既有檔案，請更名")
    extension = target.suffix.lower()
    if extension not in (".pdf", ".png", ".jpg", ".jpeg"):
        raise ValueError("本版只輸出 PDF／PNG／JPG")
    fd, name = tempfile.mkstemp(prefix=".template-ai-", suffix=extension, dir=target.parent)
    os.close(fd)
    temporary = Path(name)
    created = False
    try:
        if extension == ".pdf":
            writer = QPdfWriter(str(temporary))
            writer.setResolution(600)
            height = candidate.template.height_mm + (14 if preview else 0)
            writer.setPageSize(QPageSize(QSizeF(candidate.template.width_mm, height), QPageSize.Millimeter))
            from PySide6.QtCore import QMarginsF
            writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
            writer.setTitle("PREVIEW / 非正式" if preview else "矩形排版數位輸出")
            p = QPainter(writer)
            if not p.isActive():
                raise ValueError("PDF 編碼器無法啟動")
            p.scale(600 / 25.4, 600 / 25.4)
            try:
                paint_candidate(p, candidate, preview)
            finally:
                p.end()
            del writer
        else:
            image = render_image(candidate, dpi, preview)
            if not image.save(str(temporary), "PNG" if extension == ".png" else "JPEG", 95):
                raise ValueError("影像編碼失敗")
        if temporary.stat().st_size == 0:
            raise ValueError("輸出檔案為空")
        # 同目錄完整暫存檔以硬連結排他發布；正式檔名不暴露半寫入內容。
        # Windows NTFS／Linux 支援；不支援的磁碟明確失敗，不退回危險覆寫。
        with temporary.open("r+b") as src:
            os.fsync(src.fileno())
        os.link(temporary, target)
        created = True
        return target
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)
