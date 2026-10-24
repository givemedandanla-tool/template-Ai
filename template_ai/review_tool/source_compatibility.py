"""Conservative detection of Illustrator's visible PDF compatibility notice.

This only examines visible page text in supported PDF-backed sources. It does
not decode Illustrator private data, inspect raw payloads for warning strings,
or classify arbitrary Illustrator references as invalid artwork. Unknown and
unrecognised notices remain unknown; the signatures are deliberately narrow.
"""
from __future__ import annotations

from pathlib import Path
import unicodedata


MAX_VISIBLE_CHARACTERS = 16_384
ISSUE_CODE = 'ILLUSTRATOR_PDF_PLACEHOLDER'
SAFE_MESSAGE = ('目前讀到的是 Illustrator 的 PDF 相容性提示頁，還不是作品內容。'
                '請用 Illustrator 開啟原檔，另存一份副本並勾選「建立 PDF 相容檔案」，'
                '再加入副本重新判讀；也可另存可信 PDF／SVG。原檔保持不變。')


class ReviewSourceCompatibilityError(ValueError):
    """A fixed, content-free message that is safe to send across local IPC."""
    code = ISSUE_CODE
    safe_message = SAFE_MESSAGE

    def __init__(self):
        super().__init__(self.safe_message)


def pdf_backed_source(path) -> bool:
    """Only AI/PDF with a real PDF header can trigger this review-only gate."""
    path = Path(path)
    if path.suffix.casefold() not in {'.ai', '.pdf'}:
        return False
    with path.open('rb') as stream:
        return stream.read(5) == b'%PDF-'


def placeholder_language(text: str) -> str | None:
    """Require a product name, missing content, a precise option and remedy.

    Normalisation tolerates line wrapping, punctuation and trademark glyphs,
    never arbitrary fuzzy matches. A title, keyword, or partial instruction
    alone is insufficient. No text is returned in the diagnostic evidence.
    """
    compact = ''.join(c for c in unicodedata.normalize(
        'NFKC', text[:MAX_VISIBLE_CHARACTERS]).casefold() if c.isalnum())
    if 'adobeillustrator' not in compact:
        return None
    if ('savedwithoutpdfcontent' in compact
            and 'createpdfcompatiblefile' in compact
            and any(phrase in compact for phrase in (
                'resavedfromadobeillustrator', 'optionturnedon',
                'illustratornativeformatoptionsdialogbox'))):
        return 'en'
    if (any(phrase in compact for phrase in (
            '未開啟pdf內容', '未啟用pdf內容', '未包含pdf內容', '不含pdf內容', '沒有pdf內容'))
            and '建立pdf相容檔案' in compact
            and any(phrase in compact for phrase in (
                '重新儲存', '再儲存', '另存新檔', '原生格式選項'))):
        return 'zh-Hant'
    if (any(phrase in compact for phrase in (
            '未打开pdf内容', '未启用pdf内容', '未包含pdf内容', '不含pdf内容', '没有pdf内容'))
            and '创建pdf兼容文件' in compact
            and any(phrase in compact for phrase in ('重新保存', '另存为', '本机格式选项'))):
        return 'zh-Hans'
    return None


def visible_pdf_page(path, page: int) -> dict:
    """Read a bounded visible selection; never substitute payload/private text.

    Load failures defer to the existing importer and its established errors.
    This helper must be called only after ``pdf_backed_source`` succeeds.
    """
    from PySide6.QtPdf import QPdfDocument
    document = QPdfDocument()
    try:
        if document.load(str(path)) != QPdfDocument.Error.None_:
            return {'page_count': None, 'language': None}
        count = document.pageCount()
        if not 1 <= page <= count:
            return {'page_count': count, 'language': None}
        text = document.getSelectionAtIndex(page - 1, 0, MAX_VISIBLE_CHARACTERS).text()
        return {'page_count': count, 'language': placeholder_language(text)}
    finally:
        document.close()


def candidate_placeholder_language(candidates) -> str | None:
    """Screen visible original/OCR observations, with bounded concatenation."""
    parts = []
    remaining = MAX_VISIBLE_CHARACTERS
    for candidate in candidates:
        for observation in candidate.get('observations', []):
            if observation.get('object_type') != 'TEXT':
                continue
            value = observation.get('text')
            if not isinstance(value, str):
                continue
            part = value[:remaining]
            parts.append(part)
            remaining -= len(part)
            if remaining <= 0:
                return placeholder_language(' '.join(parts))
    return placeholder_language(' '.join(parts))
