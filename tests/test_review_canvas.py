"""True Qt interactions for page/work registration and measurement overlays."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QGraphicsRectItem, QGraphicsSimpleTextItem

from template_ai.review_tool.canvas import ReviewCanvas


APP = QApplication.instance() or QApplication([])


class ReviewCanvasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.image = Path(self.temp.name)/'original.png'
        image = QImage(1000, 500, QImage.Format.Format_RGB32)
        image.fill(QColor('white'))
        painter = QPainter(image)
        # This ink lies at page (24,15)-(34,19) mm, inside a work at (20,10).
        painter.fillRect(240,150,100,40,QColor('#114477'))
        painter.end()
        self.assertTrue(image.save(str(self.image)))
        self.before = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.fields = [
            dict(id='phone',label='手機',kind='mobile',rect=dict(x=4,y=5,w=10,h=4),review_state='UNCHECKED',measurements={
                'baseline':dict(status='UNKNOWN',value=None),
                'ink_bounds':dict(x=4.2,y=5.3,w=9.4,h=3.0),
                'container_bounds':dict(status='UNKNOWN',value=None),
                'distribution':dict(status='UNKNOWN',value=None)}),
            dict(id='email',label='電子郵件',kind='email',rect=dict(x=4.2,y=15,w=20,h=4),review_state='REVIEWED'),
        ]
        self.canvas = ReviewCanvas()
        self.canvas.resize(820, 560)
        self.canvas.set_source(self.image,100,50)
        self.canvas.set_work(dict(id='work',crop=dict(x=20,y=10,w=60,h=30),fields=self.fields))
        self.canvas.show()
        APP.processEvents()
        self.canvas.fit_work()
        self.canvas.fieldSelected.connect(lambda key: self.selected.append(key))
        self.canvas.annotationAdded.connect(lambda rect: self.added.append(rect))
        self.canvas.annotationResized.connect(lambda key,rect: self.resized.append((key,rect)))
        self.canvas.statusMessage.connect(lambda message:self.messages.append(message))
        self.selected, self.added, self.resized, self.messages = [], [], [], []

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.image.read_bytes()).hexdigest(),self.before)
        self.canvas.close()
        self.canvas.deleteLater()
        APP.sendPostedEvents()
        APP.processEvents()
        self.temp.cleanup()

    def labels(self):
        return [item.text() for item in self.canvas.measurement_items if isinstance(item,QGraphicsSimpleTextItem)]

    def test_real_image_registration_and_bidirectional_mm_coordinates(self):
        self.assertEqual(self.canvas.local_to_scene((4,5)),QPointF(24,15))
        self.assertEqual(self.canvas.scene_to_local(QPointF(34,19)),QPointF(14,9))
        self.assertEqual(self.canvas.field_items['phone'].rect().x(),24)
        self.assertEqual(self.canvas.field_items['phone'].rect().y(),15)
        transform = self.canvas.image_item.transform()
        self.assertEqual(transform.map(QPointF(240,150)),QPointF(24,15))
        QTest.mouseClick(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,self.canvas.field_center('phone'))
        self.assertEqual(self.selected,['phone'])
        self.assertEqual(self.canvas.selected_id,'phone')

    def test_click_and_draw_after_zoom_keep_work_local_coordinates(self):
        self.canvas.zoom(1.6)
        self.canvas.centerOn(QPointF(30,20))
        QTest.mouseClick(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,self.canvas.field_center('phone'))
        self.assertEqual(self.selected,['phone'])
        self.canvas.set_mode('add')
        start=self.canvas.mapFromScene(QPointF(26,17));end=self.canvas.mapFromScene(QPointF(36,22))
        QTest.mousePress(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
        QTest.mouseMove(self.canvas.viewport(),end)
        QTest.mouseRelease(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
        self.assertEqual(len(self.added),1)
        for key,want in dict(x=6,y=7,w=10,h=5).items():self.assertAlmostEqual(self.added[0][key],want,delta=.15)

    def test_dragging_a_handle_resizes_annotation_not_original(self):
        self.canvas.select_field('phone')
        self.canvas.set_mode('resize')
        start=self.canvas.mapFromScene(QPointF(34,19));end=self.canvas.mapFromScene(QPointF(39,22))
        QTest.mousePress(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
        QTest.mouseMove(self.canvas.viewport(),end)
        QTest.mouseRelease(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
        self.assertEqual(len(self.resized),1)
        key,rect=self.resized[0]
        self.assertEqual(key,'phone')
        for name,want in dict(x=4,y=5,w=15,h=7).items():self.assertAlmostEqual(rect[name],want,delta=.15)
        self.assertEqual(self.fields[0]['rect'],dict(x=4,y=5,w=10,h=4))

    def test_multiselection_can_supply_relationship_endpoints(self):
        QTest.mouseClick(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,self.canvas.field_center('phone'))
        QTest.mouseClick(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.ControlModifier,self.canvas.field_center('email'))
        self.assertEqual(self.canvas.selected_fields(),['phone','email'])
        # A main-window response selecting the current primary must not discard the set.
        self.canvas.select_field('email')
        self.assertEqual(self.canvas.selected_fields(),['phone','email'])
        self.assertEqual(self.canvas._labels['email'].text(),'電子郵件')

    def test_selected_caption_stays_above_original_content_at_each_zoom(self):
        self.canvas.select_field('phone')
        self.assertFalse(self.canvas._label_backgrounds['email'].isVisible())
        for factor in [1,1.7,.4]:
            self.canvas.zoom(factor)
            background=self.canvas._label_backgrounds['phone']
            caption=background.deviceTransform(self.canvas.viewportTransform()).mapRect(background.rect())
            field=self.canvas.mapFromScene(self.canvas.field_items['phone'].rect()).boundingRect()
            self.assertLess(caption.bottom(),field.top())

    def test_dimensions_and_ink_are_distinct_and_unknown_container_is_not_drawn(self):
        self.canvas.select_field('phone')
        self.assertTrue(self.canvas.show_measurement('size'))
        self.assertIn('欄位範圍',self.labels())
        self.assertIn('10 mm',self.labels())
        self.assertIn('4 mm',self.labels())
        self.assertTrue(self.canvas.show_measurement('ink_bounds'))
        self.assertIn('文字墨跡',self.labels())
        self.assertIn('9.4 mm',self.labels())
        overlays=[item.rect() for item in self.canvas.measurement_items if isinstance(item,QGraphicsRectItem)]
        self.assertAlmostEqual(overlays[0].left(),24.2)
        self.assertFalse(self.canvas.show_measurement('container_bounds'))
        self.assertEqual(self.canvas.measurement_items,[])
        self.assertIn('尚未取得',self.messages[-1])

    def test_unknown_baseline_and_distribution_do_not_become_fabricated_geometry(self):
        self.canvas.select_field('phone')
        for name in ['baseline','distribution']:
            self.assertFalse(self.canvas.show_measurement(name))
            self.assertEqual(self.canvas.measurement_items,[])
        self.assertIn('不能由總寬猜測',self.messages[-1])

    def test_alignment_shows_both_fields_and_observed_error(self):
        metric=dict(kind='aligned_to',alignment='left',field_ids=['phone','email'])
        self.assertTrue(self.canvas.show_measurement(metric,self.fields[0]))
        self.assertIn('切齊偏差 0.2 mm',self.labels())
        boxes=[item for item in self.canvas.measurement_items if isinstance(item,QGraphicsRectItem)]
        self.assertEqual(len(boxes),2)
        self.assertTrue(self.canvas.show_measurement('gap',self.fields[0],[self.fields[1]]))
        self.assertIn('垂直間距 6 mm',self.labels())

    def test_known_baseline_and_distribution_use_explicit_records(self):
        field=dict(self.fields[0],measurements={
            'baseline':dict(status='ANNOTATED',value=8.0),
            'distribution':dict(status='ANNOTATED',units=[dict(rect=dict(x=4,y=5,w=2,h=3)),dict(rect=dict(x=8,y=5,w=2,h=3))])})
        self.assertTrue(self.canvas.show_measurement('baseline',field))
        self.assertIn('文字基線',self.labels())
        self.assertTrue(self.canvas.show_measurement('distribution',field))
        self.assertIn('2 mm',self.labels())

    def test_unconverted_measurement_units_are_not_presented_as_millimetres(self):
        field=dict(self.fields[0],measurements={
            'baseline':dict(status='OBSERVED',value=40,unit='px'),
            'ink_bounds':dict(x=40,y=50,w=100,h=40,unit='px')})
        self.assertFalse(self.canvas.show_measurement('baseline',field))
        self.assertFalse(self.canvas.show_measurement('ink_bounds',field))
        self.assertEqual(self.canvas.measurement_items,[])

    def test_uncalibrated_preview_can_be_located_but_cannot_display_false_mm(self):
        field=dict(self.fields[0],measurements={'frame':{'coordinate':'UNVERIFIED_PREVIEW_MM'}})
        self.assertFalse(self.canvas.show_measurement('size',field))
        self.assertEqual(self.canvas.measurement_items,[])
        self.assertIn('實體比例尚未確認',self.messages[-1])
        self.canvas.set_work(dict(id='work',crop=dict(x=20,y=10,w=60,h=30),fields=self.fields,
                                  measurements={'width_mm':{'status':'UNKNOWN','value':None}}))
        self.assertTrue(self.canvas.locate_field('phone'))
        self.assertFalse(self.canvas.show_measurement('width','phone'))
        self.assertEqual(self.canvas.measurement_items,[])

    def test_hiding_overlays_preserves_source_and_clears_measurements(self):
        self.canvas.select_field('phone')
        self.canvas.show_measurement('size')
        self.canvas.set_overlays_visible(False)
        self.assertTrue(self.canvas.image_item.isVisible())
        self.assertFalse(self.canvas.field_items['phone'].isVisible())
        self.assertFalse(self.canvas._work_item.isVisible())
        self.assertEqual(self.canvas.measurement_items,[])
        self.canvas.set_overlays_visible(True)
        self.assertTrue(self.canvas.field_items['phone'].isVisible())


if __name__=='__main__':unittest.main()
