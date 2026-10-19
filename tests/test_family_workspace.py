from copy import deepcopy
from family_fixture import FamilyFixture
from template_ai.family_workspace import records, validate_query, reference, profile_differences
from template_ai.training_store import digest


class FamilyWorkspaceTests(FamilyFixture):
    def test_readonly_family_projection_keeps_sources_templates_and_instances_distinct(self):
        epoch = self.workspace.store.epoch
        templates = len(self.library.templates())
        result = self.workspace.index(dict(model_id=self.model['id']))
        self.assertEqual(result['total'], len(self.current_model['artifact']['profile_model']['families']))
        row = result['rows'][0]
        self.assertEqual(row['kind'], 'LEARNED_FAMILY')
        self.assertEqual(row['people'], 1)
        self.assertEqual(row['ref'], self.ref)
        self.assertEqual(self.workspace.store.epoch, epoch)
        self.assertEqual(len(self.library.templates()), templates)
        self.assertEqual(result['actual_template_objects_created'], 0)

    def test_saved_workset_reopens_as_query_and_frozen_selection_stays_exact(self):
        view = self.workspace.save_view('本地工作集', dict(model_id=self.model['id']), 'Reviewer')
        self.assertEqual(self.workspace.open_view(view['id'])['rows'][0]['ref'], self.ref)
        frozen = self.workspace.freeze_selection([self.ref])
        self.assertEqual(frozen['digest'], digest([self.ref]))
        self.assertEqual(self.workspace.index(dict(model_id=self.model['id']), page=99)['rows'], [])
        with self.assertRaises(ValueError):
            self.workspace.save_view('stale', {}, 'Reviewer', view_id=view['id'], expected_revision=0)
        with self.assertRaises(ValueError):
            self.workspace.freeze_selection([self.ref, self.ref])

    def test_search_filters_semantic_physical_dimensions_and_unknown_without_sql(self):
        self.assertGreater(self.workspace.index(dict(model_id=self.model['id'], semantic='email', size=[90, 54], people=1))['total'], 0)
        self.assertEqual(self.workspace.index(dict(model_id=self.model['id'], size=[200, 100]))['total'], 0)
        for query in ({'sql':'DELETE'}, {'size':[float('nan'), 54]}, {'has_unknown':1}, {'people':True}):
            with self.assertRaises(ValueError):
                validate_query(query)
        self.assertEqual(self.workspace.index({'text':"' OR 1=1 --"})['total'], 0)

    def test_stale_or_fabricated_family_reference_cannot_open_or_freeze(self):
        for field in ('family_digest', 'weights_digest', 'manifest_digest', 'family_id'):
            stale = dict(self.ref, **{field:'changed'})
            with self.assertRaises(ValueError):
                self.workspace.resolve(stale)
        with self.assertRaises(ValueError):
            self.workspace.resolve(dict(self.ref, model_revision=self.ref['model_revision']+1))

    def test_representatives_preserve_independence_and_never_sample_validation_or_holdout(self):
        first = self.workspace.representatives(self.ref, 3)
        self.assertEqual(first, self.workspace.representatives(self.ref, 3))
        _, dataset, _ = self.workspace.resolve(self.ref)
        examples = {e['id']:e for e in dataset['manifest']['examples']}
        self.assertTrue(first['selected'])
        self.assertTrue(all(examples[r['example_id']]['role'] == 'TRAIN' for r in first['selected']))
        self.assertEqual(len({r['lineage_group'] for r in first['selected']}), len(first['selected']))
        self.assertFalse(first['aesthetic_qualification'])
        self.assertTrue(first['full_impacted_hard_checks_required'])

    def test_compare_is_readonly_and_impact_retains_accepted_bytes(self):
        self.assertEqual(self.workspace.compare(self.ref, self.ref)['differences'], [])
        draft = self.draft()
        impact = self.workspace.impact(self.ref, page_size=1)
        self.assertGreaterEqual(impact['total'], 2)
        self.assertEqual(len(impact['rows']), 1)
        self.assertFalse(impact['accepted_output_bytes_changed'])
        self.assertIn('FAMILY_DRAFT', impact['counts'])
        with self.assertRaises(ValueError):
            self.workspace.impact(self.ref, source_hashes=['not-in-model'])

    def test_existing_record_iterator_does_not_silently_stop_at_two_hundred(self):
        class Store:
            def records(self, kind, offset=0, limit=200):
                return list(range(451))[offset:offset+limit]
        self.assertEqual(list(records(Store(), 'AUTHORED')), list(range(451)))

    def test_functional_comparison_includes_joint_styles_grammar_and_relations(self):
        changed = deepcopy(self.profile)
        changed['grammar']['default_basis'] = 'reviewed'
        changed['editor_relation_strengths'] = {'relation':'OFF'}
        self.assertEqual({d['section'] for d in profile_differences(self.profile, changed)},
                         {'grammar', 'editor_relation_strengths'})
