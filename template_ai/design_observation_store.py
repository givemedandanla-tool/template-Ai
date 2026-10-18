"""Observation snapshots in the existing TrainingStore transaction/history."""
from copy import deepcopy

from .design_observation import build_observation, canonical_digest


class DesignObservationMixin:
    def design_observation(self, work_id):
        return self.get('DESIGN_OBSERVATION', work_id)

    def _design_observation_document(self, work_id):
        work = self.library.artwork(work_id)
        source = self.library.source(work['source_id'])
        pins, facts = self.pins(work_id), self.facts(work_id)
        if (pins['work_revision'] != work['revision'] or pins['work_digest'] != canonical_digest(work['payload'])
                or pins['source_hash'] != source['hash']):
            raise ValueError('建立觀察計畫期間來源／作品已變更')
        noise = self.noise_decisions(work_id)
        noise_signature = canonical_digest([{k: r[k] for k in (
            'observation_id', 'state', 'protected', 'observation_digest',
            'rule_matches', 'local_revision', 'invalid_rule_ids')} for r in noise])
        result = build_observation(work, source, facts, pins, self.facts_state(work_id),
                                   noise_signature, noise)
        if self.pins(work_id) != pins or self.facts(work_id) != facts:
            raise ValueError('建立觀察計畫期間標記事實已變更')
        return result

    def design_observation_plan(self, work_id):
        from .training_store import identity
        identity(work_id)
        document = self._design_observation_document(work_id)
        before = self.design_observation(work_id)
        plan = dict(work_id=work_id, expected_revision=before['revision'] if before else 0,
                    input_signature=document['input_signature'], observation=document)
        plan['digest'] = canonical_digest(plan)
        return plan

    @staticmethod
    def _design_observation_body(record):
        return {k: deepcopy(v) for k, v in record.items()
                if k not in ('id', 'revision', 'recorded_by', 'document_digest')}

    def refresh_design_observation_in_transaction(self, work_id, actor):
        from .batch_import import healthy_source
        from .training_store import text
        if not self.db.in_transaction:
            raise RuntimeError('觀察refresh需使用既有交易')
        text(actor, '觀察記錄者', 120)
        source = self.library.source(self.library.artwork(work_id)['source_id'])
        if not healthy_source(source):
            raise ValueError('來源或衍生快取已變更，觀察未保存')
        # Never accept a caller-supplied verification token as source truth.
        proof = self.source_proof(work_id)
        self.checked(work_id, proof)
        document = self._design_observation_document(work_id)
        before = self.design_observation(work_id)
        checksum = canonical_digest(document)
        if (before and before.get('document_digest') == checksum
                and self._design_observation_body(before) == document):
            return before
        saved = self._write('DESIGN_OBSERVATION', work_id,
            dict(document, document_digest=checksum, recorded_by=actor),
            before['revision'] if before else 0, 'design_observation_recorded')
        # Detect changes during projection/audit too; rollback is owned by caller.
        self.checked(work_id, proof)
        return saved

    def save_design_observation(self, plan, actor):
        if not isinstance(plan, dict) or not isinstance(plan.get('work_id'), str):
            raise ValueError('觀察計畫格式不合法')
        with self.transaction():
            current = self.design_observation_plan(plan['work_id'])
            if current != plan:
                raise ValueError('觀察來源／事實／版次已變更，重新建立計畫')
            return self.refresh_design_observation_in_transaction(plan['work_id'], actor)

    def design_observation_state(self, work_id):
        from .batch_import import healthy_source
        record = self.design_observation(work_id)
        if not record:
            return 'MISSING'
        try:
            source = self.library.source(self.library.artwork(work_id)['source_id'])
            if not healthy_source(source):
                return 'STALE'
            document = self._design_observation_document(work_id)
            if (record.get('document_digest') != canonical_digest(document)
                    or self._design_observation_body(record) != document):
                return 'STALE'
            return 'CURRENT'  # Currency only; see separate qualification/training_admission.
        except (ValueError, OSError, KeyError, TypeError):
            return 'STALE'
