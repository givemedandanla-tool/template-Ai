"""Actual current candidates and authored source pixels, not metadata quality flags."""
import copy,unittest
from pathlib import Path
from PySide6.QtGui import QImage
import test_first_version as fixture
import test_candidate_risk as risk_fixture
from template_ai.layout import Placed
from template_ai.model import Slot,Rect
from template_ai.digital_preflight import options,scope,inspect_candidate,logo_sampling,validate_scope
APP=fixture.APP


class DigitalPreflightTests(unittest.TestCase):
    setUp=fixture.FirstVersionTests.setUp
    people=risk_fixture.CandidateRiskTests.people
    candidate=risk_fixture.CandidateRiskTests.candidate
    def asset(self,width=100,height=50,dpm=11811):
        path=self.root/'authored-source.png';image=QImage(width,height,QImage.Format_RGB32);image.fill(0xff224466);image.setDotsPerMeterX(dpm);image.setDotsPerMeterY(dpm);self.assertTrue(image.save(str(path)));return dict(image=str(path),source_width_mm=20,source_height_mm=10,crop=None)
    def placed(self,asset,rect=None):return Placed(Slot('logo','c1',rect or Rect(0,0,20,10)),logo=asset)
    def test_real_complete_candidate_still_needs_actual_encoded_format_evidence(self):
        c=self.candidate();before=copy.deepcopy(c.template.to_dict());value=inspect_candidate(c,'PDF',300);self.assertTrue(value['can_encode']);self.assertFalse(value['formal_output_allowed']);self.assertFalse(value['output_written']);self.assertFalse(value['physical_print_verified']);self.assertEqual(next(r for r in value['rows'] if r['code']=='ENCODED_FORMAT')['status'],'NOT_CHECKED');self.assertEqual(c.template.to_dict(),before)
    def test_unapproved_template_does_not_gain_trust_from_named_checklist(self):
        self.template.state='draft';value=inspect_candidate(self.candidate(),'png',150);self.assertFalse(value['can_encode']);self.assertEqual(next(r for r in value['rows'] if r['code']=='CURRENT_WHOLE_CARD_GATE')['status'],'BLOCKED')
    def test_scope_captures_format_dpi_and_rejects_candidate_geometry_changes(self):
        c=self.candidate();value=scope(c,'JPG',150);validate_scope(c,value);c.template.slots[0].rect.x+=.1
        with self.assertRaises(ValueError):validate_scope(c,value)
        self.assertNotEqual(scope(c,'PNG',150)['digest'],scope(c,'PDF',150)['digest']);self.assertNotEqual(scope(c,'PNG',150)['digest'],scope(c,'PNG',300)['digest'])
    def test_invalid_format_boolean_dpi_and_excessive_pixels_are_refused_without_downsampling(self):
        c=self.candidate()
        for format,dpi in [('exe',300),('PNG',True),('PDF',601)]:
            with self.assertRaises(ValueError):options(c,format,dpi)
        c.template.width_mm=2000;c.template.height_mm=2000
        with self.assertRaisesRegex(ValueError,'像素預算'):options(c,'PNG',600)
    def test_safe_boundary_and_trim_failures_have_exact_slot_ids(self):
        self.template.safe_margin_mm=9;c=self.candidate();value=inspect_candidate(c,'PNG',150);unsafe=next(r for r in value['rows'] if r['code']=='SAFE_ZONE');self.assertEqual(unsafe['status'],'BLOCKED');self.assertIn(c.items[0].slot.id,unsafe['slot_ids']);self.template.slots[0].rect.x=-1;c=self.candidate();value=inspect_candidate(c,'PNG',150);self.assertIn(c.items[0].slot.id,next(r for r in value['rows'] if r['code']=='TRIM_BOUNDS')['slot_ids'])
    def test_overlap_check_is_specific_instead_of_hidden_behind_generic_engine_failure(self):
        self.template.slots[1].rect=copy.deepcopy(self.template.slots[0].rect);c=self.candidate();value=inspect_candidate(c,'PNG',150);check=next(r for r in value['rows'] if r['code']=='OVERLAP');self.assertEqual(check['status'],'BLOCKED');self.assertEqual(set(check['slot_ids']),{c.items[0].slot.id,c.items[1].slot.id})
    def test_raster_sampling_uses_actual_pixels_and_placed_size_not_dpi_tag(self):
        first=logo_sampling(self.placed(self.asset(dpm=11811)),300);second=logo_sampling(self.placed(self.asset(dpm=118110)),300);self.assertEqual(first['status'],'BLOCKED');self.assertEqual(first['measurements']['effective_ppi'],second['measurements']['effective_ppi']);self.assertAlmostEqual(first['measurements']['effective_ppi'][0],127)
    def test_source_pixels_at_smaller_actual_size_can_meet_explicit_sampling_without_global_print_claim(self):
        value=logo_sampling(self.placed(self.asset(),Rect(0,0,5,2.5)),300);self.assertEqual(value['status'],'PASS');self.assertAlmostEqual(value['measurements']['effective_ppi'][0],508);self.assertFalse(value['measurements']['physical_print_verified'])
    def test_crop_available_pixels_use_whole_mark_contain_actual_geometry(self):
        asset=self.asset(1000,500);asset['crop']=dict(x=0,y=0,w=5,h=10);value=logo_sampling(self.placed(asset,Rect(0,0,20,20)),600);self.assertEqual(value['status'],'PASS');self.assertEqual(value['measurements']['available_crop_pixels'],[250,500]);self.assertAlmostEqual(value['measurements']['effective_ppi'][0],635)
    def test_original_vector_is_not_replaced_by_lower_resolution_preview_asset(self):
        path=self.root/'authored.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 200 100"><path d="M0 50 C50 0 150 100 200 50" stroke="black" fill="none"/></svg>');asset=self.asset(10,5);asset['svg']=str(path);value=logo_sampling(self.placed(asset),600);self.assertEqual(value['status'],'PASS');self.assertEqual(value['measurements']['source_type'],'VECTOR');self.assertFalse(value['measurements']['encoded_fidelity_verified'])
    def test_svg_container_with_embedded_raster_is_not_assumed_infinite_resolution(self):
        path=self.root/'mixed.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,AAAA" width="20" height="10"/></svg>');asset=self.asset();asset['svg']=str(path);value=logo_sampling(self.placed(asset),300);self.assertEqual(value['status'],'NOT_CHECKED');self.assertEqual(value['measurements']['source_type'],'MIXED')
    def test_corrupt_or_missing_actual_source_is_blocked_even_with_optimistic_flags(self):
        asset=self.asset();Path(asset['image']).write_bytes(b'not an image');asset.update(approved=True,dpi=2400,quality='PERFECT');value=logo_sampling(self.placed(asset),300);self.assertEqual(value['status'],'BLOCKED')

if __name__=='__main__':unittest.main()
