"""Authored actual Type3 PDF; preserve unknown physical typography without crashing."""
from io import BytesIO
import hashlib
import unittest
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, DecodedStreamObject, NumberObject, FloatObject
from template_ai.original_pdf_glyphs import extract_pdf_glyphs


def type3_pdf(scale_x=.001):
    writer=PdfWriter();page=writer.add_blank_page(width=255,height=153)
    glyph=DecodedStreamObject();glyph.set_data(b'600 0 0 0 600 700 d1 0 0 600 700 re f')
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type3'),
        NameObject('/Name'):NameObject('/AuthoredType3'),
        NameObject('/FontBBox'):ArrayObject([NumberObject(v) for v in (0,0,600,700)]),
        NameObject('/FontMatrix'):ArrayObject([FloatObject(v) for v in (scale_x,0,0,.001,0,0)]),
        NameObject('/FirstChar'):NumberObject(65),NameObject('/LastChar'):NumberObject(65),
        NameObject('/Widths'):ArrayObject([NumberObject(600)]),
        NameObject('/Encoding'):DictionaryObject({NameObject('/Type'):NameObject('/Encoding'),NameObject('/Differences'):ArrayObject([NumberObject(65),NameObject('/A')])}),
        NameObject('/CharProcs'):DictionaryObject({NameObject('/A'):writer._add_object(glyph)}),NameObject('/Resources'):DictionaryObject()})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 1 Tc 2 Tw 1 0 0 1 24 70 Tm (A) Tj ET');page[NameObject('/Contents')]=writer._add_object(content)
    stream=BytesIO();writer.write(stream);data=stream.getvalue()
    return data,dict(hash=hashlib.sha256(data).hexdigest(),page=1,width_mm=255*25.4/72,height_mm=153*25.4/72)


class Type3GlyphUnknownTests(unittest.TestCase):
    def check_unknown(self,scale_x):
        data,source=type3_pdf(scale_x);result=extract_pdf_glyphs(source,data);self.assertEqual(result['glyph_count'],1);run=result['runs'][0]
        self.assertEqual(run['font_declaration']['subtype'],'Type3');self.assertEqual(run['declared_pt']['value'],12)
        self.assertEqual(run['source_pt']['status'],'UNKNOWN');self.assertIsNone(run['source_pt']['value']);self.assertEqual(run['source_pt']['basis'],'UNSUPPORTED_FONT_MATRIX')
        self.assertIsNone(run['tracking']['value']);self.assertIsNone(run['word_spacing']['value']);self.assertEqual(run['font_asset_identity'],'UNKNOWN');self.assertEqual(run['native_illustrator_editability'],'UNKNOWN')
        self.assertNotIn('_private_text',run)

    def test_type3_default_matrix_remains_unknown_without_exception(self):
        self.check_unknown(.001)

    def test_type3_anisotropic_matrix_never_invents_physical_point_size(self):
        self.check_unknown(.002)
