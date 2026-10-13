"""字型複本只留本機；重開時核對內容再載入程式，從不安裝系統字型。"""
from __future__ import annotations

import os
import re
from pathlib import Path
import shutil
import tempfile

from PySide6.QtGui import QFontDatabase

from .background import file_digest


def font_errors(asset: dict | None, family: str) -> list[str]:
    if asset is None:
        return []
    try:
        if not isinstance(asset, dict) or not isinstance(asset.get("families"), list) or not asset["families"]:
            return ["本機字型資產記錄不完整，需重新匯入"]
        if not isinstance(asset.get("hash"), str) or not re.fullmatch(r"[0-9a-f]{64}", asset["hash"]):
            return ["本機字型資產內容識別不合法，需重新匯入"]
        if asset.get("approved") is not True or family not in asset["families"]:
            return ["本機字型資產尚未核准或字型家族不符"]
        path = Path(asset["path"])
        if not path.is_file():
            return ["本機字型資產失聯，需重新匯入"]
        if path.stat().st_size > 50_000_000:
            return ["本機字型資產超出原支援大小，需重新匯入"]
        if file_digest(path) != asset["hash"]:
            return ["本機字型資產內容已變更，不沿用原核准"]
    except (KeyError, TypeError, AttributeError, OSError):
        return ["本機字型資產記錄不完整，需重新匯入"]
    return []


def font_asset_errors(slots) -> list[str]:
    errors = []
    seen = set()
    for slot in slots:
        asset = slot.font_asset
        if asset is None:
            continue
        key = (str(asset.get("hash")), str(asset.get("path")), slot.font) if isinstance(asset, dict) else (id(asset), slot.font)
        if key not in seen:
            seen.add(key)
            errors.extend(slot.font + "：" + error for error in font_errors(asset, slot.font))
    return errors


class FontManager:
    def __init__(self, library):
        self.library = library
        self.loaded = {}
        self.issues = []
        for asset in library.fonts():
            families = asset.get("families", []) if isinstance(asset, dict) else []
            family = families[0] if isinstance(families, list) and families else ""
            errors = font_errors(asset, family)
            if errors:
                self.issues.extend(errors)
                continue
            font_id = QFontDatabase.addApplicationFont(asset["path"])
            if font_id < 0:
                self.issues.append("已保存字型無法載入：" + asset.get("original_name", "未知"))
            else:
                self.loaded[asset["hash"]] = (font_id, asset)

    def asset_for_family(self, family: str) -> dict | None:
        # 失聯也保留引用，讓指定此資產的欄位阻擋，而不是偷偷借用同名系統字型。
        return next((asset for asset in self.library.fonts() if family in asset["families"]), None)

    def import_font(self, path: str | Path, approved: bool = False) -> dict:
        path = Path(path)
        if not approved:
            raise ValueError("請先確認有權將此字型保存於本機並在程式使用")
        if path.suffix.lower() not in (".ttf", ".otf", ".ttc") or not path.is_file() or path.stat().st_size > 50_000_000:
            raise ValueError("字型需為可讀 TTF／OTF／TTC，單檔不超過 50 MB")
        digest = file_digest(path)
        existing = next((asset for asset in self.library.fonts() if asset["hash"] == digest), None)
        if existing:
            errors = font_errors(existing, existing["families"][0])
            if errors:
                raise ValueError("；".join(errors) + "；請恢復原核准的資產複本後再載入")
            if digest not in self.loaded:
                font_id = QFontDatabase.addApplicationFont(existing["path"])
                if font_id < 0:
                    raise ValueError("既有字型無法載入")
                self.loaded[digest] = (font_id, existing)
            return existing
        folder = self.library.assets / "fonts"
        folder.mkdir(exist_ok=True)
        target = folder / (digest + path.suffix.lower())
        fd, temporary_name = tempfile.mkstemp(prefix=".font-", suffix=path.suffix.lower(), dir=folder)
        os.close(fd)
        temporary = Path(temporary_name)
        created = False
        font_id = -1
        try:
            shutil.copyfile(path, temporary)
            if file_digest(temporary) != digest:
                raise ValueError("字型在複製期間變更，未保存")
            if target.exists():
                if file_digest(target) != digest:
                    raise ValueError("字型保存位置有不同內容，未覆寫")
            else:
                os.link(temporary, target)
                created = True
            font_id = QFontDatabase.addApplicationFont(str(target))
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if not families:
                raise ValueError("字型無法由 Qt 解析")
            if any(set(families).intersection(asset["families"]) for asset in self.library.fonts()):
                raise ValueError("同名字型家族已有不同檔案版本；本版不自動替換或混用，請先使用既有資產")
            asset = {"hash": digest, "path": str(target), "families": families,
                     "original_name": path.name, "approved": True}
            self.library.register_font(asset)
            self.loaded[digest] = (font_id, asset)
            return asset
        except BaseException:
            if font_id >= 0:
                QFontDatabase.removeApplicationFont(font_id)
            if created:
                target.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def close(self):
        for font_id, asset in self.loaded.values():
            QFontDatabase.removeApplicationFont(font_id)
        self.loaded.clear()
