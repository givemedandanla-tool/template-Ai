"""Synthetic physical measurements with hand-calculated held-out expectations."""
import unittest

from template_ai.design_joint import fit_joint, predict_joint


def measured(index, width, height, demand, point=12., frame=30.):
    return {'example_id': f'audit-measurement-{index}', 'lineage_group': f'independent-source-{index}',
            'source_font_ref': {'sha256': 'authored-metrics-only-not-a-production-font'},
            'align': 'LEFT', 'distribution': 'NONE',
            'label_binding': {'status': 'CONFIRMED', 'kind': 'NO_FIXED_LABEL'},
            'dimensions_mm': [width, height],
            'joint': {'source_pt': point, 'horizontal_scale': 1., 'tracking_mm': 0.,
                      'frame_width_mm': frame, 'frame_height_mm': 6.,
                      'shaped_advance_mm': demand * point}}


class IndependentJointOracleTests(unittest.TestCase):
    def test_joint_abstains_inside_axis_ranges_without_joint_source_support(self):
        rows = [measured(i, 90. if i < 6 else 110., 54. if i < 6 else 74.,
                         1. if i < 6 else 3.) for i in range(12)]
        model = fit_joint(rows)
        self.assertTrue(predict_joint(model, 90., 54., 1.))
        self.assertTrue(predict_joint(model, 110., 74., 3.))
        # All three coordinates are within their individual observed ranges.
        # No source supports their joint midpoint, so axis ranges cannot license it.
        self.assertEqual(predict_joint(model, 100., 64., 2.), [])

    def test_unseen_affine_measurement_matches_hand_calculated_joint_values(self):
        rows = []
        for width in (90., 95., 100.):
            for step in range(8):
                demand = 2. + step / 10
                rows.append(measured(len(rows), width, 54., demand,
                                     point=10. + (width - 90.) / 10 - (demand - 2.) / 5,
                                     frame=20. + (width - 90.) / 5 + (demand - 2.) / 2))
        model = fit_joint(rows)
        result = predict_joint(model, 97.5, 54., 2.35)
        self.assertTrue(result)
        # Independently worked out at the unseen point: 10 + .75 - .07;
        # and 20 + 1.5 + .175. Neither expected value comes from the fitted model.
        self.assertAlmostEqual(result[0]['joint']['source_pt'], 10.68, delta=.08)
        self.assertAlmostEqual(result[0]['joint']['frame_width_mm'], 21.675, delta=.08)
