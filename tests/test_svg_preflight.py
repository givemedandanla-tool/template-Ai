"""SVG syntax is not evidence that Qt preserves every source feature."""
import unittest
import test_digital_preflight as fixture
from template_ai.digital_preflight import logo_sampling
from template_ai.digital_output_proof import build_proof

class SvgPreflightTests(unittest.TestCase):
    setUp=fixture.DigitalPreflightTests.setUp
    asset=fixture.DigitalPreflightTests.asset
    placed=fixture.DigitalPreflightTests.placed
    candidate=fixture.DigitalPreflightTests.candidate
    people=fixture.DigitalPreflightTests.people

    def svg(self,body):
        path=self.root/'authored-effects.svg'
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 200 100">'+body+'</svg>')
        asset=self.asset();asset['svg']=str(path);return asset

    def test_filter_effect_cannot_pass_as_preserved_native_vector(self):
        asset=self.svg('<defs><filter id="blur"><feGaussianBlur stdDeviation="8"/></filter></defs><rect x="30" y="20" width="140" height="60" filter="url(#blur)"/>')
        row=logo_sampling(self.placed(asset),96)
        self.assertNotEqual(row['status'],'PASS')
        self.assertIn('filter',str(row['measurements']))

    def test_unpinned_svg_text_font_cannot_pass_as_verified_outlines(self):
        row=logo_sampling(self.placed(self.svg('<text x="10" y="70" font-family="Uninstalled Authored Font">ABC</text>')),96)
        self.assertNotEqual(row['status'],'PASS')

    def test_external_reference_is_not_assumed_current_source_evidence(self):
        row=logo_sampling(self.placed(self.svg('<use href="https://example.invalid/mark.svg#shape"/>')),96)
        self.assertNotEqual(row['status'],'PASS')

    def test_unknown_extension_cannot_be_silently_ignored(self):
        row=logo_sampling(self.placed(self.svg('<foreignObject width="200" height="100"><div xmlns="http://www.w3.org/1999/xhtml">Authored source</div></foreignObject>')),96)
        self.assertNotEqual(row['status'],'PASS')

    def test_native_curves_strokes_and_internal_reference_remain_vector(self):
        row=logo_sampling(self.placed(self.svg('<defs><path id="curve" d="M10 80 Q100 0 190 80" stroke="#123456" fill="none" stroke-width="2"/></defs><use href="#curve"/>')),600)
        self.assertEqual(row['status'],'PASS');self.assertEqual(row['measurements']['source_type'],'VECTOR')

    def test_large_lossless_body_has_full_rgb_evidence_without_mse_downsampling(self):
        proof=build_proof(self.candidate(),'PNG',600,self.root/'proofs')
        self.assertEqual(proof['body_comparison']['status'],'NOT_CHECKED')
        row=next(r for r in proof['rows'] if r['code']=='ENCODED_BODY_COMPARISON')
        self.assertEqual(row['status'],'PASS');self.assertTrue(row['measurements']['full_rgb_equal'])
        self.assertFalse(proof['formal_output_allowed'])

if __name__=='__main__':unittest.main()
