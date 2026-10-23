from copy import deepcopy
import unittest

from template_ai.design_joint import fit_joint, predict_joint


def observations(count=12):
    rows=[]
    for i in range(count):
        demand=2.+i*.08
        rows.append(dict(example_id='synthetic-'+str(i),lineage_group='independent-'+str(i),
            source_font_ref=dict(sha256='authored-only'),align='LEFT',distribution='NONE',
            label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL'),dimensions_mm=[90.,54.],
            joint=dict(source_pt=14.-demand,horizontal_scale=1.-demand*.02,tracking_mm=.05*demand,
                frame_width_mm=20.+demand*5,frame_height_mm=7.-demand*.1,
                shaped_advance_mm=demand*(14.-demand))))
    return rows


class JointRegressionTests(unittest.TestCase):
    def test_continuous_size_response_is_not_fragmented_into_discrete_size_modes(self):
        rows=observations(30)
        for i,row in enumerate(rows):
            width=90.+i%3*5;demand=2.+(i//3)*.05
            row['dimensions_mm']=[width,54.]
            row['joint'].update(source_pt=10.+(width-90.)*.1,horizontal_scale=.98,
                shaped_advance_mm=demand*(10.+(width-90.)*.1),tracking_mm=0.,
                frame_width_mm=30.+(width-90.)*.3,frame_height_mm=6.)
        model=fit_joint(rows)
        self.assertEqual(len(model['modes']),1)
        predicted=predict_joint(model,97.5,54.,2.2)
        self.assertTrue(predicted)
        self.assertAlmostEqual(predicted[0]['joint']['source_pt'],10.75,delta=.1)

    def test_reviewed_word_spacing_is_a_joint_response_not_one_mode_per_value(self):
        rows=observations(8)
        for i,row in enumerate(rows):
            value=.1+i*.02;row['joint']['word_spacing_mm']=value
            row['source_text_flow']=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['flow-'+str(i)],
                break_rule='WORD_WRAP',max_lines_observed=2,line_height_factor=1.,alignment='left',
                spacing_rule=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['words-'+str(i)],
                    mode='WORDS',value_mm=value,allowed_scripts=['Latn'],boundary_policy='ASCII_SPACE_QT_WORD_SPACING',
                    last_line='NATURAL',zero_boundaries='KEEP_NATURAL'))
        artifact=fit_joint(rows)
        self.assertEqual(len(artifact['modes']),1)
        prediction=predict_joint(artifact,90.,54.,2.24)[0]['joint']
        self.assertAlmostEqual(prediction['word_spacing_mm'],.16,delta=.012)
        self.assertEqual(artifact['modes'][0]['independent_support'],8)

    def test_review_provenance_does_not_fragment_shared_style_or_duplicate_weight(self):
        rows=observations(8)
        for i,row in enumerate(rows):
            row['label_binding']['evidence_refs']=['unique-review-'+str(i)]
            row['distribution']=dict(approved=True,mode='CHARACTERS',actor='reviewer-'+str(i),reason='source-'+str(i))
        baseline=fit_joint(rows)
        self.assertEqual(len(baseline['modes']),1)
        self.assertEqual(baseline['modes'][0]['independent_support'],8)
        aliases=[dict(deepcopy(rows[0]),example_id='alias-'+str(i)) for i in range(100)]
        repeated=fit_joint(rows+aliases)
        for key in ('x_centre','x_scale','y_centre','y_scale','coefficients','intercept'):
            import numpy as np
            np.testing.assert_allclose(baseline['modes'][0][key],repeated['modes'][0][key],atol=1e-12)
        self.assertEqual(len(repeated['modes'][0]['source_refs']),108)
        for row in rows[4:]:row['label_binding'].update(kind='DYNAMIC_PREFIX',prefix='Tel: ')
        self.assertEqual(fit_joint(rows)['modes'],[]) # two genuinely distinct styles, each insufficient

    def test_joint_prediction_tracks_correlated_outputs_and_is_stable(self):
        artifact=fit_joint(observations())
        result=predict_joint(artifact,90.,54.,2.4)
        self.assertTrue(result)
        vector=result[0]['joint']
        self.assertAlmostEqual(vector['source_pt'],11.6,delta=.12)
        self.assertAlmostEqual(vector['frame_width_mm'],32.,delta=.6)
        self.assertAlmostEqual(vector['horizontal_scale'],.952,delta=.003)
        self.assertEqual(result,predict_joint(artifact,90.,54.,2.4))
        self.assertEqual(artifact,fit_joint(list(reversed(observations()))))

    def test_extrapolation_and_unobserved_joint_input_holes_abstain(self):
        artifact=fit_joint(observations())
        self.assertEqual(predict_joint(artifact,100.,54.,2.4),[])
        self.assertEqual(predict_joint(artifact,90.,54.,4.),[])

    def test_missing_typography_and_correlated_aliases_do_not_create_support(self):
        rows=observations(4)
        self.assertEqual(fit_joint(rows)['modes'],[])
        aliases=[dict(deepcopy(row),example_id=row['example_id']+'copy'+str(i)) for i in range(4) for row in rows]
        self.assertEqual(fit_joint(rows+aliases)['modes'],[])
        rows=observations()
        for row in rows:row['joint']['source_pt']=None
        self.assertEqual(fit_joint(rows)['modes'],[])

    def test_rare_styles_are_preserved_without_averaging_between_modes(self):
        rows=observations(10)
        for i,row in enumerate(rows):
            if i>=5:
                row['joint']['source_pt']+=15.
                row['joint']['shaped_advance_mm']=(2.+i*.08)*row['joint']['source_pt']
        artifact=fit_joint(rows)
        self.assertEqual(len(artifact['modes']),2)
        self.assertTrue(all(mode['independent_support']==5 for mode in artifact['modes']))
        self.assertEqual({mode['quality_scope'] for mode in artifact['modes']},{'TRAIN_FIT_DIAGNOSTIC_ONLY_NOT_CALIBRATED'})

    def test_weights_tamper_and_invalid_demand_fail(self):
        artifact=fit_joint(observations())
        with self.assertRaises(ValueError):predict_joint(artifact,90.,54.,float('nan'))
        artifact['modes'][0]['intercept'][0]+=1
        with self.assertRaises(ValueError):predict_joint(artifact,90.,54.,2.4)
