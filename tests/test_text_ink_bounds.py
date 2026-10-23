from pathlib import Path
import tempfile,unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QImage,QPainter
from PySide6.QtCore import Qt,QRectF
from template_ai.model import Template,Slot,Rect
from template_ai.layout import text_geometry,generate
from template_ai.font_catalog import analyze_font
from template_ai.render import draw_text
APP=QApplication.instance() or QApplication([])

class TextInkBoundsTests(unittest.TestCase):
    def test_italic_overhang_is_measured_in_fit_bounds_and_cannot_pass_at_advance_only_width(self):
        row=dict(kind='QT',families=['DejaVu Sans'],styles=['Oblique']);result=analyze_font(row,'AV',18,90,1,'Oblique');self.assertTrue(result['measurement_verified']);self.assertGreater(result['fit_width_mm'],result['width_mm']);self.assertLess(result['ink_left_mm'],0)
        s=Slot('name','p1',Rect(4,4,result['width_mm'],15),font='DejaVu Sans',size_pt=18,font_style='Oblique',min_scale=1);t=Template('Synthetic ink bounds',90,54,[s],state='published');c=generate(t,[dict(name=['AV'])],[],{});self.assertFalse(c.valid);self.assertTrue(any(d['code']=='WIDTH' for d in c.diagnostics));self.assertEqual(s.size_pt,18)
    def test_exact_fit_italic_render_keeps_same_ink_as_large_unclipped_reference(self):
        for text in ('AV','j','f'):
            w,h,errors=text_geometry('DejaVu Sans',18,text,'Oblique');self.assertFalse(errors);images=[]
            for width in (w,70):
                image=QImage(1000,400,QImage.Format_ARGB32);image.fill(Qt.white);p=QPainter(image);p.setRenderHint(QPainter.Antialiasing);p.scale(10,10)
                try:draw_text(p,QRectF(4,4,width,h),text,'DejaVu Sans',18,1,'left',style='Oblique')
                finally:p.end()
                images.append(bytes(image.constBits()))
            self.assertTrue(images[0]==images[1],text+": ink differs from unclipped reference")
