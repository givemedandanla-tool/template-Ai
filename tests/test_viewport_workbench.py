from copy import deepcopy
import unittest
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
from template_ai.annotation_compare import build_annotation_comparison
from template_ai.comparison_view import CanvasCompareDialog
from template_ai.viewport_controls import navigation_controls
import test_annotation_gui as fixture

APP=fixture.APP

class ViewportWorkbenchTests(unittest.TestCase):
    setUp=fixture.AnnotationGuiTests.setUp
    tearDown=fixture.AnnotationGuiTests.tearDown
    job=fixture.AnnotationGuiTests.job
    run_job=fixture.AnnotationGuiTests.run_job
    window=fixture.AnnotationGuiTests.window
    ready=fixture.AnnotationGuiTests.ready

    def test_annotation_actual_before_after_images_and_bidirectional_selection_never_confirm(self):
        window,d=self.ready();slot=d.session.payload['slots'][0];d.select([slot['id']]);d.session.change(dict(operation='MOVE',ids=[slot['id']],dx=1,dy=0));d.refresh()
        old=deepcopy(d.session.base);changes=window.library.db.total_changes;d.compare();APP.processEvents();view=d.comparison
        self.assertEqual(view.windowTitle(),'原稿／修正前標記／修正草稿 · 同步唯讀對照');self.assertNotEqual(view.data['before_png'],view.data['after_png'])
        for raw in [view.data[k] for k in ('source_png','before_png','after_png')]:
            image=QImage();self.assertTrue(image.loadFromData(raw,'PNG'));self.assertLessEqual(image.width()*image.height(),1600*1600)
        view.views[2].picked.emit(slot['id']);self.assertEqual(d.ids,[slot['id']]);self.assertEqual(view.selected_id,slot['id'])
        if view.objects.count()>1:
            view.objects.setCurrentRow(1);self.assertEqual(d.ids,[view.objects.item(1).data(Qt.UserRole)])
        self.assertEqual(d.session.base,old);self.assertEqual(window.library.db.total_changes,changes);self.assertEqual(self.path.read_bytes(),self.original_bytes);view.reject()

    def test_unlinked_views_pan_independently_then_relink_to_source_anchor(self):
        window,d=self.ready();v=CanvasCompareDialog(build_annotation_comparison(d.session));self.addCleanup(v.close);v.show();APP.processEvents();v.fit_template()
        v.sync_enabled.setChecked(False);before=QPointF(v.views[0].shared_center);v.views[1].navigated.emit(QPointF(12,15),8)
        self.assertEqual(v.views[0].shared_center,before);self.assertEqual(v.views[1].shared_center,QPointF(12,15));self.assertEqual(v.views[1].shared_zoom,8)
        v.sync_enabled.setChecked(True);self.assertTrue(all(view.shared_center==before for view in v.views));self.assertTrue(all(view.shared_zoom==v.views[0].shared_zoom for view in v.views))
        v.zoom_input.setValue(7);self.assertTrue(all(view.shared_zoom==7 for view in v.views));v.zoom_slider.setValue(700);self.assertTrue(all(view.shared_zoom==v.zoom_value for view in v.views))

    def test_numeric_slider_keyboard_and_fit_change_only_view_not_slots_or_undo(self):
        window,d=self.ready();s=d.session.payload['slots'][0];d.select([s['id']]);baseline=deepcopy(d.session.payload);history=deepcopy(d.session.undo_stack) if hasattr(d.session,'undo_stack') else None
        c=d.canvas;c.zoom_percent.setValue(200);self.assertAlmostEqual(c.transform().m11(),c.logicalDpiX()/25.4*2,places=2)
        QTest.keyClick(c,Qt.Key_Plus,Qt.ControlModifier);self.assertAlmostEqual(c.transform().m11(),c.logicalDpiX()/25.4*2.5,places=2)
        c.zoom_slider.setValue(1000);self.assertAlmostEqual(c.transform().m11(),500,places=5);c.zoom_slider.setValue(0);self.assertAlmostEqual(c.transform().m11(),.2,places=5);c.fit();self.assertIn(s['id'],c.selection_intent)
        self.assertEqual(d.session.payload,baseline);self.assertEqual(self.path.read_bytes(),self.original_bytes)
        if history is not None:self.assertEqual(d.session.undo_stack,history)
