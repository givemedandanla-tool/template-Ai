"""A visible host font is not a confirmed font source/use-rights record."""
import unittest
import test_first_version as fixture
from template_ai.digital_preflight import inspect_candidate
from template_ai.font_evidence import output_rights_errors
from template_ai.render import export

class HostFontSourceRightsTests(unittest.TestCase):
    setUp=fixture.FirstVersionTests.setUp
    candidate=fixture.FirstVersionTests.candidate
    def test_unknown_host_rights_are_not_empty_success_for_any_formal_format(self):
        for format in ('png','jpg','pdf'):self.assertTrue(output_rights_errors(None,format))
    def test_actual_host_font_without_record_cannot_publish_but_can_mark_preview(self):
        c=self.candidate();self.assertTrue(c.valid,c.issues);target=self.root/'unknown-host-FINAL.png'
        with self.assertRaises(ValueError):export(c,target,96,False,7)
        self.assertFalse(target.exists());self.assertTrue(export(c,self.root/'unknown-host-PREVIEW.png',96,True,7).is_file())
    def test_original_named_checklist_blocks_unknown_font_source_and_points_to_fields(self):
        c=self.candidate();value=inspect_candidate(c,'PNG',96);row=next((r for r in value['rows'] if r['code']=='FONT_USE_RIGHTS'),None)
        self.assertIsNotNone(row);self.assertEqual(row['status'],'BLOCKED');self.assertEqual(set(row['slot_ids']),{p.slot.id for p in c.items if p.slot.kind!='logo'});self.assertFalse(value['can_encode'])

if __name__=='__main__':unittest.main()
