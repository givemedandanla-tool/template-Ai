from copy import deepcopy
from family_fixture import FamilyFixture
from template_ai.family_scenarios import FamilyScenarios
from template_ai.family_batch import FamilyBatches, execute_family_item
from template_ai.design_jobs import run_design_job
from template_ai.input_graph import InputGraph


class FamilyScenarioBatchTests(FamilyFixture):
    def setUp(self):
        super().setUp()
        self.scenarios = FamilyScenarios(self.library)
        self.batches = FamilyBatches(self.library)
        self.graph = InputGraph.from_legacy([dict(name='Alex Example', title='Designer',
                    phone='+1 202 555 0100', email='alex@example.test')], [])

    def case(self):
        return self.scenarios.save(self.ref, 'Authored case', self.graph, 90, 54, 'Reviewer')

    def run_job(self, job, cancel=None):
        claimed = self.batches.jobs.claim(job['id'], job['revision'])
        return run_design_job(self.library.root, job['id'], claimed['owner']['token'], cancel)

    def test_actual_source_case_shapes_checks_and_repeats_exactly_without_training(self):
        case = self.case(); model = deepcopy(self.current_model)
        first = self.scenarios.run(case['id'], case['revision'])
        second = self.scenarios.run(case['id'], case['revision'])
        self.assertEqual(first['status'], 'FEASIBLE_PREVIEW')
        self.assertEqual(first['placement_digest'], second['placement_digest'])
        self.assertEqual(first['integrity']['status'], 'PASS')
        self.assertFalse(first['production']); self.assertFalse(first['aesthetic_qualification'])
        self.assertEqual(first['training_labels_created'], 0)
        self.scenarios.candidate(first['id'])
        self.assertEqual(self.workspace.store.get('DESIGN_MODEL', model['id']), model)

    def test_case_change_and_draft_change_invalidate_current_results_but_preserve_history(self):
        case = self.case(); draft = self.apply(self.draft(), self.reorder())
        result = self.scenarios.run(case['id'], case['revision'], draft_id=draft['id'], draft_revision=draft['revision'])
        self.assertEqual(result['status'], 'FEASIBLE_PREVIEW')
        self.rules.command(draft['id'], draft['revision'], 'undo-case', 'UNDO', 'Reviewer')
        with self.assertRaises(ValueError):self.scenarios.checked(result['id'])
        self.assertIsNotNone(self.workspace.store.get('FAMILY_RUN', result['id']))
        self.scenarios.save(self.ref, 'changed', self.graph, 90, 54, 'Reviewer', case_id=case['id'], expected_revision=case['revision'])
        with self.assertRaises(ValueError):self.scenarios.run(case['id'], case['revision'])

    def test_case_input_validation_preview_only_and_request_idempotency(self):
        case = self.case()
        first = self.scenarios.run(case['id'], case['revision'], request_id='stable')
        self.assertEqual(first['id'], self.scenarios.run(case['id'], case['revision'], request_id='stable')['id'])
        with self.assertRaises(ValueError):self.scenarios.save(self.ref, 'bad', self.graph, float('nan'), 54, 'Reviewer')
        forced = self.scenarios.save(self.ref, 'preview', self.graph, 90, 54, 'Reviewer', policy=dict(version='author',approved=True,production=True))
        self.assertFalse(forced['policy']['production'])

    def test_batch_preview_mixed_eligibility_cancel_resume_and_local_undo(self):
        stale = dict(self.ref, family_digest='stale')
        plan = self.batches.plan_rules([self.ref, stale], self.reorder())
        self.assertEqual([r['precheck'] for r in plan['items']], ['READY','BLOCKED'])
        with self.assertRaises(ValueError):self.batches.submit(plan, 'Reviewer')
        job = self.batches.submit(plan, 'Reviewer', True)
        paused = self.run_job(job, lambda:True)
        self.assertEqual(paused['phase'], 'PAUSED'); self.assertEqual(paused['next_index'], 0)
        done = self.run_job(paused)
        self.assertEqual(done['phase'], 'COMPLETE')
        results = self.batches.jobs.results(done['id'])
        self.assertEqual(results[0]['status'], 'APPLIED')
        self.assertIn(results[1]['status'], ('STALE_OR_BLOCKED','SKIPPED_BLOCKED'))
        self.assertEqual(execute_family_item(self.library, self.batches.jobs.current(done['id']), 0)['status'], 'ALREADY_APPLIED')
        undo = self.batches.undo(done['id'], 'Reviewer'); self.run_job(undo)
        self.assertEqual(self.rules.current(results[0]['draft_id'])['cursor'], 0)
        self.assertEqual(self.workspace.store.get('DESIGN_MODEL', self.model['id']), self.current_model)

    def test_batch_undo_preserves_later_manual_edits_and_plan_tampering_is_refused(self):
        plan = self.batches.plan_rules([self.ref], self.reorder())
        tampered = deepcopy(plan); tampered['items'][0]['operation']['order'].reverse()
        with self.assertRaises(ValueError):self.batches.submit(tampered, 'Reviewer', True)
        job = self.batches.submit(plan, 'Reviewer', True); self.run_job(job)
        result = self.batches.jobs.results(job['id'])[0]
        draft = self.rules.current(result['draft_id'])
        self.apply(draft, self.reorder(), 'manual-after-batch')
        undo = self.batches.undo(job['id'], 'Reviewer'); self.run_job(undo)
        self.assertEqual(self.batches.jobs.results(undo['id'])[0]['status'], 'STALE_OR_BLOCKED')
        self.assertEqual(self.rules.current(draft['id'])['cursor'], 2)

    def test_case_review_job_uses_actual_layout_and_reports_checks_without_qualification(self):
        case = self.case(); job = self.batches.cases([case['id']], 'Reviewer')
        done = self.run_job(job)
        self.assertEqual(done['phase'], 'COMPLETE')
        self.assertEqual(done['summary']['items'], 1)
        self.assertTrue(done['summary']['all_hard_checks_pass'])
        self.assertEqual(done['summary']['published_templates'], 0)
