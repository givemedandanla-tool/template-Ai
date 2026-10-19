from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from template_ai.background import file_digest
from template_ai.demo import demo_template
from template_ai.design_learning import CrossWorkLearning,USE
from template_ai.design_source_binding import SourceTypographyReview
from template_ai.fonts import FontManager
from template_ai.importer import import_file
from template_ai.local_font_recovery import LocalFontRecovery
from template_ai.model import Rect
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.visual_font_match import match_fonts
from test_noise_authoring import confirmed
from test_trusted_samples import admitted

APP=QApplication.instance() or QApplication([])


class VisualSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.manager=FontManager(self.library);self.addCleanup(self.manager.close)
        self.font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf');self.asset=self.manager.import_font(self.font,True)
        path=self.root/'visual-source.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><text x="8" y="14" font-family="DejaVu Sans" font-size="6.35">Alex Example</text></svg>')
        self.source=self.library.add_source(path,import_file(path,self.library.assets));template=demo_template();self.slot=template.slots[0]
        self.work=self.library.create_artwork(self.source['id'],'Authored visible source',dict(crop=asdict(Rect(0,0,90,54)),work_width=90,work_height=54,slots=[asdict(s) for s in template.slots],visual_confirmed=True))
        self.store=TrainingStore(self.library);confirmed(self.store,self.work);self.sample=admitted(self.store,self.work)
        image=QImage(self.source['image']);r=self.slot.rect;self.rect=[round(r.x*image.width()/90),round(r.y*image.height()/54),round(r.w*image.width()/90),round(r.h*image.height()/54)]
        cropped=image.copy(*self.rect);face=dict(path=str(self.font),sha256=file_digest(self.font),face_index=0)
        self.match=match_fonts(cropped,[dict(text='Alex Example',origin='REVIEWED_TEXT')],[face],pixels_per_mm=image.width()/90,tracking_options=(0.,))
        self.service=LocalFontRecovery(self.library)
        self.review=dict(source_identity_confirmed=True,visual_geometry_confirmed=True,basis='Compared authored visible source and exact local face',
            label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['authored review']),source_alignment='left')

    def record(self):return self.service.record(self.work['id'],self.slot.id,self.rect,self.match,0,'Author',True)

    def test_reproduced_visual_match_becomes_traceable_learning_evidence_without_native_truth(self):
        record=self.record();source=SourceTypographyReview(self.library)
        plan=source.plan_visual(self.work['id'],self.slot.id,record['id'],self.asset,self.review)
        saved=source.confirm(plan,'Author',True)
        self.assertEqual(saved['typography']['source_page_pt']['status'],'UNKNOWN')
        self.assertEqual(saved['typography']['source_pt']['status'],'DERIVED')
        self.assertAlmostEqual(saved['typography']['source_pt']['value'],18.,delta=.4)
        self.assertEqual(saved['typography']['word_spacing']['status'],'UNKNOWN')
        dataset=CrossWorkLearning(self.library).dataset_plan({self.sample['id']:'TRAIN'},dict(use=USE,actor='Author',basis='Owned visual rule learning'))
        field=next(row for row in dataset['examples'][0]['fields'] if row['id']==self.slot.id)
        self.assertIn('VISUAL_HYPOTHESIS',field['source_typography']['source_font_status'])

    def test_wrong_crop_face_and_changed_source_image_cannot_enter_model(self):
        with self.assertRaises(ValueError):self.service.record(self.work['id'],self.slot.id,[0,0,30,30],self.match,0,'Author',True)
        record=self.record();other=self.manager.import_font('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',True)
        with self.assertRaisesRegex(ValueError,'differs'):self.service.plan_binding(self.work['id'],self.slot.id,record['id'],other,self.review)
        Path(self.source['image']).write_bytes(b'changed source cache')
        with self.assertRaisesRegex(ValueError,'image changed'):self.service.checked(record['id'])

    def test_missing_review_and_stale_field_facts_are_rejected(self):
        record=self.record()
        with self.assertRaises(ValueError):self.service.plan_binding(self.work['id'],self.slot.id,record['id'],self.asset,dict(self.review,visual_geometry_confirmed=False))
        facts=self.store.facts(self.work['id']);self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):self.service.checked(record['id'])
