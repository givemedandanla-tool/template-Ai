from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from template_ai.model import Rect
from template_ai.source_region_hypotheses import size_note,region_hypotheses,original_pdf_texts
import test_original_pdf_glyphs as glyph_fixture


class SourceRegionHypothesesTests(unittest.TestCase):
    def test_explicit_units_are_required_and_normalized_without_identity_inference(self):
        self.assertEqual(size_note('8.5 × 5.4 cm')['width_mm'],85.)
        self.assertEqual(size_note('85mm x 54mm')['height_mm'],54.)
        self.assertIsNone(size_note('85 x 54'))
        self.assertIsNone(size_note('ID 85-54'))

    def test_separated_unframed_works_have_review_only_size_conditioned_crops(self):
        rows=[('note-a','85x54mm',Rect(20,2,20,3)),('a-name','Name A',Rect(20,20,30,5)),
              ('a-mail','a@example.test',Rect(20,30,35,5)),
              ('note-b','90x54mm',Rect(200,2,20,3)),('b-name','Name B',Rect(200,20,30,5)),
              ('b-mail','b@example.test',Rect(200,30,35,5))]
        report=region_hypotheses(rows,Rect(0,0,300,150))
        self.assertEqual(len(report['candidates']),2)
        self.assertTrue(all(row['review_required'] for row in report['candidates']))
        self.assertEqual(report['identity'],'UNKNOWN')
        self.assertEqual(report,region_hypotheses(rows,Rect(0,0,300,150)))

    def test_competing_size_notes_do_not_duplicate_a_cluster_as_two_works(self):
        rows=[('note-a','85x54mm',Rect(20,2,20,3)),('note-b','90x54mm',Rect(20,6,20,3)),
              ('name','Name',Rect(20,20,30,5))]
        self.assertEqual(region_hypotheses(rows,Rect(0,0,200,100))['candidates'],[])

    def test_original_pdf_readable_text_survives_outlined_derivative_and_hides_nonpainting(self):
        data,source=glyph_fixture.OriginalPdfGlyphTests().pdf(
            b'BT /F1 12 Tf 1 0 0 1 24 70 Tm (authored@example.test) Tj 3 Tr 1 0 0 1 24 30 Tm (Hidden) Tj ET')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'owned.ai';path.write_bytes(data);source['current_path']=str(path)
            rows,evidence=original_pdf_texts(source)
            self.assertEqual(len(rows),1);self.assertEqual(rows[0][1],'authored@example.test')
            self.assertEqual(evidence['person_and_role'],'UNKNOWN')
            source['hash']='0'*64
            with self.assertRaises(ValueError):original_pdf_texts(source)
