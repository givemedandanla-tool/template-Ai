"""Current actual-format review, real encoded references and final-byte safeguards."""
import copy,unittest
from pathlib import Path
import test_first_version as fixture
import test_candidate_risk as risk_fixture
from template_ai.digital_output_proof import build_proof,decoded_image,pdf_evidence
from template_ai.digital_review import confirm,pdf_signature
from template_ai.render import export
APP=fixture.APP


class DigitalReviewTests(unittest.TestCase):
    setUp=fixture.FirstVersionTests.setUp
    people=risk_fixture.CandidateRiskTests.people
    candidate=risk_fixture.CandidateRiskTests.candidate
    def review(self,c,format):
        proof=build_proof(c,format,96,self.root/'proofs');receipt=confirm(c,proof,'SYNTHETIC_SOURCE_AUTHOR','Actual authored original-size same-format snapshot and full source content verified',True);return proof,receipt
    def test_real_pdf_and_jpeg_exact_snapshot_review_matches_final_pixels_and_pdf_structure(self):
        c=self.candidate()
        for format in ('PDF','JPG'):
            proof,receipt=self.review(c,format);self.assertIsNotNone(proof['exact_file']);self.assertEqual(decoded_image(proof['exact_file']['path'],proof['scope']['size_mm'],96).height(),proof['scope']['pixels'][1]);path=export(c,self.root/('reviewed-FINAL.'+format.lower()),96,False,7,format_review=receipt);self.assertTrue(path.is_file());self.assertFalse(receipt['physical_print_verified'])
    def test_missing_or_nonliteral_visual_review_never_publishes_nonlossless_format(self):
        c=self.candidate();proof=build_proof(c,'JPG',96,self.root/'proofs')
        for approved in (False,1,'yes'):
            with self.assertRaises(ValueError):confirm(c,proof,'Synthetic author','Actual snapshot proof',approved)
        with self.assertRaises(ValueError):export(c,self.root/'unreviewed-FINAL.jpg',96,False,7)
        self.assertFalse((self.root/'unreviewed-FINAL.jpg').exists())
    def test_changed_scope_or_tampered_review_cannot_reuse_old_authorization(self):
        c=self.candidate();_,receipt=self.review(c,'JPG');target=self.root/'stale-FINAL.jpg'
        with self.assertRaises(ValueError):export(c,target,150,False,7,format_review=receipt)
        tampered=copy.deepcopy(receipt);tampered['actor']='Another actor'
        with self.assertRaises(ValueError):export(c,target,96,False,7,format_review=tampered)
        self.assertFalse(target.exists())
    def test_changed_actual_reference_file_is_rejected_without_publishing(self):
        c=self.candidate();_,receipt=self.review(c,'PDF');Path(receipt['file']['path']).write_bytes(b'corrupt actual reference')
        with self.assertRaises(ValueError):export(c,self.root/'changed-FINAL.pdf',96,False,7,format_review=receipt)
        self.assertFalse((self.root/'changed-FINAL.pdf').exists())
    def test_pdf_signature_captures_actual_vectors_and_images_but_ignores_subset_resource_ids(self):
        c=self.candidate();proof,_=self.review(c,'PDF');actual=pdf_evidence(proof['exact_file']['path']);altered=copy.deepcopy(actual);altered['operator_histogram']['c']=altered['operator_histogram'].get('c',0)+1;self.assertNotEqual(pdf_signature(actual),pdf_signature(altered));renamed=copy.deepcopy(actual)
        for f in renamed['fonts']:f['base_font']='/ZZZZZZ+'+f['base_font'].split('+')[-1].lstrip('/')
        self.assertEqual(pdf_signature(actual),pdf_signature(renamed))
    def test_exact_card_mode_is_only_explicitly_marked_diagnostic_preview(self):
        c=self.candidate()
        with self.assertRaises(ValueError):export(c,self.root/'unmarked.png',96,True,7,exact_preview=True)
        with self.assertRaises(ValueError):export(c,self.root/'PREVIEW-not-final.png',96,False,7,exact_preview=True)

if __name__=='__main__':unittest.main()
