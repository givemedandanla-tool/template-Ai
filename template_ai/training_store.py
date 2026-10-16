"""Versioned training metadata in the existing Library SQLite, never in source pixels."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import time
from contextlib import contextmanager
from pathlib import Path
from .model import Rect, new_id
from .source_links import hash_source, check_verified
from .noise import NoiseMixin
from .noise_review import RuleReviewMixin
from .noise_hits import NoiseHitMixin
from .noise_recovery import NoiseRecoveryMixin
from .trusted_samples import TrustedSampleMixin
from .datasets import DatasetMixin
from .quality_coverage import CoverageMixin
from .training_pipeline import TrainingQueueMixin


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def text(value, label, maximum=512):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
        raise ValueError(label+'需完整非空文字且不超過'+str(maximum)+'字')
    return value


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('stable ID不合法')
    return value


class TrainingStore(NoiseMixin, RuleReviewMixin, NoiseHitMixin, NoiseRecoveryMixin, TrustedSampleMixin, DatasetMixin, CoverageMixin, TrainingQueueMixin):
    def __init__(self, library):
        self.library = library; self.db = library.db
        self.db.create_function('training_casefold', 1, lambda value: str(value).casefold(), deterministic=True)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS training_records(kind TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS training_history(kind TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,action TEXT NOT NULL,before_json TEXT,after_json TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(kind,id,revision));
        CREATE TABLE IF NOT EXISTS training_meta(id INTEGER PRIMARY KEY CHECK(id=1),epoch INTEGER NOT NULL);
        INSERT OR IGNORE INTO training_meta VALUES(1,0);
        '''); self.db.commit()

    @classmethod
    def bind(cls, library):
        # Read/commit helpers inside an existing transaction must not execute schema DDL or commit.
        obj=object.__new__(cls);obj.library=library;obj.db=library.db;return obj

    @property
    def epoch(self):
        return self.db.execute('SELECT epoch FROM training_meta WHERE id=1').fetchone()[0]

    def get(self, kind, record_id):
        row = self.db.execute('SELECT revision,payload FROM training_records WHERE kind=? AND id=?', (kind, record_id)).fetchone()
        return {'id': record_id, 'revision': row[0], **json.loads(row[1])} if row else None

    def records(self, kind, offset=0, limit=200):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('查詢需有效分頁，最多200項')
        return [self.get(kind, r[0]) for r in self.db.execute('SELECT id FROM training_records WHERE kind=? ORDER BY id LIMIT ? OFFSET ?', (kind, limit, offset))]

    def count(self, kind):
        return self.db.execute('SELECT count(*) FROM training_records WHERE kind=?', (kind,)).fetchone()[0]

    def history(self, kind, record_id):
        return [{'revision': r[0], 'action': r[1], 'before': json.loads(r[2]) if r[2] else None, 'after': json.loads(r[3]), 'created': r[4]}
                for r in self.db.execute('SELECT revision,action,before_json,after_json,created FROM training_history WHERE kind=? AND id=? ORDER BY revision DESC LIMIT 200', (kind, record_id))]

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback(); raise

    def _write(self, kind, record_id, payload, expected_revision, action):
        identity(record_id); before = self.get(kind, record_id)
        if type(expected_revision) is not int or expected_revision < 0 or (before['revision'] if before else 0) != expected_revision:
            raise ValueError('資料版次已變更，請重新載入')
        payload = copy.deepcopy(payload); payload.pop('id', None); payload.pop('revision', None)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        if len(raw.encode()) > 1_048_576: raise ValueError('單筆metadata超過1MiB')
        revision = expected_revision+1
        self.db.execute('INSERT INTO training_records VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload', (kind, record_id, revision, raw))
        self.db.execute('INSERT INTO training_history VALUES(?,?,?,?,?,?,?)', (kind, record_id, revision, action, json.dumps(before, ensure_ascii=False) if before else None, raw, time.time()))
        self.db.execute('UPDATE training_meta SET epoch=epoch+1 WHERE id=1')
        self.library.event(record_id, 'training_'+action)
        return self.get(kind, record_id)

    def pins(self, work_id):
        work = self.library.artwork(work_id); source = self.library.source(work['source_id'])
        return {'work_id': work_id, 'work_revision': work['revision'], 'work_digest': digest(work['payload']),
                'source_id': source['id'], 'source_hash': source['hash'], 'page': source.get('page', 1), 'link_revision': source['link_revision']}

    def source_proof(self, work_id):
        source = self.library.source(self.library.artwork(work_id)['source_id'])
        return hash_source(source['current_path'], byte_limit=50_000_000)

    def checked(self, work_id, proof):
        source = self.library.source(self.library.artwork(work_id)['source_id'])
        check_verified(proof, source['hash'])
        if proof.path != str(Path(source['current_path']).resolve()) or proof.stat[2] != source['byte_size']:
            raise ValueError('來源位置或長度已變更')

    def validate_observations(self, work_id, observations):
        from .semantic_fields import recognize
        if not isinstance(observations, list) or not 1 <= len(observations) <= 200:
            raise ValueError('觀察需1～200項；空白不算來源事實')
        work = self.library.artwork(work_id); source = self.library.source(work['source_id'])
        slots = work['payload']['slots']; ids = [s.get('id') for s in slots];by_slot={s.get('id'):s for s in slots}
        if len(ids) != len(set(ids)): raise ValueError('作品stable slot IDs重複，先修標記')
        result = []; seen = set(); linked = set()
        for item in observations:
            if not isinstance(item, dict): raise ValueError('觀察schema不合法')
            oid = identity(item.get('id'))
            if oid in seen: raise ValueError('觀察stable ID重複')
            seen.add(oid); slot_id = item.get('slot_id')
            if slot_id is not None:
                identity(slot_id)
                if slot_id not in ids or slot_id in linked: raise ValueError('框連結不存在或重複')
                linked.add(slot_id)
            if item.get('object_type') not in ('TEXT', 'ANNOTATION', 'LOGO_PART', 'UNKNOWN') or item.get('classification') not in ('FIELD', 'ANNOTATION', 'LOGO', 'UNKNOWN'):
                raise ValueError('物件類型或分類不合法')
            try:
                rect = Rect(**item['region'])
                if not rect.inside(source['width_mm'], source['height_mm']): raise ValueError()
            except (KeyError, TypeError, ValueError): raise ValueError('來源區域需有效毫米矩形') from None
            result.append({'id': oid, 'slot_id': slot_id, 'text': text(item.get('text'), '完整來源文字',2048),
                           'object_type': item['object_type'], 'classification': item['classification'], 'region': copy.deepcopy(item['region']),
                           'evidence': item.get('evidence') if item.get('evidence') in ('AI_SOURCE_HYPOTHESIS','USER_OBSERVATION_DRAFT') else 'USER_OBSERVATION', 'native_mapping': 'UNKNOWN',
                           'prior_prediction': item.get('prior_prediction') if item.get('prior_prediction') is not None else None,
                           'semantic': recognize(item['text']) if item['object_type']=='TEXT' else None,
                           'slot_kind':by_slot.get(slot_id,{}).get('kind'),'owner':by_slot.get(slot_id,{}).get('owner')})
            if item.get('review') is not None:
                review=item['review']
                if not isinstance(review,dict) or review.get('state') not in ('HUMAN_PENDING_CONFIRMATION','REJECTED','QUARANTINED'):raise ValueError('標記審核狀態不合法')
                text(review.get('reason'),'標記審核理由');text(review.get('actor'),'標記審核者',120)
                result[-1]['review']=copy.deepcopy(review)
            if result[-1]['prior_prediction'] is not None: text(result[-1]['prior_prediction'], '原預測')
        return sorted(result, key=lambda x: x['id'])

    def facts(self, work_id):
        return self.get('FACTS', work_id) or {'id': work_id, 'revision': 0, 'observations': [], 'confirmation': None, 'state': 'PENDING', 'pins': self.pins(work_id)}

    def save_facts(self, work_id, observations, expected_revision, expected_work_revision):
        with self.transaction():
            pins = self.pins(work_id)
            if pins['work_revision'] != expected_work_revision: raise ValueError('作品已變更，觀察未覆蓋新標記')
            checked = self.validate_observations(work_id, observations)
            before = self.facts(work_id)
            saved = self._write('FACTS', work_id, {'observations': checked, 'confirmation': None, 'state': 'PENDING', 'pins': pins}, expected_revision, 'facts_saved')
            from .trusted_sample_pool import TrustedSamplePool
            TrustedSamplePool(self.library).collect_in_transaction(work_id, before, saved)
            self._refresh_noise(work_id); return saved

    def facts_state(self, work_id, proof=None):
        record = self.facts(work_id)
        if record['pins'] != self.pins(work_id): return 'STALE'
        if record['confirmation']:
            from .source_links import VerifiedSource
            source = self.library.source(record['pins']['source_id'])
            try:
                self.checked(work_id, VerifiedSource(str(Path(source['current_path']).resolve()), source['hash'], tuple(record['confirmation']['source_stat'])))
            except (ValueError, OSError): return 'STALE'
        if proof is not None:
            try: self.checked(work_id, proof)
            except (ValueError, OSError): return 'STALE'
        if record['confirmation'] and record['confirmation']['observations_digest'] == digest(record['observations']): return 'CONFIRMED'
        return record['state']

    def confirm_facts(self, work_id, observation_ids, expected_revision, expected_pins, proof, actor, approved=False):
        if approved is not True: raise ValueError('需要人工明確確認作品事實')
        text(actor, '確認者', 120)
        with self.transaction():
            record = self.facts(work_id); self.checked(work_id, proof)
            self.checked(work_id, self.source_proof(work_id))
            if self.pins(work_id) != expected_pins or record['pins'] != expected_pins: raise ValueError('來源或作品範圍已變更')
            ids = sorted(observation_ids)
            if not ids or len(ids) != len(set(ids)) or not set(ids) <= {o['id'] for o in record['observations']}: raise ValueError('明列有效且不重複的觀察範圍')
            if any(o['id'] in ids and o.get('review',{}).get('state') in ('REJECTED','QUARANTINED') for o in record['observations']):raise ValueError('拒絕／疑義隔離標記不可確認；先明確恢復待確認並核對來源')
            previous=record.get('confirmation')
            if previous and previous['observations_digest']==digest(record['observations']) and previous['pins']==expected_pins:
                ids=sorted(set(ids)|set(previous['observation_ids']))
            # Accumulate correction evidence without creating or enabling a global rule.
            prior=next((h for h in self.history('FACTS',work_id) if h['after'].get('confirmation') and
                h['after'].get('pins',{}).get('source_hash')==expected_pins['source_hash'] and
                digest(h['after']['observations'])!=digest(record['observations'])),None)
            if prior:
                old={o['id']:o for o in prior['after']['observations']}
                for observation in record['observations']:
                    before=old.get(observation['id']);keys=('text','slot_id','classification','region','slot_kind','owner')
                    if observation['id'] in ids and before and any(before.get(k)!=observation.get(k) for k in keys):
                        hint_id=digest([work_id,prior['after']['pins'].get('work_revision'),expected_pins['work_revision'],observation['id'],{k:before.get(k) for k in keys},{k:observation.get(k) for k in keys}])
                        if not self.get('RULE_HINT',hint_id):self._write('RULE_HINT',hint_id,dict(state='PENDING',risk='HIGH',work_id=work_id,
                            observation_id=observation['id'],pins=expected_pins,before={k:before.get(k) for k in keys},after={k:observation.get(k) for k in keys},
                            actor=actor,reason='單例修正證據；跨作品適用條件／反例尚待驗證，不自動啟用',created=time.time()),0,'confirmed_correction_rule_hint_proposed')
            record['confirmation'] = {'actor': actor, 'timestamp': time.time(), 'observation_ids': ids, 'observations_digest': digest(record['observations']), 'pins': expected_pins,
                                      'source_stat': list(proof.stat), 'scope': 'EXACT_WORK_FACTS_ONLY; NOT_SAMPLE_OR_RULE_APPROVAL'}
            record['state'] = 'CONFIRMED'
            saved = self._write('FACTS', work_id, record, expected_revision, 'facts_confirmed')
            self._refresh_noise(work_id); return saved

    def revoke_facts(self, work_id, expected_revision, reason):
        text(reason, '撤銷原因')
        with self.transaction():
            record = self.facts(work_id)
            if not record['confirmation']: raise ValueError('沒有有效確認可撤銷')
            record.update(confirmation=None, state='REVOKED', revocation_reason=reason)
            saved = self._write('FACTS', work_id, record, expected_revision, 'facts_revoked')
            self._refresh_noise(work_id); return saved
