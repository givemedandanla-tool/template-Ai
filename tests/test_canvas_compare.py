"""Full comparison contract: real sources/fonts, affine math, read-only Qt navigation and jobs."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPoint,QPointF,QTimer,Qt,QSize
from PySide6.QtGui import QImage,QColor,QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox,QGraphicsItem,QDialog
from template_ai.background import make_background
from template_ai.canvas_compare import build_comparison,source_point,template_point,pixel_point,verify_comparison
from template_ai.comparison_view import CanvasCompareDialog
from template_ai.demo import demo_template
from template_ai.font_catalog import build_inventory
from template_ai.font_review import field_key,fingerprint
from template_ai.font_review_dialog import FontReviewDialog
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.model import Rect
APP=QApplication.instance() or QApplication([])
FONT=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
MONO=Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')


class CanvasCompareTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.window=MainWindow(self.root/'data');self.addCleanup(self.window.close);self.library=self.window.library
        self.old=self.window.font_manager.import_font(FONT,approved=True);self.asset=self.window.font_manager.import_font(MONO,approved=True)
        self.target=build_inventory([self.asset],[],[])['rows'][0];self.t=demo_template()
        for s in self.t.slots:s.font=self.old['families'][0];s.font_asset=copy.deepcopy(self.old)
        self.t.slots[0].color='#a51b63';self.t.slots[0].align='right'
        self.path=self.root/'source.svg';self.path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="108mm" viewBox="0 0 180 108"><rect width="180" height="108" fill="#cdeeff"/><rect x="30" y="20" width="90" height="54" fill="#ffffcc"/></svg>')
        self.source=self.library.add_source(self.path,import_file(self.path,self.library.assets))
        self.work=self.library.create_artwork(self.source['id'],'anonymous',{'crop':Rect(30,20,90,54).__dict__,'work_width':90,'work_height':54,'slots':[],'visual_confirmed':False})
        self.t.source_id=self.source['id'];self.t.source_work_id=self.work['id'];self.t.source_work_revision=1;self.t.artwork=Rect(30,20,90,54)
        self.library.save_template(self.t);self.row=None;self.refresh()

    def refresh(self):
        self.snap=next(s for s in self.library.template_snapshots() if s['template']['id']==self.t.id)
        from template_ai.font_review import evaluate_review
        self.row=evaluate_review([self.snap],self.target,{field_key(self.t.id,self.t.slots[0].id):'Alex'})['rows'][0]
        self.context=self.library.comparison_source(self.snap['template'])

    def build(self,**kw):
        return build_comparison(kw.get('snapshot',self.snap),kw.get('row',self.row),kw.get('target',self.target),kw.get('text','Alex'),kw.get('context',self.context),kw.get('dpi',150))

    def wait(self,review):
        deadline=time.monotonic()+15
        while (review.busy or self.window.busy) and time.monotonic()<deadline:APP.processEvents();time.sleep(.005)
        self.assertFalse(review.busy);self.assertFalse(self.window.busy)

    def review(self):
        r=FontReviewDialog(self.window,self.target,'Alex');self.addCleanup(r.close)
        r.table.selectRow(0);r.fill_selected();r.validate();self.wait(r);return r

    def test_mapping_inverse_pixel_units_and_exact_historical_crop(self):
        changed=copy.deepcopy(self.work['payload']);changed['crop']=Rect(45,25,90,54).__dict__
        self.library.save_artwork(self.work['id'],changed,1)
        self.refresh();result=self.build();m=result['source']['mapping']
        self.assertEqual(m['revision'],1);self.assertEqual(m['crop'],Rect(30,20,90,54).__dict__)
        self.assertEqual(source_point(m,45,27),(75,47));self.assertEqual(template_point(m,75,47),(45,27))
        x,y=pixel_point(m,45,27);self.assertAlmostEqual(x,75*m['pixel_size'][0]/180);self.assertAlmostEqual(y,47*m['pixel_size'][1]/108)
        self.assertIn('已標定',m['unit'])
        raw=self.root/'raster.png';im=QImage(640,384,QImage.Format_RGB32);im.fill(QColor('#abcdef'));self.assertTrue(im.save(str(raw)))
        src=self.library.add_source(raw,import_file(raw,self.library.assets));self.assertFalse(src['calibrated'])
        work=self.library.create_artwork(src['id'],'raster',{'crop':Rect(20,10,50,30).__dict__,'work_width':90,'work_height':54,'slots':[]})
        self.t.source_id=src['id'];self.t.source_work_id=work['id'];self.t.artwork=Rect(20,10,50,30);self.library.save_template(self.t);self.refresh()
        m=self.build()['source']['mapping'];self.assertIn('未物理標定',m['unit']);self.assertEqual(source_point(m,45,27),(45,25));self.assertEqual(template_point(m,45,25),(45,27))
        bad=copy.deepcopy(self.context);bad['revision']=99
        with self.assertRaisesRegex(ValueError,'身份'):self.build(context=bad)
        bad=copy.deepcopy(self.context);bad['work']['crop']['w']=-1
        with self.assertRaisesRegex(ValueError,'範圍'):self.build(context=bad)

    def test_full_rectangles_only_selected_text_style_color_and_unknown_before(self):
        result=self.build();self.assertTrue(result['original_known']);self.assertTrue(result['source_png'])
        a=QImage.fromData(result['after_png']);b=QImage.fromData(result['before_png']);self.assertEqual(a.size(),QSize(*result['pixel_size']));self.assertNotEqual(result['before_png'],result['after_png'])
        # Every changed pixel is within the selected fixed rectangle; other fields stay blank.
        r=self.t.slots[0].rect;fx=a.width()/90;fy=a.height()/54;colored=False
        for y in range(a.height()):
            for x in range(a.width()):
                ca=a.pixelColor(x,y)
                if ca!=b.pixelColor(x,y):self.assertTrue(r.x*fx-1<=x<=(r.x+r.w)*fx+1 and r.y*fy-1<=y<=(r.y+r.h)*fy+1)
                if ca.red()>ca.green()+25 and ca.blue()>ca.green()+10:colored=True
        self.assertTrue(colored)
        Path(self.old['path']).unlink();result=self.build();self.assertFalse(result['original_known']);self.assertIn('fallback',result['original_reason'])
        original=QImage.fromData(result['before_png']);self.assertEqual(original.pixelColor(round(20*fx),round(10*fy)),QColor('white'))
        with self.assertRaisesRegex(ValueError,'文字'):self.build(text='  ')
        result=self.build(context={'status':'UNKNOWN','reason':'匿名來源未提供'});self.assertFalse(result['source_png']);self.assertIsNone(result['source']['mapping'])
        with self.assertRaisesRegex(ValueError,'過期'):self.build(snapshot={**self.snap,'revision':self.snap['revision']+1})

    def test_corrupt_source_background_target_budget_and_mid_render_mutation(self):
        result=self.build();path=Path(self.source['image']);old=path.read_bytes();path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'異動'):verify_comparison(result)
        with self.assertRaisesRegex(ValueError,'異動'):self.build()
        path.write_bytes(old)
        meta=path.parent/'metadata.json';saved=meta.read_text();meta.write_text('{}')
        with self.assertRaisesRegex(ValueError,'metadata'):self.build()
        meta.write_text(saved)
        from template_ai import canvas_compare as module
        with patch.object(module,'MAX_BYTES',1):
            with self.assertRaisesRegex(ValueError,'預算'):self.build()
        with patch.object(module,'MAX_TEMPLATE_PIXELS',1):
            with self.assertRaisesRegex(ValueError,'6 MP'):self.build()
        with patch.object(module.QImageReader,'size',return_value=QSize(5000,5000)):
            with self.assertRaisesRegex(ValueError,'12 MP'):self.build()
        clean=self.root/'background.svg';clean.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="90mm" height="54mm" fill="#f7f7f7"/></svg>')
        bg=import_file(clean,self.library.assets);self.t.background=make_background(bg,90,54,True);self.library.save_template(self.t);self.refresh()
        self.build();Path(bg['image']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'異動'):self.build()
        self.t.background=None;self.library.save_template(self.t);self.refresh()
        real=module.png;count=[0]
        def mutate(im):
            raw=real(im);count[0]+=1
            if count[0]==2:self.path.write_text('modified during rendering')
            return raw
        with patch.object(module,'png',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'異動'):self.build()
        self.path.write_text('original changed')
        with self.assertRaisesRegex(ValueError,'異動'):self.build()
        self.path.unlink();result=self.build();self.assertEqual(result['source']['status'],'UNKNOWN')
        Path(self.asset['path']).write_bytes(b'corrupt target')
        with self.assertRaisesRegex(ValueError,'異動'):self.build()

    def test_synchronized_fit_pan_zoom_selection_and_readonly(self):
        before=self.library.template_snapshots();db=self.library.db.total_changes;result=self.build()
        d=CanvasCompareDialog(result);self.addCleanup(d.close);d.show();APP.processEvents();d.fit_template()
        centers=lambda:[(v.shared_center,v.shared_zoom) for v in d.views]
        self.assertTrue(all(x==centers()[0] for x in centers()))
        d.fit_source();self.assertEqual(d.center,QPointF(60,34));d.focus_selected();d.zoom(1.25)
        event=QWheelEvent(QPointF(20,20),QPointF(20,20),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
        APP.sendEvent(d.views[1].viewport(),event);self.assertTrue(all(x==centers()[0] for x in centers()))
        d.fit_template();v=d.views[2];s=self.t.slots[1];pos=v.mapFromScene(QPointF(s.rect.x+s.rect.w/2,s.rect.y+s.rect.h/2))
        QTest.mouseClick(v.viewport(),Qt.LeftButton,pos=pos);self.assertEqual(d.selected_id,s.id);self.assertEqual(d.objects.currentItem().data(Qt.UserRole),s.id)
        d.focus_selected();self.assertEqual(d.center,QPointF(s.rect.x+s.rect.w/2,s.rect.y+s.rect.h/2));self.assertFalse(d.select_slot('other-template'))
        previous=d.center;QTest.mousePress(v.viewport(),Qt.LeftButton,pos=QPoint(50,50));QTest.mouseMove(v.viewport(),QPoint(80,65));QTest.mouseRelease(v.viewport(),Qt.LeftButton,pos=QPoint(80,65))
        self.assertNotEqual(d.center,previous);self.assertTrue(all(x==centers()[0] for x in centers()))
        for view in d.views:
            for frame in view.frames.values():self.assertFalse(frame.flags() & QGraphicsItem.ItemIsMovable)
        self.assertEqual(self.library.template_snapshots(),before);self.assertEqual(self.library.db.total_changes,db)

    def test_real_review_entry_worker_failure_retry_stale_and_no_writes(self):
        review=self.review();before=self.library.template_snapshots();changes=self.library.db.total_changes
        from template_ai import font_review_dialog as module
        with patch.object(module,'build_comparison',side_effect=OSError('comparison worker error')):review.review_selected();self.wait(review)
        self.assertIn('comparison worker error',review.status.text());self.assertTrue(review.review_button.isEnabled());self.assertFalse(review.approved)
        real_exec=CanvasCompareDialog.exec;seen=[]
        def inspect(dialog):
            seen.append(dialog);QTimer.singleShot(0,dialog.accept);return real_exec(dialog)
        with patch.object(CanvasCompareDialog,'exec',inspect),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            review.review_selected();self.wait(review)
        self.assertEqual(len(seen),1);self.assertTrue(review.approved);self.assertTrue(review.comparison_data['source_png']);self.assertFalse(review.table.cellWidget(0,0).isChecked())
        self.assertEqual(self.library.template_snapshots(),before);self.assertEqual(self.library.db.total_changes,changes)
        review.invalidate();review.validate();self.wait(review)
        jobs=[]
        with patch.object(self.window,'run_job',side_effect=lambda msg,work,callback:jobs.append((work,callback))):review.review_selected()
        review.table.cellWidget(0,3).setText('New input');jobs[0][1](jobs[0][0]());self.assertFalse(review.approved);self.assertIsNone(review.comparison_data)
        self.assertTrue(review.check_button.isEnabled())

    def test_live_file_and_clock_change_prevents_approval(self):
        review=self.review();real_exec=CanvasCompareDialog.exec
        def mutate_file(dialog):
            QTimer.singleShot(0,lambda:(self.path.write_text('modified while displayed'),dialog.accept()));return real_exec(dialog)
        with patch.object(CanvasCompareDialog,'exec',mutate_file),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):review.review_selected();self.wait(review)
        self.assertFalse(review.approved);self.assertIn('異動',review.status.text());self.assertEqual(self.library.font_change_history(),[])
        self.path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="108mm" viewBox="0 0 180 108"><rect width="180" height="108" fill="#cdeeff"/><rect x="30" y="20" width="90" height="54" fill="#ffffcc"/></svg>')
        def mutate_clock(dialog):
            def act():self.t.name='changed';self.library.save_template(self.t);dialog.accept()
            QTimer.singleShot(0,act);return real_exec(dialog)
        with patch.object(CanvasCompareDialog,'exec',mutate_clock),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):review.review_selected();self.wait(review)
        self.assertFalse(review.approved);self.assertIn('變更',review.status.text())
