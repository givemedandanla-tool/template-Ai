"""資料模型只使用毫米與穩定識別碼；視窗倍率不會改變真實幾何。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import re
import uuid

KINDS = {"name": "姓名", "title": "職稱", "phone": "電話", "email": "Email",
         "address": "地址", "line": "LINE", "ig": "IG", "company": "獨立公司文字", "logo": "完整 Logo"}


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def valid(self) -> bool:
        return all(math.isfinite(v) for v in (self.x, self.y, self.w, self.h)) and self.w > 0 and self.h > 0

    def inside(self, w: float, h: float) -> bool:
        return self.valid() and self.x >= -1e-6 and self.y >= -1e-6 and self.x + self.w <= w + 1e-6 and self.y + self.h <= h + 1e-6

    def intersects(self, other: Rect) -> bool:
        return min(self.x + self.w, other.x + other.w) - max(self.x, other.x) > 1e-4 and min(self.y + self.h, other.y + other.h) - max(self.y, other.y) > 1e-4


@dataclass
class Slot:
    kind: str
    owner: str
    rect: Rect
    index: int = 0
    font: str = "Noto Sans CJK TC"
    size_pt: float = 10.0
    min_scale: float = 0.85
    align: str = "left"
    required: bool = True
    id: str = field(default_factory=new_id)
    color: str = "#111827"


@dataclass
class Template:
    name: str
    width_mm: float
    height_mm: float
    slots: list[Slot]
    capacity: int = 1
    source_id: str = ""
    artwork: Rect | None = None
    id: str = field(default_factory=new_id)
    family_id: str = field(default_factory=new_id)
    version: int = 1
    state: str = "draft"
    reasons: list[str] = field(default_factory=list)
    company_bindings: dict[str, str] = field(default_factory=dict)
    background: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Template:
        d = dict(data)
        d["slots"] = [Slot(**{**s, "rect": Rect(**s["rect"])}) for s in d["slots"]]
        if d.get("artwork"):
            d["artwork"] = Rect(**d["artwork"])
        return cls(**d)


def template_errors(t: Template) -> list[str]:
    """發布與正式數位輸出使用同一套幾何和語意檢查。"""
    errors = []
    from .background import background_errors
    errors.extend(background_errors(t.background, t.width_mm, t.height_mm, verify_files=False))
    if not all(math.isfinite(v) and 0 < v <= 2000 for v in (t.width_mm, t.height_mm)):
        errors.append("矩形尺寸必須大於 0，且不超過本版 2000 mm 支援範圍")
    if not 1 <= t.capacity <= 20:
        errors.append("本版人物容量支援 1～20 人")
    keys = set()
    if not t.slots:
        errors.append("模板沒有欄位")
    for s in t.slots:
        label = KINDS.get(s.kind, s.kind) + "／" + s.owner
        if s.kind not in KINDS or not s.rect.inside(t.width_mm, t.height_mm):
            errors.append(label + "：欄位類型或矩形邊界不合法")
        prefix = "c" if s.kind in ("company", "logo") else "p"
        try:
            owner_n = int(s.owner[1:])
            if not s.owner.startswith(prefix) or owner_n < 1 or (prefix == "p" and owner_n > t.capacity):
                raise ValueError()
        except ValueError:
            errors.append(label + "：人物／公司歸屬不合法")
        key = (s.owner, s.kind, s.index)
        if key in keys or s.index < 0:
            errors.append(label + "：同一資料欄位重複映射")
        keys.add(key)
        if not 0.05 <= s.min_scale <= 1 or not math.isfinite(s.size_pt) or not 1 <= s.size_pt <= 200:
            errors.append(label + "：定案字級或模板字寬界限不合法")
        if s.align not in ("left", "center", "right"):
            errors.append(label + "：對齊設定不合法")
        if not isinstance(s.color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", s.color):
            errors.append(label + "：文字色彩需為 #RRGGBB")
    for n in range(1, t.capacity + 1):
        if (f"p{n}", "name", 0) not in keys:
            errors.append(f"人物 {n} 缺少姓名欄位")
    companies = {s.owner for s in t.slots if s.kind in ("company", "logo")}
    if companies:
        for n in range(1, t.capacity + 1):
            if t.company_bindings.get(f"p{n}") not in companies:
                errors.append(f"人物 {n} 的模板公司歸屬尚未確認")
        for company in companies:
            if company not in t.company_bindings.values():
                errors.append(company + " 沒有已確認的人物關聯")
    for i, s in enumerate(t.slots):
        for other in t.slots[i + 1:]:
            if s.rect.intersects(other.rect):
                errors.append(f"{KINDS.get(s.kind)}／{s.owner} 與 {KINDS.get(other.kind)}／{other.owner} 重疊")
    return errors


def learn_from_labels(name: str, width: float, height: float, slots: list[Slot], source_id: str, artwork: Rect, bindings: dict[str, str] | None = None) -> Template:
    """從已確認標記內化框位及對齊，建立有來源的規則模板；不假稱神經模型已訓練。"""
    import copy
    capacity = max([int(s.owner[1:]) for s in slots if s.kind == "name" and s.owner.startswith("p")] or [1])
    t = Template(name, width, height, copy.deepcopy(slots), capacity, source_id, artwork)
    t.company_bindings = bindings or {}
    t.reasons = ["框位來自人工確認作品標記", "保留人物／公司歸屬及固定欄位字級",
                 "依實體矩形尺寸分類；不直接跨尺寸套用", "本版學習方法：標記幾何與明確對齊規則內化"]
    errors = template_errors(t)
    if errors:
        raise ValueError("\n".join(errors))
    return t
