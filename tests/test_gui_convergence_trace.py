"""Original-parent link checks cannot turn document/registry claims into test PASS."""
from copy import deepcopy
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from gui_convergence import reconcile,traceability,DECISION_STATES


class GuiConvergenceTraceTests(unittest.TestCase):
    def registry(self):return json.loads((ROOT/'docs/dev/REQUIREMENTS.json').read_text())

    def test_completed_registry_claim_never_substitutes_for_current_source_evidence(self):
        r=self.registry();topic=next(x for x in r['requirements'] if x['kind']=='topic');topic['completed']=True;topic['status']='VERIFIED'
        row=next(x for x in reconcile(r)['rows'] if x['id']==topic['id'])
        self.assertTrue(row['registry_completion_claim']);self.assertFalse(row['fully_verified']);self.assertEqual(row['verification_state'],'REQUIRES_CURRENT_SOURCE_EVIDENCE_GATE')
        self.assertIn(row['decision_state'],DECISION_STATES)

    def test_duplicate_original_parent_or_missing_decision_source_is_refused(self):
        r=self.registry();topics=[x for x in r['requirements'] if x['kind']=='topic'];topics[1]['id']=topics[0]['id']
        with self.assertRaises(ValueError):reconcile(r)
        r=self.registry();next(x for x in r['requirements'] if x['kind']=='topic')['sources']=[]
        with self.assertRaises(ValueError):reconcile(r)

    def test_unapproved_report_unblock_and_broken_test_link_are_refused(self):
        r=self.registry();row=next(x for x in r['requirements'] if x['id']=='UI-066-R1');row['sources']=[]
        with self.assertRaises(ValueError):reconcile(r)
        r=self.registry();row=next(x for x in r['requirements'] if x['kind']=='topic');row['acceptance'][0]['tests'].append('test_no_actual_source.NoClass.test_no_behavior')
        with self.assertRaisesRegex(ValueError,'Unknown test link'):traceability(r)

    def test_actual_original75_have_exact_links_and_resolved_history_without_product_growth(self):
        r=traceability(self.registry());self.assertEqual(len(r['rows']),75);self.assertEqual(r['product_features_added'],0)
        self.assertEqual(r['formal_output_formats'],['PDF','PNG','JPG']);self.assertEqual(r['human_decisions'],[]);self.assertFalse(r['coverage_inference'])
        self.assertEqual({x['id'] for x in r['conflicts']},{'X-01','X-02','X-03','X-04','X-05','X-06'})
        self.assertTrue(all(x['resolution']=='RESOLVED' for x in r['conflicts']));self.assertTrue(r['research']);self.assertTrue(r['future_backlog'])
        for parent in ('UI-019','UI-031','UI-032','UI-066'):
            row=next(x for x in r['rows'] if x['id']==parent);self.assertTrue(row['exact_test_ids']);self.assertTrue(row['components_referenced_by_tests']);self.assertFalse(row['fully_verified'])
