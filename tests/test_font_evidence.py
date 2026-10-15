"""Actual system-font bytes; no font files or legal rights inferred in fixtures."""
import copy
import tempfile
import unittest
from pathlib import Path
from fontTools.ttLib import TTFont, TTCollection
from PySide6.QtWidgets import QApplication

from template_ai.font_evidence import inspect_font, output_rights_errors
from template_ai.fonts import FontManager
from template_ai.storage import Library

APP=QApplication.instance() or QApplication([])
SANS=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
SERIF=Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf')


class FontEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        self.manager=FontManager(self.library);self.addCleanup(self.manager.close)

    def test_collection_requires_face_then_persists_actual_selected_family_and_source_hash(self):
        collection=TTCollection();collection.fonts=[TTFont(SANS),TTFont(SERIF)]
        path=self.root/'two.ttc';collection.save(path)
        for font in collection.fonts:font.close()
        proof=inspect_font(path)
        self.assertEqual([f['family'] for f in proof['faces']],['DejaVu Sans','DejaVu Serif'])
        with self.assertRaisesRegex(ValueError,'明確選取'):self.manager.import_font(path,approved=True)
        self.assertEqual(self.library.fonts(),[])
        asset=self.manager.import_font(path,approved=True,face_index=1)
        self.assertEqual(asset['families'],['DejaVu Serif'])
        self.assertEqual(asset['font_evidence']['source_hash'],proof['hash'])
        self.assertEqual(asset['font_evidence']['index'],1)
        self.assertEqual(inspect_font(asset['path'])['faces'][0]['family'],'DejaVu Serif')
        self.assertTrue(output_rights_errors(asset,'png'))

    def test_technical_embedding_flags_never_supply_legal_rights_and_pdf_restrictions_are_stricter(self):
        font=TTFont(SANS);font['OS/2'].fsType=2;path=self.root/'restricted.ttf';font.save(path);font.close()
        asset=self.manager.import_font(path,approved=True)
        self.assertEqual(asset['font_evidence']['embedding'],'RESTRICTED')
        self.assertTrue(output_rights_errors(asset,'png'))
        approved=self.manager.record_output_rights(asset,'synthetic-test','test-only fixture attestation',True)
        self.assertEqual(output_rights_errors(approved,'png'),[])
        self.assertTrue(output_rights_errors(approved,'pdf'))
        forged=copy.deepcopy(approved);forged['font_evidence']['fs_type']=0
        self.assertTrue(output_rights_errors(forged,'pdf'))  # Re-read actual OS/2, not caller metadata.
        self.assertEqual(asset['usage_rights'],{})
        with self.assertRaisesRegex(ValueError,'已改變'):
            self.manager.record_output_rights(asset,'test','stale attestation')

    def test_approval_is_per_face_does_not_install_or_modify_templates_and_invalid_font_never_registers(self):
        asset=self.manager.import_font(SANS,approved=True)
        before=self.library.templates()
        updated=self.manager.record_output_rights(asset,'test','synthetic rights record',False)
        self.assertFalse(updated['usage_rights']['pdf_embedding'])
        self.assertEqual(self.library.templates(),before)
        self.assertEqual(inspect_font(updated['path'])['hash'],asset['hash'])
        bad=self.root/'broken.ttf';bad.write_bytes(b'not a font')
        with self.assertRaises(ValueError):self.manager.import_font(bad,approved=True)
        self.assertEqual(len(self.library.fonts()),1)

    def test_font_change_after_attestation_is_still_rejected_by_health_gate(self):
        from template_ai.fonts import font_errors
        asset=self.manager.import_font(SANS,approved=True)
        approved=self.manager.record_output_rights(asset,'test','synthetic test',True)
        Path(approved['path']).write_bytes(b'changed')
        self.assertTrue(font_errors(approved,approved['families'][0]))

    def test_actual_export_blocks_unknown_rights_allows_labelled_preview_and_only_new_explicit_binding_gets_rights(self):
        from template_ai.model import Template,Slot,Rect
        from template_ai.layout import generate
        from template_ai.render import export
        asset=self.manager.import_font(SANS,approved=True)
        template=Template('Synthetic rights',90,54,[Slot('name','p1',Rect(5,5,75,12),font=asset['families'][0],font_asset=asset,size_pt=12)])
        self.library.save_template(template);self.library.publish(template)
        candidate=generate(template,[{'name':'Example Person'}],[],{})
        self.assertTrue(candidate.valid,candidate.issues)
        with self.assertRaisesRegex(ValueError,'授權'):export(candidate,self.root/'FINAL.png',96)
        self.assertFalse((self.root/'FINAL.png').exists())
        self.assertGreater(export(candidate,self.root/'PREVIEW.png',96,True).stat().st_size,100)
        approved=self.manager.record_output_rights(asset,'synthetic-test','Synthetic test fixture rights',True)
        with self.assertRaisesRegex(ValueError,'授權'):export(candidate,self.root/'STILL-OLD-FINAL.png',96)
        from template_ai.model import new_id
        new=copy.deepcopy(template);new.id=new_id();new.version+=1;new.state='DRAFT';new.slots[0].font_asset=approved
        self.library.save_template(new);self.library.publish(new)
        fresh=generate(new,[{'name':'Example Person'}],[],{})
        for ext in ('png','pdf'):self.assertGreater(export(fresh,self.root/('NEW-FINAL.'+ext),96).stat().st_size,100)
        mixed=copy.deepcopy(new);mixed.id=new_id();mixed.version+=1;mixed.state='DRAFT'
        mixed.slots.append(Slot('phone','p1',Rect(5,25,75,12),font=asset['families'][0],font_asset=asset,size_pt=12))
        self.library.save_template(mixed);self.library.publish(mixed)
        candidate=generate(mixed,[{'name':'Example Person','phone':['0100']}],[],{})
        self.assertTrue(candidate.valid,candidate.issues)
        with self.assertRaisesRegex(ValueError,'授權'):export(candidate,self.root/'MIXED-FINAL.png',96)
