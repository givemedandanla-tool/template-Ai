"""Logo 品質／等比幾何共用核心，預覽與正式輸出使用同一份完整資產。

contain 的縮放係數為 min(框寬/原寬, 框高/原高)，不裁切、不重排內文。
留白是量測值，不使用未經驗證的通用百分比判定品質。
"""
import json
import math
from pathlib import Path

from .background import file_digest
from .model import Rect


def geometry(asset, frame):
    if not isinstance(frame, Rect) or not frame.valid():
        raise ValueError('Logo 框位需有效毫米矩形')
    width, height = asset['source_width_mm'], asset['source_height_mm']
    crop = Rect(**asset['crop']) if asset.get('crop') else Rect(0, 0, width, height)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (width, height)) \
            or not crop.inside(width, height):
        raise ValueError('Logo 來源／完整框位不合法')
    scale = min(frame.w / crop.w, frame.h / crop.h)
    if not math.isfinite(scale):
        raise ValueError('Logo 尺度超出可計算範圍')
    actual = Rect(frame.x + (frame.w - crop.w * scale) / 2,
                  frame.y + (frame.h - crop.h * scale) / 2, crop.w * scale, crop.h * scale)
    from dataclasses import asdict
    return dict(frame=asdict(frame), actual=asdict(actual), scale=scale,
                occupied_fraction=(actual.w * actual.h) / (frame.w * frame.h),
                padding_mm=dict(left=actual.x-frame.x, top=actual.y-frame.y,
                                right=frame.x+frame.w-actual.x-actual.w,
                                bottom=frame.y+frame.h-actual.y-actual.h),
                operation='CONTAIN_ENTIRE_MARK', quality='REQUIRES_DIGITAL_OUTPUT_VALIDATION')


def errors(asset, require_approved=True):
    """新管理資產驗證 hash 與核准憑證；既有資產保留原來的相容路徑。"""
    if not asset.get('managed_logo'):
        return []
    result = []
    if require_approved and (not asset.get('approved') or asset.get('status') != 'APPROVED'):
        result.append('Logo 未核准或已撤銷')
    try:
        geometry(asset, Rect(0, 0, 10, 10))
        proofs = asset.get('file_hashes', {})
        if not isinstance(proofs, dict) or not proofs or not ('image' in proofs or 'svg' in proofs):
            raise ValueError('Logo 缺少可核對來源')
        for key, expected in proofs.items():
            path = Path(asset[key])
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 200_000_000 \
                    or file_digest(path) != expected:
                raise ValueError('Logo 來源失聯／變更，不能替代原版通過')
        if require_approved:
            path = Path(asset['approval_file'])
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
                raise ValueError('Logo 核准憑證不可核對')
            record = json.loads(path.read_text())
            if not isinstance(record, dict) or file_digest(path) != asset['approval_sha256'] or record.get('asset_id') != asset['id'] \
                    or record.get('status') != 'APPROVED':
                raise ValueError('Logo 核准版本已變更／撤銷，舊候選需重新驗證')
    except (ValueError, KeyError, TypeError, OSError) as error:
        result.append(str(error))
    return result


def checked_payload(payload):
    """只保留受支持的渲染欄位，不讓外部 metadata 冒充核准／版本資訊。"""
    keys = ('image', 'svg', 'source_width_mm', 'source_height_mm', 'crop', 'source_id', 'source_hash')
    result = {key: payload[key] for key in keys if key in payload}
    result['managed_logo'] = True
    result['file_hashes'] = {}
    for key in ('image', 'svg'):
        if result.get(key):
            path = Path(result[key]).resolve(strict=True)
            if not path.is_file() or path.stat().st_size > 200_000_000:
                raise ValueError('Logo 來源超出單檔預算')
            result[key] = str(path)
            result['file_hashes'][key] = file_digest(path)
    issues = errors(result, require_approved=False)
    if issues:
        raise ValueError('；'.join(issues))
    return result
