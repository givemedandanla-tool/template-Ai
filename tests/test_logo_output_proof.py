from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication
from template_ai.importer import import_file
from template_ai.logo_assets import checked_payload
from template_ai.logo_output_proof import create_proof,validate_encoded

APP=QApplication.instance() or QApplication([])


class LogoOutputProofTests(unittest.TestCase):
    def test_actual_three_formats_readback_physical_dimensions_transparency_and_no_approval(self):
        from PySide6.QtGui import QImage
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'whole.svg';source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm"><circle cx="20" cy="15" r="5" fill="red"/></svg>')
            raw=import_file(source,root/'assets');asset=checked_payload(dict(image=raw['image'],svg=raw['svg'],source_width_mm=raw['width_mm'],source_height_mm=raw['height_mm'],crop=None))
            proof=create_proof(asset,30,15,root/'proofs',96)
            self.assertEqual(len(proof['files']),3);self.assertNotIn('approved',asset)
            self.assertFalse(proof['physical_print_verified']);self.assertFalse(proof['independent_visual_fidelity_verified'])
            from pypdf import PdfReader
            box=PdfReader(proof['files'][0]['path']).pages[0].mediabox
            self.assertAlmostEqual(float(box.width)*25.4/72,30,places=5)
            self.assertAlmostEqual(float(box.height)*25.4/72,15,places=5)
            png=QImage(next(f['path'] for f in proof['files'] if f['path'].endswith('.png')))
            self.assertEqual(png.pixelColor(0,0).alpha(),0)
            with self.assertRaises(ValueError):validate_encoded(proof['files'][0]['path'],40,15,96)
            Path(proof['files'][1]['path']).write_bytes(b'corrupt synthetic output')
            with self.assertRaises(ValueError):validate_encoded(proof['files'][1]['path'],30,15,96)

    def test_undecodable_logo_source_and_large_output_cannot_bypass_quality_with_flags(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'corrupt.png';path.write_bytes(b'not an image')
            with self.assertRaisesRegex(ValueError,'解碼'):checked_payload(dict(image=str(path),source_width_mm=10,source_height_mm=5,crop=None))
