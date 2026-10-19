from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter
from PySide6.QtWidgets import QApplication
from template_ai.design_text_flow import shape_flow,draw_flow
from template_ai.storage import Library
from template_ai.fonts import FontManager
from template_ai.demo import demo_template
from template_ai.model import Template
from authored_font_fixture import bind_authored_fonts

APP=QApplication.instance() or QApplication([])


class SourceConditionedFlowTests(unittest.TestCase):
    def test_word_spacing_keeps_single_word_natural_and_rejects_unreviewed_boundaries(self):
        rule=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['authored word spacing'],mode='WORDS',
            value_mm=.6,allowed_scripts=['Latn'],boundary_policy='ASCII_SPACE_QT_WORD_SPACING',
            last_line='NATURAL',zero_boundaries='KEEP_NATURAL')
        policy=dict(self.policy,spacing_rule=rule)
        plain=self.shape(value='Authored',policy=self.policy)
        single=self.shape(value='Authored',policy=policy)
        self.assertAlmostEqual(single['width_mm'],plain['width_mm'])
        self.assertEqual(single['spacing_rule']['boundary_count'],0)
        result=self.shape(value='North Road',policy=policy)
        plain=self.shape(value='North Road',policy=self.policy)
        self.assertGreater(result['width_mm'],plain['width_mm'])
        self.assertEqual(result['spacing_rule']['boundary_count'],1)
        for changed in (dict(rule,allowed_scripts=['Hani']),dict(rule,mode='OBJECT_GAPS'),dict(rule,last_line='FORCE')):
            with self.assertRaises(ValueError):self.shape(policy=dict(self.policy,spacing_rule=changed))
        with self.assertRaisesRegex(ValueError,'mixed-boundary'):
            self.shape(value='North Road',policy=dict(policy,alignment='justify'))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.library=Library(Path(self.temp.name)/'data');self.addCleanup(self.library.close)
        self.template=bind_authored_fonts(demo_template(),FontManager(self.library))
        self.slot=self.template.slots[0];self.slot.kind='address';self.slot.size_pt=10.
        self.policy=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',break_rule='WORD_WRAP',
            max_lines_observed=4,line_height_factor=1.,alignment='left',evidence_refs=['authored reviewed source'])
        self.slot.text_flow=deepcopy(self.policy)
        self.value='123 Authored Road North District'

    def shape(self,value=None,policy=None,kind='address'):
        return shape_flow(value or self.value,self.slot.font,self.slot.size_pt,1.,30.,self.slot.font_asset,
            self.slot.font_style,0.,policy or self.policy,kind)

    def test_actual_qt_line_shaping_preserves_all_input_and_rejects_over_capacity(self):
        result=self.shape()
        self.assertGreater(len(result['lines']),1)
        self.assertEqual(sum(row['length'] for row in result['lines']),len(self.value))
        self.assertLessEqual(result['width_mm'],30.)
        with self.assertRaisesRegex(ValueError,'exceeds'):
            self.shape(policy=dict(self.policy,max_lines_observed=1))

    def test_semantic_tokens_do_not_acquire_arbitrary_break_permission(self):
        for kind in ('phone','email','line','ig','name'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.shape(kind=kind)
        with self.assertRaises(ValueError):self.shape(policy=dict(self.policy,evidence_refs=[]))

    def test_persisted_slot_recreates_same_pixels_and_actual_ink_fits_frame(self):
        clone=Template.from_dict(self.template.to_dict()).slots[0]
        def render(slot):
            image=QImage(600,400,QImage.Format_ARGB32);image.fill('white')
            painter=QPainter(image);painter.scale(10,10)
            try:draw_flow(painter,QRectF(5,5,30,25),self.value,slot,1.,0.)
            finally:painter.end()
            return image
        first=render(self.slot);second=render(clone)
        self.assertEqual(first,second)
        occupied=[(x,y) for y in range(first.height()) for x in range(first.width())
                  if first.pixelColor(x,y).red()<200]
        self.assertTrue(occupied)
        self.assertTrue(all(48<=x<=352 and 48<=y<=302 for x,y in occupied))

    def test_missing_font_and_short_actual_height_are_blocked(self):
        asset=deepcopy(self.slot.font_asset);asset['path']='/missing/authored-font.ttf'
        with self.assertRaises(ValueError):
            shape_flow(self.value,self.slot.font,10.,1.,30.,asset,self.slot.font_style,0.,self.policy,'address')
        image=QImage(100,100,QImage.Format_ARGB32);painter=QPainter(image)
        try:
            with self.assertRaises(ValueError):draw_flow(painter,QRectF(0,0,30,1),self.value,self.slot,1.,0.)
        finally:painter.end()

    def test_legacy_serialization_does_not_gain_null_flow_parameters(self):
        self.slot.text_flow=None
        self.assertTrue(all('text_flow' not in slot for slot in self.template.to_dict()['slots']))
