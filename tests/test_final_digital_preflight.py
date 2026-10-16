"""Formal publication must reject wrong encoded bytes, source sampling and races."""
import copy,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtGui import QImage
import test_first_version as fixture
import test_candidate_risk as risk_fixture
from template_ai.layout import generate
from template_ai.model import Slot,Rect
from template_ai.render import export
APP=fixture.APP


class FinalDigitalPreflightTests(unittest.TestCase):
    setUp=fixture.FirstVersionTests.setUp
    people=risk_fixture.CandidateRiskTests.people
    candidate=risk_fixture.CandidateRiskTests.candidate
    def logo_candidate(self,pixels=10):
        path=self.root/'authored-mark.png';image=QImage(pixels,max(1,pixels//2),QImage.Format_RGB32);image.fill(0xff224488);self.assertTrue(image.save(str(path)));t=copy.deepcopy(self.template);t.company_bindings={'p1':'c1'};t.slots.extend([Slot('company','c1',Rect(8,48,40,6),size_pt=8),Slot('logo','c1',Rect(75,48,10,5))]);people=self.people();people[0]['company']='c1';asset=dict(image=str(path),source_width_mm=20,source_height_mm=10,crop=None,approved=True,company='Authored Alpha',width_mm=90,height_mm=54);return generate(t,people,[dict(name='Authored Alpha')],{'c1':asset},7)
    def test_codec_success_flag_with_corrupt_png_bytes_does_not_publish(self):
        c=self.candidate();target=self.root/'corrupt-FINAL.png'
        def corrupt(image,path,*args):Path(path).write_bytes(b'not encoded pixels');return True
        with patch('template_ai.render.QImage.save',new=corrupt):
            with self.assertRaises(ValueError):export(c,target,96,False,7)
        self.assertFalse(target.exists());self.assertEqual(list(self.root.glob('.template-ai-*')),[])
    def test_valid_png_wrong_pixels_cannot_publish_on_dimensions_alone(self):
        c=self.candidate();target=self.root/'wrong-FINAL.png';original=QImage.save
        def wrong(image,path,*args):bad=QImage(image.size(),image.format());bad.fill(0xff000000);return original(bad,path,*args)
        with patch('template_ai.render.QImage.save',new=wrong):
            with self.assertRaises(ValueError):export(c,target,96,False,7)
        self.assertFalse(target.exists())
    def test_candidate_mutation_during_encoding_cannot_publish_stale_approval(self):
        c=self.candidate();target=self.root/'stale-FINAL.png';original=QImage.save
        def change(image,path,*args):result=original(image,path,*args);c.template.slots[0].rect.x+=.1;return result
        with patch('template_ai.render.QImage.save',new=change):
            with self.assertRaises(ValueError):export(c,target,96,False,7)
        self.assertFalse(target.exists())
    def test_current_source_pixel_shortfall_blocks_final_but_retains_marked_preview(self):
        c=self.logo_candidate();self.assertTrue(c.formal_eligible,c.issues);target=self.root/'low-source-FINAL.png'
        with self.assertRaises(ValueError):export(c,target,300,False,7)
        self.assertFalse(target.exists());preview=export(c,self.root/'low-source-PREVIEW.png',96,True,7);self.assertTrue(preview.is_file())
    def test_sufficient_actual_pixels_and_original_gate_can_publish_exact_png(self):
        c=self.logo_candidate(1000);self.assertTrue(c.formal_eligible,c.issues);path=export(c,self.root/'adequate-FINAL.png',96,False,7);self.assertFalse(QImage(str(path)).isNull())
    def test_corrupt_pdf_after_page_box_writer_cannot_publish(self):
        c=self.candidate();target=self.root/'corrupt-FINAL.pdf'
        def corrupt(path,*args):Path(path).write_bytes(b'not a readable pdf')
        with patch('template_ai.pdf_geometry.exact_page_box',side_effect=corrupt):
            with self.assertRaises(ValueError):export(c,target,96,False,7)
        self.assertFalse(target.exists())
    def test_pdf_boolean_sampling_setting_is_not_silently_ignored(self):
        with self.assertRaises(ValueError):export(self.candidate(),self.root/'invalid-FINAL.pdf',True,False,7)

    def test_valid_jpeg_with_wrong_logo_pixels_is_not_accepted_as_lossy_noise(self):
        c=self.logo_candidate(1000);target=self.root/'wrong-FINAL.jpg';original=QImage.save
        def wrong(image,path,*args):bad=QImage(image.size(),image.format());bad.fill(0xff000000);return original(bad,path,*args)
        with patch('template_ai.render.QImage.save',new=wrong):
            with self.assertRaises(ValueError):export(c,target,96,False,7)
        self.assertFalse(target.exists())
    def test_readable_same_size_blank_pdf_is_not_a_valid_substitute_for_the_card(self):
        from pypdf import PdfWriter
        c=self.candidate();target=self.root/'blank-FINAL.pdf'
        def blank(path,width,height):
            writer=PdfWriter();writer.add_blank_page(width=width*72/25.4,height=height*72/25.4)
            with open(path,'wb') as file:writer.write(file)
        with patch('template_ai.pdf_geometry.exact_page_box',side_effect=blank):
            with self.assertRaises(ValueError):export(c,target,96,False,7)
        self.assertFalse(target.exists())

if __name__=='__main__':unittest.main()
