"""Actual extracted TTC face shaping identity and same-name changed metrics."""
from copy import deepcopy
import unittest
from fontTools.ttLib import TTFont
import test_multi_size as fixture
from template_ai.background import file_digest
from template_ai.render import render_image
from template_ai.font_catalog import analyze_font,raw_asset,face_fingerprint


class FontCollectionShapingTests(unittest.TestCase):
    setUp=fixture.MultiSizeTests.setUp
    tearDown=fixture.MultiSizeTests.tearDown

    def test_actual_extracted_collection_face_measures_and_renders_with_same_shaped_face(self):
        slot=self.templates[0].slots[0];proof=analyze_font({'kind':'ASSET','asset':slot.font_asset},'Alex',10,60,.85)
        self.assertTrue(proof['measurement_verified'],proof['issues']);self.assertTrue(self.entries[0]['candidates'][0].formal_eligible)
        image=render_image(self.entries[0]['candidates'][0],96,True)
        self.assertFalse(image.isNull());self.assertEqual(image.width(),round(90/25.4*96))

    def test_actual_same_family_with_changed_metric_table_is_still_rejected_for_shaping(self):
        slot=self.templates[0].slots[0];asset=deepcopy(slot.font_asset);original=raw_asset(asset)
        with TTFont(asset['path'],recalcTimestamp=False) as font:
            name=font.getBestCmap()[ord('A')];advance,bearing=font['hmtx'].metrics[name];font['hmtx'].metrics[name]=(advance+20,bearing);path=self.root/'changed-advance.otf';font.save(path)
        asset.update(path=str(path),hash=file_digest(path),usage_rights={})
        changed=raw_asset(asset);self.assertEqual(changed.familyName(),original.familyName());self.assertNotEqual(face_fingerprint(changed),face_fingerprint(original))
        result=analyze_font({'kind':'ASSET','asset':asset},'Alex',10,60,.85)
        self.assertFalse(result['measurement_verified']);self.assertIn('混用',result['issues'][0]);self.assertIsNone(result['width_mm'])
