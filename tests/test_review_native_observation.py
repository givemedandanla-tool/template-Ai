"""Synthetic regression for native derivative provenance and geometry."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from template_ai.review_tool.native_observation import vector_objects,pdf_source
from template_ai.review_tool.native_reader import digest,IsolationError,NativeReaderError

class NativeObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_transformed_shapes_and_shifted_artboard_use_page_mm(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'synthetic.svg'
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="320 0 300 200" width="300pt" height="200pt"><g transform="translate(340,20)"><rect id="card" width="180" height="90"/></g><text id="text" x="330" y="20">SYNTHETIC</text></svg>')
            source=dict(current_path=str(p),hash=digest(p),semantic_svg=str(p),file_hashes={'semantic_svg':digest(p)},width_mm=300*25.4/72,height_mm=200*25.4/72)
            _,_,bounds=vector_objects(source,Path(folder))
            self.assertAlmostEqual(bounds['card'].x,20*25.4/72)
            self.assertAlmostEqual(bounds['card'].y,20*25.4/72)
            self.assertAlmostEqual(bounds['card'].w,180*25.4/72)
            self.assertNotIn('text',bounds)

    def test_derivative_does_not_replace_original_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.ai';source.write_bytes(b'synthetic-original')
            pdf=Path(folder)/'derived.pdf';pdf.write_bytes(b'%PDF-synthetic-identity-only')
            data=dict(current_path=str(source),hash=digest(source),native_derivative=dict(pdf=str(pdf),sha256=digest(pdf),source_sha256=digest(source)))
            derived=pdf_source(data)
            self.assertEqual(data['hash'],digest(source));self.assertEqual(derived['hash'],digest(pdf))
            pdf.write_bytes(b'changed')
            with self.assertRaises(IsolationError):pdf_source(data)

    def test_native_failure_never_falls_back_to_inkscape_or_placeholder(self):
        from template_ai.review_tool.analysis import analyse_file
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'test.ai';source.write_bytes(b'%PDF-synthetic')
            with patch('template_ai.review_tool.native_reader.read_document',side_effect=NativeReaderError('FAIL','Synthetic failure')),patch('template_ai.importer.import_file') as old:
                with self.assertRaises(NativeReaderError):analyse_file(source,Path(folder)/'cache',ocr=False)
                old.assert_not_called()

if __name__=='__main__':unittest.main()
