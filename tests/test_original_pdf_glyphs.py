"""Authored PDF operator/glyph evidence, not private Illustrator qualification."""
from io import BytesIO
import hashlib
import unittest
from unittest.mock import patch
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,NumberObject

from template_ai.original_pdf_glyphs import extract_pdf_glyphs,GlyphBudget


class OriginalPdfGlyphTests(unittest.TestCase):
    def test_original_word_spacing_is_distinct_from_character_spacing(self):
        data,source=self.pdf(b'BT /F1 12 Tf 50 Tz 1 Tc 4 Tw 1 0 0 1 24 70 Tm (A B) Tj ET')
        run=extract_pdf_glyphs(source,data)['runs'][0]
        self.assertAlmostEqual(run['tracking']['value'],25.4/72)
        self.assertAlmostEqual(run['word_spacing']['value'],4*25.4/72)
        self.assertNotEqual(run['tracking'],run['word_spacing'])

    def pdf(self,content,*,rotation=0,user_unit=1,second=None):
        writer=PdfWriter()
        for payload in ([content] if second is None else [content,second]):
            page=writer.add_blank_page(width=255,height=153)
            font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),
                                   NameObject('/BaseFont'):NameObject('/Helvetica')})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            if rotation:page[NameObject('/Rotate')]=NumberObject(rotation)
            if user_unit!=1:page[NameObject('/UserUnit')]=NumberObject(user_unit)
            stream=DecodedStreamObject();stream.set_data(payload);page[NameObject('/Contents')]=writer._add_object(stream)
        stream=BytesIO();writer.write(stream);data=stream.getvalue()
        w,h=(153,255) if rotation in (90,270) else (255,153)
        return data,dict(hash=hashlib.sha256(data).hexdigest(),page=1,
                         width_mm=w*user_unit*25.4/72,height_mm=h*user_unit*25.4/72)

    def test_actual_glyph_origins_follow_tc_tz_not_bbox_height_guess(self):
        data,source=self.pdf(b'BT /F1 12 Tf 50 Tz 2 Tc 1 0 0 1 24 70 Tm (AB) Tj ET')
        result=extract_pdf_glyphs(source,data,include_private_text=True);run=result['runs'][0]
        self.assertEqual(result['glyph_count'],2);self.assertEqual(run['source_pt']['value'],12)
        self.assertEqual(run['horizontal_scale']['value'],.5)
        self.assertAlmostEqual(run['tracking']['value'],2*25.4/72)
        a,b=run['glyphs'];self.assertAlmostEqual(b['origin_mm']['x']-a['origin_mm']['x'],(12*.667+2)*.5*25.4/72)
        self.assertEqual(run['_private_text'],'AB');self.assertEqual(run['font_asset_identity'],'UNKNOWN')
        self.assertEqual(run['native_illustrator_editability'],'UNKNOWN')

    def test_uniform_cm_and_user_unit_produce_physical_pt_and_rotated_canvas(self):
        data,source=self.pdf(b'q 2 0 0 2 0 0 cm BT /F1 12 Tf 1 0 0 1 24 40 Tm (A) Tj ET Q',rotation=90,user_unit=2)
        result=extract_pdf_glyphs(source,data)
        self.assertEqual(result['source_canvas_mapping'],'VERIFIED_PHYSICAL_VIEWPORT')
        self.assertEqual(result['runs'][0]['source_pt']['value'],48)
        self.assertNotIn('_private_text',str(result))

    def test_anisotropic_transform_keeps_original_tf_without_inventing_unique_effective_pt(self):
        data,source=self.pdf(b'q 2 0 0 3 0 0 cm BT /F1 12 Tf 1 0 0 1 20 20 Tm (A) Tj ET Q')
        run=extract_pdf_glyphs(source,data)['runs'][0]
        self.assertEqual(run['declared_pt']['value'],12)
        self.assertIsNone(run['source_pt']['value'])

    def test_invisible_text_and_viewport_mismatch_are_not_visible_original_design_proof(self):
        data,source=self.pdf(b'BT /F1 12 Tf 3 Tr 1 0 0 1 24 70 Tm (Hidden OCR) Tj ET')
        result=extract_pdf_glyphs(dict(source,width_mm=source['width_mm']+1),data)
        self.assertEqual(result['runs'][0]['visibility'],'NONPAINTING_TEXT')
        self.assertEqual(result['source_canvas_mapping'],'UNKNOWN_VIEWPORT_DIFFERENCE')

    def test_page_selection_and_original_content_identity_are_exact(self):
        data,source=self.pdf(b'BT /F1 12 Tf (A) Tj ET',second=b'BT /F1 15 Tf (B) Tj ET')
        first=extract_pdf_glyphs(source,data);second=extract_pdf_glyphs(dict(source,page=2),data)
        self.assertNotEqual(first['runs'][0]['id'],second['runs'][0]['id'])
        self.assertEqual(second['runs'][0]['source_pt']['value'],15)
        with self.assertRaises(ValueError):extract_pdf_glyphs(dict(source,hash='0'*64),data)

    def test_budget_failure_has_no_partial_pretend_complete_result(self):
        data,source=self.pdf(b'BT /F1 12 Tf (AB) Tj ET')
        with patch('template_ai.original_pdf_glyphs.MAX_GLYPHS',1):
            with self.assertRaises(GlyphBudget):extract_pdf_glyphs(source,data)

    def test_separate_text_shows_have_real_cursor_advances_and_stable_run_ids(self):
        data,source=self.pdf(b'BT /F1 12 Tf 1 0 0 1 24 70 Tm (A) Tj (B) Tj ET')
        first=extract_pdf_glyphs(source,data)
        self.assertEqual(first,extract_pdf_glyphs(source,data))
        self.assertEqual(len(first['runs']),2)
        self.assertGreater(first['runs'][1]['baseline_anchor_mm']['x'],first['runs'][0]['baseline_anchor_mm']['x'])

    def test_addressed_observation_keeps_detail_out_of_default_graph_and_resolves_exactly(self):
        from pathlib import Path
        import tempfile
        from template_ai.original_text_observation import original_text_observation
        from template_ai.original_pdf_glyphs import resolve_glyph_run
        data,source=self.pdf(b'BT /F1 12 Tf 1 0 0 1 24 70 Tm (Owned glyph reference) Tj ET')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'owned.ai';path.write_bytes(data);source['current_path']=str(path)
            doc=original_text_observation(source)
            run=next(row for row in doc['runs'] if row['id'].startswith('PDF_GLYPH_RUN:'))
            self.assertNotIn('glyphs',run);self.assertNotIn('_private_text',str(doc))
            resolved=resolve_glyph_run(source,run['glyph_evidence'])
            self.assertEqual(len(resolved['glyphs']),run['glyph_evidence']['count'])
            bad=dict(run['glyph_evidence'],digest='0'*64)
            with self.assertRaises(ValueError):resolve_glyph_run(source,bad)
