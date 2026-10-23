"""Shared layout learning in the existing SAMPLE/DATASET/TrainingStore lifecycle.

New-purpose permission is explicit. No customer text, filename or ID is a family
feature. Candidate training, evaluation and activation are distinct operations.
"""
from copy import deepcopy
import math
import time

from .training_store import TrainingStore, digest, text, identity
from .model import new_id
from .quality_groups import QualityGroups
from .design_family import train_families, feature_vector, project
from .design_profiles import learn_profiles

USE = 'CROSS_WORK_RULE_LEARNING_LOCAL'
MODEL = 'DESIGN_MODEL'
ACTIVE = 'DESIGN_ACTIVE'
VERSION = 'cross-work-learning-1'


def grapheme_count(value):
    from PySide6.QtCore import QTextBoundaryFinder
    finder = QTextBoundaryFinder(QTextBoundaryFinder.BoundaryType.Grapheme, value)
    result = 0; finder.toStart()
    while finder.toNextBoundary() != -1:
        result += 1
    return result


class CrossWorkLearning:
    def __init__(self, library):
        self.library = library
        self.store = TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)

    def dataset_plan(self, sample_roles, permission):
        if (not isinstance(sample_roles, dict) or not 1 <= len(sample_roles) <= 10000
                or set(sample_roles.values())-{'TRAIN', 'VALIDATION', 'HOLDOUT'}):
            raise ValueError('Cross-work dataset needs explicit bounded sample roles')
        if not isinstance(permission, dict) or permission.get('use') != USE:
            raise ValueError('Geometry-only sample permission is not cross-work-rule permission')
        text(permission.get('actor'), 'Dataset rights actor', 120)
        text(permission.get('basis'), 'Dataset rights evidence', 2048)
        examples, entries, scopes, assignments = [], [], [], []
        groups = QualityGroups(self.library)
        graph, group_state, _ = groups.graph_state()
        import networkx as nx
        component_ids = {}
        for component in nx.connected_components(graph):
            group_id = digest(sorted(component))
            for node in component:
                if node.startswith('CONTENT:'):
                    component_ids[node.split(':', 1)[1]] = group_id
        verified_font_assets=set()
        for sample_id, role in sorted(sample_roles.items()):
            identity(sample_id)
            sample = self.store.get('SAMPLE', sample_id)
            if not sample or self.store.sample_state(sample_id) != 'APPROVED':
                raise ValueError('Cross-work training requires a current approved source sample')
            work_id = sample['work_id']; work = self.library.artwork(work_id)
            source = self.library.source(work['source_id'])
            from .trusted_sample_pool import source_restriction
            if any(source_restriction(self.store, source['hash'], purpose) for purpose in
                   (USE, 'GEOMETRY_TRAINING_LOCAL', 'RULE_APPROVAL_LOCAL')):
                raise ValueError('Source use has been stopped')
            observation = self.store._design_observation_document(work_id)
            self.store.checked(work_id, self.store.source_proof(work_id))
            properties = {node['properties']['slot_ref']:node['properties'] for node in observation['nodes']
                          if node['kind'] == 'FIELD_ROLE'}
            labels = {label['slot_id']:label for label in sample['positive_labels']}
            fields, binding_refs = [], []
            for slot in sample['label_slots']:
                metadata = properties[slot['id']]
                binding = self.store.get('DESIGN_SOURCE_BINDING', digest([work_id, slot['id']]))
                typography = deepcopy(metadata['typography'])
                label = labels.get(slot['id'])
                if binding:
                    if binding.get('visual_match_id'):
                        from .local_font_recovery import LocalFontRecovery
                        if digest(LocalFontRecovery(self.library).checked(binding['visual_match_id']))!=binding['visual_match_digest']:
                            raise ValueError('Visual source correspondence changed')
                    if (binding['pins'] != sample['pins']
                            or binding['original_evidence_digest'] != observation['original_text_evidence']['document_digest']
                            or binding['state'] != 'APPROVED'):
                        raise ValueError('Source typography binding is stale or withdrawn')
                    typography = deepcopy(binding['typography'])
                    from .design_components import component_fonts
                    from .design_components import presentation_errors
                    if presentation_errors(binding.get('source_text_flow')):raise ValueError('Bound source component resource changed')
                    assets=[typography.get('font_asset_ref')]+component_fonts(binding.get('source_text_flow'))
                    for asset in assets:
                        asset_key=digest(asset)
                        if asset_key in verified_font_assets:continue
                        from .fonts import font_errors
                        if not asset or font_errors(asset,(asset.get('families') or [''])[0]):
                            raise ValueError('Bound source font file is unavailable or changed')
                        verified_font_assets.add(asset_key)
                    binding_refs.append(dict(id=binding['id'], revision=binding['revision'], digest=digest(binding)))
                field = dict(id=slot['id'], kind=slot['kind'], owner=slot['owner'], index=slot['index'],
                    rect=deepcopy(slot['rect']), source_typography=typography,
                    measured_grapheme_count=grapheme_count(label['text']) if label else None)
                if binding:
                    for key in ('container_binding', 'label_binding', 'icon_binding', 'source_alignment', 'source_distribution', 'source_text_flow'):
                        if key in binding:
                            field[key] = deepcopy(binding[key])
                if label:
                    from .design_assignment import semantic_observation
                    field.update(semantic_observation(slot['kind'],label['text']))
                fields.append(field)
            group_id = component_ids.get(source['hash'])
            if not group_id:
                raise ValueError('Source independence projection is unavailable')
            example = dict(id=sample_id, role=role, lineage_group=group_id,
                width_mm=sample['width_mm'], height_mm=sample['height_mm'], fields=fields)
            entry = dict(sample_id=sample_id, sample_revision=sample['revision'], scope_digest=sample['scope_digest'],
                work_id=work_id, pins=deepcopy(sample['pins']), facts_revision=sample['facts_revision'],
                observation_signature=observation['input_signature'], observation_digest=digest(observation),
                source_hash=source['hash'], source_group=source['hash'], role=role,
                lineage_group=group_id, source_binding_refs=binding_refs,
                rights=deepcopy(sample['rights']), use=USE)
            examples.append(example); entries.append(entry)
            assignments.append((source['hash'], role))
            scopes.append(dict(work_id=work_id, pins=deepcopy(sample['pins']), role=role))
        conflicts = groups.role_conflicts(assignments)
        if conflicts:
            raise ValueError('Known correlated sources cannot span training/validation/holdout')
        projection = groups.projection([entry['source_hash'] for entry in entries], graph, group_state)
        plan = dict(version=VERSION, purpose=USE, entries=entries, examples=examples, scopes=scopes,
            sample_roles=deepcopy(sample_roles), permission=deepcopy(permission),
            correlation_digest=projection['digest'], unreviewed_near_duplicates='UNKNOWN',
            source_identity_features_used=False)
        plan['digest'] = digest(plan)
        return plan

    def freeze_dataset(self, plan, actor, approved=False):
        if approved is not True:
            raise ValueError('Explicit approval of source scope, dataset roles and new-purpose use is required')
        text(actor, 'Dataset curator', 120)
        with self.store.transaction():
            current = self.dataset_plan(plan['sample_roles'], plan['permission'])
            if current['digest'] != plan.get('digest'):
                raise ValueError('Dataset sources/roles/observations changed during review')
            for entry in current['entries']:
                prior = self.store.get('GROUP_ROLE', entry['source_hash'])
                if not prior:
                    self.store._write('GROUP_ROLE', entry['source_hash'],
                        dict(role=entry['role'], source_hash=entry['source_hash'], actor=actor,
                             basis='CROSS_WORK_DATASET_SOURCE_ROLE'), 0, 'cross_work_source_role_locked')
            return self.store._write('DATASET', new_id(), dict(state='FROZEN', purpose=USE,
                manifest=current, manifest_digest=current['digest'], entries=current['entries'],
                actor=actor, created=time.time(), training_started=False,
                training_started_scope='AT_MANIFEST_FREEZE;current uses in DESIGN_MODEL/DESIGN_USE'),
                0, 'cross_work_dataset_frozen')

    def checked_dataset(self, dataset_id):
        row = self.store.get('DATASET', dataset_id)
        if not row or row.get('purpose') != USE or row['state'] != 'FROZEN':
            raise ValueError('Not a frozen cross-work learning dataset')
        current = self.dataset_plan(row['manifest']['sample_roles'], row['manifest']['permission'])
        if current['digest'] != row['manifest_digest'] or current != row['manifest']:
            raise ValueError('Dataset source/scope/rights/lineage is stale')
        return row

    def train(self, dataset_id, actor, settings=None, approved=False, *, origin_job=None, previous_model_id=None):
        if approved is not True:
            raise ValueError('Explicit local cross-work training authorization is required')
        text(actor, 'Training actor', 120)
        dataset = self.checked_dataset(dataset_id)
        request_digest=digest([dataset_id,dataset['manifest_digest'],settings or {},previous_model_id])
        if origin_job:
            row=self.store.db.execute("SELECT id FROM training_records WHERE kind='DESIGN_MODEL' AND json_extract(payload,'$.origin_job')=?",(origin_job,)).fetchone()
            if row:
                existing,_=self.checked_model(row[0])
                if existing.get('training_request_digest')!=request_digest:raise ValueError('Training job request changed')
                return existing
        previous=None
        if previous_model_id:
            prior=self.store.get(MODEL,previous_model_id)
            if not prior or digest(prior['artifact'])!=prior['weights_digest']:raise ValueError('Previous family correspondence proof differs')
            previous=prior['artifact']['family_model']
        selected = [row for row in dataset['manifest']['examples'] if row['role'] == 'TRAIN']
        families = train_families(selected, settings, previous=previous)
        profiles = learn_profiles(families, selected)
        artifact = dict(version=VERSION, family_model=families, profile_model=profiles)
        with self.store.transaction():
            if self.checked_dataset(dataset_id) != dataset:
                raise ValueError('Dataset changed while fitting')
            saved = self.store._write(MODEL, new_id(), dict(state='PENDING', actor=actor,
                dataset_id=dataset_id, dataset_revision=dataset['revision'],
                manifest_digest=dataset['manifest_digest'], plan=dict(scopes=deepcopy(dataset['manifest']['scopes'])),
                artifact=artifact, weights_digest=digest(artifact), settings=deepcopy(settings or {}),
                created=time.time(), actual_template_objects_created=0,
                formal_qualification='NOT_EVALUATED', evaluation_ids=[],origin_job=origin_job,
                training_request_digest=request_digest,previous_model_id=previous_model_id), 0,
                'cross_work_family_and_rule_candidate_trained_not_activated')
            for entry in dataset['entries']:
                self.store._write('DESIGN_USE',new_id(),dict(model_id=saved['id'],dataset_id=dataset_id,
                    sample_id=entry['sample_id'],sample_revision=entry['sample_revision'],role=entry['role'],
                    source_hash=entry['source_hash'],manifest_digest=dataset['manifest_digest'],purpose=USE),
                    0,'cross_work_model_source_use_recorded')
            return saved

    def checked_model(self, model_id):
        model = self.store.get(MODEL, model_id)
        if not model or model['state'] == 'REVOKED':
            raise ValueError('Learning model is unavailable or revoked')
        dataset = self.checked_dataset(model['dataset_id'])
        if (dataset['revision'] != model['dataset_revision'] or dataset['manifest_digest'] != model['manifest_digest']
                or digest(model['artifact']) != model['weights_digest']):
            raise ValueError('Model data or immutable weights differ')
        return model, dataset

    def evaluate_family_descriptors(self, model_id, role='VALIDATION', truth=None):
        """Descriptor matching only; not new-input layout or aesthetic evaluation."""
        if role not in ('VALIDATION', 'HOLDOUT'):
            raise ValueError('Evaluation role must be explicit and outside TRAIN')
        model, dataset = self.checked_model(model_id); family_model=model['artifact']['family_model']
        rows = [row for row in dataset['manifest']['examples'] if row['role'] == role]
        if not rows:
            raise ValueError('No examples in selected evaluation role')
        records = []
        truth = deepcopy(truth or {})
        if set(truth)-{row['id'] for row in rows}:
            raise ValueError('Truth references a different evaluation query')
        for row in rows:
            vector = project(feature_vector(row), family_model['preprocessing'])
            ranked = sorted((math.dist(vector, family['feature_centre']), family['id'])
                            for family in family_model['families'])
            records.append(dict(example_id=row['id'], candidates=[dict(family_id=fid,distance=distance)
                for distance,fid in ranked], independent_truth=truth.get(row['id']),
                correct=None if row['id'] not in truth else bool(ranked and ranked[0][1] == truth[row['id']])))
        report = dict(model_id=model_id, model_revision=model['revision'], weights_digest=model['weights_digest'],
            manifest_digest=model['manifest_digest'], role=role, records=records,
            total=len(records), labeled=sum(row['correct'] is not None for row in records),
            correct=sum(row['correct'] is True for row in records),
            status='DESCRIPTOR_MECHANISM_ONLY_NOT_LAYOUT_OR_PRODUCTION_QUALIFICATION',
            scope='NO_FIT_OR_PREPROCESSING_UPDATE;NO_INDEPENDENT_TRUTH_IF_LABELS_ABSENT')
        report['digest']=digest(report)
        with self.store.transaction():
            if self.checked_model(model_id)[0] != model:
                raise ValueError('Model changed during evaluation')
            saved=self.store._write('DESIGN_EVALUATION',new_id(),report,0,'cross_work_descriptor_evaluated')
            if role=='HOLDOUT':
                self.store._write('DESIGN_HOLDOUT_EXPOSURE',new_id(),dict(model_id=model_id,
                    manifest_digest=model['manifest_digest'],evaluation_id=saved['id'],actor='CORE_EVALUATOR',
                    refitting_this_sealed_version_forbidden=True),0,'design_holdout_exposure_recorded')
            return saved

    def activate(self, model_id, expected_active_revision, actor, policy, approved=False):
        if approved is not True:
            raise ValueError('Model activation/rollback requires an explicit versioned policy decision')
        text(actor,'Activation actor',120);text(policy.get('version'),'Policy version',128)
        text(policy.get('basis'),'Policy basis',2048)
        with self.store.transaction():
            model,_=self.checked_model(model_id)
            if not model['artifact']['family_model']['families']:
                raise ValueError('No independently supported shared family')
            if policy.get('production') is True:
                if model['formal_qualification']!='PASS':raise ValueError('Production activation needs actual independent layout/asset/source qualification')
                from .design_qualification import validate_certificate
                validate_certificate(self.library,model)
            return self.store._write(ACTIVE,'local-layout',dict(model_id=model_id,
                model_revision=model['revision'],weights_digest=model['weights_digest'],
                manifest_digest=model['manifest_digest'],policy=dict(deepcopy(policy),approved=True),actor=actor,
                scope='PRODUCTION' if policy.get('production') is True else 'EXPLORATORY_PREVIEW_ONLY'),
                expected_active_revision,'cross_work_model_activated_or_rolled_back')

    def active(self):
        row=self.store.get(ACTIVE,'local-layout')
        if not row:return None,dict(state='NONE')
        try:
            model,_=self.checked_model(row['model_id'])
            if model['revision']!=row['model_revision'] or model['weights_digest']!=row['weights_digest']:
                raise ValueError('Active model version differs')
            if row['policy'].get('production') is True:
                from .design_qualification import validate_certificate
                validate_certificate(self.library,model)
            return model,dict(row,state='ACTIVE')
        except (ValueError,OSError) as error:
            return None,dict(state='STALE',model_id=row['model_id'],reason=str(error))

    def feedback(self, before_ref, intent, after_ref, accepted, scope, actor, reason=None):
        if scope not in ('ORDER','PERSON','COMPANY','FAMILY') or type(accepted) is not bool:
            raise ValueError('Feedback needs a typed acceptance and explicit scope')
        text(actor,'Feedback actor',120)
        if reason is not None:text(reason,'Feedback reason',2048)
        if not all(isinstance(value,dict) and value for value in (before_ref,intent,after_ref)):
            raise ValueError('Feedback must retain before,intent and after references')
        with self.store.transaction():
            return self.store._write('DESIGN_FEEDBACK',new_id(),dict(before=deepcopy(before_ref),
                intent=deepcopy(intent),after=deepcopy(after_ref),accepted=accepted,scope=scope,
                actor=actor,reason=reason,reason_status='KNOWN' if reason else 'UNKNOWN',
                global_policy_changed=False,reference_status='UNVERIFIED_EXTERNAL_REPORT',preference_eligible=False,created=time.time()),0,'scoped_design_feedback_recorded')
