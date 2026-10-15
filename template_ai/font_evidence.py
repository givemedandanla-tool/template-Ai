"""Bounded OpenType evidence through fontTools, separate from legal permission.

OS/2 fsType describes technical embedding restrictions. It is not a licence.
Collection faces are extracted independently so Qt cannot silently pick face 0.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib

from fontTools.ttLib import TTFont, TTCollection, TTLibError

MAX_FONT_BYTES = 50_000_000
MAX_FACES = 64


def _bytes(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_FONT_BYTES:
        raise ValueError("字型需為正常本機檔案，大小1至50 MB")
    data = path.read_bytes()
    if len(data) > MAX_FONT_BYTES:
        raise ValueError("字型讀取期間超出大小預算")
    return data


def _faces(data):
    try:
        if data[:4] == b"ttcf":
            if len(data) < 12 or not 1 <= int.from_bytes(data[8:12], "big") <= MAX_FACES:
                raise ValueError("TTC字面數超出1至64預算")
            collection = TTCollection(BytesIO(data), lazy=True)
            return collection.fonts
        return [TTFont(BytesIO(data), lazy=True)]
    except (TTLibError, OSError, IndexError, AssertionError) as error:
        raise ValueError("無法解析OpenType字型證據") from error


def inspect_font(path):
    data = _bytes(path)
    faces = _faces(data)
    result = []
    try:
        for index, font in enumerate(faces):
            names = font["name"]
            name = lambda *ids: next((names.getDebugName(i) for i in ids if names.getDebugName(i)), None)
            fs_type = int(font["OS/2"].fsType) if "OS/2" in font else None
            result.append(dict(index=index, family=name(16, 1), style=name(17, 2),
                               postscript_name=name(6), unique_name=name(3), version=name(5),
                               fs_type=fs_type, glyph_count=len(font.getBestCmap() or {}),
                               embedding="UNKNOWN" if fs_type is None else "RESTRICTED" if fs_type & 2 else
                               "PREVIEW_PRINT" if fs_type & 4 else "EDITABLE" if fs_type & 8 else "INSTALLABLE",
                               no_subsetting=bool(fs_type & 0x100) if fs_type is not None else None,
                               bitmap_only=bool(fs_type & 0x200) if fs_type is not None else None))
    except (TTLibError, KeyError, ValueError, IndexError, AssertionError) as error:
        raise ValueError("字型名稱／OS2／字形表不完整，不能核實") from error
    finally:
        for font in faces:
            font.close()
    return dict(hash=hashlib.sha256(data).hexdigest(), bytes=len(data), faces=result,
                collection=data[:4] == b"ttcf", licence="NOT_INFERRED_FROM_FSTYPE")


def face_bytes(path, index):
    data = _bytes(path)
    faces = _faces(data)
    try:
        if type(index) is not int or not 0 <= index < len(faces):
            raise ValueError("必須明確選擇存在的字面")
        if data[:4] != b"ttcf":
            return data
        stream = BytesIO()
        faces[index].recalcTimestamp = False
        faces[index].save(stream)
        return stream.getvalue()
    finally:
        for font in faces:
            font.close()


def output_rights_errors(asset, output_format):
    """Imported assets require explicit rights; unknown remains blocked."""
    if asset is None:
        return []  # Host font rights are reported separately by the inventory.
    rights = asset.get("usage_rights", {})
    if not rights.get("print_export") or not rights.get("actor") or not rights.get("basis"):
        return ["匯入字型尚無印製／轉出授權確認，僅允許非正式預覽"]
    if output_format.lower() == "pdf":
        evidence = asset.get("font_evidence", {})
        if not rights.get("pdf_embedding"):
            return ["PDF字型嵌入尚未明確授權"]
        if evidence.get("fs_type") is None or evidence.get("fs_type", 0) & (2 | 0x100 | 0x200):
            return ["字型嵌入未知／限制／禁止子集／僅點陣；目前PDF引擎不能保證遵守，阻擋正式PDF"]
    return []
