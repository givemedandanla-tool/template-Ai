"""Actual original encoded previews, decoded pixels/PDF resources and immutable scope."""
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtGui import QImage
import test_first_version as fixture
import test_candidate_risk as risk_fixture
from template_ai.digital_output_proof import build_proof,decoded_image,pdf_evidence,compare_images,region_images
APP=fixture.APP


class DigitalOutputProofTests(unittest.TestCase):
    setUp=fixture.FirstVersionTests.setUp
    people=risk_fixture.CandidateRiskTests.people
    candidate=risk_fixture.CandidateRiskTests.candidate
    def test_actual_png_preview_body_matches_original_pixels_and_never_claims_formal_output(self):
        c=self.candidate();value=build_proof(c,'PNG',96,self.root/'proofs');self.assertTrue(value['body_comparison']['exact_equal']);self.assertFalse(value['formal_output_allowed']);self.assertTrue(value['diagnostic_preview_written']);self.assertEqual(next(r for r in value['rows'] if r['code']=='ENCODED_FORMAT')['status'],'PASS');self.assertFalse(value['output_written']);self.assertIn('PREVIEW',value['file']['path']);self.assertGreater(value['preview_page_mm'][1],value['card_body_mm'][1]);self.assertFalse(value['physical_print_verified'])
    def test_actual_pdf_fonts_and_physical_preview_page_are_read_back_without_print_certification(self):
        value=build_proof(self.candidate(),'PDF',96,self.root/'proofs');pdf=value['pdf'];self.assertEqual(pdf['page_count'],1);self.assertTrue(pdf['fonts']);self.assertTrue(pdf['all_fonts_embedded']);self.assertGreater(pdf['text_operator_count'],0);self.assertFalse(pdf['pdfa_or_print_certified']);self.assertFalse(pdf['individual_logo_fidelity_approved'])
    def test_actual_jpeg_difference_is_measured_without_fabricated_perceptual_threshold(self):
        value=build_proof(self.candidate(),'JPG',96,self.root/'proofs');metrics=value['body_comparison'];self.assertEqual(metrics['status'],'MEASURED');self.assertGreater(metrics['mse'],0);self.assertFalse(metrics['perceptual_quality_approved']);self.assertTrue(value['explicit_visual_review_required'])
    def test_rgb_mse_excludes_row_padding_and_reports_exact_channel_difference(self):
        a=QImage(3,1,QImage.Format_RGB888);a.fill(0xff000000);b=a.copy();b.setPixelColor(0,0,'red');value=compare_images(a,b);self.assertEqual(value['mse'],7225);self.assertEqual(value['changed_channels'],1);self.assertEqual(value['max_absolute_error'],255)
    def test_dimension_mismatch_is_not_rescaled_and_large_comparison_is_not_called_pass(self):
        a=QImage(3,1,QImage.Format_RGB32);b=QImage(4,1,QImage.Format_RGB32)
        with self.assertRaises(ValueError):compare_images(a,b)
        a=QImage(1001,1000,QImage.Format_RGB32);a.fill(0xffffffff);self.assertEqual(compare_images(a,a)['status'],'NOT_CHECKED')
    def test_exact_selected_slot_crop_uses_encoded_pixels_and_rejects_changed_candidate(self):
        c=self.candidate();value=build_proof(c,'PNG',96,self.root/'proofs');a,b,detail=region_images(c,value,c.items[0].slot.id);self.assertFalse(a.isNull());self.assertEqual(a.size(),b.size());self.assertTrue(detail['metrics']['exact_equal']);self.assertEqual(detail['slot_id'],c.items[0].slot.id);c.template.slots[0].rect.x+=.2
        with self.assertRaises(ValueError):region_images(c,value,c.items[0].slot.id)
    def test_changed_actual_encoded_bytes_cannot_reuse_saved_proof(self):
        c=self.candidate();value=build_proof(c,'PNG',96,self.root/'proofs');Path(value['file']['path']).write_bytes(b'corrupt authored output')
        with self.assertRaises(ValueError):region_images(c,value,c.items[0].slot.id)
    def test_failed_original_encoding_leaves_no_success_or_partial_preview_directory(self):
        root=self.root/'proofs'
        with patch('template_ai.render.export',side_effect=OSError('Authored storage failure')):
            with self.assertRaises(OSError):build_proof(self.candidate(),'PNG',96,root)
        self.assertEqual(list(root.iterdir()),[])
    def test_actual_vector_logo_pdf_contains_curve_operators_without_raster_xobject(self):
        from template_ai.importer import import_file
        from template_ai.logo_assets import checked_payload
        from template_ai.logo_output_proof import create_proof
        source=self.root/'authored-composite.svg';source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 200 100"><path d="M5 50 C50 5 150 95 195 50" fill="none" stroke="black" stroke-width="1"/><circle cx="90" cy="50" r="18" fill="#cc3300"/><path d="M20 70 L180 70" stroke="#113388" stroke-width=".5"/></svg>');raw=import_file(source,self.root/'assets');asset=checked_payload(dict(image=raw['image'],svg=raw['svg'],source_width_mm=raw['width_mm'],source_height_mm=raw['height_mm'],crop=None));proof=create_proof(asset,20,10,self.root/'logos',96);pdf=pdf_evidence(proof['files'][0]['path']);self.assertGreater(pdf['vector_operator_count'],0);self.assertEqual(pdf['image_xobjects'],[])
    def test_real_encoded_pixels_and_pdf_size_cannot_be_approved_with_wrong_dimensions(self):
        c=self.candidate()
        for format in ('PNG','PDF'):
            value=build_proof(c,format,96,self.root/'proofs')
            with self.assertRaises(ValueError):decoded_image(value['file']['path'],[91,value['preview_page_mm'][1]],96)

if __name__=='__main__':unittest.main()
