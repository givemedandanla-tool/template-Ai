"""有界、可重現字型候選與唯讀 PNG；所有 Qt 字面均留在呼叫執行緒。"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QTextLayout

from .font_catalog import (MM_PER_POINT, STATUS_NAMES, analyze_font, asset_health,
                           face_fingerprint, validate_inputs)

SCOPE = "單行候選與唯讀預覽；原稿身份／外觀一致／使用授權／完整模板及正式輸出尚未核准"


def _key(row, style):
    return str(row["id"]), style or ""


def _source_priority(row):
    return 0 if row["kind"] == "ASSET" else 1 if row["kind"] == "QT" else 2


def find_candidates(inventory, text, size_pt=10., width_mm=80., min_scale=.85,
                    reference=None, reference_style=None, max_faces=64,
                    max_results=10, max_bytes=64*1024*1024):
    validate_inputs(text, size_pt, width_mm, min_scale)
    if (type(max_faces) is not int or not 1 <= max_faces <= 64 or
        type(max_results) is not int or not 1 <= max_results <= 10 or
        type(max_bytes) is not int or not 0 <= max_bytes <= 64*1024*1024):
        raise ValueError("候選預算超出安全範圍")
    report = {"status":"COMPLETE", "candidates":[], "excluded":[], "checked_faces":0,
              "omitted_faces":0, "hidden_eligible":0, "bytes_budgeted":0,
              "reference_width_mm":None, "reference_issue":"未指定比較字面，原稿字寬未知",
              "reference_label":"使用者選定比較字面，非已證實原稿身份", "scope":SCOPE,
              "input":{"text":text, "size_pt":size_pt, "width_mm":width_mm, "min_scale":min_scale}}
    if not any(not c.isspace() for c in text):
        report.update(status="NO_TEXT", reference_issue="無實際非空白文字，未進行候選量測")
        return report
    if inventory.get("status") != "COMPLETE": report["status"] = "PARTIAL"
    cache, seen_assets = {}, set()

    def measure(row, style):
        key = _key(row, style)
        if key in cache: return cache[key]
        if report["checked_faces"] >= max_faces: return None
        # 預算是檔案大小而非所有 hash I/O；不承諾硬性牆鐘時限。
        if row["kind"] == "ASSET":
            asset_key = (row.get("asset", {}).get("hash"), row.get("asset", {}).get("path"))
            try: length = Path(row["asset"]["path"]).stat().st_size
            except (KeyError, OSError, TypeError): length = 0
            if asset_key not in seen_assets:
                if report["bytes_budgeted"] + length > max_bytes: return None
                report["bytes_budgeted"] += length; seen_assets.add(asset_key)
        report["checked_faces"] += 1
        if row["kind"] == "REFERENCE":
            result = {"status":"BLOCKED", "issues":row.get("notes", []) or ["引用未證實可用"],
                      "width_mm":None, "scale":None, "coverage":None, "missing":[]}
        elif row["status"] not in ("HEALTHY", "QT_AVAILABLE"):
            result = {"status":"BLOCKED", "issues":[STATUS_NAMES.get(row["status"], "未核實")],
                      "width_mm":None, "scale":None, "coverage":None, "missing":[]}
        else:
            result = analyze_font(row, text, size_pt, width_mm, min_scale, style or None)
        cache[key] = result
        return result

    if reference:
        ref_style = reference_style or (reference["styles"][0] if reference["styles"] else "")
        measured = measure(reference, ref_style)
        if measured is None:
            report["status"] = "PARTIAL"; report["reference_issue"] = "比較字面超出本輪預算，字寬未知"
        elif measured.get("measurement_verified") is True and measured.get("width_mm") is not None:
            report["reference_width_mm"] = measured["width_mm"]
            report["reference_issue"] = "僅比較所選字面的實測自然字寬，不代表外觀相同或原稿身份"
        else:
            report["reference_issue"] = "比較字面未通過核驗，字寬未知：" + "；".join(measured["issues"])
    faces = {}
    for row in inventory["rows"]:
        for style in sorted(set(row["styles"] or [""])):
            faces.setdefault(_key(row, style), (row, style))
    ordered = sorted(faces.values(), key=lambda item:(_source_priority(item[0]), *_key(*item)))
    eligible = []
    for row, style in ordered:
        result = measure(row, style)
        if result is None:
            report["omitted_faces"] += 1; report["status"] = "PARTIAL"; continue
        record = {"id":row["id"], "requested_style":style, "row":row, "analysis":result,
                  "source_priority":_source_priority(row), "scope":SCOPE, "input":dict(report["input"])}
        if result["status"] != "FEASIBLE_WIDTH":
            record["reasons"] = result["issues"] + result["missing"]
            report["excluded"].append(record); continue
        ref_width = report["reference_width_mm"]
        difference = result["width_mm"] / ref_width - 1 if ref_width else None
        record.update(width_delta_ratio=difference,
                      reasons=["必要字形全覆蓋；固定字級下水平比例合格",
                               "核准複本內容身份已核對" if row["kind"]=="ASSET" else "Qt可用字面；檔案來源與授權未核實",
                               report["reference_issue"]])
        record["rank_key"] = [record["source_priority"], round(abs(difference), 12) if difference is not None else 0.,
                              round(1-result["scale"], 12), *_key(row, style)]
        eligible.append(record)
    eligible.sort(key=lambda c:tuple(c["rank_key"]))
    for index, record in enumerate(eligible, 1): record["rank"] = index
    report["candidates"] = eligible[:max_results]
    report["hidden_eligible"] = max(0, len(eligible)-max_results)
    report["eligible_count"] = len(eligible)
    report["excluded"].sort(key=lambda c:(c["id"], c["requested_style"]))
    return report


def render_candidate(candidate, inputs):
    """重新核對後繪圖，回傳普通 bytes／dict，不傳 QImage／QRawFont。"""
    if inputs != candidate["input"]:
        raise ValueError("候選的文字／字級／框寬／比例已過期，請重新查詢")
    row, expected = candidate["row"], candidate["analysis"]
    actual = analyze_font(row, inputs["text"], inputs["size_pt"], inputs["width_mm"],
                          inputs["min_scale"], candidate["requested_style"] or None)
    if (actual["status"] != "FEASIBLE_WIDTH" or
        actual.get("face_fingerprint") != expected.get("face_fingerprint") or
        any(not math.isclose(actual[key], expected[key], rel_tol=1e-10, abs_tol=1e-10)
            for key in ("width_mm", "scale", "size_pt"))):
        raise ValueError("候選字型或量測已變更／不可用，請重新查詢候選")
    font = QFontDatabase.font(actual["family"],actual["style"],1000); font.setPixelSize(1000)
    font.setHintingPreference(QFont.PreferNoHinting); font.setStyleStrategy(QFont.NoFontMerging)
    layout = QTextLayout(inputs["text"], font)
    layout.beginLayout(); line = layout.createLine()
    if line.isValid(): line.setLineWidth(1e9)
    layout.endLayout()
    if (not line.isValid() or line.textLength() != len(inputs["text"].encode("utf-16-le"))//2 or
        not layout.glyphRuns() or any(face_fingerprint(r.rawFont()) != actual["face_fingerprint"] for r in layout.glyphRuns()) or
        not math.isclose(line.naturalTextWidth()*inputs["size_pt"]*MM_PER_POINT/1000, actual["width_mm"], rel_tol=1e-10)):
        raise ValueError("預覽字面與已核驗量測不一致，不使用fallback")
    # 限制 raster 大小；整框縮放是觀看倍率，物理 pt 與水平比例不變。
    height_mm = max(actual["height_mm"]+4, 8)
    ppm = min(120/25.4, 1700/inputs["width_mm"], 400/height_mm)
    margin = 12
    image = QImage(math.ceil(inputs["width_mm"]*ppm)+2*margin,
                   math.ceil(height_mm*ppm)+2*margin, QImage.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing); painter.setRenderHint(QPainter.TextAntialiasing)
    try:
        painter.setPen(QColor("#426782"))
        painter.drawRect(QRectF(margin, margin, inputs["width_mm"]*ppm, height_mm*ppm))
        painter.translate(margin, margin+2*ppm)
        em = inputs["size_pt"]*MM_PER_POINT*ppm/1000
        painter.scale(em*actual["scale"], em)
        painter.setPen(QColor("#111111")); layout.draw(painter, QPointF(0, 0))
    finally: painter.end()
    data = QByteArray(); buffer = QBuffer(data); buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer, "PNG"): raise ValueError("唯讀預覽PNG建立失敗")
    buffer.close()
    if row["kind"] == "ASSET" and asset_health(row["asset"])[0] != "HEALTHY":
        raise ValueError("預覽期間字型檔異動，未發布畫面；請重新查詢")
    return {"png":bytes(data), "analysis":actual, "pixels_per_mm":ppm,
            "pixel_width":image.width(), "pixel_height":image.height(), "scope":SCOPE}
