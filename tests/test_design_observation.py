"""Synthetic mechanism tests; no original-AI/font recovery or trained-model claim."""
from copy import deepcopy
import math
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from template_ai.automatic_training import AutomaticTraining, run_automatic
from template_ai.design_observation import (
    DesignObservation, ObservationEdge, ObservationNode, ObservedScalar,
    effective_point_size,
)
from template_ai.storage import Library
from template_ai.training_pipeline import LIVE_OWNERS
from template_ai.training_store import TrainingStore
from training_fixture import source_work, observations

APP = QApplication.instance() or QApplication([])


class ObservationMetricTests(unittest.TestCase):
    def test_unknown_defaults_untraceable_and_nonfinite_metrics_rejected(self):
        self.assertIsNone(ObservedScalar(None, 'pt', 'UNKNOWN', 'No source').value)
        for value in (True, math.nan, math.inf, 10**1000):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(ValueError):
                    ObservedScalar(value, 'pt', 'OBSERVED', 'source', ('object:t',))
        for args in [(10, 'pt', 'UNKNOWN', 'default', ()),
                     (10, 'pt', 'OBSERVED', 'source', ()),
                     (10, 'px', 'OBSERVED', 'source', ('t',)),
                     (10, 'pt', 'OBSERVED', 'source', 't')]:
            with self.assertRaises(ValueError):
                ObservedScalar(*args)

    def test_uniform_rotation_and_scale_preserve_known_point_measurement(self):
        point = ObservedScalar(12, 'pt', 'OBSERVED', 'Synthetic source text', ('object:t',))
        result = effective_point_size(point, (0, 2, -2, 0, 100, -30))
        self.assertEqual((result.value, result.unit, result.status), (24, 'pt', 'DERIVED'))
        self.assertEqual(result.evidence_refs, point.evidence_refs)
        self.assertEqual(effective_point_size(point, (-1, 0, 0, 1, 0, 0)).value, 12)

    def test_anisotropy_shear_unknown_and_template_defaults_do_not_become_source_pt(self):
        point = ObservedScalar(12, 'pt', 'OBSERVED', 'source', ('object:t',))
        for matrix in [(2, 0, 0, 3, 0, 0), (1, 0, .3, 1, 0, 0), (0, 0, 0, 0, 0, 0)]:
            self.assertEqual(effective_point_size(point, matrix).status, 'UNKNOWN')
        default = ObservedScalar(10, 'pt', 'ANNOTATED', 'Slot design', ('work:slot',))
        self.assertIsNone(effective_point_size(default, (2, 0, 0, 2, 0, 0)).value)
        absent = ObservedScalar(None, 'pt', 'UNKNOWN', 'source missing')
        self.assertIsNone(effective_point_size(absent, (1, 0, 0, 1, 0, 0)).value)
        with self.assertRaises(ValueError):
            effective_point_size(point, (True, 0, 0, 1, 0, 0))

    def test_graph_rejects_duplicate_or_dangling_identity(self):
        node = ObservationNode('a', 'WORK_CONTAINER', {})
        with self.assertRaises(ValueError):
            DesignObservation({}, (node, node), ()).to_dict()
        with self.assertRaises(ValueError):
            DesignObservation({}, (node,), (ObservationEdge('a', 'missing', 'contains', {}),)).to_dict()
        with self.assertRaises(ValueError):
            ObservationNode('a', 'FAKE_KIND', {})


class DesignObservationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = Library(self.root/'data')
        self.source, self.work = source_work(self.library, self.root)
        self.source = self.library.source(self.source['id'])
        self.store = TrainingStore(self.library)
        self.facts = self.store.save_facts(self.work['id'], observations(self.work), 0, self.work['revision'])
        self.tokens = []

    def tearDown(self):
        for token in self.tokens:
            LIVE_OWNERS.discard(token)
        self.library.db.close()
        self.temp.cleanup()

    def save(self, work=None):
        work = work or self.work
        return self.store.save_design_observation(self.store.design_observation_plan(work['id']), 'Synthetic Reviewer')

    def confirm(self):
        self.facts = self.store.confirm_facts(self.work['id'],
            [r['id'] for r in self.facts['observations']], self.facts['revision'],
            self.facts['pins'], self.store.source_proof(self.work['id']), 'Synthetic Reviewer', True)

    def test_original_page_text_evidence_does_not_become_annotated_role_font_truth(self):
        graph = self.save()
        original = graph['original_text_evidence']
        self.assertEqual(original['channel'], 'ORIGINAL_SVG')
        self.assertEqual(original['scope'], 'SOURCE_PAGE_NOT_WORK_OR_FIELD')
        self.assertTrue(any(r['source_pt']['value'] is not None for r in original['runs']))
        self.assertTrue(all(r['font_asset_identity'] == 'UNKNOWN' for r in original['runs']))
        for node in graph['nodes']:
            if node['kind'] == 'FIELD_ROLE':
                self.assertEqual(node['properties']['typography']['source_pt']['status'], 'UNKNOWN')
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'CURRENT')

    def test_newly_confirmed_cross_file_lineage_stales_existing_observation_and_old_plan(self):
        from template_ai.quality_groups import QualityGroups
        first = self.save(); plan = self.store.design_observation_plan(self.work['id'])
        other, _ = source_work(self.library, self.root, name='revision.svg', note_text='Authored revision')
        groups = QualityGroups(self.library)
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'CURRENT')
        link = groups.link_plan('CONTENT:'+self.source['hash'], 'CONTENT:'+other['hash'],
            'NEAR_DUPLICATE', 'Authored related revision', 'Synthetic source author confirms relation')
        groups.confirm_link(link, 'Synthetic Reviewer', True)
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'STALE')
        with self.assertRaises(ValueError):
            self.store.save_design_observation(plan, 'Synthetic Reviewer')
        updated = self.save()
        self.assertEqual(updated['revision'], first['revision']+1)
        self.assertEqual(set(updated['lineage']['correlated_source_hashes']),
                         {self.source['hash'], other['hash']})
        self.assertEqual(updated['lineage']['unreviewed_near_duplicates'], 'UNKNOWN')

    def test_default_typography_not_learned_and_no_source_or_training_records_rewritten(self):
        raw = Path(self.source['current_path']).read_bytes()
        work, facts, epoch = deepcopy(self.work), deepcopy(self.facts), self.store.epoch
        plan = self.store.design_observation_plan(self.work['id'])
        self.assertEqual(self.store.epoch, epoch)  # Planning has no writes.
        saved = self.store.save_design_observation(plan, 'Synthetic Reviewer')
        text_nodes = [n for n in saved['nodes'] if n['kind'] == 'TEXT']
        self.assertTrue(text_nodes)
        for n in text_nodes + [n for n in saved['nodes'] if n['kind'] == 'FIELD_ROLE']:
            t = n['properties']['typography']
            self.assertIsNone(t['source_pt']['value'])
            self.assertEqual(t['source_pt']['unit'], 'pt')
            self.assertEqual(t['glyph_runs']['status'], 'UNKNOWN')
            self.assertEqual(t['alignment'], 'UNKNOWN')
        self.assertEqual(saved['qualification']['training_admission'], 'NOT_EVALUATED')
        self.assertEqual(saved['qualification']['facts_state'], 'PENDING')
        self.assertIsNone(saved['counts']['logical_data_count']['value'])
        self.assertNotIn('Alex Example', str(saved))  # Content is referenced, not duplicated.
        self.assertEqual(self.library.artwork(work['id']), work)
        self.assertEqual(self.store.facts(work['id']), facts)
        self.assertEqual(Path(self.source['current_path']).read_bytes(), raw)
        self.assertEqual(self.library.templates(), [])
        self.assertEqual(self.store.count('SAMPLE'), 0)
        self.assertEqual(self.store.design_observation_state(work['id']), 'CURRENT')

    def test_multi_size_same_source_has_distinct_scoped_nodes_and_one_content_group(self):
        payload = deepcopy(self.work['payload'])
        payload.update(work_width=45, work_height=27)
        other = self.library.create_artwork(self.source['id'], 'Second size', payload)
        a, b = self.save(), self.save(other)
        self.assertEqual(a['lineage']['source_content_group'], b['lineage']['source_content_group'])
        self.assertNotEqual(a['pins']['work_id'], b['pins']['work_id'])
        self.assertFalse({n['id'] for n in a['nodes']} & {n['id'] for n in b['nodes']})
        self.assertEqual(b['lineage']['cross_work_person_and_family_correspondence'], 'UNKNOWN')
        self.assertEqual(b['coordinate_systems']['work_size']['width_mm'], 45)
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'CURRENT')

    def test_people_remain_separate_and_can_reference_one_company_without_position_identity(self):
        payload = deepcopy(self.work['payload'])
        added = deepcopy(payload['slots'][0]); added.update(id='second-person-name', owner='p2')
        payload['slots'].append(added)
        payload['company_bindings'] = {'p1': ['c1'], 'p2': ['c1']}
        self.work = self.library.save_artwork(self.work['id'], payload, self.work['revision'])
        graph = self.save()
        people = [n for n in graph['nodes'] if n['kind'] == 'PERSON_GROUP']
        companies = [n for n in graph['nodes'] if n['kind'] == 'COMPANY_GROUP']
        self.assertEqual(len(people), 2); self.assertEqual(len(companies), 1)
        links = [e for e in graph['edges'] if e['kind'] == 'person_company']
        self.assertEqual(len(links), 2)
        self.assertEqual({e['target'] for e in links}, {companies[0]['id']})
        p2 = next(n['id'] for n in people if n['properties']['local_owner_ref'] == 'p2')
        role = next(n for n in graph['nodes'] if n['properties'].get('slot_ref') == 'second-person-name')
        self.assertTrue(any(e['source'] == role['id'] and e['target'] == p2 and e['kind'] == 'owned_by' for e in graph['edges']))
        payload['slots'].reverse()
        self.work = self.library.save_artwork(self.work['id'], payload, self.work['revision'])
        again = self.save()
        self.assertEqual({n['id'] for n in people}, {n['id'] for n in again['nodes'] if n['kind'] == 'PERSON_GROUP'})

    def test_source_crop_to_nominal_work_transform_is_not_a_font_transform(self):
        payload = dict(crop=dict(x=10, y=5, w=70, h=40), work_width=35, work_height=20,
                       slots=[], visual_confirmed=False)
        work = self.library.create_artwork(self.source['id'], 'Offset crop', payload)
        graph = self.save(work)
        a, b, c, d, tx, ty = graph['coordinate_systems']['source_to_work']
        self.assertEqual((a*10+c*5+tx, b*10+d*5+ty), (0, 0))
        self.assertEqual((a*80+c*45+tx, b*80+d*45+ty), (35, 20))
        self.assertIn('NOT_FONT_TRANSFORM', graph['coordinate_systems']['basis'])

    def test_idempotent_refresh_cas_history_and_reopen(self):
        original_plan = self.store.design_observation_plan(self.work['id'])
        first = self.store.save_design_observation(original_plan, 'Synthetic Reviewer')
        self.assertEqual(self.save()['revision'], first['revision'])
        self.assertEqual(len(self.store.history('DESIGN_OBSERVATION', self.work['id'])), 1)
        with self.assertRaises(ValueError):
            self.store.save_design_observation(original_plan, 'Stale writer')
        changed = deepcopy(self.facts['observations']); changed[0]['text'] = 'Synthetic corrected name'
        self.facts = self.store.save_facts(self.work['id'], changed, self.facts['revision'], self.work['revision'])
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'STALE')
        second = self.save()
        self.assertEqual(second['revision'], first['revision']+1)
        self.library.db.close(); self.library = Library(self.root/'data'); self.store = TrainingStore(self.library)
        self.assertEqual(self.store.design_observation(self.work['id']), second)
        self.assertEqual(len(self.store.history('DESIGN_OBSERVATION', self.work['id'])), 2)
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'CURRENT')

    def test_old_facts_are_not_relinked_after_work_revision_changes(self):
        first = self.save()
        payload = deepcopy(self.work['payload']); payload['slots'][0]['rect']['x'] += 1
        self.work = self.library.save_artwork(self.work['id'], payload, self.work['revision'])
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'STALE')
        second = self.save()
        self.assertEqual(second['facts_ref']['applicability'], 'STALE')
        self.assertEqual(second['counts']['stale_regions_not_relinked'], len(self.facts['observations']))
        self.assertFalse(any(n['kind'] == 'TEXT' for n in second['nodes']))
        self.assertTrue(any(n['kind'] == 'TEXT' for n in first['nodes']))

    def test_modified_original_or_derivative_invalidates_and_cannot_be_saved(self):
        first = self.save()
        for name in ('current_path', 'svg'):
            path = Path(self.source[name]); raw = path.read_bytes(); path.write_bytes(raw+b' ')
            self.assertEqual(self.store.design_observation_state(self.work['id']), 'STALE')
            with self.assertRaises(ValueError):
                self.save()
            self.assertEqual(self.store.design_observation(self.work['id']), first)
            path.write_bytes(raw)

    def test_noise_revision_stales_snapshot_but_excluded_region_is_preserved(self):
        self.confirm(); self.save()
        facts_before = self.store.facts(self.work['id'])
        self.store.local_noise(self.work['id'], ['note'], 0, self.facts['revision'], True)
        self.assertEqual(self.store.design_observation_state(self.work['id']), 'STALE')
        graph = self.save()
        note = next(n for n in graph['nodes'] if n['properties'].get('observation_ref') == 'note')
        self.assertEqual(note['properties']['noise_state'], 'EXCLUDED_LOCAL')
        self.assertEqual(self.store.facts(self.work['id']), facts_before)

    def test_transaction_failure_rolls_back_snapshot_history_and_epoch(self):
        plan = self.store.design_observation_plan(self.work['id']); epoch = self.store.epoch
        actual = self.library.event
        def fail(entity, action):
            if action == 'training_design_observation_recorded':
                raise RuntimeError('Synthetic audit failure')
            return actual(entity, action)
        with patch.object(self.library, 'event', side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.store.save_design_observation(plan, 'Synthetic Reviewer')
        self.assertIsNone(self.store.design_observation(self.work['id']))
        self.assertFalse(self.store.history('DESIGN_OBSERVATION', self.work['id']))
        self.assertEqual(self.store.epoch, epoch)
        self.assertEqual(self.store.facts(self.work['id']), self.facts)

    def test_oversized_role_budget_is_explicit_and_does_not_truncate(self):
        payload = deepcopy(self.work['payload']); slot = payload['slots'][0]
        payload['slots'] = [dict(deepcopy(slot), id='slot-'+str(i)) for i in range(513)]
        self.work = self.library.save_artwork(self.work['id'], payload, self.work['revision'])
        with self.assertRaisesRegex(ValueError, '未截斷'):
            self.store.design_observation_plan(self.work['id'])
        self.assertIsNone(self.store.design_observation(self.work['id']))

    def test_field_from_another_work_region_cannot_be_linked(self):
        payload = deepcopy(self.work['payload']); payload['crop']['w'] = 45; payload['work_width'] = 45
        work = self.library.create_artwork(self.source['id'], 'Narrow work', payload)
        row = deepcopy(observations(work)[0]); row['region'] = dict(x=70, y=10, w=10, h=5)
        self.store.save_facts(work['id'], [row], 0, work['revision'])
        with self.assertRaisesRegex(ValueError, '跨出本作品'):
            self.save(work)

    def test_automatic_work_records_references_and_reuses_without_creating_templates(self):
        service = AutomaticTraining(self.library)
        first, reused = service.process_work(self.work, {'actor': 'Synthetic worker'})
        self.assertFalse(reused)
        graph = self.store.design_observation(self.work['id'])
        self.assertEqual(first['design_observation_ref']['document_digest'], graph['document_digest'])
        second, reused = service.process_work(self.work, {'actor': 'Synthetic worker'})
        self.assertTrue(reused); self.assertEqual(first, second)
        self.assertEqual(self.library.templates(), [])
        self.assertEqual(len(self.store.history('DESIGN_OBSERVATION', self.work['id'])), 1)

    def test_late_automatic_unit_failure_rolls_back_observation_too(self):
        service = AutomaticTraining(self.library); actual = self.library.event
        def fail(entity, action):
            if action == 'training_automatic_work_analysed':
                raise RuntimeError('Synthetic late automatic failure')
            return actual(entity, action)
        with patch.object(self.library, 'event', side_effect=fail):
            with self.assertRaises(RuntimeError):
                service.process_work(self.work, {'actor': 'Synthetic worker'})
        self.assertIsNone(self.store.design_observation(self.work['id']))
        self.assertEqual(self.store.count('AUTO_UNIT'), 0)

    def test_cancel_resume_preserves_exact_observation_identity_and_history(self):
        service = AutomaticTraining(self.library)
        job = service.create(service.preflight([self.source['current_path']], compare=False), 'Synthetic worker', True)
        event = threading.Event(); event.set()
        def run(row, cancel=None):
            claimed = service.claim(row['id'], row['revision'], True)
            token = claimed['owner']['token']; self.tokens.append(token)
            return run_automatic(self.library.root, claimed['id'], token, cancel=cancel)
        cancelled = run(job, event)
        self.assertEqual(cancelled['phase'], 'CANCELLED')
        self.assertEqual(self.store.count('DESIGN_OBSERVATION'), 0)
        done = run(cancelled)
        first = self.store.design_observation(self.work['id'])
        self.assertIsNotNone(first)
        again = run(done)
        self.assertEqual(self.store.design_observation(self.work['id']), first)
        self.assertEqual(again['items'][0]['reused_units'], 1)
        self.assertEqual(len(self.store.history('DESIGN_OBSERVATION', self.work['id'])), 1)


if __name__ == '__main__':
    unittest.main()
