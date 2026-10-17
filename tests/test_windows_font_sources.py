"""Actual font files and bounded source inventory; no native Windows scan claim."""
import shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import test_font_center as fixture
from template_ai.windows_font_sources import collect_registered_font_sources,windows_font_sources
from template_ai.font_catalog import build_inventory,filter_inventory,recorded_use_rights
from template_ai.font_evidence import inspect_font

class WindowsFontSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.machine=self.root/'MachineFonts';self.machine.mkdir();self.user=self.root/'UserFonts';self.user.mkdir();self.source=self.machine/'Authored.ttf';shutil.copyfile(fixture.FONT,self.source);self.records=[dict(scope='MACHINE',file='Authored.ttf')];self.roots=dict(MACHINE=self.machine,USER=self.user)
    def collect(self,**kwargs):return collect_registered_font_sources(self.records,self.roots,**kwargs)
    def test_actual_registered_source_file_does_not_prove_current_qt_face_or_licence(self):
        value=self.collect();self.assertEqual(value['status'],'COMPLETE');self.assertEqual(len(value['files']),1);entry=value['files'][0];self.assertEqual(entry['hash'],inspect_font(self.source)['hash']);self.assertTrue(entry['faces']);self.assertFalse(entry['actual_qt_face_verified']);self.assertFalse(entry['source_rights_verified'])
    def test_source_outside_known_directory_or_network_is_rejected_before_font_read(self):
        self.records=[dict(scope='USER',file=str(self.source)),dict(scope='MACHINE',file='../escape.ttf'),dict(scope='MACHINE',file=r'\\server\share\font.ttf')]
        with patch('template_ai.windows_font_sources.inspect_font') as read:
            value=self.collect();read.assert_not_called()
        self.assertEqual(value['status'],'PARTIAL');self.assertFalse(value['files']);self.assertEqual(len(value['rejected']),3)
    def test_budget_exhaustion_is_partial_not_empty_complete_source_proof(self):
        with patch('template_ai.windows_font_sources.inspect_font') as read:value=self.collect(max_bytes=0);read.assert_not_called()
        self.assertEqual(value['status'],'PARTIAL');self.assertFalse(value['files']);self.assertEqual(value['source_bytes_budgeted'],0)
    def test_mutated_during_actual_parse_is_not_retained_as_current_source(self):
        def changed(path):
            value=inspect_font(path);Path(path).write_bytes(b'late changed authored font');return value
        with patch('template_ai.windows_font_sources.inspect_font',side_effect=changed):value=self.collect()
        self.assertEqual(value['status'],'PARTIAL');self.assertFalse(value['files'])
    def test_duplicate_registry_entries_share_byte_budget_without_losing_scopes(self):
        self.records*=2;value=self.collect();self.assertEqual(len(value['files']),1);self.assertEqual(value['source_bytes_budgeted'],self.source.stat().st_size)
    def test_nonwindows_source_catalog_is_explicitly_unavailable_without_native_io(self):
        with patch('template_ai.windows_font_sources.sys.platform','linux'),patch('template_ai.windows_font_sources._registry_snapshot') as read:value=windows_font_sources();read.assert_not_called()
        self.assertEqual(value['status'],'UNAVAILABLE');self.assertFalse(value['files'])
    def test_original_inventory_distinguishes_registered_file_qt_candidate_and_use_rights(self):
        origin=self.collect();family=origin['files'][0]['faces'][0]['family'];rows=build_inventory([],[],[dict(family=family,styles=['Book'])],windows_sources=origin)['rows'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['kind'],'QT');self.assertTrue(rows[0]['windows_sources']);self.assertEqual(recorded_use_rights(rows[0]),'UNKNOWN');self.assertEqual(filter_inventory(rows,kind='WINDOWS_SOURCE'),rows)
        unloaded=build_inventory([],[],[],windows_sources=origin)['rows'];self.assertEqual(unloaded[0]['kind'],'WINDOWS_SOURCE');self.assertEqual(unloaded[0]['status'],'WINDOWS_SOURCE_UNRESOLVED');self.assertEqual(recorded_use_rights(unloaded[0]),'UNKNOWN')

if __name__=='__main__':unittest.main()
