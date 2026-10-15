"""Closed report vocabulary. No user strings, object identifiers or file paths cross this boundary."""
import math

MESSAGES = {
    'MISSING_NAME': '必要姓名欄位未提供或缺少映射',
    'UNKNOWN_COMPANY': '公司關聯不存在', 'NO_SLOT': '輸入資料沒有可用框位',
    'MEASURED': '指定字型的固定字級量測；不代表其他驗證通過',
    'FIT_RISK': '已檢查框位有固定字級適配風險；不是全域無解',
    'INVALID_INPUT': '輸入格式未能核對', 'NO_CANDIDATE': '本次沒有已計算候選；不代表全域無解',
    'TEMPLATE_CHECK': '原模板驗證器發現問題，詳情需本機核對',
    'BACKGROUND_CHECK': '原背景驗證器未通過，詳情需本機核對',
    'UNPUBLISHED': '模板尚未發布', 'CAPACITY': '人物容量不符',
    'COMPANY_BINDING': '人物與公司的已確認映射不符或未確認',
    'UNBOUND_COMPANY': '公司資料沒有已確認人物關聯',
    'LOGO_MISSING': '缺少已核准同尺寸Logo，僅可作非正式占位預覽',
    'LOGO_MISMATCH': 'Logo公司或尺寸不符，不能跨尺寸借用',
    'REQUIRED': '必要資料未提供', 'FONT_UNVERIFIED': '指定字型／字形未能驗證，不採用隱性替代',
    'WIDTH': '固定字級所需水平比例低於本模板下限',
    'HEIGHT': '固定字級完整字形高度超出框位',
    'DIMENSIONS': '作品尺寸不合法', 'SOURCE_CROP': '切分框不符合來源界線',
    'OBJECT_BUDGET': '物件數或格式超出支援預算', 'NO_LABELS': '尚無已保存標記',
    'STABLE_ID': '缺少有效物件識別，不能可靠定位', 'SLOT_SCHEMA': '欄位格式無法核對',
    'OWNER_KIND_SCHEMA': '歸屬與種類格式無法核對', 'KIND': '欄位種類未知',
    'BOUNDS': '欄位超出作品邊界', 'OWNER': '人物／公司歸屬不合法',
    'MAPPING_INDEX': '資料映射序號不合法', 'FIELD_PROPERTIES': '欄位屬性不合法',
    'DUPLICATE_ID': '同一識別對應多個物件，禁止任意定位',
    'DUPLICATE_MAPPING': '同一資料重複映射，需人工核對',
    'BINDING_SCHEMA': '公司關聯格式不合法',
    'CONTAINMENT_UNKNOWN': '包含關係可能合法，來源群組未知',
    'OVERLAP_REVIEW': '矩形相交，需核對語意，不自動刪除',
    'VISUAL_PENDING': '尚未人工核對可信原稿，視覺一致未驗證',
    'LOGO_CONTENT_UNKNOWN': 'Logo內容及群組完整性未知',
    'SOURCE_IDENTITY_UNKNOWN': '來源文字與語意對應未驗證',
    'ISSUE_BUDGET': '問題清單達預算，仍有未納入項目',
    'SOURCE_MISSING': '來源失聯，歷史標記不代表來源健康',
    'SOURCE_CHANGED': '來源異動或無法核對，需重新審核',
    'SOURCE_UNREADABLE': '來源無法讀取', 'SOURCE_OK': '指定來源內容與登錄一致',
    'WORKER_FAILED': '背景工作失敗；未檢查項不能當通過',
    'UNCLASSIFIED': '未分類診斷已省略自由文字，請在本機核對',
}
NUMBER_KEYS = {'size_pt', 'width_mm', 'height_mm', 'text_width_mm', 'text_height_mm',
               'required_scale', 'min_scale', 'x', 'y', 'w', 'h', 'index', 'capacity', 'people'}
KINDS = {'name', 'title', 'phone', 'email', 'line', 'ig', 'address', 'company', 'logo', 'unknown'}
SEVERITIES = {'BLOCK', 'REVIEW', 'INFO'}


def safe_parameters(parameters):
    return {k: v for k, v in parameters.items() if k in NUMBER_KEYS and
            (v is None or type(v) in (int, float) and math.isfinite(v) and abs(v) <= 1e9)}


def issue(code, severity='BLOCK', *, slot=None, owner='', kind='unknown', parameters=None):
    """Private typed result emitted beside the original validator's human message."""
    return {'code': code, 'severity': severity, 'slot_ids': [slot.id] if slot else [],
            'owner': slot.owner if slot else owner, 'kind': slot.kind if slot else kind,
            'parameters': safe_parameters(parameters or {}), 'locatable': bool(slot)}


def public_issue(row, target, fields):
    code = row.get('code') if row.get('code') in MESSAGES else 'UNCLASSIFIED'
    return {'code': code, 'severity': row.get('severity') if row.get('severity') in SEVERITIES else 'REVIEW',
            'target': target, 'fields': fields, 'kind': row.get('kind') if row.get('kind') in KINDS else 'unknown',
            'parameters': safe_parameters(row.get('parameters', {})),
            'locatable': bool(row.get('locatable')),
            'action': 'LOCAL_REVIEW_THEN_REVALIDATE'}
