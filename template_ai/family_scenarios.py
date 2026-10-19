"""Persistent local scenario inputs and actual shaped-layout comparisons.

Cases are engineering checks, not TRAIN labels or independent aesthetic truth.
"""
from copy import deepcopy
import math

from .family_rules import FamilyRuleDrafts
from .family_workspace import FamilyWorkspace
from .input_graph import InputGraph
from .design_session import DesignSessions, _serialize, _candidate
from .design_synthesis import synthesize
from .design_evaluation import check_layout
from .candidate_risk import placement_digest, engine_digest
from .training_store import digest, text
from .model import new_id


def preview_policy(policy=None):
    policy = deepcopy(policy or dict(version='family-scenarios-1', approved=True,
                                    enable_joint_prediction=True, candidate_budget=32))
    if policy.get('approved') is not True or not policy.get('version'):
        raise ValueError('Scenario needs an explicit versioned preview policy')
    policy['production'] = False
    return policy


class FamilyScenarios:
    def __init__(self, library):
        self.library = library
        self.workspace = FamilyWorkspace(library)
        self.rules = FamilyRuleDrafts(library)
        self.store = self.workspace.store

    def save(self, ref, name, graph, width, height, actor, *, intents=None,
             policy=None, case_id=None, expected_revision=0):
        self.workspace.resolve(ref); graph.validate(graph.data)
        text(name, 'Scenario name', 120); text(actor, 'Scenario author', 120)
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 2000 for v in (width, height)):
            raise ValueError('Scenario physical size is invalid')
        intents = deepcopy(intents or [])
        from .design_synthesis import _relation_graph, input_facts
        _relation_graph(intents, {f['render_id'] for f in input_facts(graph)})
        with self.store.transaction():
            self.workspace.resolve(ref)
            return self.store._write('FAMILY_CASE', case_id or new_id(), dict(ref=deepcopy(ref), name=name,
                input_graph=deepcopy(graph.data), width_mm=width, height_mm=height, intents=intents,
                policy=preview_policy(policy), actor=actor, role='ENGINEERING_CASE_NOT_TRAIN_GOLD'),
                expected_revision, 'local_family_scenario_saved')

    def current(self, case_id, expected_revision=None):
        case = self.store.get('FAMILY_CASE', case_id)
        if not case or expected_revision is not None and case['revision'] != expected_revision:
            raise ValueError('Scenario is missing or its inputs changed')
        self.workspace.resolve(case['ref'])
        InputGraph.validate(case['input_graph'])
        return case

    def run(self, case_id, expected_revision, *, draft_id=None, draft_revision=None, request_id=None):
        case = self.current(case_id, expected_revision)
        _, _, profile = self.workspace.resolve(case['ref'])
        draft_ref = None
        if draft_id:
            draft, _, _, profile = self.rules.compiled(draft_id, draft_revision)
            if draft['base_ref'] != case['ref']:
                raise ValueError('Scenario and draft refer to different family versions')
            draft_ref = dict(id=draft_id, revision=draft['revision'], content_digest=draft['content_digest'])
        identity = 'family-run-'+digest([request_id or new_id(), case_id, case['revision'], draft_ref, engine_digest()])[:40]
        previous = self.store.get('FAMILY_RUN', identity)
        if previous:
            return self.checked(previous['id'])
        graph = InputGraph(case['input_graph'])
        logos = DesignSessions(self.library).resolve_logos(graph, case['width_mm'], case['height_mm'])
        result = synthesize(profile, graph, case['width_mm'], case['height_mm'], preview_policy(case['policy']), case['intents'], logos)
        candidates = []
        for item in result['candidates']:
            candidate = item['candidate']
            integrity = check_layout(candidate, graph, case['intents'])
            if integrity['status'] == 'PASS':
                candidates.append((placement_digest(candidate), candidate, integrity))
        selected = candidates[0] if candidates else None
        status = ('FEASIBLE_PREVIEW' if selected else 'SEARCH_BUDGET_EXHAUSTED'
                  if not result.get('complete_search', True) and result['searched'] >= case['policy'].get('candidate_budget',32)
                  else 'HARD_CHECK_FAILED' if result['candidates'] else result['status'])
        value = dict(ref=deepcopy(case['ref']), case_ref=dict(id=case_id, revision=case['revision'], digest=digest(case)),
            draft_ref=draft_ref, engine_digest=engine_digest(), status=status,
            synthesis_status=result['status'], issues=deepcopy(result['issues']),
            searched=result['searched'], complete_search=result['complete_search'],
            placement_digest=selected[0] if selected else None,
            candidate=_serialize(selected[1]) if selected else None,
            integrity=selected[2] if selected else None,
            observed_legal_results=len(candidates), global_optimality_proven=False,
            production=False, aesthetic_qualification=False, training_labels_created=0)
        value['content_digest'] = digest(value)
        with self.store.transaction():
            self.current(case_id, expected_revision)
            if draft_ref:
                self.rules.current(draft_id, draft_ref['revision'])
            if engine_digest() != value['engine_digest']:
                raise ValueError('Layout engine changed while scenario was running')
            return self.store._write('FAMILY_RUN', identity, value, 0, 'actual_family_layout_scenario_checked')

    def checked(self, run_id):
        run = self.store.get('FAMILY_RUN', run_id)
        if not run or digest({k:v for k,v in run.items() if k not in ('id','revision','content_digest')}) != run['content_digest']:
            raise ValueError('Scenario result is missing or changed')
        case = self.current(run['case_ref']['id'], run['case_ref']['revision'])
        if digest(case) != run['case_ref']['digest'] or engine_digest() != run['engine_digest']:
            raise ValueError('Scenario inputs or engine are stale')
        if run['draft_ref']:
            self.rules.current(run['draft_ref']['id'], run['draft_ref']['revision'])
        return run

    def candidate(self, run_id):
        run = self.checked(run_id)
        if not run['candidate']:
            raise ValueError('This scenario has no verified preview layout')
        candidate = _candidate(run['candidate'])
        case = self.current(run['case_ref']['id'])
        if placement_digest(candidate) != run['placement_digest'] or check_layout(candidate, InputGraph(case['input_graph']), case['intents'])['status'] != 'PASS':
            raise ValueError('Stored scenario geometry no longer verifies')
        return candidate

    def compare(self, case_id, revision, draft_id, draft_revision):
        before = self.run(case_id, revision)
        after = self.run(case_id, revision, draft_id=draft_id, draft_revision=draft_revision)
        return dict(before=before, after=after,
                    same_placement=before['placement_digest'] == after['placement_digest'],
                    both_actual_layouts_pass=bool(before['integrity'] and after['integrity']),
                    aesthetic_winner='NOT_REVIEWED')
