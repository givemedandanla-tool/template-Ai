"""Exercise real SVG/Qt paths; runtime identities are controlled upgrade fixtures."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from template_ai.importer import import_file,cache_matches,metadata_checksum,inkscape_path

APP=QApplication.instance() or QApplication([])


class InkscapeCacheIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.assets=self.root/'assets'
        self.source=self.root/'authored.svg'
        self.source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="10" height="10"/></svg>')

    @unittest.skipUnless(inkscape_path(),'Real Inkscape required for cache upgrade integration')
    def test_runtime_upgrade_creates_new_cache_preserving_old_bytes(self):
        with patch('template_ai.inkscape_runtime.runtime_identity',return_value={'policy':'CONTROLLED_UPGRADE','version':'A','executable_sha256':'a'*64}):
            a=import_file(self.source,self.assets)
        first=Path(a['image']);old_bytes=first.read_bytes();old_mtime=first.stat().st_mtime_ns
        with patch('template_ai.inkscape_runtime.runtime_identity',return_value={'policy':'CONTROLLED_UPGRADE','version':'B','executable_sha256':'b'*64}):
            b=import_file(self.source,self.assets);again=import_file(self.source,self.assets)
        self.assertNotEqual(a['image'],b['image']);self.assertFalse(b['reused']);self.assertTrue(again['reused'])
        self.assertEqual(first.read_bytes(),old_bytes);self.assertEqual(first.stat().st_mtime_ns,old_mtime)
        self.assertEqual(b['renderer_identity']['version'],'B')

    def test_historical_integrity_validation_does_not_require_current_engine(self):
        with patch('template_ai.importer.inkscape_path',return_value=None):row=import_file(self.source,self.assets)
        row.pop('renderer_identity');row.pop('renderer_execution');row['metadata_sha256']=metadata_checksum(row)
        self.assertTrue(cache_matches(row,Path(row['image']).parent,row['hash'],row['page']))

    def test_raster_import_keeps_working_without_a_usable_bundle(self):
        path=self.root/'authored.png';image=QImage(40,40,QImage.Format_ARGB32);image.fill(0xffffffff);image.save(str(path))
        with patch('template_ai.importer.inkscape_path',side_effect=ValueError('bundle unavailable')):
            row=import_file(path,self.assets);again=import_file(path,self.assets)
        self.assertEqual(row['engine'],'點陣來源；毫米尺寸待使用者標定');self.assertTrue(again['reused'])

    def test_non_object_metadata_is_rebuilt_instead_of_crashing(self):
        with patch('template_ai.importer.inkscape_path',return_value=None):
            row=import_file(self.source,self.assets)
            (Path(row['image']).parent/'metadata.json').write_text('[]')
            fixed=import_file(self.source,self.assets)
        self.assertFalse(fixed['reused']);self.assertEqual(fixed['renderer_execution'],'BUILTIN_QT_FALLBACK')

    def test_qt_fallback_is_not_reported_as_successful_inkscape_execution(self):
        with patch('template_ai.importer.inkscape_path',return_value=None):row=import_file(self.source,self.assets)
        self.assertEqual(row['renderer_identity']['policy'],'BUILTIN_QT_FALLBACK')
        self.assertEqual(row['renderer_execution'],'BUILTIN_QT_FALLBACK')


if __name__=='__main__':unittest.main()
