"""Local recovery facts and allowlisted, content-free support reports.

Never serialize exception messages, paths, text, font names or source hashes in
the shareable projection. The full local report remains in the source cache.
"""
from collections import Counter
import json
from pathlib import Path

VERSION = 'local-recovery-diagnostics-1'
ISSUES = {
    'CONVERTER_UNAVAILABLE': ('CONVERSION', 'Inkscape 不可用', '安裝或指定本機 Inkscape，或使用 PDF 相容內容。'),
    'CONVERSION_FAILED': ('CONVERSION', '外觀轉換失敗', '檢查本機轉換器；可用時改走原始 PDF／SVG 渲染。'),
    'SEMANTIC_CONVERSION_FAILED': ('TEXT', '可編輯文字轉換失敗', '保留外觀參考；以原始文字或 OCR 加本機字型比對補足。'),
    'NO_EDITABLE_TEXT': ('TEXT', '未取得可編輯文字', '可能已轉外框或為圖片；對選定文字區使用 OCR 與字型比對。'),
    'DERIVATIVE_TEXT_ONLY': ('TEXT', '僅有轉換後文字資訊', '核對外觀與原稿；轉換字型宣告不能直接當原始字型真值。'),
    'VISUAL_MISMATCH': ('FIDELITY', '轉換與獨立渲染有差異', '檢查差異位置、缺字、透明度及尺寸；確認前暫不採作可信訓練資料。'),
    'FIDELITY_UNKNOWN': ('FIDELITY', '缺少獨立外觀參考', '可提供本地可信預覽作比對，或在本體審查確認。'),
    'FONT_AMBIGUOUS': ('FONT', '字型候選無法唯一區分', '換用包含較多辨識字形的區域；保留候選或人工核對。'),
    'FONT_NO_MATCH': ('FONT', '未找到符合條件的字型', '檢查 OCR 文字、欄位裁切、字型庫與幾何搜尋範圍。'),
    'FONT_MISSING_GLYPHS': ('FONT', '候選字面缺字', '補足本機字型或檢查是否為多字型混排，不允許靜默 fallback。'),
    'SEARCH_INCOMPLETE': ('BUDGET', '搜尋未涵蓋全部候選', '繼續下一批或擴大本地預算；本輪結果不宣稱全庫最佳。'),
    'OCR_UNAVAILABLE': ('OCR', 'OCR 引擎或語言模型不可用', '在本機設定 Tesseract 與所需語言模型，或輸入已核對文字。'),
    'OCR_REVIEW_REQUIRED': ('OCR', 'OCR 文字尚未核對', '核對辨識文字；辨識信心不等於字型身份或內容正確。'),
    'UNSUPPORTED_STRUCTURE': ('STRUCTURE', '結構目前不受支援', '保留原始觀察與外觀，依診斷類型補測試及解析能力。'),
}


def issue(code, *, count=1):
    if code not in ISSUES or type(count) is not int or not 1 <= count <= 100000:
        raise ValueError('Unknown recovery issue or invalid count')
    stage, message, remedy = ISSUES[code]
    return dict(code=code, stage=stage, count=count, message=message, remedy=remedy)


def shareable_report(local):
    """Reconstruct values from fixed vocabulary; never copy arbitrary strings."""
    codes = Counter()
    for row in local.get('issues', []):
        if not isinstance(row, dict) or row.get('code') not in ISSUES:
            codes['UNSUPPORTED_STRUCTURE'] += 1
            continue
        count = row.get('count', 1)
        codes[row['code']] += count if type(count) is int and 1 <= count <= 100000 else 1
    result = dict(schema=VERSION, scope='CONTENT_FREE_LOCAL_SUPPORT_REPORT',
                  privacy='NO_SOURCE_TEXT_PATH_FONT_NAMES_IMAGES_HASHES_OR_RAW_LOGS',
                  issues=[issue(code, count=min(count, 100000)) for code, count in sorted(codes.items())])
    # Only fixed software identifiers and bounded numeric counters are public.
    for key, allowed in {
        'source_kind': ('PDF', 'SVG', 'RASTER', 'OTHER'),
        'semantic_status': ('ORIGINAL_TEXT', 'DERIVATIVE_TEXT', 'NO_TEXT', 'FAILED', 'UNKNOWN'),
        'fidelity_status': ('WITHIN_POLICY', 'REVIEW_REQUIRED', 'UNKNOWN'),
        'font_match_status': ('CANDIDATE', 'AMBIGUOUS', 'NO_MATCH', 'INCOMPLETE', 'UNKNOWN'),
    }.items():
        result[key] = local.get(key) if local.get(key) in allowed else 'UNKNOWN'
    counters = local.get('counts', {})
    result['counts'] = {key: counters[key] for key in ('text_nodes', 'path_nodes', 'checked_faces', 'omitted_faces')
                        if type(counters.get(key)) is int and 0 <= counters[key] <= 100000}
    return result


def export_shareable(local, target):
    report = shareable_report(local)
    target = Path(target)
    if target.is_symlink():
        raise ValueError('Diagnostic target cannot be a symlink')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report
