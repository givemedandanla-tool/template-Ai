"""環境字型／匿名模板：資產身份、實際 shaping、Unicode 與 GUI 不改模板。"""
import copy
import os
from pathlib import Path
import tempfile
import time
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtGui import QFont,QFontMetricsF,QRawFont
from PySide6.QtWidgets import QApplication
from template_ai.demo import demo_template
from template_ai.fonts import FontManager
from template_ai.font_catalog import asset_health,build_inventory,filter_inventory,host_candidates,raw_asset,analyze_font
from template_ai.font_dialog import FontCenterDialog
from template_ai.gui import MainWindow
from template_ai.storage import Library

APP=QApplication.instance() or QApplication([])
FONT=next((p for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),Path(r'C:\Windows\Fonts\arial.ttf')) if p.is_file()),None)


@unittest.skipUnless(FONT,"沒有環境可用字型，真實資產／shaping驗收未執行")
class FontCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.library=Library(self.root/'data'); self.addCleanup(self.library.close)
        self.manager=FontManager(self.library); self.addCleanup(self.manager.close)
        self.asset=self.manager.import_font(FONT,approved=True)
        self.row=build_inventory([self.asset],[],[])["rows"][0]

    def test_asset_identity_and_draft_published_template_impacts_preserved(self):
        template=demo_template()
        for slot in template.slots: slot.font=self.asset['families'][0]; slot.font_asset=copy.deepcopy(self.asset)
        self.library.save_template(template); self.library.publish(template)
        before=[t.to_dict() for t in self.library.templates()]
        row=build_inventory(self.library.fonts(),self.library.templates(),[])["rows"][0]
        self.assertEqual(row['status'],'HEALTHY'); self.assertEqual(row['asset'],self.asset)
        self.assertEqual(len(row['references']),len(template.slots)); self.assertTrue(all(r['state']=='published' for r in row['references']))
        self.assertTrue(row['styles']); self.assertEqual(self.library.templates()[0].to_dict(),before[0])
        self.assertEqual(self.library.fonts(),[self.asset])

    def test_missing_modified_unapproved_invalid_and_unparseable_are_distinct(self):
        target=Path(self.asset['path']); target.unlink()
        self.assertEqual(asset_health(self.asset)[0],'MISSING')
        target.write_bytes(b'changed'); self.assertEqual(asset_health(self.asset)[0],'MODIFIED')
        self.assertEqual(asset_health({**self.asset,'approved':False})[0],'UNAPPROVED')
        self.assertEqual(asset_health({})[0],'INVALID')
        from template_ai.background import file_digest
        broken={**self.asset,'hash':file_digest(target)}
        self.assertEqual(build_inventory([broken],[],[])['rows'][0]['status'],'UNREADABLE')

    def test_unregistered_template_path_never_borrows_same_family_catalog_asset(self):
        template=demo_template(); template.slots[0].font=self.asset['families'][0]
        template.slots[0].font_asset={**self.asset,'path':str(self.root/'missing.ttf')}
        report=build_inventory([self.asset],[template],[])
        unknown=next(r for r in report['rows'] if r['status']=='REFERENCE_UNKNOWN')
        self.assertEqual(len(unknown['references']),1); self.assertEqual(analyze_font(unknown,'Alex')['status'],'BLOCKED')
        healthy=next(r for r in report['rows'] if r['kind']=='ASSET')
        self.assertEqual(healthy['references'],[])

    def test_qt_candidates_not_claimed_as_verified_original_or_installed_file(self):
        family=self.asset['families'][0]
        report=build_inventory([],[],[{'family':family,'styles':['Book']}])
        row=report['rows'][0]
        self.assertEqual(row['status'],'QT_AVAILABLE'); self.assertNotIn('asset',row)
        self.assertIn('未取得',row['identity'])
        missing=demo_template(); missing.slots[0].font='Unknown Family That Does Not Exist'
        report=build_inventory([],[missing],[])
        self.assertTrue(any(r['status']=='REFERENCE_MISSING' for r in report['rows']))

    def test_filters_and_limits_do_not_hide_unverified_assets_as_healthy(self):
        report=build_inventory([self.asset],[],[],max_bytes=1)
        self.assertEqual(report['status'],'PARTIAL'); self.assertEqual(report['rows'][0]['status'],'NOT_CHECKED')
        report=build_inventory([self.asset,self.asset],[],[],max_assets=1)
        self.assertEqual(report['omitted_assets'],1)
        self.assertEqual(filter_inventory([self.row],self.asset['families'][0].upper(),'ASSET','HEALTHY'),[self.row])
        self.assertEqual(filter_inventory([self.row],status='MISSING'),[])
        _,partial=host_candidates(limit=1); self.assertTrue(partial)

    def test_coverage_counts_unique_codepoints_and_missing_nonbmp_without_fallback(self):
        result=analyze_font(self.row,'AAA'+chr(0x10ffff))
        self.assertEqual(result['coverage'],.5); self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(len(result['missing']),1); self.assertIsNone(result['width_mm'])
        raw=raw_asset(self.asset); glyphs=raw.glyphIndexesForString(chr(0x1f600))
        result=analyze_font(self.row,'A'+chr(0x1f600))
        self.assertEqual(result['coverage'],1.0 if glyphs and all(glyphs) else .5)
        self.assertEqual(result['status'],'FEASIBLE_WIDTH' if glyphs and all(glyphs) else 'BLOCKED')

    def test_real_shaping_mm_scales_linearly_and_matches_independent_font_metrics(self):
        small=analyze_font(self.row,'AV Example',10,80)
        large=analyze_font(self.row,'AV Example',20,80)
        self.assertEqual(small['status'],'FEASIBLE_WIDTH'); self.assertEqual(large['status'],'FEASIBLE_WIDTH')
        self.assertAlmostEqual(large['width_mm'],2*small['width_mm'],places=8)
        self.assertEqual(small['size_pt'],10)
        raw=raw_asset(self.asset); font=QFont(raw.familyName()); font.setStyleName(raw.styleName()); font.setPixelSize(1000)
        font.setHintingPreference(QFont.PreferNoHinting); font.setStyleStrategy(QFont.NoFontMerging)
        expected=QFontMetricsF(font).horizontalAdvance('AV Example')*10*25.4/72/1000
        self.assertAlmostEqual(small['width_mm'],expected,places=6)
        self.assertLess(analyze_font(self.row,'AV')['width_mm'],analyze_font(self.row,'A')['width_mm']+analyze_font(self.row,'V')['width_mm'])

    def test_horizontal_fit_boundary_does_not_change_size_or_drop_text(self):
        measure=analyze_font(self.row,'Alex Example',12,80)['width_mm']
        exact=analyze_font(self.row,'Alex Example',12,measure*.85,.85)
        below=analyze_font(self.row,'Alex Example',12,measure*.84,.85)
        self.assertEqual(exact['status'],'FEASIBLE_WIDTH'); self.assertEqual(below['status'],'BLOCKED')
        self.assertAlmostEqual(exact['scale'],.85); self.assertEqual(exact['size_pt'],12); self.assertEqual(below['size_pt'],12)

    def test_changed_asset_and_different_shaping_face_block_even_if_system_family_exists(self):
        with patch('template_ai.font_catalog.face_fingerprint',side_effect=['expected','wrong']):
            result=analyze_font(self.row,'Alex Example')
        self.assertEqual(result['status'],'BLOCKED'); self.assertIsNone(result['width_mm'])
        Path(self.asset['path']).write_bytes(b'changed after inventory')
        self.assertEqual(analyze_font(self.row,'Alex')['status'],'BLOCKED')
        self.assertIn(self.asset['families'][0],__import__('PySide6.QtGui',fromlist=['QFontDatabase']).QFontDatabase.families())

    def test_empty_invalid_controls_multiline_and_out_of_range_inputs_rejected(self):
        empty=analyze_font(self.row,'   '); self.assertEqual(empty['status'],'NO_TEXT'); self.assertIsNone(empty['coverage'])
        for text in ('a\nb','a\tb','a\u2028b','a\u0085b','\ud800','x'*4097):
            with self.assertRaises(ValueError): analyze_font(self.row,text)
        for args in ((0,80,.85),(float('nan'),80,.85),(10,0,.85),(10,80,1.1),(True,80,.85)):
            with self.assertRaises(ValueError): analyze_font(self.row,'A',*args)
        with_style=analyze_font(self.row,'A',style='invented wrong face')
        self.assertEqual(with_style['status'],'BLOCKED')


@unittest.skipUnless(FONT,"環境沒有字型，GUI實際核對未執行")
class FontCenterGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.window=MainWindow(Path(self.temp.name)/'gui'); self.addCleanup(self.window.close)
        self.asset=self.window.font_manager.import_font(FONT,approved=True)
        self.window.add_demo()
        for slot in self.window.template.slots: slot.font=self.asset['families'][0]; slot.font_asset=copy.deepcopy(self.asset)
        self.window.library.save_template(self.window.template); self.window.library.publish(self.window.template)
        self.dialog=FontCenterDialog(self.window); self.addCleanup(self.dialog.close)

    def prepare_selection(self):
        with patch.object(self.window,'run_job',side_effect=lambda message,fn,callback:callback(fn())): self.dialog.refresh()
        self.dialog.kind.setCurrentIndex(self.dialog.kind.findData('ASSET')); self.dialog.table.selectRow(0)

    def test_background_snapshot_and_selection_show_references_without_mutating_templates(self):
        before=[t.to_dict() for t in self.window.library.templates()]; jobs=[]
        with patch.object(self.window,'run_job',side_effect=lambda message,fn,callback:jobs.append((fn,callback))): self.dialog.refresh()
        self.assertTrue(self.dialog.busy); jobs[0][1](jobs[0][0]()); self.assertFalse(self.dialog.busy)
        self.assertIsNone(self.dialog.selected()); self.assertFalse(self.dialog.analyze_button.isEnabled())
        self.dialog.kind.setCurrentIndex(self.dialog.kind.findData('ASSET')); self.dialog.table.selectRow(0)
        self.assertIn('published',self.dialog.details.text())
        self.assertEqual([t.to_dict() for t in self.window.library.templates()],before)

    def test_diagnosis_stale_input_does_not_publish_old_feasibility(self):
        self.prepare_selection(); jobs=[]
        with patch.object(self.window,'run_job',side_effect=lambda message,fn,callback:jobs.append((fn,callback))): self.dialog.analyze()
        self.dialog.text.setText('new text entered while analysis running')
        jobs[0][1](jobs[0][0]())
        self.assertIn('過期',self.dialog.result.text()); self.assertFalse(self.dialog.busy)

    def test_gui_measures_selected_asset_without_modifying_published_pin(self):
        self.prepare_selection(); before=[t.to_dict() for t in self.window.library.templates()]
        with patch.object(self.window,'run_job',side_effect=lambda message,fn,callback:callback(fn())): self.dialog.analyze()
        self.assertIn('單行',self.dialog.result.text()); self.assertIn('mm',self.dialog.result.text()); self.assertIn('100.00%',self.dialog.result.text())
        self.assertEqual([t.to_dict() for t in self.window.library.templates()],before)

    def test_failed_worker_releases_ui_and_repair_refreshes_health(self):
        with patch('template_ai.font_dialog.build_inventory',side_effect=OSError('inspection failed')), \
             patch.object(self.window,'run_job',side_effect=lambda message,fn,callback:callback(fn())): self.dialog.refresh()
        self.assertFalse(self.dialog.busy); self.assertIn('inspection failed',self.dialog.status.text())
        Path(self.asset['path']).unlink()
        with patch.object(self.window,'run_job',side_effect=lambda message,fn,callback:callback(fn())): self.dialog.refresh()
        self.assertEqual(next(r for r in self.dialog.inventory['rows'] if r['kind']=='ASSET')['status'],'MISSING')
        with patch.object(self.window,'repair_font',side_effect=lambda:self.window.font_manager.repair_font(self.asset['hash'],FONT,approved=True)), \
             patch.object(self.window,'run_job',side_effect=lambda message,fn,callback:callback(fn())): self.dialog.repair_font()
        self.assertEqual(next(r for r in self.dialog.inventory['rows'] if r['kind']=='ASSET')['status'],'HEALTHY')

    def test_real_background_inventory_and_diagnosis_return_plain_data(self):
        def wait_for_work():
            deadline=time.monotonic()+10
            while self.dialog.busy and time.monotonic()<deadline:
                APP.processEvents(); time.sleep(.005)
            self.assertFalse(self.dialog.busy,'背景字型核對未在預算內完成')
        self.dialog.refresh(); wait_for_work()
        self.assertIsNotNone(self.dialog.inventory)
        self.dialog.kind.setCurrentIndex(self.dialog.kind.findData('ASSET')); self.dialog.table.selectRow(0)
        self.dialog.analyze(); wait_for_work()
        self.assertIn('100.00%',self.dialog.result.text())
        self.assertIn('mm',self.dialog.result.text())


class BackgroundJobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.window=MainWindow(Path(self.temp.name)/'gui'); self.addCleanup(self.window.close)
        self.errors=[]
        self.window.error=lambda text:self.errors.append((text,threading.get_ident()))
        self.owner=threading.get_ident()

    def wait_for_work(self):
        deadline=time.monotonic()+10
        while self.window.busy and time.monotonic()<deadline:
            APP.processEvents(); time.sleep(.005)
        # 失敗亦避免測試清理走modal而隱藏真正assertion；故障狀態先明列。
        busy=self.window.busy
        if busy: self.window.busy=False
        self.assertFalse(busy,'worker完成通知未回GUI')

    def test_real_success_holds_job_until_gui_callback_then_releases(self):
        received=[]
        self.window.run_job('anonymous job',lambda:threading.get_ident(),lambda worker:received.append((worker,threading.get_ident())))
        self.assertEqual(len(self.window._background_jobs),1)
        self.wait_for_work()
        self.assertEqual(len(received),1); self.assertNotEqual(received[0][0],self.owner); self.assertEqual(received[0][1],self.owner)
        self.assertEqual(self.window._background_jobs,{}); self.assertTrue(self.window.import_button.isEnabled())

    def test_real_worker_failure_returns_to_gui_and_can_run_next_job(self):
        def failing(): raise ValueError('synthetic worker failed')
        self.window.run_job('failed job',failing,lambda value:self.fail('失敗工作不得當成功'))
        self.wait_for_work()
        self.assertEqual(self.errors,[('synthetic worker failed',self.owner)]); self.assertEqual(self.window._background_jobs,{})
        done=[]; self.window.run_job('retry',lambda:'ok',done.append); self.wait_for_work(); self.assertEqual(done,['ok'])

    def test_gui_callback_failure_still_releases_job_and_busy_state(self):
        def callback(value): raise ValueError('synthetic callback failed')
        self.window.run_job('callback fault',lambda:'ok',callback); self.wait_for_work()
        self.assertEqual(self.errors,[('synthetic callback failed',self.owner)])
        self.assertEqual(self.window._background_jobs,{})
