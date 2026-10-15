"""固定字級下的文字配對和量測；無合法解即回報，不暗縮字級。"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QRawFont

from .model import KINDS, Slot, Template, template_errors

MM_PER_POINT = 25.4 / 72.0


@dataclass
class Placed:
    slot: Slot
    text: str = ""
    scale: float = 1.0
    logo: dict | None = None


@dataclass
class Candidate:
    template: Template
    items: list[Placed]
    issues: list[str]
    score: float = 0.0
    generation: int = 0
    reasons: list[str] = field(default_factory=list)

    diagnostics: list[dict] = field(default_factory=list)
    measurements: list[dict] = field(default_factory=list)
    dependency_stamp: str = ""

    @property
    def valid(self) -> bool:
        return not self.issues


def text_geometry(font_family: str, size_pt: float, text: str, style: str = "", asset: dict | None = None) -> tuple[float, float, list[str]]:
    """用固定 1000 像素 em 度量再換算毫米，避免螢幕 DPI 改變輸出。"""
    issues = []
    if style or asset:
        from .font_catalog import analyze_font
        row={"kind":"ASSET","asset":asset} if asset else {"kind":"QT","families":[font_family],"styles":[style]}
        result=analyze_font(row,text,size_pt,2000,.05,style or None)
        if result.get("measurement_verified") and result.get("family")==font_family:
            return result["width_mm"],result["height_mm"],[]
        return 0,0,result["issues"] or ["指定家族與實際核驗字面不符"]
    if font_family not in QFontDatabase.families():
        return 0, 0, ["指定字型未安裝：" + font_family]
    font = QFont(font_family)
    font.setPixelSize(1000)
    metrics = QFontMetricsF(font)
    raw = QRawFont.fromFont(font)
    if any(not raw.supportsCharacter(ch) for ch in text if not ch.isspace()):
        issues.append("指定字型缺少必要字形，不能默默以替代字型通過")
    if any(ch in text for ch in ("\n", "\r", "\t")):
        issues.append("本版單行欄位不接受換行或 Tab")
    factor = size_pt * MM_PER_POINT / 1000.0
    return metrics.horizontalAdvance(text) * factor, metrics.height() * factor, issues


def layout_dependency(t, logos):
    # A local freshness marker, not a signature or proof of visual equivalence.
    import hashlib, json
    from pathlib import Path
    paths=set()
    def visit(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if isinstance(x,str) and ('path' in k or k in ('svg','png','file')):paths.add(x)
                else:visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(t.to_dict());visit(logos)
    stamps={}
    for path in paths:
        try:
            v=Path(path).stat();stamps[path]=[v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns]
        except (OSError,ValueError):stamps[path]=None
    fonts=[(f,list(QFontDatabase.styles(f))) for f in sorted({s.font for s in t.slots})]
    return hashlib.sha256(json.dumps([stamps,fonts],sort_keys=True).encode()).hexdigest()


def generate(t: Template, people: list[dict], companies: list[dict], logos: dict[str, dict], generation: int = 0) -> Candidate:
    from .diagnostic_schema import issue
    dependency = layout_dependency(t, logos)
    issues = template_errors(t)
    diagnostics = [issue("TEMPLATE_CHECK") for _ in issues]
    measurements = []
    def add(reason, code, slot=None, **parameters):
        issues.append(reason)
        diagnostics.append(issue(code, slot=slot, parameters=parameters))
    from .background import background_errors
    background_issues = background_errors(t.background, t.width_mm, t.height_mm)
    issues.extend(background_issues)
    diagnostics.extend(issue("BACKGROUND_CHECK") for _ in background_issues)
    if t.state != "published":
        add("模板尚未發布", "UNPUBLISHED")
    if len(people) != t.capacity:
        add(f"人物容量需精確匹配：模板 {t.capacity}，輸入 {len(people)}", "CAPACITY", capacity=t.capacity, people=len(people))
    persons = {f"p{i+1}": p for i, p in enumerate(people)}
    company_map = {f"c{i+1}": p for i, p in enumerate(companies)}
    for owner, company in t.company_bindings.items():
        if persons.get(owner, {}).get("company") != company:
            add(owner + "：輸入公司與模板已確認歸屬不符，不能混配人物／Logo", "COMPANY_BINDING")
    items = []
    used = set()
    for s in t.slots:
        label = KINDS[s.kind] + "／" + s.owner
        if s.owner.startswith("c"):
            person_indexes = [p.get("company") for p in people]
            if s.owner not in person_indexes:
                add(label + "：沒有任何人物關聯此公司", "UNBOUND_COMPANY", s)
        if s.kind == "logo":
            asset = logos.get(s.owner)
            company = company_map.get(s.owner, {}).get("name", "")
            if not asset or not asset.get("approved"):
                add(label + "：缺少已核准 Logo，僅供黑底白字占位預覽", "LOGO_MISSING", s)
                asset = None
            elif asset.get("company") != company or abs(asset.get("width_mm", 0) - t.width_mm) > 1e-5 or abs(asset.get("height_mm", 0) - t.height_mm) > 1e-5:
                add(label + "：公司或矩形尺寸不符，不可跨尺寸借用 Logo", "LOGO_MISMATCH", s)
                asset = None
            items.append(Placed(s, company, logo=asset))
            continue
        data = company_map.get(s.owner, {}) if s.kind == "company" else persons.get(s.owner, {})
        key = "name" if s.kind == "company" else s.kind
        values = data.get(key, [])
        values = values if isinstance(values, list) else [values]
        text = str(values[s.index]) if s.index < len(values) else ""
        used.add((s.owner, key, s.index))
        if not text:
            if s.required:
                add(label + "：必要資料尚未提供", "REQUIRED", s)
            items.append(Placed(s))
            continue
        tw, th, font_errors = text_geometry(s.font, s.size_pt, text, s.font_style, s.font_asset)
        for error in font_errors:
            add(label + "：" + error, "FONT_UNVERIFIED", s)
        parameters = dict(size_pt=s.size_pt, width_mm=s.rect.w, height_mm=s.rect.h,
                          text_width_mm=None if font_errors else tw, text_height_mm=None if font_errors else th,
                          required_scale=None if font_errors else min(1.0, s.rect.w / tw) if tw > 0 else 1.0, min_scale=s.min_scale,
                          x=s.rect.x, y=s.rect.y, w=s.rect.w, h=s.rect.h)
        measurements.append(issue("FONT_UNVERIFIED" if font_errors else "MEASURED", "INFO", slot=s, parameters=parameters))
        scale = min(1.0, s.rect.w / tw) if tw > 0 else 1.0
        if scale + 1e-6 < s.min_scale:
            add(label + f"：固定 {s.size_pt:g} pt 下需字寬 {scale:.1%}，低於本模板核准下限 {s.min_scale:.1%}", "WIDTH", s, **parameters)
        if th > s.rect.h + 1e-5:
            add(label + "：固定字級的完整字形高度超出框位", "HEIGHT", s, **parameters)
        items.append(Placed(s, text, max(scale, s.min_scale)))
    # 不允許輸入的聯絡資料無聲消失。
    for owner, data in persons.items():
        for kind, values in data.items():
            if kind not in KINDS or kind in ("logo", "company"):
                continue
            values = values if isinstance(values, list) else [values]
            for index, value in enumerate(values):
                if value and (owner, kind, index) not in used:
                    add(f"{owner}／{KINDS[kind]} 第 {index+1} 筆沒有可用模板框位", "NO_SLOT", index=index)
        if data.get("company") and data["company"] not in company_map:
            add(owner + "：關聯公司不存在", "UNKNOWN_COMPANY")
        if data.get("company") and owner not in t.company_bindings:
            add(owner + "：模板未提供此人物公司的已確認映射", "COMPANY_BINDING")
    for owner, data in company_map.items():
        if data.get("name") and owner not in t.company_bindings.values():
            add(owner + "：公司資料沒有可用模板映射，不可無聲略去", "UNBOUND_COMPANY")
    if layout_dependency(t, logos) != dependency:
        add("依賴檔案在排版期間異動，需重新產生", "DEPENDENCY_CHANGED")
    score = sum(item.scale for item in items if item.text) / max(1, sum(bool(item.text) for item in items))
    return Candidate(t, items, list(dict.fromkeys(issues)), score, generation,
                     ["精確匹配矩形尺寸與人物容量", "固定字級，僅在本模板允許的字寬範圍適配", "排名比較字寬保持程度；不宣稱審美模型或全域最優"], diagnostics, measurements, dependency)


def match(templates: list[Template], width: float, height: float, people: list[dict], companies: list[dict], logos: dict[str, dict], generation: int = 0) -> list[Candidate]:
    candidates = [generate(t, people, companies, logos, generation) for t in templates if abs(t.width_mm - width) < 1e-5 and abs(t.height_mm - height) < 1e-5 and t.capacity == len(people)]
    return sorted(candidates, key=lambda c: (not c.valid, -c.score, c.template.name))
