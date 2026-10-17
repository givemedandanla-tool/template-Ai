from copy import deepcopy
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QImage,QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.gui import MainWindow
from template_ai.demo import demo_template
from template_ai.model import template_errors
from template_ai.layout import text_geometry,generate
from template_ai.text_policy import tracking_geometry
from template_ai.text_policy_dialog import TextPolicyDialog
from template_ai.render import draw_text

APP=QApplication.instance() or QApplication([])

class TextPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.w=MainWindow(Path(self.temp.name)/'data');self.addCleanup(self.w.library.close);self.w.error=lambda message:None
        self.t=demo_template();self.w.library.save_template(self.t);self.w.refresh_templates(self.t.id);self.w.open_catalog_editor(self.t.id);self.w.show();APP.processEvents();self.w.edit_canvas.fit()

    def test_main_canvas_tree_property_keyboard_resize_and_undo_are_one_draft(self):
        c=self.w.edit_canvas;slot=self.w.template.slots[0];original=deepcopy(self.w.template.to_dict());node=next(item for item in self.w.editor_tree_nodes if item.data(0,Qt.UserRole)==[slot.id]);self.w.editor_tree.clearSelection();node.setSelected(True)
        self.assertEqual(c.selection_intent,{slot.id});self.assertEqual(self.w.current_slot.id,slot.id)
        c.setFocus(Qt.OtherFocusReason);APP.processEvents()
        QTest.keyClick(c,Qt.Key_Right);self.assertAlmostEqual(self.w.template.slots[0].rect.x,slot.rect.x+.1)
        current=self.w.template.slots[0];corner=c.mapFromScene(QPointF(current.rect.x+current.rect.w,current.rect.y+current.rect.h));end=c.mapFromScene(QPointF(current.rect.x+current.rect.w+1,current.rect.y+current.rect.h+1));QTest.mousePress(c.viewport(),Qt.LeftButton,pos=corner);QTest.mouseMove(c.viewport(),end);QTest.mouseRelease(c.viewport(),Qt.LeftButton,pos=end)
        self.assertGreater(self.w.template.slots[0].rect.w,original['slots'][0]['rect']['w']);self.assertEqual(self.w.template.slots[0].size_pt,18);self.assertEqual(self.w.library.template_snapshots()[0]['template'],original)
        self.w.undo();self.w.undo();self.assertEqual(self.w.template.to_dict(),original)

    def test_bounded_measured_tracking_keeps_fixed_size_and_blocks_long_content(self):
        slot=deepcopy(self.t.slots[1]);text='Designer Example';base=text_geometry(slot.font,slot.size_pt,text)[0];slot.tracking_mm=.5;slot.tracking_min_mm=0;slot.tracking_max_mm=.5;slot.rect.w=base+1
        width,height,errors,chosen,strategy=tracking_geometry(slot,text,text_geometry);self.assertFalse(errors);self.assertGreater(chosen,0);self.assertLess(chosen,.5);self.assertLessEqual(width,slot.rect.w+.0001);self.assertEqual(slot.size_pt,11)
        t=deepcopy(self.t);t.state='published';t.slots[1]=slot;candidate=generate(t,[dict(name='Alex',title='X'*200,phone='123',email='a@example.test')],[],{})
        self.assertTrue(any('固定' in reason for reason in candidate.issues));self.assertEqual(candidate.items[1].text,'X'*200);self.assertEqual(candidate.items[1].slot.size_pt,11)

    def test_distributed_requires_explicit_semantic_approval_and_never_applies_to_identifiers(self):
        slot=self.t.slots[1];slot.align='distributed';slot.tracking_max_mm=.5;self.assertTrue(any('分散' in reason for reason in template_errors(self.t)))
        slot.distribution_approval=dict(approved=True,actor='SYNTHETIC',reason='Reviewed title-only design');self.assertFalse(template_errors(self.t))
        for kind in ('name','email','phone','mobile','company'):
            slot.kind=kind;self.assertTrue(any('分散' in reason for reason in template_errors(self.t)))

    def test_actual_text_policy_dialog_cancel_then_explicit_draft_apply_and_normal_edit_preserves_policy(self):
        slot=self.w.template.slots[1];self.w.editor_selection([slot.id]);d=TextPolicyDialog(self.w);self.addCleanup(d.close);d.values[0].setValue(.2);d.values[2].setValue(.5);d.distribute.setChecked(True);d.reason.setText('SYNTHETIC title design')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):d.apply()
        self.assertEqual(self.w.template.slots[1].tracking_mm,0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.apply()
        slot=self.w.template.slots[1];self.assertEqual(slot.tracking_mm,.2);self.assertEqual(slot.align,'distributed');self.assertEqual(slot.size_pt,11);self.w.select_slot(slot);self.w.coords[0].setValue(9);self.w.apply_properties();self.assertEqual(self.w.template.slots[1].tracking_max_mm,.5);self.assertEqual(self.w.template.slots[1].distribution_approval['reason'],'SYNTHETIC title design')
        self.assertEqual(self.w.library.template_snapshots()[0]['template']['slots'][1]['tracking_mm'],0)

    def test_raster_uses_same_fixed_point_tracking_parameter_as_measurement(self):
        from PySide6.QtCore import QRectF
        slot=self.t.slots[1];images=[]
        for spacing in (0,.5):
            image=QImage(800,200,QImage.Format_ARGB32);image.fill(Qt.white);p=QPainter(image);p.scale(8,8)
            try:draw_text(p,QRectF(0,0,90,20),'Designer',slot.font,slot.size_pt,1,'left',tracking_mm=spacing)
            finally:p.end()
            images.append(bytes(image.constBits()))
        self.assertNotEqual(*images);a=text_geometry(slot.font,slot.size_pt,'Designer');b=text_geometry(slot.font,slot.size_pt,'Designer',tracking_mm=.5);self.assertGreater(b[0],a[0]);self.assertEqual(b[1],a[1])
