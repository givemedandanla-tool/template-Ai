from copy import deepcopy
from family_fixture import FamilyFixture
from template_ai.family_rules import apply_rule, compile_rules, relation_key
from template_ai.training_store import digest


class FamilyRuleTests(FamilyFixture):
    def test_persistent_draft_undo_redo_and_branch_preserve_original_model(self):
        draft = self.draft(); original = deepcopy(self.current_model)
        draft = self.apply(draft, self.reorder())
        compiled = self.rules.compiled(draft['id'])[3]
        self.assertEqual(compiled['grammar']['default_order'], self.reorder()['order'])
        draft = self.rules.command(draft['id'], draft['revision'], 'undo', 'UNDO', 'Reviewer')
        self.assertEqual(self.rules.compiled(draft['id'])[3], self.profile)
        draft = self.rules.command(draft['id'], draft['revision'], 'redo', 'REDO', 'Reviewer')
        self.assertTrue(self.rules.differences(draft['id']))
        self.assertEqual(self.workspace.store.get('DESIGN_MODEL', self.model['id']), original)
        self.assertEqual(self.rules.current(draft['id'])['cursor'], 1)

    def test_command_is_idempotent_and_stale_commands_cannot_overwrite_manual_edits(self):
        draft = self.draft(); operation = self.reorder()
        first = self.apply(draft, operation)
        replay = self.apply(draft, operation)
        self.assertEqual(first['revision'], replay['revision'])
        self.assertTrue(replay['replayed'])
        with self.assertRaises(ValueError):
            self.rules.command(draft['id'], draft['revision'], 'other', 'APPLY', 'Reviewer', operation)
        with self.assertRaises(ValueError):
            self.rules.command(draft['id'], first['revision'], 'request', 'UNDO', 'Reviewer')

    def test_typed_operations_cannot_invent_roles_semantics_styles_or_patterns(self):
        key = self.profile['roles'][0]['key']
        invalid = [dict(kind='DEFAULT_ORDER', order=[key]),
                   dict(kind='DEFAULT_SEMANTIC', role=key, semantic='invented'),
                   dict(kind='CONTAINER_TYPES', container='invented', types=['email']),
                   dict(kind='OPTIONAL_ROLES', roles=['p99:name:0']),
                   dict(kind='ALLOWED_PATTERNS', patterns=['fabricated']),
                   dict(kind='PREFER_STYLE', role=key, source_example='fabricated'),
                   dict(kind='WRITE_WEIGHTS', coefficients=[1])]
        draft = self.draft(); epoch = self.workspace.store.epoch
        for i, operation in enumerate(invalid):
            with self.assertRaises(ValueError):
                self.apply(draft, operation, str(i))
        self.assertEqual(self.workspace.store.epoch, epoch)
        self.assertEqual(self.rules.current(draft['id'])['revision'], draft['revision'])

    def test_source_supported_joint_preference_and_pattern_subset_compile_without_refitting(self):
        data = self.profile['data_requirement_profiles'][0]['presentation_evidence'][0]
        operation = dict(kind='PREFER_STYLE', role=data['role_key'], source_example=data['example_id'])
        compiled = apply_rule(self.profile, operation)
        self.assertEqual(compiled['roles'], self.profile['roles'])
        self.assertEqual(compiled['editor_preferred_sources'][data['role_key']], data['example_id'])
        pattern = self.profile['grammar']['observed_joint_counts'][0]['pattern']
        compiled = apply_rule(compiled, dict(kind='ALLOWED_PATTERNS', patterns=[digest(pattern)]))
        self.assertEqual(compiled['grammar']['editor_allowed_patterns'], [digest(pattern)])

    def test_candidate_is_new_pending_version_and_never_inherits_production_qualification(self):
        draft = self.apply(self.draft(), self.reorder())
        with self.assertRaises(ValueError):
            self.rules.create_candidate(draft['id'], draft['revision'], 'Reviewer')
        candidate = self.rules.create_candidate(draft['id'], draft['revision'], 'Reviewer', True)
        self.assertNotEqual(candidate['id'], self.model['id'])
        self.assertEqual(candidate['formal_qualification'], 'NOT_EVALUATED')
        self.assertEqual(candidate['state'], 'PENDING')
        self.assertNotIn('qualification_id', candidate)
        self.assertNotEqual(candidate['weights_digest'], self.model['weights_digest'])
        self.assertEqual(self.rules.create_candidate(draft['id'], draft['revision'], 'Reviewer', True)['id'], candidate['id'])
        self.workspace.learning.checked_model(candidate['id'])
        self.assertEqual(len(self.library.templates()), 0)

    def test_rebase_preserves_original_and_invalid_new_family_ref_is_refused(self):
        draft = self.apply(self.draft(), self.reorder())
        rebased = self.rules.rebase(draft['id'], self.ref, 'Reviewer')
        self.assertNotEqual(rebased['id'], draft['id'])
        self.assertEqual(self.rules.compiled(rebased['id'])[3], self.rules.compiled(draft['id'])[3])
        self.assertEqual(self.rules.current(draft['id'])['revision'], draft['revision'])
        with self.assertRaises(ValueError):
            self.rules.rebase(draft['id'], dict(self.ref, family_id='absent'), 'Reviewer')

    def test_relation_strength_requires_source_support_and_same_owner(self):
        relation = next(r for r in self.profile['relations'] if r['support'] >= 5)
        metric = next(k for k,v in relation['residuals'].items() if v.get('support',0) >= 5 and v.get('centre') is not None)
        operation = dict(kind='RELATION_STRENGTH', left=relation['left'], right=relation['right'], metric=metric, strength='OFF')
        compiled = apply_rule(self.profile, operation)
        self.assertEqual(compiled['editor_relation_strengths'][relation_key(relation['left'],relation['right'],metric)], 'OFF')
        weak = deepcopy(self.profile)
        next(r for r in weak['relations'] if r['left'] == relation['left'] and r['right'] == relation['right'])['residuals'][metric]['support'] = 0
        with self.assertRaises(ValueError):
            apply_rule(weak, operation)
