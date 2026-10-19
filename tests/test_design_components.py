from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor,QImage,QPainter
from PySide6.QtWidgets import QApplication

from template_ai.background import file_digest
from template_ai.design_text_flow import shape_flow,draw_flow
from template_ai.font_evidence import font_rights_diagnostics
from template_ai.fonts import FontManager,font_asset_errors
from template_ai.layout import Candidate,Placed
from template_ai.model import Slot,Rect,Template
from template_ai.storage import Library

APP=QApplication.instance() or QApplication([])


class SeparateComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.manager=FontManager(self.library);self.addCleanup(self.manager.close)
        rights=dict(actor='Authored fixture',basis='Open local test font and anonymous generated output',print_export=True,pdf_embedding=True)
        self.font=self.manager.import_font('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',True,usage_rights=rights)
        self.label_font=self.manager.import_font('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',True,usage_rights=rights)
        self.icon=self.root/'authored-icon.svg';self.icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M1 1 L9 1 L9 9 L1 9 Z" fill="black"/></svg>')
        self.asset=dict(path=str(self.icon),hash=file_digest(self.icon),source_hash='owned-source',reviewed_source_association=True,usage_rights=dict(print_export=True))
        self.presentation=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['authored label-value and icon frames'],
            value_frame=[.34,0.,.66,.20],components=[
                dict(kind='STATIC_TEXT',text='TEL',font_asset=self.label_font,pt_ratio=.8,frame=[.10,0.,.2,.18]),
                dict(kind='SVG_ICON',asset=self.asset,frame=[0.,.01,.06,.06])])
        self.policy=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['authored grouped container'],
            break_rule='NO_WRAP',max_lines_observed=1,line_height_factor=1.,alignment='left',presentation=self.presentation)
        self.slot=Slot('phone','p1',Rect(0,0,70,18),font=self.font['families'][0],size_pt=12,font_asset=self.font,text_flow=self.policy)

    def shape(self,value='+1 202 555 0100',policy=None):
        return shape_flow(value,self.slot.font,12,1.,70,self.font,'',0.,policy or self.policy,'phone')

    def test_actual_static_label_icon_and_dynamic_value_share_measured_output(self):
        result=self.shape();self.assertEqual(result['text_length'],len('+1 202 555 0100'))
        self.assertEqual(len(result['static_icons']),1)
        self.assertEqual(len({r.rawFont().familyName() for r in result['positioned_runs']}),2)
        self.assertLessEqual(result['width_mm'],70.);self.assertLessEqual(result['height_mm'],18.)
        image=QImage(1000,250,QImage.Format_RGB32);image.fill(QColor('white'));painter=QPainter(image)
        try:painter.scale(10,10);draw_flow(painter,QRectF(0,0,70,18),'+1 202 555 0100',self.slot,1.,0.)
        finally:painter.end()
        from template_ai.source_recovery import image_gray
        self.assertGreater(int((image_gray(image)<180).sum()),500)
        self.assertFalse(font_asset_errors([self.slot]))

    def test_overlap_missing_icon_and_secondary_font_rights_block_admission(self):
        policy=deepcopy(self.policy);policy['presentation']['components'][0]['frame'][0]=.4
        with self.assertRaisesRegex(ValueError,'collision'):self.shape(policy=policy)
        candidate=Candidate(Template('Owned',90,54,[self.slot]),[Placed(self.slot,'+1 202 555 0100',1.,0.)],[])
        self.assertEqual(font_rights_diagnostics(candidate,'PDF'),[])
        self.presentation['components'][0]['font_asset']=dict(self.label_font,usage_rights={})
        self.assertTrue(font_rights_diagnostics(candidate,'PDF'))
        self.icon.write_text('<svg/>')
        self.assertTrue(font_asset_errors([self.slot]))

    def test_long_values_do_not_overwrite_or_move_static_components_silently(self):
        with self.assertRaises(ValueError):self.shape('1234567890'*20)
        one=self.shape('202 555 0100');two=self.shape('202 555 0200')
        self.assertEqual(one['static_icons'][0]['rect'],two['static_icons'][0]['rect'])
        self.assertEqual(self.presentation['components'][0]['text'],'TEL')

    def test_source_binding_checks_original_label_run_and_physical_ratio(self):
        from dataclasses import asdict
        from template_ai.demo import demo_template
        from template_ai.importer import import_file
        from template_ai.training_store import TrainingStore
        from template_ai.design_source_binding import SourceTypographyReview
        from test_noise_authoring import confirmed
        path=self.root/'label-source.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><text x="15" y="14" font-size="6.35">Alex Example</text><text x="2" y="14" font-size="5.08">TEL</text></svg>')
        source=self.library.add_source(path,import_file(path,self.library.assets));template=demo_template()
        work=self.library.create_artwork(source['id'],'Owned label',dict(crop=asdict(Rect(0,0,90,54)),work_width=90,work_height=54,slots=[asdict(s) for s in template.slots],visual_confirmed=True))
        store=TrainingStore(self.library);confirmed(store,work);original=store._design_observation_document(work['id'])['original_text_evidence']
        review=dict(source_identity_confirmed=True,basis='Owned original label/font/container comparison',horizontal_scale=1.,tracking=0.,parameter_measurement_refs=['authored source'],
            label_binding=dict(status='CONFIRMED',kind='SEPARATE_STATIC_LABEL',evidence_refs=['authored label correspondence']),source_text_flow=deepcopy(self.policy))
        parts=review['source_text_flow']['presentation']['components'];parts.pop();parts[0]['source_run_id']=original['runs'][1]['id']
        service=SourceTypographyReview(self.library)
        plan=service.plan(work['id'],template.slots[0].id,original['runs'][0]['id'],self.font,review)
        saved=service.confirm(plan,'Author',True)
        self.assertEqual(saved['label_binding']['kind'],'SEPARATE_STATIC_LABEL')
        review['source_text_flow']['presentation']['components'][0]['pt_ratio']=.5
        with self.assertRaisesRegex(ValueError,'ratio contradicts'):service.plan(work['id'],template.slots[0].id,original['runs'][0]['id'],self.font,review)
