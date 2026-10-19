"""Authored source-evidence mechanics, not real Illustrator corpus qualification."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from template_ai.original_text_observation import original_text_observation

FONT_PROGRAM = b'%!PS-AdobeFont-1.0: Authored\n/Encoding 256 array\nreadonly def\n'

class OriginalTextObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, data, suffix='.svg', page=1):
        path = self.root/('customer'+suffix); path.write_bytes(data)
        return dict(current_path=str(path), hash=hashlib.sha256(data).hexdigest(), page=page,
                    width_mm=90, height_mm=54, svg=str(self.root/'untrusted-derivative.svg'))

    def svg(self, body, attributes=''):
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" '
                'viewBox="0 0 90 54" '+attributes+'>'+body+'</svg>').encode()

    def pdf(self, pages=1, embed=False):
        writer = PdfWriter()
        for i in range(pages):
            page = writer.add_blank_page(width=255, height=153)
            font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),
                                     NameObject('/Subtype'):NameObject('/Type1'),
                                     NameObject('/BaseFont'):NameObject('/Helvetica')})
            if embed:
                program = DecodedStreamObject(); program.set_data(FONT_PROGRAM)
                descriptor = DictionaryObject({NameObject('/FontFile'):writer._add_object(program)})
                font[NameObject('/FontDescriptor')] = writer._add_object(descriptor)
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            content = DecodedStreamObject()
            content.set_data(b'BT /F1 '+str(12+i).encode()+b' Tf 1 0 0 1 24 70 Tm (Authored source) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(content)
        path=self.root/'authored.pdf'; writer.write(path)
        return path.read_bytes()

    def test_original_svg_uniform_physical_size_and_declared_anchor_are_distinct(self):
        row = original_text_observation(self.source(self.svg(
            '<g transform="translate(4 2) scale(2)"><text id="t" x="3" y="5" font-family="Example" font-size="3.5">Private label</text></g>')))
        self.assertEqual(row['channel'], 'ORIGINAL_SVG'); self.assertEqual(row['state'],'OBSERVED')
        run=row['runs'][0]
        self.assertAlmostEqual(run['source_pt']['value'], 7*72/25.4)
        self.assertEqual(run['baseline_anchor_mm'], {'x':10.,'y':12.})
        self.assertEqual(run['font_asset_identity'],'UNKNOWN'); self.assertEqual(run['glyph_runs'],'UNKNOWN')
        self.assertEqual(run['role_mapping'],'UNKNOWN')
        self.assertNotIn('Private label', str(row))

    def test_nonuniform_transform_retains_declaration_but_not_unique_physical_pt(self):
        run=original_text_observation(self.source(self.svg(
            '<text font-size="12pt" transform="scale(2 3)">Text</text>')))['runs'][0]
        self.assertEqual(run['declared_pt']['value'],12)
        self.assertEqual(run['source_pt']['status'],'UNKNOWN')

    def test_css_and_relative_size_do_not_become_source_font_truth(self):
        for body in ['<style>text {font-size:20pt}</style><text font-size="12pt">X</text>',
                     '<text font-size="2em">X</text>',
                     '<text style="font:12px Example">X</text>']:
            with self.subTest(body=body):
                run=original_text_observation(self.source(self.svg(body)))['runs'][0]
                self.assertIsNone(run['source_pt']['value'])
                self.assertIsNone(run['declared_pt']['value'])

    def test_missing_size_no_default_and_unsupported_transform_no_fake_anchor(self):
        data=self.svg('<text x="2" y="3">X</text><text x="2" y="3" font-size="4" transform="skewX(15)">Y</text>')
        runs=original_text_observation(self.source(data))['runs']
        self.assertIsNone(runs[0]['source_pt']['value'])
        self.assertIsNone(runs[1]['source_pt']['value']); self.assertIsNone(runs[1]['baseline_anchor_mm'])

    def test_viewport_mismatch_and_css_transform_cannot_change_original_physical_truth(self):
        source=self.source(self.svg('<text x="2" y="3" font-size="4">X</text>'))
        source['width_mm']=180
        self.assertIsNone(original_text_observation(source)['runs'][0]['source_pt']['value'])
        run=original_text_observation(self.source(self.svg(
            '<text style="transform:scale(2)" x="2" y="3" font-size="4">X</text>')))['runs'][0]
        self.assertIsNone(run['source_pt']['value']); self.assertIsNone(run['baseline_anchor_mm'])

    def test_tail_and_duplicate_ids_keep_distinct_source_locator_without_inventing_metrics(self):
        row=original_text_observation(self.source(self.svg(
            '<text id="same" font-size="4">A<tspan>B</tspan>C</text><text id="same">D</text>')))
        self.assertEqual(len(row['runs']),4)
        self.assertEqual(len({r['id'] for r in row['runs']}),4)
        tail=next(r for r in row['runs'] if r['source_locator']['kind']=='SVG_TEXT_TAIL')
        self.assertIsNone(tail['source_pt']['value'])

    def test_pdf_compatible_ai_records_original_font_state_not_native_editability_or_glyph_positions(self):
        row=original_text_observation(self.source(self.pdf(),'.ai'))
        self.assertEqual(row['state'],'OBSERVED'); run=row['runs'][0]
        self.assertEqual(run['declared_pt']['value'],12)
        self.assertEqual(run['font_declaration']['base_font'],'/Helvetica')
        self.assertIsNone(run['source_pt']['value']); self.assertIsNone(run['baseline_anchor_mm'])
        self.assertEqual(row['native_illustrator_editability'],'UNKNOWN')
        self.assertEqual(row['scope'],'SOURCE_PAGE_NOT_WORK_OR_FIELD')

    def test_pdf_page_and_embedded_program_hash_do_not_claim_original_font_asset(self):
        row=original_text_observation(self.source(self.pdf(pages=2,embed=True),'.ai',page=2))
        self.assertEqual(row['runs'][0]['declared_pt']['value'],13)
        self.assertEqual(row['runs'][0]['font_program_sha256'],
            hashlib.sha256(FONT_PROGRAM).hexdigest())
        self.assertEqual(row['runs'][0]['font_asset_identity'],'UNKNOWN')

    def test_budget_failure_does_not_return_a_truncated_complete_document(self):
        source=self.source(self.svg('<text>A</text><text>B</text>'))
        with patch('template_ai.original_text_observation.MAX_RUNS',1):
            row=original_text_observation(source)
        self.assertEqual(row['state'],'BUDGET_EXCEEDED'); self.assertEqual(row['runs'],[])

    def test_unsupported_original_does_not_read_derivative_font_declarations(self):
        source=self.source(b'%!PS-Adobe-3.0 example','.ai')
        Path(source['svg']).write_text('<svg><text font-size="99pt">False evidence</text></svg>')
        row=original_text_observation(source)
        self.assertEqual(row['state'],'UNSUPPORTED'); self.assertEqual(row['runs'],[])

    def test_invalid_and_changing_sources_cannot_be_used_as_current_evidence(self):
        source=self.source(self.svg('<text>A</text>'))
        changed=deepcopy(source); changed['hash']='0'*64
        with self.assertRaises(ValueError):original_text_observation(changed)
        from template_ai.source_links import verify_source
        calls=[]
        def verify(*args):
            calls.append(1)
            if len(calls)==2:Path(source['current_path']).write_text('changed source')
            return verify_source(*args)
        with patch('template_ai.original_text_observation.verify_source',side_effect=verify):
            with self.assertRaises(ValueError):original_text_observation(source)

    def test_same_source_is_repeatable_and_other_page_has_different_identity(self):
        source=self.source(self.pdf(pages=2),'.ai')
        first=original_text_observation(source)
        self.assertEqual(first,original_text_observation(source))
        other=original_text_observation(dict(source,page=2))
        self.assertNotEqual(first['runs'][0]['id'],other['runs'][0]['id'])
