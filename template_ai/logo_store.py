"""沿用 Library 的尺寸獨立 Logo 庫；候選、版本與身分核對不隱含發布。

資產 ID 是不可變版本，撤銷寫入本機憑證，使先前產生的候選也失效。
同名公司可有不同身分，不以字串相似度自動合併。
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile

from .background import file_digest
from .customers import digest
from .logo_assets import checked_payload, errors, geometry
from .model import Rect, new_id
from .source_links import verify_source


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class LogoStore:
    def __init__(self, library):
        self.library, self.db = library, library.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS logo_company_identities(id TEXT PRIMARY KEY,name TEXT NOT NULL,note TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS logo_entity_bindings(entity_id TEXT PRIMARY KEY,company_id TEXT NOT NULL REFERENCES logo_company_identities(id),confirmed_name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS logo_proposals(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL);
        ''')
        self.db.commit()

    def companies(self):
        return [dict(id=r[0], name=r[1], note=r[2]) for r in self.db.execute(
            'SELECT id,name,note FROM logo_company_identities ORDER BY name,id LIMIT 200')]

    def company(self, company_id):
        row = self.db.execute('SELECT name,note FROM logo_company_identities WHERE id=?', (company_id,)).fetchone()
        if row is None:
            raise ValueError('Logo 公司身分尚未明確確認')
        return dict(id=company_id, name=row[0], note=row[1])

    def create_company(self, name, note, approved=False):
        if not approved or not all(isinstance(s, str) and s.strip() and len(s) <= 256 for s in (name, note)):
            raise ValueError('需明確核對公司名稱及身分依據，不按同名字串合併')
        identity = new_id()
        with self.db:
            self.db.execute('INSERT INTO logo_company_identities VALUES(?,?,?)', (identity, name.strip(), note))
            self.library.event(identity, 'logo_company_identity_confirmed')
        return self.company(identity)

    def bind(self, entity_id, company_id, label, approved=False):
        company = self.company(company_id)
        if not approved or not isinstance(entity_id, str) or not entity_id or len(entity_id) > 128 \
                or company['name'] != label:
            raise ValueError('需明確核對當次公司實體與資產公司身分')
        with self.db:
            self.db.execute('INSERT INTO logo_entity_bindings VALUES(?,?,?) ON CONFLICT(entity_id) '
                'DO UPDATE SET company_id=excluded.company_id,confirmed_name=excluded.confirmed_name',
                (entity_id, company_id, label))
            self.library.event(entity_id, 'logo_company_binding_confirmed')

    def proposal(self, identity):
        row = self.db.execute('SELECT revision,state,payload FROM logo_proposals WHERE id=?', (identity,)).fetchone()
        if not row:
            raise ValueError('Logo 候選不存在')
        return dict(id=identity, revision=row[0], state=row[1], **json.loads(row[2]))

    def proposals(self, width, height, offset=0):
        self._size(width, height)
        if type(offset) is not int or offset < 0:
            raise ValueError('候選分頁不合法')
        # 尺寸存在 payload 但查詢不靠浮點字串；最多一頁100筆，索引保存精確尺寸。
        rows = self.db.execute("SELECT id FROM logo_proposals WHERE "
            "abs(json_extract(payload,'$.width_mm')-?)<0.00001 AND "
            "abs(json_extract(payload,'$.height_mm')-?)<0.00001 ORDER BY rowid LIMIT 100 OFFSET ?",
            (width, height, offset))
        return [self.proposal(r[0]) for r in rows]

    @staticmethod
    def _size(width, height):
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and
                   math.isfinite(v) and 0 < v <= 2000 for v in (width, height)):
            raise ValueError('Logo 所屬卡片尺寸需為0～2000 mm範圍的正數')

    def propose(self, payload, width, height, origin='MANUAL', company_id=None,
                pins=None, evidence=None, family_base=None, _commit=True):
        self._size(width, height)
        if origin not in ('MANUAL', 'SOURCE', 'SIZE_PREDICTION'):
            raise ValueError('候選來源類型不合法')
        if company_id:
            self.company(company_id)
        asset = checked_payload(payload)
        identity = new_id()
        data = dict(asset=asset, width_mm=width, height_mm=height, origin=origin,
                    company_id=company_id, pins=deepcopy(pins), evidence=deepcopy(evidence or {}),
                    family_base=family_base, review=None)
        if origin == 'SOURCE':
            data['candidate_key'] = digest([pins, asset.get('crop'),
                data['evidence'].get('object_ids'), data['evidence'].get('source_evidence')])
            existing = self.db.execute("SELECT id FROM logo_proposals WHERE json_extract(payload,'$.candidate_key')=?",
                                       (data['candidate_key'],)).fetchone()
            if existing:
                return self.proposal(existing[0])
        def insert():
            self.db.execute('INSERT INTO logo_proposals VALUES(?,1,?,?)',
                (identity, 'PENDING', json.dumps(data, ensure_ascii=False, allow_nan=False)))
            self.library.event(identity, 'logo_candidate_proposed_not_approved')
        if _commit:
            with self.db:
                insert()
        else:
            insert()
        return self.proposal(identity)

    def regions(self, selections, regions, note):
        """同作品候選合併／拆分只建立新待審項；原始圖文與既有資產都不動。"""
        if not isinstance(note, str) or not note.strip() or len(note) > 512 or not 1 <= len(selections) <= 20 \
                or len({x['id'] for x in selections}) != len(selections):
            raise ValueError('選取確切來源候選並記錄邊界校正理由')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            originals = [self.proposal(x['id']) for x in selections]
            for old, selected in zip(originals, selections):
                if old['revision'] != selected['revision'] or old['state'] not in ('PENDING', 'NEEDS_REPAIR') \
                        or old['origin'] != 'SOURCE':
                    raise ValueError('只校正同一作品、尚待審核的來源候選')
                self._fresh(old)
            first = originals[0]
            if any(digest(x['pins']) != digest(first['pins']) for x in originals):
                raise ValueError('不同來源／作品／版本不能合併')
            work = self.library.artwork(first['pins']['artwork_id'])
            area = Rect(**work['payload']['crop'])
            if regions is None:
                frames = [Rect(**x['asset']['crop']) for x in originals]
                x, y = min(r.x for r in frames), min(r.y for r in frames)
                regions = [dict(x=x, y=y, w=max(r.x+r.w for r in frames)-x,
                                h=max(r.y+r.h for r in frames)-y)]
            if not isinstance(regions, list) or not 1 <= len(regions) <= 10:
                raise ValueError('明確指定1至10個新完整候選區域')
            for region in regions:
                rect = Rect(**region)
                if not rect.valid() or rect.x < area.x or rect.y < area.y \
                        or rect.x+rect.w > area.x+area.w+1e-5 or rect.y+rect.h > area.y+area.h+1e-5:
                    raise ValueError('新候選不能跨入其他作品或越界')
            results = []
            for region in regions:
                asset = {**first['asset'], 'crop': deepcopy(region)}
                evidence = dict(object_ids=sorted({oid for x in originals for oid in x['evidence'].get('object_ids', [])}),
                    source_evidence=dict(method='HUMAN_REGION_CORRECTION', note=note),
                    corrected_from=[x['id'] for x in originals],
                    uncertainty='校正後每個區域均須重新核對圖文完整性及公司身分')
                results.append(self.propose(asset, first['width_mm'], first['height_mm'], 'SOURCE',
                    first['company_id'], first['pins'], evidence, _commit=False))
            self.db.commit()
            return results
        except BaseException:
            self.db.rollback()
            raise

    def propose_source(self, source_id, work_id, crop, company_id=None, object_ids=None, evidence=None):
        source = self.library.source(source_id)
        work = self.library.artwork(work_id)
        if work['source_id'] != source_id:
            raise ValueError('作品不屬於指定來源')
        verify_source(source['current_path'], source['hash'])
        rect = Rect(**crop)
        area = Rect(**work['payload']['crop'])
        if not rect.inside(source['width_mm'], source['height_mm']) or rect.x < area.x-1e-5 \
                or rect.y < area.y-1e-5 or rect.x+rect.w > area.x+area.w+1e-5 \
                or rect.y+rect.h > area.y+area.h+1e-5:
            raise ValueError('Logo 邊界必須屬於此完整作品，不能混入其他作品')
        payload = dict(image=source['image'], svg=source.get('svg', ''),
                       source_width_mm=source['width_mm'], source_height_mm=source['height_mm'],
                       crop=deepcopy(crop), source_id=source_id, source_hash=source['hash'])
        pins = dict(source_id=source_id, source_hash=source['hash'], link_revision=source['link_revision'],
                    artwork_id=work_id, artwork_revision=work['revision'], artwork_digest=digest(work['payload']))
        return self.propose(payload, work['payload']['work_width'], work['payload']['work_height'],
            'SOURCE', company_id, pins, dict(object_ids=list(object_ids or []),
            source_evidence=deepcopy(evidence or {}), identity='UNKNOWN_UNTIL_HUMAN_REVIEW',
            composite='ENTIRE_TEXT_AND_GRAPHIC_REGION'))

    def revise(self, identity, expected_revision, crop, company_id=None, object_ids=None, note=''):
        candidate = self.proposal(identity)
        if candidate['revision'] != expected_revision or candidate['state'] not in ('PENDING', 'NEEDS_REPAIR'):
            raise ValueError('候選版本已變更或已審核，請另建候選')
        if not isinstance(note, str) or not note.strip() or len(note) > 512:
            raise ValueError('邊界合併／拆分／歸屬修正需記錄來源理由')
        if company_id:
            self.company(company_id)
        data = {k: deepcopy(v) for k, v in candidate.items() if k not in ('id', 'revision', 'state')}
        data['asset']['crop'] = deepcopy(crop)
        if errors(data['asset'], False):
            raise ValueError('修正邊界或來源不合法')
        if candidate.get('pins'):
            work = self.library.artwork(candidate['pins']['artwork_id'])
            rect, area = Rect(**crop), Rect(**work['payload']['crop'])
            if rect.x < area.x or rect.y < area.y or rect.x+rect.w > area.x+area.w+1e-5 \
                    or rect.y+rect.h > area.y+area.h+1e-5:
                raise ValueError('修正不能跨入另一作品')
        data['company_id'] = company_id
        data['evidence']['object_ids'] = list(object_ids or [])
        data['evidence']['correction_note'] = note
        with self.db:
            count = self.db.execute('UPDATE logo_proposals SET revision=revision+1,state=?,payload=? '
                'WHERE id=? AND revision=?', ('PENDING', json.dumps(data, ensure_ascii=False),
                identity, expected_revision)).rowcount
            if count != 1:
                raise ValueError('候選版本競爭')
            self.library.event(identity, 'logo_candidate_region_corrected')
        return self.proposal(identity)

    def _fresh(self, candidate):
        issues = errors(candidate['asset'], False)
        if issues:
            raise ValueError('；'.join(issues))
        pins = candidate.get('pins')
        if pins:
            source = self.library.source(pins['source_id'])
            work = self.library.artwork(pins['artwork_id'])
            if source['hash'] != pins['source_hash'] or source['link_revision'] != pins['link_revision'] \
                    or work['revision'] != pins['artwork_revision'] or digest(work['payload']) != pins['artwork_digest']:
                raise ValueError('來源／作品已更新，需重新核對完整圖文')
            verify_source(source['current_path'], pins['source_hash'])
        reference = candidate.get('evidence', {}).get('prediction_source')
        if reference:
            original = self.asset(reference['id'])
            if digest(original) != reference['digest'] or errors(original):
                raise ValueError('新尺寸參考版本已變更／撤銷，不能繼續核准')

    def asset(self, identity):
        row = self.db.execute('SELECT payload FROM logos WHERE id=?', (identity,)).fetchone()
        if not row:
            raise ValueError('確切 Logo 版本不存在')
        return json.loads(row[0])

    def approve(self, identity, expected_revision, company_id, review, approved=False):
        if approved is not True or not isinstance(review, dict) or not all(review.get(key) is True
                for key in ('identity_confirmed', 'whole_mark_confirmed', 'usage_authorized', 'digital_quality_confirmed')):
            raise ValueError('需逐項確認公司身分、完整圖文、使用權與目標尺寸數位品質')
        actor, note = review.get('actor'), review.get('note')
        if not all(isinstance(s, str) and s.strip() and len(s) <= 512 for s in (actor, note)):
            raise ValueError('需具名審核及實際品質／來源核對說明')
        self.db.execute('BEGIN IMMEDIATE')
        approval_path = None
        try:
            candidate = self.proposal(identity)
            if candidate['revision'] != expected_revision or candidate['state'] != 'PENDING':
                raise ValueError('候選未待審或版本過期，不能重複核准')
            self._fresh(candidate)
            company = self.company(company_id)
            base = self.asset(candidate['family_base']) if candidate.get('family_base') else None
            if base and not base.get('managed_logo'):
                raise ValueError('舊資產須先核對公司身分與來源，建立受管理版本')
            if base and (base.get('company_id') != company_id or
                abs(base['width_mm']-candidate['width_mm']) > 1e-5 or
                abs(base['height_mm']-candidate['height_mm']) > 1e-5):
                raise ValueError('版本更新須為同一公司、同一卡片尺寸，其他身分保留獨立')
            family = base['family_id'] if base else new_id()
            versions = [a.get('version', 1) for a in self.library.logos() if a.get('family_id') == family]
            asset_id = new_id()
            approval_path = self.library.assets / 'logo-approvals' / (asset_id + '.json')
            _atomic_json(approval_path, dict(asset_id=asset_id, status='APPROVED', candidate_id=identity))
            asset = dict(candidate['asset'], id=asset_id, family_id=family,
                version=max(versions, default=0)+1, company_id=company_id, company=company['name'],
                width_mm=candidate['width_mm'], height_mm=candidate['height_mm'],
                approved=True, status='APPROVED', approval_file=str(approval_path),
                approval_sha256=file_digest(approval_path), review=deepcopy(review),
                candidate_id=identity, origin=candidate['origin'], evidence=deepcopy(candidate['evidence']),
                pins=deepcopy(candidate.get('pins')), created_utc=datetime.now(timezone.utc).isoformat())
            self.db.execute('INSERT INTO logos VALUES(?,?,?,?,?)', (asset_id, company['name'],
                asset['width_mm'], asset['height_mm'], json.dumps(asset, ensure_ascii=False)))
            payload = {k: deepcopy(v) for k, v in candidate.items() if k not in ('id', 'revision', 'state')}
            payload.update(review=deepcopy(review), approved_asset_id=asset_id)
            self.db.execute('UPDATE logo_proposals SET revision=revision+1,state=?,payload=? WHERE id=?',
                ('APPROVED', json.dumps(payload, ensure_ascii=False), identity))
            self.library.event(asset_id, 'logo_entire_mark_and_size_explicitly_approved')
            self.db.commit()
            return asset
        except BaseException:
            self.db.rollback()
            if approval_path:
                approval_path.unlink(missing_ok=True)
            raise

    def reject(self, identity, expected_revision, reason, approved=False, repair=False):
        if not approved or not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise ValueError('拒絕／待修正需明確原因')
        with self.db:
            row = self.proposal(identity)
            if row['state'] not in ('PENDING', 'NEEDS_REPAIR') or row['revision'] != expected_revision:
                raise ValueError('候選已更新／已核准')
            data = {k: v for k, v in row.items() if k not in ('id', 'revision', 'state')}
            data['review'] = dict(reason=reason)
            self.db.execute('UPDATE logo_proposals SET revision=revision+1,state=?,payload=? WHERE id=? AND revision=?',
                ('NEEDS_REPAIR' if repair else 'REJECTED', json.dumps(data, ensure_ascii=False), identity, expected_revision))
            self.library.event(identity, 'logo_candidate_rejected_or_repair')
        return self.proposal(identity)

    def revoke(self, identity, expected_digest, reason, approved=False):
        if not approved or not isinstance(reason, str) or not reason.strip() or len(reason) > 512:
            raise ValueError('撤銷需核對影響及明確原因')
        self.db.execute('BEGIN IMMEDIATE')
        old_record = None
        path = None
        try:
            asset = self.asset(identity)
            if not asset.get('managed_logo') or digest(asset) != expected_digest:
                raise ValueError('Logo 版本已變更，需重新核對')
            path = Path(asset['approval_file'])
            old_record = path.read_bytes()
            _atomic_json(path, dict(asset_id=identity, status='REVOKED', reason=reason))
            asset.update(approved=False, status='REVOKED', revocation_reason=reason)
            self.db.execute('UPDATE logos SET payload=? WHERE id=?', (json.dumps(asset, ensure_ascii=False), identity))
            self.library.event(identity, 'logo_version_revoked_revalidate_exact_references')
            self.db.commit()
            return asset
        except BaseException:
            self.db.rollback()
            if path and old_record is not None:
                # 回復原核准內容；若磁碟故障使回復也失敗，舊憑證 hash 不符會 fail closed。
                _atomic_json(path, json.loads(old_record))
            raise

    def match(self, entity_id, label, width, height, frame=None, selected_id=None):
        self._size(width, height)
        binding = self.db.execute('SELECT company_id,confirmed_name FROM logo_entity_bindings WHERE entity_id=?',
                                  (entity_id,)).fetchone()
        same_size = [a for a in self.library.logos() if abs(a['width_mm']-width) < 1e-5 and
                     abs(a['height_mm']-height) < 1e-5]
        if binding is None or binding[1] != label:
            return dict(state='IDENTITY_REVIEW_REQUIRED', selected=None, candidates=[],
                        name_clues=[a['id'] for a in same_size if a['company'] == label],
                        reason='公司名稱僅為線索，先核對當次實體與資產公司身分')
        assets = [a for a in same_size if a.get('company_id') == binding[0] and not errors(a)]
        if frame:
            assets.sort(key=lambda a: (-geometry(a, frame)['occupied_fraction'], a['id']))
        selected = next((a for a in assets if a['id'] == selected_id), None) if selected_id else None
        if selected_id and selected is None:
            state, reason = 'SELECTION_INVALID', '原選定版本已撤銷／失聯／尺寸或身分不符；不靜默替換'
        elif selected:
            state, reason = 'SELECTED_PENDING_OUTPUT_CHECK', '確切版本已綁定；仍須重新驗證數位輸出'
        elif len(assets) == 1:
            selected = assets[0]
            state, reason = 'SINGLE_PREVIEW', '唯一明確版本可預覽，尚未通過當次輸出驗證'
        elif assets:
            state, reason = 'MULTIPLE_REVIEW_REQUIRED', '多個同尺寸已核准版本，須明確比較選擇'
        else:
            state, reason = 'MISSING', '本尺寸缺少合格版本；黑底白字占位不能正式輸出'
        return dict(state=state, selected=selected, candidates=assets, reason=reason,
                    company_id=binding[0], size_mm=[width, height])

    def predict_new_size(self, company_id, width, height):
        self._size(width, height)
        self.company(company_id)
        if any(abs(t.width_mm-width) < 1e-5 and abs(t.height_mm-height) < 1e-5
               for t in self.library.templates()) or any(abs(a['width_mm']-width) < 1e-5 and
               abs(a['height_mm']-height) < 1e-5 for a in self.library.logos()):
            raise ValueError('目標已是已知尺寸；一般缺圖不能藉新尺寸流程跨庫借用')
        result = []
        for asset in self.library.logos():
            if asset.get('company_id') == company_id and not errors(asset):
                result.append(self.propose(asset, width, height, 'SIZE_PREDICTION', company_id,
                    evidence=dict(prediction_source=dict(id=asset['id'], digest=digest(asset),
                    size_mm=[asset['width_mm'], asset['height_mm']], version=asset.get('version', 1)),
                    target_size_mm=[width, height], risk='來源尺寸品質不代表新尺寸合格；須獨立審核')))
        return result
