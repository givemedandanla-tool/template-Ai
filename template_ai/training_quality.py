"""Bounded marking facts, with geometric uncertainty kept separate from publication PASS."""
from collections import defaultdict
import hashlib
import json
import math
import re
from .model import KINDS, Rect, Slot

MAX_OBJECTS = 200
MAX_ISSUES = 400
SEVERITY = {'BLOCK': 3, 'REVIEW': 2, 'INFO': 1}


def analyse_work(work, source=None):
    payload = work['payload']; issues = []; overflow = False
    def add(code, severity, reason, ids=(), locatable=True):
        nonlocal overflow
        if len(issues) >= MAX_ISSUES:
            overflow = True; return
        ids = sorted(set(ids))
        identity = json.dumps([work['id'], code, ids, reason], ensure_ascii=False, sort_keys=True)
        issues.append({'id': hashlib.sha256(identity.encode()).hexdigest(), 'code': code,
                       'severity': severity, 'reason': reason, 'slot_ids': ids,
                       'work_id': work['id'], 'source_id': work['source_id'],
                       'work_revision': work['revision'], 'work_name': work['name'],
                       'locatable': bool(ids) and locatable,
                       'source_text_identity': 'UNKNOWN', 'native_mapping': 'UNKNOWN'})
    if payload.get('analysis_evidence',{}).get('oversized_text'):
        add('SOURCE_TEXT_BUDGET','BLOCK','來源文字超出2048字觀察資源預算；未截斷。此作品來源內容尚未完整核實，禁止訓練／發布')
    dimensions = (payload.get('work_width'), payload.get('work_height'))
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 2000 for v in dimensions):
        add('DIMENSIONS', 'BLOCK', '作品毫米尺寸不合法，不能推論可學習或可輸出')
        return sorted(issues, key=issue_key)
    width, height = dimensions
    try:
        crop = Rect(**payload['crop'])
        if not crop.valid() or (source and not crop.inside(source['width_mm'], source['height_mm'])):
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        add('SOURCE_CROP', 'BLOCK', '作品切分框與已知來源界線不相容；不可跨作品猜測')
    raw_slots = payload.get('slots')
    if not isinstance(raw_slots, list) or len(raw_slots) > MAX_OBJECTS:
        add('OBJECT_BUDGET', 'BLOCK', '標記需為清單，且單件作品最多200物件')
        return sorted(issues, key=issue_key)
    if not raw_slots:
        add('NO_LABELS', 'BLOCK', '尚無已保存標記；無法建立目前模型的幾何模板')
    slots = []; by_id = defaultdict(list); mappings = defaultdict(list); people = set(); companies = set()
    for index, raw in enumerate(raw_slots):
        sid = raw.get('id', '') if isinstance(raw, dict) else ''
        if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', sid):
            add('STABLE_ID', 'BLOCK', '缺少有效stable ID／不能安全定位', (), False); continue
        by_id[sid].append(raw)
        try:
            slot = Slot(**{**raw, 'rect': Rect(**raw['rect'])})
        except (TypeError, ValueError, KeyError):
            add('SLOT_SCHEMA', 'BLOCK', '欄位schema無法完整解碼', [sid]); continue
        slots.append(slot)
        if not isinstance(slot.kind, str) or not isinstance(slot.owner, str):
            add('OWNER_KIND_SCHEMA', 'BLOCK', '欄位種類／歸屬需為明確文字識別', [sid]); continue
        if slot.kind not in KINDS:
            add('KIND', 'BLOCK', '未知欄位種類；行政註記應走來源觀察與雜訊候選', [sid])
        if not all(type(v) in (int, float) for v in (slot.rect.x, slot.rect.y, slot.rect.w, slot.rect.h)) or not slot.rect.inside(width, height):
            add('BOUNDS', 'BLOCK', '欄位超出作品或框位無效', [sid])
        prefix = 'c' if slot.kind in ('company', 'logo') or (slot.kind in ('phone','email','line','ig','address') and isinstance(slot.owner,str) and slot.owner.startswith('c')) else 'p'
        owner = re.fullmatch(prefix + r'([1-9][0-9]*)', slot.owner) if isinstance(slot.owner, str) else None
        if not owner or (prefix == 'p' and int(owner[1]) > 20):
            add('OWNER', 'BLOCK', '人物／公司歸屬與欄位類型不相容', [sid])
        elif prefix == 'p': people.add(slot.owner)
        else: companies.add(slot.owner)
        if type(slot.index) is not int or slot.index < 0:
            add('MAPPING_INDEX', 'BLOCK', '資料映射序號不合法', [sid])
        else: mappings[(slot.owner, slot.kind, slot.index)].append(sid)
        if (type(slot.size_pt) not in (int, float) or not math.isfinite(slot.size_pt) or not 1 <= slot.size_pt <= 200
                or type(slot.min_scale) not in (int, float) or not 0.05 <= slot.min_scale <= 1
                or slot.align not in ('left', 'center', 'right') or type(slot.required) is not bool or type(slot.locked) is not bool):
            add('FIELD_PROPERTIES', 'BLOCK', '固定字級／縮放／對齊／required／locked屬性不合法', [sid])
    duplicated_ids = {sid for sid, items in by_id.items() if len(items) > 1}
    for sid in sorted(duplicated_ids):
        add('DUPLICATE_ID', 'BLOCK', '同一stable ID指向多個框；不選取任意其中一件', [sid], False)
    for mapping, ids in sorted(mappings.items()):
        if len(ids) > 1:
            add('DUPLICATE_MAPPING', 'BLOCK', '同一人物／公司資料重複映射：' + str(mapping), ids,
                not duplicated_ids.intersection(ids))
    for person in sorted(people):
        if (person, 'name', 0) not in mappings:
            add('MISSING_NAME', 'BLOCK', person + '缺少目前模板模型必需的姓名欄位；不臆造Email／地址需求')
    bindings = payload.get('company_bindings', {})
    if not isinstance(bindings, dict):
        add('BINDING_SCHEMA', 'BLOCK', '公司關聯資料格式不合法'); bindings = {}
    from .model import binding_errors
    for error in binding_errors(bindings, people, companies):
        add('COMPANY_BINDING', 'REVIEW', error)
    ordered = sorted(slots, key=lambda s: (s.id, s.owner, s.kind, s.index if type(s.index) is int else -1))
    for index, a in enumerate(ordered):
        for b in ordered[index + 1:]:
            if not all(type(v) in (int, float) for r in (a.rect, b.rect) for v in (r.x, r.y, r.w, r.h)): continue
            if not a.rect.valid() or not b.rect.valid() or not a.rect.intersects(b.rect): continue
            contains = ((a.rect.x <= b.rect.x and a.rect.y <= b.rect.y and a.rect.x+a.rect.w >= b.rect.x+b.rect.w and a.rect.y+a.rect.h >= b.rect.y+b.rect.h)
                        or (b.rect.x <= a.rect.x and b.rect.y <= a.rect.y and b.rect.x+b.rect.w >= a.rect.x+a.rect.w and b.rect.y+b.rect.h >= a.rect.y+a.rect.h))
            code = 'CONTAINMENT_UNKNOWN' if contains and 'logo' in (a.kind, b.kind) else 'OVERLAP_REVIEW'
            reason = ('包含可能是合法複合Logo／群組；來源物件關係UNKNOWN，不自動刪框' if code == 'CONTAINMENT_UNKNOWN'
                      else '實際矩形相交；需核對欄位語意，不自動合併／刪除')
            add(code, 'REVIEW', reason, [a.id, b.id], not duplicated_ids.intersection((a.id, b.id)))
    if not payload.get('visual_confirmed'):
        add('VISUAL_PENDING', 'REVIEW', '目前作品尚未人工核對可信原稿，不能宣稱視覺一致')
    if any(s.kind == 'logo' for s in slots):
        add('LOGO_CONTENT_UNKNOWN', 'INFO', 'Logo圖文完整性與原生群組需來源證據；矩形檢查不能證實')
    add('SOURCE_IDENTITY_UNKNOWN', 'INFO', '原生文字／語意↔SVG對應UNKNOWN；只檢查已保存標記的已知事實')
    for issue in issues:
        if duplicated_ids.intersection(issue['slot_ids']): issue['locatable'] = False
    if overflow:
        issues.append({'id': work['id']+'-budget', 'code': 'ISSUE_BUDGET', 'severity': 'BLOCK',
                       'reason': '單作品問題超過400件展示預算，需分批核查，不當PASS', 'slot_ids': [],
                       'work_id': work['id'], 'source_id': work['source_id'], 'work_revision': work['revision'],
                       'work_name': work['name'], 'locatable': False, 'native_mapping': 'UNKNOWN', 'source_text_identity': 'UNKNOWN'})
    return sorted(issues, key=issue_key)


def issue_key(row):
    return (-SEVERITY[row['severity']], row['source_id'], row['work_id'], row['code'], row['id'])


def quality_rows(library, source_id=None, query='', severity='ALL', offset=0, limit=200):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('品質檢視分頁範圍不合法')
    where = ' WHERE source_id=?' if source_id else ''
    args = [source_id] if source_id else []
    total = library.db.execute('SELECT COUNT(*) FROM artworks'+where, args).fetchone()[0]
    records = library.db.execute('SELECT id,source_id,name,revision,payload FROM artworks'+where+' ORDER BY source_id,id LIMIT ? OFFSET ?', [*args, limit, offset]).fetchall()
    rows = []; scanned = 0
    for record in records:
        if len(rows) >= 2000: break
        work = library._decode_artwork(record)
        try: source = library.source(work['source_id'])
        except ValueError: source = None
        rows.extend(analyse_work(work, source))
        scanned += 1
    tokens = query.casefold().split()
    rows = [r for r in rows if (severity == 'ALL' or r['severity'] == severity)
            and all(t in (r['reason']+' '+r['code']+' '+r['work_name']+' '+r['source_id']+' '+' '.join(r['slot_ids'])).casefold() for t in tokens)]
    return {'issues': sorted(rows, key=issue_key), 'total_works': total, 'scanned_works': scanned,
            'offset': offset, 'limit': limit, 'has_more': offset+scanned < total,
            'full_quality_pass': False, 'unknown': '原生內容／實際文字／Logo完整性未驗'}
