"""CORE-031：真實字面、確定排名、有界PNG與共用GUI端到端唯讀驗收。"""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from template_ai.demo import demo_template
from template_ai.font_catalog import analyze_font, build_inventory
from template_ai.font_candidates import find_candidates, render_candidate
from template_ai.font_candidate_dialog import FontCandidateDialog
from template_ai.font_dialog import FontCenterDialog
from template_ai.fonts import FontManager
from template_ai.gui import MainWindow
from template_ai.storage import Library

APP = QApplication.instance() or QApplication([])
FONT = next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'), Path(r'C:\Windows\Fonts\arial.ttf')) if p.is_file()), None)


@unittest.skipUnless(FONT, "缺少實際環境字型，不能當候選驗收PASS")
class FontCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.library=Library(Path(self.temp.name)/'data'); self.addCleanup(self.library.close)
        self.manager=FontManager(self.library); self.addCleanup(self.manager.close)
        self.asset=self.manager.import_font(FONT,approved=True)
        self.inventory=build_inventory([self.asset],[],[]); self.row=self.inventory['rows'][0]
        self.host={'id':'qt:'+self.row['families'][0], 'kind':'QT', 'families':self.row['families'],
                   'styles':self.row['styles'], 'status':'QT_AVAILABLE', 'source':'Qt來源未核實',
                   'references':[], 'notes':[], 'identity':'未知檔案身份'}

    def test_hard_filter_missing_glyph_never_produces_fallback_width(self):
        report=find_candidates(self.inventory,'AA'+chr(0x10ffff))
        self.assertEqual(report['candidates'],[]); self.assertEqual(len(report['excluded']),1)
        rejected=report['excluded'][0]
        self.assertEqual(rejected['analysis']['coverage'],.5)
        self.assertIsNone(rejected['analysis']['width_mm']); self.assertIn('U+10FFFF',' '.join(rejected['reasons']))

    def test_unapproved_missing_modified_unknown_are_excluded_with_reasons(self):
        unknown={'id':'reference:x','kind':'REFERENCE','families':self.row['families'],'styles':[],
                 'status':'REFERENCE_UNKNOWN','source':'未知引用','references':[],'notes':['引用未知'],'identity':'未知'}
        self.inventory['rows'].append(unknown)
        Path(self.asset['path']).write_bytes(b'changed after inventory')
        report=find_candidates(self.inventory,'Alex')
        self.assertEqual(report['candidates'],[])
        self.assertTrue(any('異動' in ' '.join(r['reasons']) for r in report['excluded']))
        self.assertTrue(any('引用未知' in ' '.join(r['reasons']) for r in report['excluded']))
        for status in ('MISSING','UNAPPROVED','UNREADABLE','NOT_CHECKED'):
            report=find_candidates({'status':'COMPLETE','rows':[{**self.row,'status':status}]},'Alex')
            self.assertEqual(len(report['excluded']),1); self.assertTrue(report['excluded'][0]['reasons'])

    def test_exact_horizontal_boundary_preserves_size_and_full_text(self):
        natural=analyze_font(self.row,'AV Example',12,80)['width_mm']
        good=find_candidates(self.inventory,'AV Example',12,natural*.85,.85)
        bad=find_candidates(self.inventory,'AV Example',12,natural*.84,.85)
        self.assertEqual(len(good['candidates']),1); self.assertEqual(bad['candidates'],[])
        self.assertEqual(good['candidates'][0]['analysis']['size_pt'],12)
        self.assertEqual(good['input']['text'],'AV Example')

    def test_source_identity_precedes_width_rank_and_unknown_reference_has_no_score(self):
        inventory={'status':'COMPLETE','rows':[self.host,self.row]}
        report=find_candidates(inventory,'AV Example')
        self.assertEqual([c['row']['kind'] for c in report['candidates']],['ASSET','QT'])
        self.assertTrue(all(c['width_delta_ratio'] is None for c in report['candidates']))
        self.assertIsNone(report['reference_width_mm']); self.assertIn('未知',report['reference_issue'])
        self.assertFalse(any('similarity' in c or 'original_font' in c for c in report['candidates']))

    def test_reference_width_is_measured_and_missing_reference_stays_unknown(self):
        report=find_candidates({'status':'COMPLETE','rows':[self.host,self.row]},'Alex',reference=self.row)
        self.assertAlmostEqual(report['reference_width_mm'],analyze_font(self.row,'Alex')['width_mm'])
        self.assertTrue(all(abs(c['width_delta_ratio'])<1e-12 for c in report['candidates']))
        Path(self.asset['path']).unlink()
        report=find_candidates({'status':'COMPLETE','rows':[self.host,self.row]},'Alex',reference=self.row)
        self.assertIsNone(report['reference_width_mm']); self.assertIn('未知',report['reference_issue'])
        self.assertEqual(len(report['candidates']),1); self.assertIsNone(report['candidates'][0]['width_delta_ratio'])

    def test_reference_delta_orders_actual_different_widths(self):
        other=Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
        if not other.is_file(): self.fail('驗收需要另一款環境字型，未測試不能PASS')
        asset=self.manager.import_font(other,approved=True)
        inventory=build_inventory([self.asset,asset],[],[])
        row=next(r for r in inventory['rows'] if r['asset']['hash']==asset['hash'])
        report=find_candidates(inventory,'AV Wi Example',reference=row)
        self.assertEqual(report['candidates'][0]['row']['asset']['hash'],asset['hash'])
        self.assertAlmostEqual(report['candidates'][0]['width_delta_ratio'],0)
        self.assertGreater(abs(report['candidates'][1]['width_delta_ratio']),.001)

    def test_permutation_and_duplicate_identity_do_not_change_rank_or_measure_twice(self):
        rows=[self.host,self.row,self.host,copy.deepcopy(self.row)]
        a=find_candidates({'status':'COMPLETE','rows':rows},'Alex')
        b=find_candidates({'status':'COMPLETE','rows':list(reversed(rows))},'Alex')
        keys=lambda r:[(c['id'],c['requested_style'],c['rank_key']) for c in r['candidates']]
        self.assertEqual(keys(a),keys(b)); self.assertEqual(a['checked_faces'],2)
        json.dumps(a)  # worker result 沒有Qt物件

    def test_face_bytes_and_inventory_limits_are_explicit_partial(self):
        inventory={'status':'COMPLETE','rows':[self.host,self.row]}
        report=find_candidates(inventory,'Alex',max_faces=1)
        self.assertEqual(report['status'],'PARTIAL'); self.assertEqual(report['checked_faces'],1)
        self.assertEqual(report['omitted_faces'],1)
        report=find_candidates(self.inventory,'Alex',max_bytes=1)
        self.assertEqual(report['status'],'PARTIAL'); self.assertEqual(report['omitted_faces'],1)
        self.assertEqual(report['checked_faces'],0)
        self.assertEqual(find_candidates({**self.inventory,'status':'PARTIAL'},'Alex')['status'],'PARTIAL')
        report=find_candidates(inventory,'Alex',max_results=1)
        self.assertEqual(report['hidden_eligible'],1)
        self.assertEqual(len(report['candidates']),1)

    def test_empty_invalid_and_over_budget_requests_do_not_claim_success(self):
        report=find_candidates(self.inventory,'   ')
        self.assertEqual(report['status'],'NO_TEXT'); self.assertEqual(report['checked_faces'],0)
        for text in ('A\nB','A\x00','a'*4097):
            with self.assertRaises(ValueError): find_candidates(self.inventory,text)
        for kwargs in ({'size_pt':float('nan')},{'width_mm':0},{'min_scale':1.1},{'max_faces':65},{'max_results':11},{'max_bytes':-1}):
            with self.assertRaises(ValueError): find_candidates(self.inventory,'Alex',**kwargs)

    def test_preview_real_png_fixed_point_size_and_bounded_frame(self):
        report=find_candidates(self.inventory,'AV Example',12,40)
        result=render_candidate(report['candidates'][0],report['input'])
        image=QImage.fromData(result['png'],'PNG')
        self.assertFalse(image.isNull()); self.assertEqual(result['analysis']['size_pt'],12)
        self.assertLessEqual(image.width(),1724); self.assertLessEqual(image.height(),424)
        # 真正字形像素（框線顏色不是黑色），不能只建立空白PNG。
        dark=sum(image.pixelColor(x,y).red()<40 and image.pixelColor(x,y).green()<40
                 for x in range(image.width()) for y in range(image.height()))
        self.assertGreater(dark,30)
        large=find_candidates(self.inventory,'Alex',12,2000)
        self.assertLessEqual(render_candidate(large['candidates'][0],large['input'])['pixel_width'],1724)

    def test_preview_rejects_modified_file_and_same_width_changed_text(self):
        report=find_candidates(self.inventory,'AB',12,40)
        with self.assertRaisesRegex(ValueError,'過期'):
            render_candidate(report['candidates'][0],{**report['input'],'text':'BA'})
        Path(self.asset['path']).write_bytes(b'changed after search')
        with self.assertRaisesRegex(ValueError,'變更|不可用'):
            render_candidate(report['candidates'][0],report['input'])

    def test_changed_shaping_identity_blocks_candidate_and_preview(self):
        with patch('template_ai.font_catalog.face_fingerprint',side_effect=['one','other']):
            report=find_candidates(self.inventory,'Alex')
        self.assertEqual(report['candidates'],[])
        report=find_candidates(self.inventory,'Alex')
        with patch('template_ai.font_candidates.face_fingerprint',return_value='changed'):
            with self.assertRaisesRegex(ValueError,'字面'):
                render_candidate(report['candidates'][0],report['input'])

    def test_search_preview_leave_published_pin_registry_and_source_bytes_unchanged(self):
        template=demo_template()
        for slot in template.slots: slot.font=self.asset['families'][0]; slot.font_asset=copy.deepcopy(self.asset)
        self.library.save_template(template); self.library.publish(template)
        before=([t.to_dict() for t in self.library.templates()],self.library.fonts(),Path(self.asset['path']).read_bytes(),FONT.read_bytes())
        report=find_candidates(build_inventory(self.library.fonts(),self.library.templates(),[]),'Alex')
        render_candidate(report['candidates'][0],report['input'])
        after=([t.to_dict() for t in self.library.templates()],self.library.fonts(),Path(self.asset['path']).read_bytes(),FONT.read_bytes())
        self.assertEqual(before,after)


@unittest.skipUnless(FONT, "缺少實際環境字型，GUI候選驗收未執行")
class FontCandidateGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.window=MainWindow(Path(self.temp.name)/'gui'); self.addCleanup(self.window.close)
        self.errors=[]; self.window.error=lambda text:self.errors.append(text)
        self.asset=self.window.font_manager.import_font(FONT,approved=True)
        template=demo_template()
        for slot in template.slots: slot.font=self.asset['families'][0]; slot.font_asset=copy.deepcopy(self.asset)
        self.window.library.save_template(template); self.window.library.publish(template)
        self.center=FontCenterDialog(self.window); self.addCleanup(self.center.close)
        self.center.show_inventory(build_inventory([self.asset],self.window.library.templates(),[]))
        self.center.table.selectRow(0)
        self.dialog=FontCandidateDialog(self.center); self.addCleanup(self.dialog.close)
        self.hosts=patch('template_ai.font_candidate_dialog.host_candidates',return_value=([],False))
        self.hosts.start(); self.addCleanup(self.hosts.stop)

    def wait_for_work(self):
        deadline=time.monotonic()+10
        while (self.dialog.busy or self.window.busy) and time.monotonic()<deadline:
            APP.processEvents(); time.sleep(.005)
        self.assertFalse(self.dialog.busy,'候選worker未交接'); self.assertFalse(self.window.busy)
        self.assertEqual(self.errors,[])

    def search_sync(self):
        with patch.object(self.window,'run_job',side_effect=lambda msg,fn,callback:callback(fn())): self.dialog.search()

    def test_shared_center_entry_has_explicit_unchecked_reference_and_no_auto_selection(self):
        self.assertFalse(self.dialog.compare.isChecked())
        with patch('template_ai.font_candidate_dialog.FontCandidateDialog.exec',return_value=0) as execute:
            self.center.candidates_button.click(); execute.assert_called_once()
        self.search_sync(); self.assertIsNone(self.dialog.selected()); self.assertFalse(self.dialog.preview_button.isEnabled())
        self.assertIn('未知',self.dialog.table.item(0,5).text())
        self.dialog.compare.setChecked(True); self.search_sync(); self.assertIn('+0.000',self.dialog.table.item(0,5).text())

    def test_real_worker_search_selection_preview_and_readonly_state(self):
        before=([t.to_dict() for t in self.window.library.templates()],self.window.library.fonts())
        self.dialog.search_button.click(); self.wait_for_work()
        self.assertEqual(self.dialog.table.rowCount(),1); self.dialog.table.selectRow(0)
        self.dialog.preview_button.click(); self.wait_for_work()
        self.assertIsNotNone(self.dialog.preview_data); self.assertIn('固定',self.dialog.details.text())
        self.assertFalse(self.dialog.preview_label.pixmap().isNull())
        self.assertEqual(before,([t.to_dict() for t in self.window.library.templates()],self.window.library.fonts()))
        self.assertTrue(self.dialog.search_button.isEnabled())

    def test_input_changes_reject_late_search_and_preview_results(self):
        for action in ('search','preview'):
            self.search_sync(); self.dialog.table.selectRow(0); jobs=[]
            with patch.object(self.window,'run_job',side_effect=lambda msg,fn,callback:jobs.append((fn,callback))):
                getattr(self.dialog,action)()
            self.dialog.text.setText('different text '+action)
            jobs[0][1](jobs[0][0]())
            self.assertIn('過期',self.dialog.status.text()); self.assertIsNone(self.dialog.report)
            self.assertIsNone(self.dialog.preview_data); self.assertFalse(self.dialog.busy)

    def test_real_worker_failure_restores_controls_and_retry_succeeds(self):
        with patch('template_ai.font_candidate_dialog.find_candidates',side_effect=OSError('candidate failure')):
            self.dialog.search(); self.wait_for_work()
        self.assertIn('candidate failure',self.dialog.status.text())
        self.assertTrue(self.dialog.search_button.isEnabled()); self.assertTrue(self.dialog.table.isEnabled())
        self.dialog.search(); self.wait_for_work(); self.assertEqual(self.dialog.table.rowCount(),1)

    def test_modified_preview_clears_old_image_and_can_requery(self):
        self.search_sync(); self.dialog.table.selectRow(0)
        with patch.object(self.window,'run_job',side_effect=lambda msg,fn,callback:callback(fn())): self.dialog.preview()
        self.assertIsNotNone(self.dialog.preview_data)
        Path(self.asset['path']).write_bytes(b'changed between previews')
        with patch.object(self.window,'run_job',side_effect=lambda msg,fn,callback:callback(fn())): self.dialog.preview()
        self.assertIsNone(self.dialog.preview_data); self.assertTrue(self.dialog.preview_label.pixmap().isNull())
        self.assertIn('未完成',self.dialog.status.text()); self.search_sync()
        self.assertEqual(self.dialog.table.rowCount(),0); self.assertEqual(self.dialog.exclusions.rowCount(),1)

    def test_empty_missing_glyph_and_no_candidate_are_visible_not_success(self):
        self.dialog.text.setText(' '); self.search_sync()
        self.assertIn('無實際文字',self.dialog.status.text()); self.assertEqual(self.dialog.table.rowCount(),0)
        self.dialog.text.setText('Alex'+chr(0x10ffff)); self.search_sync()
        self.assertEqual(self.dialog.table.rowCount(),0); self.assertEqual(self.dialog.exclusions.rowCount(),1)
        self.assertIn('U+10FFFF',self.dialog.exclusions.item(0,1).text())

    def test_callback_error_still_restores_dialog_controls(self):
        with patch.object(self.dialog,'show_report',side_effect=ValueError('callback error')), \
             patch.object(self.window,'run_job',side_effect=lambda msg,fn,callback:callback(fn())):
            with self.assertRaisesRegex(ValueError,'callback error'): self.dialog.search()
        self.assertFalse(self.dialog.busy); self.assertTrue(self.dialog.search_button.isEnabled())
        self.assertTrue(self.dialog.table.isEnabled())
