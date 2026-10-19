from copy import deepcopy
import unittest

from template_ai.design_capacity import fit_capacity,capacity_advice
from template_ai.design_object_spacing import learn_object_spacing,apply_object_spacing
from template_ai.design_rank_qualification import rank_quality_errors
from template_ai.design_ranking import candidate_features
from template_ai.layout import Candidate,Placed
from template_ai.model import Template,Slot,Rect
import test_design_text_flow as flow_fixture


class WordJustificationTests(unittest.TestCase):
    setUp=flow_fixture.SourceConditionedFlowTests.setUp
    shape=flow_fixture.SourceConditionedFlowTests.shape

    def rule(self,last='NATURAL'):
        return dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['authored word boundaries'],mode='WORDS',
            value_mm=0.,allowed_scripts=['Latn'],boundary_policy='ASCII_SPACE_QT_WORD_SPACING',
            last_line=last,zero_boundaries='KEEP_NATURAL',justification='WORD_BOUNDARIES_ONLY')

    def test_actual_qt_words_expand_only_at_spaces_and_keep_last_line_natural(self):
        policy=dict(self.policy,alignment='justify',spacing_rule=self.rule())
        result=self.shape(value='North Road South Street Main Avenue Long District',policy=policy)
        self.assertGreater(len(result['lines']),1)
        self.assertTrue(any(r['applied'] for r in result['word_justification'][:-1]))
        self.assertFalse(result['word_justification'][-1]['applied'])
        self.assertLessEqual(result['width_mm'],30.+1e-6)
        # In-word glyph distances stay equal to the natural layout; the gap moves.
        plain=self.shape(value='North Road',policy=self.policy)
        forced=self.shape(value='North Road',policy=dict(policy,spacing_rule=self.rule('DISTRIBUTE')))
        self.assertGreater(forced['width_mm'],plain['width_mm'])
        original=list(plain['layout'].glyphRuns()[0].positions())
        shifted=list(forced['positioned_runs'][0].positions())
        self.assertAlmostEqual(original[1].x()-original[0].x(),shifted[1].x()-shifted[0].x())
        self.assertGreater(shifted[-1].x()-shifted[0].x(),original[-1].x()-original[0].x())

    def test_single_word_and_zero_word_boundaries_are_not_implicitly_stretched(self):
        policy=dict(self.policy,alignment='justify',spacing_rule=self.rule('DISTRIBUTE'))
        single=self.shape(value='North',policy=policy);plain=self.shape(value='North',policy=self.policy)
        self.assertAlmostEqual(single['width_mm'],plain['width_mm'])
        self.assertIsNone(single['positioned_runs'])


class CharacterJustificationTests(unittest.TestCase):
    setUp=flow_fixture.SourceConditionedFlowTests.setUp
    shape=flow_fixture.SourceConditionedFlowTests.shape

    def policy_for(self,**changes):
        rule=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['authored shaped-cluster reference'],
            mode='CHARACTERS',value_mm=0.,allowed_scripts=['Hani','Latn'],
            boundary_policy='QT_SHAPED_GRAPHEME_TRACKING',last_line='DISTRIBUTE',
            zero_boundaries='KEEP_NATURAL',justification='SHAPED_CLUSTER_BOUNDARIES_ONLY',maximum_extra_gap_mm=20.)
        rule.update(changes)
        return dict(self.policy,break_rule='NO_WRAP',max_lines_observed=1,alignment='justify',spacing_rule=rule)

    def test_actual_cjk_name_shaped_clusters_distribute_with_fixed_point_size(self):
        for value in ('王小明','王小明君'):
            result=self.shape(value=value,policy=self.policy_for(),kind='name')
            row=result['boundary_justification'][0]
            self.assertTrue(row['applied']);self.assertEqual(row['boundary_count'],len(value)-1)
            actual_advance=result['lines'][0]['natural_width_mm']+row['extra_per_boundary_layout_units']*row['boundary_count']*result['factor']
            self.assertAlmostEqual(actual_advance,30.)
            self.assertLessEqual(result['width_mm'],30.+1e-6)
            natural=self.shape(value=value,policy=self.policy_for(last_line='NATURAL'),kind='name')
            self.assertLess(natural['width_mm'],result['width_mm'])
            self.assertEqual(result['layout'].font().pixelSize(),natural['layout'].font().pixelSize())

    def test_single_cluster_and_combining_mark_are_not_split(self):
        for value in ('王','e\u0301'):
            result=self.shape(value=value,policy=self.policy_for(),kind='name')
            self.assertEqual(result['boundary_justification'][0]['boundary_count'],0)
            self.assertIsNone(result['positioned_runs'])

    def test_gap_limit_unreviewed_mode_and_inconsistent_alignment_are_rejected(self):
        for changes in (dict(maximum_extra_gap_mm=.01),dict(maximum_extra_gap_mm=None),
                        dict(justification='IMPLICIT_QT'),dict(maximum_extra_gap_mm=float('nan'))):
            with self.assertRaises(ValueError):self.shape(value='王小明',policy=self.policy_for(**changes),kind='name')
        with self.assertRaisesRegex(ValueError,'alignment'):
            self.shape(value='王小明',policy=dict(self.policy_for(),alignment='left'),kind='name')


class ObjectGapTests(unittest.TestCase):
    def examples(self,count=6):
        return [dict(id='source-'+str(i),role='TRAIN',lineage_group='independent-'+str(i),width_mm=100.,height_mm=50.,
            fields=[dict(id='f'+str(n),owner='p1',kind=kind,index=0,rect=dict(x=10.+n*25,y=10.,w=15.,h=8.))
                for n,kind in enumerate(('name','phone','email'))]) for i in range(count)]

    def test_shared_equal_object_gaps_are_learned_and_used_by_actual_kiwi(self):
        import kiwisolver as kiwi
        rules=learn_object_spacing(self.examples());rule=next(r for r in rules if r['axis']=='x')
        self.assertEqual(rule['status'],'SHARED_SOFT_EQUAL_GAP');self.assertAlmostEqual(rule['normalized_gap'],.1)
        variables={key:(kiwi.Variable(key+'x'),kiwi.Variable(key+'y'),15.,8.) for key in ('a','b','c')}
        facts=[dict(role_key=role,render_id=key) for role,key in zip(rule['roles'],('a','b','c'))]
        solver=kiwi.Solver();solver.addConstraint(variables['a'][0]==10.);solver.addConstraint(variables['c'][0]==70.)
        apply_object_spacing(solver,variables,facts,rules,100.,50.);solver.updateVariables()
        self.assertAlmostEqual(variables['b'][0].value(),40.)

    def test_duplicates_do_not_multiply_support_and_conflicts_are_preserved(self):
        rows=self.examples(1);rows=[dict(rows[0],id='alias-'+str(i)) for i in range(20)]
        self.assertFalse(any(r['status']=='SHARED_SOFT_EQUAL_GAP' for r in learn_object_spacing(rows)))
        rows=self.examples();rows[-1]['fields'][1]['rect']['x']+=7.
        rules=learn_object_spacing(rows)
        self.assertTrue(any(r['counterexample_groups'] for r in rules))
        self.assertFalse(any(r['status']=='SHARED_SOFT_EQUAL_GAP' for r in rules))
        rows=self.examples();rows[0]['role']='HOLDOUT'
        with self.assertRaises(ValueError):learn_object_spacing(rows)


class CapacityCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.context=dict(family_id='shared-family',font_signature='owned-face',field_count=4,width_mm=90.,height_mm=54.)
        self.policy=dict(version='authored-capacity-1',minimum_independent_groups=5,minimum_success_lower_bound=.8,
            alpha=.05,bin_widths=[20.,10.],maximum_support_distance=.25)
        self.records=[dict(id='validation-'+str(i),role='VALIDATION',lineage_group='independent-'+str(i),context=self.context,
            demand=[10.+i%3,4.+i%3*.1],layout_pass=True,qualified_style=True,evidence_refs=['independent known-style oracle']) for i in range(30)]

    def test_joint_region_calibrates_without_claiming_global_field_limit(self):
        model=fit_capacity(self.records,self.policy)
        good=capacity_advice(model,self.context,[11.,4.1]);bad=capacity_advice(model,self.context,[19.,9.])
        self.assertEqual(good['status'],'WITHIN_VALIDATED_EMPIRICAL_REGION')
        self.assertEqual(good['maximum_validated_field_count'],4);self.assertIsNone(good['hard_global_capacity'])
        self.assertEqual(bad['status'],'UNKNOWN_OR_OUTSIDE_VALIDATED_REGION')
        self.assertEqual(capacity_advice(model,dict(self.context,field_count=5),[11.,4.1])['status'],'UNKNOWN_OR_OUTSIDE_VALIDATED_REGION')

    def test_correlated_aliases_failure_and_heldout_leak_cannot_produce_safe_region(self):
        repeated=[dict(r,lineage_group='one-family-lineage') for r in self.records]
        self.assertIsNone(fit_capacity(repeated,self.policy)['maximum_validated_field_count'])
        bad=[dict(r,qualified_style=False) for r in self.records]
        self.assertIsNone(fit_capacity(bad,self.policy)['maximum_validated_field_count'])
        leaked=[dict(self.records[0],role='HOLDOUT')]
        with self.assertRaises(ValueError):fit_capacity(leaked,self.policy)
        model=fit_capacity(self.records,self.policy);model['cells'][0]['observed_upper'][0]=999
        with self.assertRaises(ValueError):capacity_advice(model,self.context,[11.,4.1])


class RankerCompletionTests(unittest.TestCase):
    def test_explicit_production_quality_policy_rejects_synthetic_or_incomplete_evidence(self):
        report=dict(origin='REAL_AUTHORIZED_CORPUS',independent_groups=8,known_queries=8,denominator=8,unknown_queries=0,
            group_macro_ndcg_at_k=.95,baseline_group_macro_ndcg_at_k=.75,ndcg_group_bootstrap_95=[.85,1.])
        policy=dict(minimum_independent_groups=5,minimum_ndcg=.8,minimum_improvement=.05,minimum_ndcg_lower_bound=.8)
        self.assertEqual(rank_quality_errors(report,policy),[])
        self.assertIn('REAL_CORPUS_REVIEW_REQUIRED',rank_quality_errors(dict(report,origin='AUTHORED_SYNTHETIC'),policy))
        self.assertIn('INCOMPLETE_INDEPENDENT_GRADES',rank_quality_errors(dict(report,unknown_queries=1),policy))
        self.assertIn('RANKING_QUALITY_BELOW_POLICY',rank_quality_errors(dict(report,group_macro_ndcg_at_k=.7),policy))

    def test_joint_style_feature_changes_when_actual_typography_changes(self):
        slot=Slot('name','p1',Rect(5,5,40,10),size_pt=12)
        candidate=Candidate(Template('Owned',90,54,[slot]),[Placed(slot,'Alex',1.,0.)],[])
        candidate.risk_context['design_joint_style_reference']={slot.id:[[12/54,1.,0.,40/90,10/54]]}
        before=candidate_features(candidate,90,54,[])['joint_style_residual']
        slot.size_pt=18
        after=candidate_features(candidate,90,54,[])['joint_style_residual']
        self.assertEqual(before,0.);self.assertGreater(after,before)
