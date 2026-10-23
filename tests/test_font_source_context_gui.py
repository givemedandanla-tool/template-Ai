"""Original centre/current worker, actual local reference and stale input fences."""
import threading,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QFileDialog
import test_font_center as fixture
from gui_wait import wait_for_gui
from runtime_fixture import controlled_resources
from template_ai.font_catalog import analyze_font

class FontSourceContextGuiTests(unittest.TestCase):
    def setUp(self):
        fixture.FontCenterGuiTests.setUp(self);controlled_resources(self.window);self.d=self.dialog;self.d.show();self.d.refresh();self.wait();self.d.kind.setCurrentIndex(self.d.kind.findData('ASSET'));self.d.table.selectRow(0)
    def wait(self):self.assertTrue(wait_for_gui(lambda:not self.d.busy and not self.window.busy,15),self.d.status.text())
    def reference(self):
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(fixture.FONT),'Font')):self.d.choose_source_font()
        self.wait();self.assertIsNotNone(self.d.source_reference)
    def test_real_source_reference_and_current_face_match_do_not_rewrite_template_or_install(self):
        before=[t.to_dict() for t in self.window.library.templates()];self.assertIsNone(self.d.source_reference);self.assertIsNone(self.d.identity_report);self.reference();self.d.verify_source_identity();self.wait()
        self.assertEqual(self.d.identity_report['state'],'PROVEN_SAME_BYTES');self.assertEqual(self.d.identity_report['original_ai_font_relation'],'UNVERIFIED');self.assertIn('仍待證據',self.d.identity_label.text());self.assertEqual([t.to_dict() for t in self.window.library.templates()],before)
    def test_corrupt_current_copy_cannot_keep_source_identity_confirmation(self):
        self.reference();self.d.verify_source_identity();self.wait();self.assertEqual(self.d.identity_report['state'],'PROVEN_SAME_BYTES');Path(self.asset['path']).write_bytes(b'changed actual font');self.d.verify_source_identity();self.wait();self.assertEqual(self.d.identity_report['state'],'UNIDENTIFIED');self.assertIn('未核准',self.d.identity_label.text())
    def test_current_text_glyph_filter_resets_old_coverage_then_lists_real_missing(self):
        self.d.text.setText('A1');self.d.analyze();self.wait();self.assertEqual(len(self.d.measurements),1);self.d.glyph.setCurrentIndex(self.d.glyph.findData('COVERED'));self.assertEqual(len(self.d.visible_rows),1)
        self.d.text.setText('\U0010ffff');self.assertFalse(self.d.measurements);self.assertEqual(self.d.visible_rows,[]);self.d.glyph.setCurrentIndex(self.d.glyph.findData(None));self.d.table.selectRow(0);self.d.analyze();self.wait();self.d.glyph.setCurrentIndex(self.d.glyph.findData('MISSING'));self.assertEqual(len(self.d.visible_rows),1);self.assertIn('U+10FFFF',self.d.measurement_label.text())
    def test_owned_late_analysis_cannot_fill_new_input_coverage_cache(self):
        started=threading.Event();release=threading.Event();self.addCleanup(release.set);self.d.text.setText('A1')
        def slow(*args):started.set();release.wait(5);return analyze_font(*args)
        with patch('template_ai.font_dialog.analyze_font',side_effect=slow):
            self.d.analyze();self.assertTrue(wait_for_gui(started.is_set,3));self.d.text.setText('New current input');release.set();self.wait()
        self.assertFalse(self.d.measurements);self.assertIn('未將舊診斷',self.d.status.text())

    def test_registered_source_file_comparison_is_separate_from_current_qt_selected_face(self):
        from template_ai.windows_font_sources import collect_registered_font_sources
        from template_ai.font_catalog import build_inventory
        origin=collect_registered_font_sources([dict(scope='MACHINE',file=str(fixture.FONT))],dict(MACHINE=fixture.FONT.parent))
        family=origin['files'][0]['faces'][0]['family'];inventory=build_inventory([],[],[dict(family=family,styles=['Book'])],windows_sources=origin);self.d.kind.setCurrentIndex(self.d.kind.findData(None));self.d.show_inventory(inventory);self.d.kind.setCurrentIndex(self.d.kind.findData('WINDOWS_SOURCE'));self.d.table.selectRow(0);self.reference();self.d.verify_source_identity();self.wait()
        self.assertEqual(self.d.identity_report['state'],'PROVEN_SAME_BYTES');self.assertEqual(self.d.identity_report['comparison_scope'],'REGISTERED_WINDOWS_SOURCE_ONLY');self.assertFalse(self.d.identity_report['actual_qt_face_verified']);self.assertIn('仍待核對',self.d.identity_label.text())

if __name__=='__main__':unittest.main()
