"""Actual imported faces, real glyph checks and independently recorded use rights."""
import unittest
import test_font_center as fixture
from template_ai.font_catalog import build_inventory,filter_inventory,analyze_font,recorded_use_rights,measured_glyph_state

class FontCenterFilterTests(unittest.TestCase):
    setUp=fixture.FontCatalogTests.setUp
    def test_import_or_system_availability_does_not_imply_recorded_use_rights(self):
        self.assertEqual(recorded_use_rights(self.row),'UNKNOWN')
        rows=build_inventory([],[],[dict(family='Synthetic host family',styles=['Regular'])])['rows'];self.assertTrue(rows);self.assertTrue(all(recorded_use_rights(r)=='UNKNOWN' for r in rows))
        self.assertEqual(filter_inventory([self.row],rights='PDF_RECORDED'),[])
    def test_actual_recorded_raster_and_pdf_rights_are_separate_filters(self):
        raster=self.manager.record_output_rights(self.asset,'Synthetic source author','Authored legal raster use',False);row=build_inventory([raster],[],[])['rows'][0];self.assertEqual(recorded_use_rights(row),'RASTER_RECORDED');self.assertEqual(filter_inventory([row],rights='PDF_RECORDED'),[])
        pdf=self.manager.record_output_rights(raster,'Synthetic source author','Authored legal raster and PDF use',True);row=build_inventory([pdf],[],[])['rows'][0];self.assertEqual(recorded_use_rights(row),'PDF_RECORDED');self.assertEqual(filter_inventory([row],rights='PDF_RECORDED'),[row])
    def test_actual_missing_glyph_and_covered_glyph_filters_keep_unmeasured_unknown(self):
        self.assertEqual(measured_glyph_state(self.row,{}),'NOT_CHECKED')
        good=analyze_font(self.row,'A1',10,80,.85);self.assertTrue(good['measurement_verified']);measurements={self.row['id']:good};self.assertEqual(filter_inventory([self.row],glyph='COVERED',measurements=measurements),[self.row])
        bad=analyze_font(self.row,'\U0010ffff',10,80,.85);self.assertTrue(bad['missing']);measurements[self.row['id']]=bad;self.assertEqual(filter_inventory([self.row],glyph='MISSING',measurements=measurements),[self.row]);self.assertEqual(filter_inventory([self.row],glyph='COVERED',measurements=measurements),[])
    def test_changed_asset_is_not_listed_as_authorized_healthy_font(self):
        asset=self.manager.record_output_rights(self.asset,'Synthetic source author','Authored rights',True)
        from pathlib import Path
        Path(asset['path']).write_bytes(b'corrupt authored font');row=build_inventory([asset],[],[])['rows'][0];self.assertEqual(recorded_use_rights(row),'BLOCKED');self.assertEqual(filter_inventory([row],rights='PDF_RECORDED'),[])

if __name__=='__main__':unittest.main()
