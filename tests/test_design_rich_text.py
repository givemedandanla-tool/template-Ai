from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from template_ai.demo import demo_template
from template_ai.design_rich_text import resolve_segments
from template_ai.design_source_binding import SourceTypographyReview
from template_ai.design_text_flow import shape_flow, draw_flow
from template_ai.fonts import FontManager, font_asset_errors
from template_ai.importer import import_file
from template_ai.model import Rect, Slot
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from test_noise_authoring import confirmed
from test_trusted_samples import admitted

APP=QApplication.instance() or QApplication([])


class CompositeSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.manager=FontManager(self.library)
        self.addCleanup(self.manager.close)
        self.assets=[self.manager.import_font(Path('/usr/share/fonts/truetype/dejavu')/name,True)
            for name in ('DejaVuSans.ttf','DejaVuSerif.ttf')]
        path=self.root/'composite.svg'
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><text x="8" y="14" font-family="DejaVu Sans" font-size="6.35">Alex <tspan font-family="DejaVu Serif" font-size="4.23333333333333">Example</tspan></text></svg>')
        self.source=self.library.add_source(path,import_file(path,self.library.assets))
        self.template=demo_template();self.slot=self.template.slots[0]
        self.work=self.library.create_artwork(self.source['id'],'Authored composite',dict(crop=asdict(Rect(0,0,90,54)),
            work_width=90,work_height=54,slots=[asdict(s) for s in self.template.slots],visual_confirmed=True))
        self.store=TrainingStore(self.library);confirmed(self.store,self.work);self.sample=admitted(self.store,self.work)
        runs=self.store._design_observation_document(self.work['id'])['original_text_evidence']['runs']
        self.spans=[dict(start=0,end=5,source_run_id=runs[0]['id'],font_asset=self.assets[0],selector=dict(kind='WORD_SLICE',start=0,end=1)),
                    dict(start=5,end=12,source_run_id=runs[1]['id'],font_asset=self.assets[1],selector=dict(kind='WORD_SLICE',start=1,end=None))]
        self.review=dict(source_identity_confirmed=True,basis='Authored original source spans and locally verified faces',
            horizontal_scale=1.,tracking=0.,parameter_measurement_refs=['authored source'],
            label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['authored field']))
        self.service=SourceTypographyReview(self.library)

    def test_actual_multirun_binding_persists_all_fonts_and_new_text_selectors(self):
        plan=self.service.plan_composite(self.work['id'],self.slot.id,self.spans,self.review)
        saved=self.service.confirm(plan,'Author',True)
        self.assertEqual(len(saved['typography']['source_components']),2)
        rich=saved['source_text_flow']['rich_text']
        self.assertAlmostEqual(rich['segments'][1]['pt_ratio'],2/3)
        self.assertEqual([r['text'] for r in resolve_segments('Jamie Longer Family Name',rich)],['Jamie ','Longer Family Name'])
        from template_ai.design_learning import CrossWorkLearning,USE
        dataset=CrossWorkLearning(self.library).dataset_plan({self.sample['id']:'TRAIN'},dict(use=USE,actor='Author',basis='Authored test source'))
        field=next(f for f in dataset['examples'][0]['fields'] if f['id']==self.slot.id)
        self.assertEqual(len(field['source_text_flow']['rich_text']['segments']),2)

    def test_shared_qt_shaping_and_drawing_preserve_mixed_face_text(self):
        plan=self.service.plan_composite(self.work['id'],self.slot.id,self.spans,self.review)
        policy=plan['review']['source_text_flow'];asset=self.assets[0]
        result=shape_flow('Jamie New Family',asset['families'][0],18.,1.,150.,asset,'',0.,policy,'name')
        self.assertEqual(result['text_length'],len('Jamie New Family'))
        self.assertEqual(len({r.rawFont().familyName() for r in result['layout'].glyphRuns()}),2)
        slot=Slot('name','person:1',Rect(0,0,150,25),font=asset['families'][0],size_pt=18,font_asset=asset,text_flow=policy)
        image=QImage(1000,250,QImage.Format_RGB32);image.fill(QColor('white'));painter=QPainter(image)
        try:painter.scale(6,6);draw_flow(painter,QRectF(0,0,150,25),'Jamie New Family',slot,1.,0.)
        finally:painter.end()
        from template_ai.source_recovery import image_gray
        self.assertGreater(int((image_gray(image)<180).sum()),100)

    def test_wrong_coverage_stale_source_and_missing_secondary_font_are_rejected(self):
        with self.assertRaises(ValueError):self.service.plan_composite(self.work['id'],self.slot.id,[dict(self.spans[0],end=4),self.spans[1]],self.review)
        plan=self.service.plan_composite(self.work['id'],self.slot.id,self.spans,self.review)
        facts=self.store.facts(self.work['id']);self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):self.service.confirm(plan,'Author',True)
        policy=plan['review']['source_text_flow'];Path(self.assets[1]['path']).unlink()
        slot=Slot('name','person:1',Rect(0,0,100,20),font=self.assets[0]['families'][0],font_asset=self.assets[0],text_flow=policy)
        self.assertTrue(font_asset_errors([slot]))

    def test_exact_source_spans_do_not_guess_new_text_and_unicode_coverage_is_complete(self):
        spans=[{k:v for k,v in span.items() if k!='selector'} for span in self.spans]
        plan=self.service.plan_composite(self.work['id'],self.slot.id,spans,self.review)
        with self.assertRaisesRegex(ValueError,'no reviewed new-text'):resolve_segments('New Name',plan['review']['source_text_flow']['rich_text'])
        policy=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['authored'],segments=[
            dict(selector=dict(kind='WORD_SLICE',start=0,end=1)),dict(selector=dict(kind='WORD_SLICE',start=1,end=None))])
        value='王😀 家族 名稱'
        self.assertEqual(''.join(p['text'] for p in resolve_segments(value,policy)),value)
