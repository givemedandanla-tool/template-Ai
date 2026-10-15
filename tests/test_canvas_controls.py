import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
import test_object_tools as fixture

APP=fixture.APP


class CanvasControlTests(unittest.TestCase):
    setUp=fixture.ObjectToolsGuiTests.setUp

    def test_actual_resize_handle_previews_without_writing_and_applies_through_existing_history(self):
        slot=self.t.slots[0];before=self.w.library.object_snapshot('TEMPLATE',self.t.id);self.d.select_ids([slot.id]);canvas=self.d.canvas;r=slot.rect
        start=canvas.mapFromScene(QPointF(r.x+r.w,r.y+r.h));end=canvas.mapFromScene(QPointF(r.x+r.w+2,r.y+r.h+1))
        QTest.mousePress(canvas.viewport(),Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(canvas.viewport(),end);QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,Qt.NoModifier,end);APP.processEvents()
        self.assertIsNotNone(self.d.plan,self.d.status.text());self.assertEqual(self.d.request['operation'],'PATCH');self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before);self.assertGreater(self.d.plan['after']['slots'][0]['rect']['w'],r.w)
        self.assertEqual(self.d.plan['after']['slots'][0]['size_pt'],slot.size_pt);self.d.apply();self.assertNotEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id)['payload'],before['payload']);self.assertTrue(self.d.records)

    def test_keyboard_millimetre_nudge_space_pan_preserves_selection_and_lock_blocks_changes(self):
        identity=self.ids[0];self.d.select_ids([identity]);canvas=self.d.canvas;canvas.nudge_mm=.2
        QTest.keyClick(canvas,Qt.Key_Right);APP.processEvents();self.assertAlmostEqual(self.d.plan['changes'][0]['dx'],.2);self.d.apply();self.d.select_ids([identity])
        QTest.keyPress(canvas,Qt.Key_Space);self.assertEqual(canvas.mode,'pan');QTest.keyRelease(canvas,Qt.Key_Space);self.assertEqual(canvas.mode,'edit');self.assertEqual(canvas.selection_intent,{identity})
        self.d.preview_lock(True);self.d.apply();self.d.select_ids([identity]);before=self.w.library.object_snapshot('TEMPLATE',self.t.id)
        QTest.keyClick(canvas,Qt.Key_Right);APP.processEvents();self.assertIsNone(self.d.plan);self.assertIn('鎖定',self.d.status.text());self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before)

    def test_snap_projection_is_mm_based_toggleable_and_hiding_boundary_never_disables_validation(self):
        self.d.select_ids([self.ids[0]]);canvas=self.d.canvas;canvas.snap_enabled=True;dx,dy=canvas.snap(-7.9,0);self.assertAlmostEqual(dx,-8);self.assertTrue(canvas.snap_lines)
        canvas.snap_enabled=False;self.assertEqual(canvas.snap(-7.9,0),(-7.9,0));canvas.safety_visible=False
        self.d.preview_request(dict(operation='MOVE',ids=[self.ids[0]],dx=200,dy=0));self.assertIsNotNone(self.d.plan);self.assertTrue(any('邊界' in warning for warning in self.d.plan['warnings']));self.assertFalse(canvas.safety_visible)
