"""Typed professional rule drafts. Source observations and fitted weights stay immutable."""
from copy import deepcopy
import math

from .family_workspace import FamilyWorkspace, profile_differences
from .training_store import digest, text
from .model import new_id

METRICS = {'left_delta', 'right_delta', 'centre_delta', 'vertical_gap', 'horizontal_gap', 'baseline_delta'}
OPERATIONS = {'DEFAULT_ORDER', 'DEFAULT_SEMANTIC', 'CONTAINER_TYPES', 'OPTIONAL_ROLES',
              'ALLOWED_PATTERNS', 'PREFER_STYLE', 'RELATION_STRENGTH'}


def relation_key(left, right, metric):
    return digest([left, right, metric])


def apply_rule(profile, operation):
    if not isinstance(operation, dict) or operation.get('kind') not in OPERATIONS:
        raise ValueError('Choose a supported, typed family rule operation')
    result = deepcopy(profile)
    kind = operation['kind']; roles = {r['key']: r for r in result['roles']}
    if kind == 'DEFAULT_ORDER':
        order = operation.get('order')
        if not isinstance(order, list) or len(order) != len(roles) or set(order) != set(roles):
            raise ValueError('Default order must contain every role exactly once')
        result['grammar']['default_order'] = list(order)
        result['grammar']['default_basis'] = 'EXPLICIT_VERSIONED_PROFESSIONAL_PREFERENCE'
        result['editor_default_order'] = True
    elif kind == 'DEFAULT_SEMANTIC':
        key, semantic = operation.get('role'), operation.get('semantic')
        if key not in roles:
            raise ValueError('Unknown role')
        allowed = {s['semantic_type'] for data in result['data_requirement_profiles']
                   for s in data['presentation_evidence'] if s['role_key'] == key}
        if semantic not in allowed:
            raise ValueError('Default semantic has no source-supported correspondence for this role')
        result['grammar'].setdefault('default_semantic_roles', {})[key] = semantic
    elif kind == 'CONTAINER_TYPES':
        key, values = operation.get('container'), operation.get('types')
        container = next((c for c in result['field_capability_profiles'] if c['container_key'] == key), None)
        if (container is None or not isinstance(values, list) or not values
                or len(set(values)) != len(values) or not set(values) <= set(container['observed_semantic_types'])):
            raise ValueError('Container restrictions must use source-observed semantic types')
        result.setdefault('editor_container_types', {})[key] = sorted(values)
    elif kind == 'OPTIONAL_ROLES':
        values = operation.get('roles')
        supported = {r['key'] for r in result['roles'] if r['observed_optional']}
        if not isinstance(values, list) or len(set(values)) != len(values) or not set(values) <= supported:
            raise ValueError('Optional roles need observed source optionality')
        result['grammar']['optional_roles'] = sorted(values)
        result['grammar']['editor_required_roles'] = sorted(set(roles)-set(values))
    elif kind == 'ALLOWED_PATTERNS':
        values = operation.get('patterns')
        supported = {digest(r['pattern']): r for r in result['grammar']['observed_joint_counts']}
        if not isinstance(values, list) or not values or len(set(values)) != len(values) or not set(values) <= set(supported):
            raise ValueError('Choose a nonempty subset of source-observed joint field patterns')
        result['grammar']['editor_allowed_patterns'] = sorted(values)
    elif kind == 'PREFER_STYLE':
        key, source = operation.get('role'), operation.get('source_example')
        supported = [s for data in result['data_requirement_profiles'] for s in data['presentation_evidence']
                     if s['role_key'] == key and s['example_id'] == source]
        if not supported or any(not s.get('source_font_ref') or s['joint']['source_pt'] is None for s in supported):
            raise ValueError('Preferred joint style needs verified source typography')
        result.setdefault('editor_preferred_sources', {})[key] = source
    elif kind == 'RELATION_STRENGTH':
        left, right, metric = operation.get('left'), operation.get('right'), operation.get('metric')
        strength = operation.get('strength')
        relation = next((r for r in result['relations'] if r['left'] == left and r['right'] == right), None)
        if left not in roles or right not in roles or roles[left]['owner_port'] != roles[right]['owner_port']:
            raise ValueError('Relation edits require existing same-owner roles')
        if relation is None or metric not in METRICS or strength not in ('OFF', 'SOFT', 'HARD'):
            raise ValueError('Unsupported relation edit')
        evidence = relation['residuals'].get(metric, {})
        value = evidence.get('centre')
        if (evidence.get('support', 0) < 5 or type(value) not in (float, int)
                or not math.isfinite(value) or not relation.get('source_refs')):
            raise ValueError('Relation needs at least five independent source-supported measurements')
        result.setdefault('editor_relation_strengths', {})[relation_key(left, right, metric)] = strength
    return result


def compile_rules(profile, operations, cursor=None):
    result = deepcopy(profile)
    cursor = len(operations) if cursor is None else cursor
    if type(cursor) is not int or not 0 <= cursor <= len(operations) or len(operations) > 200:
        raise ValueError('Invalid bounded rule edit history')
    for operation in operations[:cursor]:
        result = apply_rule(result, operation)
    return result


def add_relation_constraint(solver, expression, value, strength, default_strength):
    """Called from the existing solver; no second layout engine."""
    if strength == 'OFF':
        return False
    if strength == 'HARD':
        solver.addConstraint(expression == value)
    else:
        solver.addConstraint((expression == value) | default_strength)
    return True


class FamilyRuleDrafts:
    def __init__(self, library):
        self.workspace = FamilyWorkspace(library)
        self.library = library
        self.store = self.workspace.store

    def create(self, ref, actor, name='Family rule draft', *, draft_id=None):
        self.workspace.resolve(ref)
        text(actor, 'Rule author', 120); text(name, 'Rule name', 120)
        with self.store.transaction():
            self.workspace.resolve(ref)
            return self.store._write('FAMILY_DRAFT', draft_id or new_id(), dict(base_ref=deepcopy(ref), actor=actor,
                name=name, state='DRAFT', operations=[], cursor=0, content_digest=digest([])),
                0, 'professional_family_rule_draft_created')

    def current(self, identity, expected_revision=None):
        row = self.store.get('FAMILY_DRAFT', identity)
        if not row or expected_revision is not None and row['revision'] != expected_revision:
            raise ValueError('Rule draft is missing or its revision changed')
        if row['state'] == 'ARCHIVED':
            raise ValueError('Rule draft is archived')
        self.workspace.resolve(row['base_ref'])
        if digest(row['operations'][:row['cursor']]) != row['content_digest']:
            raise ValueError('Rule history content differs')
        return row

    def compiled(self, identity, expected_revision=None):
        row = self.current(identity, expected_revision)
        model, dataset, profile = self.workspace.resolve(row['base_ref'])
        return row, model, dataset, compile_rules(profile, row['operations'], row['cursor'])

    def command(self, identity, expected_revision, request_id, action, actor, operation=None):
        text(request_id, 'Rule request', 128); text(actor, 'Rule author', 120)
        if action not in ('APPLY', 'UNDO', 'REDO'):
            raise ValueError('Unsupported draft command')
        command_id = digest([identity, request_id]); body_digest = digest([action, operation, actor])
        with self.store.transaction():
            prior = self.store.get('FAMILY_EDIT_COMMAND', command_id)
            if prior:
                if prior['body_digest'] != body_digest:
                    raise ValueError('Rule request ID already refers to a different command')
                current = self.current(identity)
                return dict(current, replayed=True, original_revision=prior['result_revision'])
            row, _, _, _ = self.compiled(identity, expected_revision)
            body = {k:deepcopy(v) for k,v in row.items() if k not in ('id', 'revision')}
            if action == 'APPLY':
                if row['cursor'] >= 200:
                    raise ValueError('Rule draft edit budget reached;create an explicit candidate/rebase')
                body['operations'] = body['operations'][:row['cursor']]+[deepcopy(operation)]
                body['cursor'] += 1
            elif action == 'UNDO':
                if body['cursor'] == 0:
                    raise ValueError('No rule edit to undo')
                body['cursor'] -= 1
            else:
                if body['cursor'] == len(body['operations']):
                    raise ValueError('No rule edit to redo')
                body['cursor'] += 1
            _, _, source = self.workspace.resolve(row['base_ref'])
            compile_rules(source, body['operations'], body['cursor'])
            body['content_digest'] = digest(body['operations'][:body['cursor']]); body['actor'] = actor
            saved = self.store._write('FAMILY_DRAFT', identity, body, expected_revision, 'family_rule_'+action.lower())
            self.store._write('FAMILY_EDIT_COMMAND', command_id,
                              dict(draft_id=identity, body_digest=body_digest, result_revision=saved['revision']),
                              0, 'idempotent_family_edit_command')
            return saved

    def differences(self, identity):
        row, _, _, profile = self.compiled(identity)
        _, _, original = self.workspace.resolve(row['base_ref'])
        return profile_differences(original, profile)

    def rebase(self, identity, new_ref, actor):
        old = self.current(identity)
        _, _, profile = self.workspace.resolve(new_ref)
        operations = old['operations'][:old['cursor']]
        compile_rules(profile, operations)
        with self.store.transaction():
            self.current(identity, old['revision']); self.workspace.resolve(new_ref)
            return self.store._write('FAMILY_DRAFT', new_id(), dict(base_ref=deepcopy(new_ref), actor=actor,
                name=old['name']+' (rebased)', state='DRAFT', operations=deepcopy(operations), cursor=len(operations),
                content_digest=digest(operations), rebased_from=dict(id=identity, revision=old['revision'])),
                0, 'family_rule_rebased_with_original_preserved')

    def create_candidate(self, identity, expected_revision, actor, approved=False):
        """Create a PENDING model, never publish a draft as a production template."""
        if approved is not True:
            raise ValueError('Explicit review of the rule differences is required')
        text(actor, 'Candidate author', 120)
        with self.store.transaction():
            row, base, _, profile = self.compiled(identity, expected_revision)
            if not self.differences(identity):
                raise ValueError('No effective rule changes')
            key = digest([identity, expected_revision, row['content_digest']])
            prior = self.store.get('FAMILY_CANDIDATE', key)
            if prior:
                return self.workspace.learning.checked_model(prior['model_id'])[0]
            body = {k:deepcopy(v) for k,v in base.items()
                    if k not in ('id', 'revision', 'qualification_id', 'formal_qualification', 'evaluation_ids')}
            artifact = body['artifact']; profiles = artifact['profile_model']
            profiles['families'] = [profile if p['family_id'] == profile['family_id'] else p for p in profiles['families']]
            profiles['digest'] = digest({k:v for k,v in profiles.items() if k != 'digest'})
            body.update(state='PENDING', actor=actor, weights_digest=digest(artifact), formal_qualification='NOT_EVALUATED',
                        evaluation_ids=[], origin_job=None, previous_model_id=base['id'],
                        family_rule_revision=dict(draft_id=identity, revision=expected_revision,
                                                  content_digest=row['content_digest'], base_ref=row['base_ref']))
            saved = self.store._write('DESIGN_MODEL', new_id(), body, 0, 'edited_family_rules_candidate_not_activated')
            self.store._write('FAMILY_CANDIDATE', key, dict(model_id=saved['id'], draft_id=identity,
                              draft_revision=expected_revision, weights_digest=saved['weights_digest']),
                              0, 'family_candidate_reference_saved')
            return saved
