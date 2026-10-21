"""Independent negative examples for the meaning of a qualified capacity region.

An aggregate success rate cannot turn an explicitly unqualified demand into
positive support. Synthetic validation records; no real-corpus quality claim.
"""
from copy import deepcopy
import unittest

from template_ai.design_capacity import fit_capacity, capacity_advice
from template_ai.training_store import digest


class QualifiedCapacityMeaningTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(family_id='authored-family',font_signature='authored-face',
                            field_count=2,width_mm=90.,height_mm=54.)
        self.policy = dict(version='noncode-authored-capacity-1',minimum_independent_groups=5,
                           minimum_success_lower_bound=.8,alpha=.05,bin_widths=[20.,10.],
                           maximum_support_distance=.25)

    def record(self, identity, demand, *, style=True, layout=True):
        return dict(id=identity,lineage_group=identity,role='VALIDATION',context=deepcopy(self.context),
                    demand=list(demand),layout_pass=layout,qualified_style=style,
                    evidence_refs=['Human-authored positive/negative expectation'])

    def positives(self):
        return [self.record('qualified-'+str(i),[2.+i%2,2.]) for i in range(60)]

    def test_known_unqualified_outlier_cannot_expand_suitable_region(self):
        records=self.positives()+[self.record('explicitly-unqualified',[18.,2.],style=False)]
        model=fit_capacity(records,self.policy)
        self.assertEqual(capacity_advice(model,self.context,[2.,2.])['status'],
                         'WITHIN_VALIDATED_EMPIRICAL_REGION')
        self.assertEqual(capacity_advice(model,self.context,[18.,2.])['status'],
                         'UNKNOWN_OR_OUTSIDE_VALIDATED_REGION')

    def test_known_layout_failure_inside_otherwise_supported_region_abstains(self):
        records=self.positives()+[self.record('known-layout-failure',[2.5,2.],layout=False)]
        model=fit_capacity(records,self.policy)
        self.assertEqual(capacity_advice(model,self.context,[2.5,2.])['status'],
                         'UNKNOWN_OR_OUTSIDE_VALIDATED_REGION')

    def test_conflicting_outcomes_at_same_measured_demand_do_not_claim_certainty(self):
        records=self.positives()+[self.record('conflicting-review',[2.,2.],style=False)]
        model=fit_capacity(records,self.policy)
        self.assertEqual(capacity_advice(model,self.context,[2.,2.])['status'],
                         'UNKNOWN_OR_OUTSIDE_VALIDATED_REGION')
        self.assertEqual(capacity_advice(model,self.context,[3.,2.])['status'],
                         'WITHIN_VALIDATED_EMPIRICAL_REGION')

    def test_old_artifact_without_negative_support_contract_needs_recalibration(self):
        model=fit_capacity(self.positives(),self.policy)
        model['version']='conditional-capacity-calibration-1'
        model['digest']=digest({k:v for k,v in model.items() if k!='digest'})
        with self.assertRaisesRegex(ValueError,'changed or incompatible'):
            capacity_advice(model,self.context,[2.,2.])
