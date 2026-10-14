"""受控替代大功能：真實量測／多模板交易／ABA／重開UndoRedo／GUI。"""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QFont,QFontMetricsF
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.demo import demo_template
from template_ai.font_catalog import analyze_font,build_inventory
from template_ai.font_review import FontReviewEngine,evaluate_review,field_key
from template_ai.font_review_dialog import FontReviewDialog
from template_ai.fonts import FontManager
from template_ai.gui import MainWindow
from template_ai.layout import generate,text_geometry
from template_ai.model import Template,Slot,Rect,template_errors
from template_ai.render import render_image,export
from template_ai.storage import Library

APP=QApplication.instance() or QApplication([])
FONT=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
MONO=Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
ITALIC=next((p for p in (Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf'),Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Italic.otf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf')) if p.is_file()),None)


@unittest.skipUnless(FONT.is_file() and MONO.is_file(),'缺少本包Linux真實字型樣本，未驗收不可當PASS')
class FontReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        self.manager=FontManager(self.library);self.addCleanup(self.manager.close)
        self.old=self.manager.import_font(FONT,approved=True);self.asset=self.manager.import_font(MONO,approved=True)
        self.target=build_inventory([self.asset],[],[])['rows'][0]
        self.template=demo_template()
        for slot in self.template.slots:slot.font=self.old['families'][0];slot.font_asset=copy.deepcopy(self.old)
        self.library.save_template(self.template);self.library.publish(self.template)
        self.engine=FontReviewEngine();self.texts={field_key(self.template.id,self.template.slots[0].id):'Alex Example'}

    def report(self,**kwargs):return self.engine.analyze(self.library.template_snapshots(),self.target,kwargs.get('texts',self.texts))

    def apply(self,report=None,selections=None):
        report=report or self.report()
        selections=selections or [{'key':k,'reviewed':True} for k in self.texts]
        return self.engine.commit(self.library,self.engine.prepare_apply(report['review_id'],selections),confirmed=True)

    def test_actual_impact_dimensions_owner_source_and_unknown_reference(self):
        report=self.report();row=report['rows'][0]
        self.assertEqual(len(report['rows']),4);self.assertEqual(row['dimensions'],[90,54])
        self.assertEqual(row['slot']['owner'],'p1');self.assertEqual(row['risk'],'HIGH');self.assertTrue(row['eligible'])
        self.assertIsNotNone(row['width_delta_ratio']);self.assertEqual(row['proposed']['coverage'],1)
        Path(self.old['path']).unlink();report=self.report()
        self.assertTrue(report['rows'][0]['eligible']);self.assertIsNone(report['rows'][0]['width_delta_ratio'])
        self.assertIn('未知',' '.join(report['rows'][0]['reasons']))

    def test_empty_missing_glyph_height_and_geometry_block_individual_field(self):
        report=self.report(texts={});self.assertTrue(all(not r['eligible'] for r in report['rows']))
        report=self.report(texts={next(iter(self.texts)):'Alex'+chr(0x10ffff)})
        self.assertFalse(report['rows'][0]['eligible']);self.assertIsNone(report['rows'][0]['proposed']['width_mm'])
        snapshots=self.library.template_snapshots();snapshots[0]['template']['slots'][0]['rect']['h']=.1
        report=evaluate_review(snapshots,self.target,self.texts)
        self.assertIn('高度',' '.join(report['rows'][0]['reasons']))
        snapshots[0]['template']['slots'][0]['rect']['x']=-2
        self.assertFalse(evaluate_review(snapshots,self.target,self.texts)['rows'][0]['eligible'])

    def test_unverified_qt_modified_target_and_logo_never_eligible(self):
        qt={'kind':'QT','families':self.asset['families'],'styles':['Book']}
        self.assertFalse(evaluate_review(self.library.template_snapshots(),qt,self.texts)['rows'][0]['eligible'])
        snapshots=self.library.template_snapshots();snapshots[0]['template']['slots'][1]['kind']='logo'
        self.assertEqual(len(evaluate_review(snapshots,self.target,{})['rows']),3)
        Path(self.asset['path']).write_bytes(b'changed')
        self.assertFalse(self.report()['rows'][0]['eligible'])

    def test_limits_and_same_binding_low_noop_are_visible(self):
        snapshots=self.library.template_snapshots()
        self.assertEqual(evaluate_review(snapshots,self.target,self.texts,max_rows=1)['omitted_rows'],3)
        report=evaluate_review(snapshots,self.target,{field_key(self.template.id,s.id):'Alex' for s in self.template.slots},max_fields=1)
        self.assertEqual(report['status'],'PARTIAL');self.assertEqual(report['checked_fields'],1)
        report=evaluate_review(snapshots,self.target,self.texts,max_bytes=1)
        self.assertEqual(report['status'],'PARTIAL');self.assertFalse(report['rows'][0]['eligible'])
        self.template.state='draft';self.template.id='new';self.template.family_id='new'
        for s in self.template.slots:s.font=self.asset['families'][0];s.font_asset=copy.deepcopy(self.asset);s.font_style=self.target['styles'][0]
        self.library.save_template(self.template)
        report=evaluate_review(self.library.template_snapshots(),self.target,{field_key(self.template.id,self.template.slots[0].id):'Alex'})
        row=next(r for r in report['rows'] if r['template_id']=='new' and r['slot']['kind']=='name')
        self.assertEqual(row['risk'],'LOW');self.assertFalse(row['eligible'])

    def test_high_risk_unreviewed_unselected_duplicate_and_forged_ticket_rejected(self):
        report=self.report();key=next(iter(self.texts))
        for selections in ([],[{'key':key,'reviewed':False}],[{'key':key,'reviewed':True}]*2,[{'key':'unknown','reviewed':True}]):
            with self.assertRaises(ValueError):self.engine.prepare_apply(report['review_id'],selections)
        report['rows'][0]['eligible']=False;report['rows'][0]['after']['font']='forged'
        record=self.apply(report)
        self.assertEqual(record['drafts'][0]['after']['slots'][0]['font'],self.asset['families'][0])
        with self.assertRaises(ValueError):self.engine.commit(self.library,'forged',confirmed=True)

    def test_selected_only_new_draft_preserves_publication_geometry_and_no_raw_text(self):
        original=self.template.to_dict();fonts=self.library.fonts();raw=FONT.read_bytes()
        record=self.apply();draft=record['drafts'][0]
        self.assertEqual(draft['version'],2);self.assertEqual(draft['after']['state'],'draft')
        self.assertEqual(draft['after']['slots'][1:],original['slots'][1:])
        before=original['slots'][0];after=draft['after']['slots'][0]
        for k in before:
            if k not in ('font','font_asset','font_style'):self.assertEqual(before[k],after[k])
        published=next(t for t in self.library.templates() if t.id==self.template.id)
        self.assertEqual(published.to_dict(),original);self.assertEqual(self.library.fonts(),fonts);self.assertEqual(FONT.read_bytes(),raw)
        self.assertNotIn('Alex Example',json.dumps(self.library.font_change_history(),ensure_ascii=False))

    def test_base_change_aba_and_target_registration_race_block_commit(self):
        # 用草稿基底，任意變更後恢復原bytes仍需clock擋下。
        self.template=Template.from_dict(self.template.to_dict());self.template.id='draft';self.template.family_id='draft';self.template.state='draft'
        self.library.save_template(self.template);self.texts={field_key(self.template.id,self.template.slots[0].id):'Alex'}
        report=self.report();ticket=self.engine.prepare_apply(report['review_id'],[{'key':k,'reviewed':True} for k in self.texts])
        self.template.name='intermediate';self.library.save_template(self.template)
        self.template.name='匿名示範 · 單人矩形';self.library.save_template(self.template)
        with self.assertRaisesRegex(ValueError,'變更'):self.engine.commit(self.library,ticket,confirmed=True)
        report=self.report();ticket=self.engine.prepare_apply(report['review_id'],[{'key':k,'reviewed':True} for k in self.texts])
        self.library.db.execute('UPDATE font_assets SET payload=? WHERE hash=?',(json.dumps({**self.asset,'approved':False}),self.asset['hash']));self.library.db.commit()
        with self.assertRaisesRegex(ValueError,'登錄'):self.engine.commit(self.library,ticket,confirmed=True)
        self.assertEqual(self.library.font_change_history(),[])

    def test_multi_template_late_audit_failure_rolls_back_every_draft_and_clock(self):
        other=copy.deepcopy(self.template);other.id='other';other.family_id='other';other.state='draft';self.library.save_template(other)
        self.texts[field_key(other.id,other.slots[0].id)]='Jordan'
        report=self.report();before=self.library.template_snapshots();events=self.library.db.execute('SELECT count(*) FROM reviews').fetchone()[0]
        original_event=self.library.event
        def late_failure(entity,action):
            if action=='font_replacement_batch_scope_confirmed':raise RuntimeError('late audit failed')
            original_event(entity,action)
        with patch.object(self.library,'event',side_effect=late_failure):
            with self.assertRaisesRegex(RuntimeError,'late audit'):self.apply(report)
        self.assertEqual(self.library.template_snapshots(),before);self.assertEqual(self.library.font_change_history(),[])
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM reviews').fetchone()[0],events);self.assertFalse(self.library.db.in_transaction)
        record=self.apply();self.assertEqual(len(record['drafts']),2)

    def test_undo_redo_persist_after_reopen_and_reject_later_editor_change(self):
        record=self.apply();self.library.close();self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        engine=FontReviewEngine();record=self.library.font_change_history()[0]
        undone=engine.commit(self.library,engine.prepare_history(record,'UNDO'),confirmed=True)
        t=next(t for t in self.library.templates() if t.id==record['drafts'][0]['template_id'])
        self.assertEqual(t.slots[0].font,self.old['families'][0]);self.assertEqual(undone['phase'],'UNDONE')
        redone=engine.commit(self.library,engine.prepare_history(undone,'REDO'),confirmed=True)
        t=next(t for t in self.library.templates() if t.id==record['drafts'][0]['template_id'])
        self.assertEqual(t.slots[0].font,self.asset['families'][0]);self.assertEqual(redone['phase'],'APPLIED')
        t.name+='edited';self.library.save_template(t)
        with self.assertRaisesRegex(ValueError,'變更'):engine.commit(self.library,engine.prepare_history(redone,'UNDO'),confirmed=True)

    def test_undo_publish_aba_and_late_failure_do_not_overwrite(self):
        record=self.apply();t=next(t for t in self.library.templates() if t.id==record['drafts'][0]['template_id'])
        original_name=t.name;t.name+='temp';self.library.save_template(t);t.name=original_name;self.library.save_template(t)
        with self.assertRaises(ValueError):self.engine.commit(self.library,self.engine.prepare_history(record,'UNDO'),confirmed=True)
        fresh=self.apply();before=self.library.template_snapshots()
        with patch.object(self.library,'event',side_effect=RuntimeError('undo audit failure')):
            with self.assertRaises(RuntimeError):self.engine.commit(self.library,self.engine.prepare_history(fresh,'UNDO'),confirmed=True)
        self.assertEqual(self.library.template_snapshots(),before);self.assertEqual(self.library.font_change_history()[0]['phase'],'APPLIED')
        t=next(t for t in self.library.templates() if t.id==fresh['drafts'][0]['template_id']);self.library.publish(t)
        with self.assertRaises(ValueError):self.engine.commit(self.library,self.engine.prepare_history(fresh,'UNDO'),confirmed=True)

    def test_modified_target_blocks_prepare_and_redo_while_undo_keeps_draft_gate(self):
        report=self.report();Path(self.asset['path']).write_bytes(b'changed after analysis')
        with self.assertRaises(ValueError):self.engine.prepare_apply(report['review_id'],[{'key':k,'reviewed':True} for k in self.texts])
        Path(self.asset['path']).write_bytes(MONO.read_bytes());record=self.apply()
        Path(self.old['path']).unlink()
        undone=self.engine.commit(self.library,self.engine.prepare_history(record,'UNDO'),confirmed=True)
        t=next(t for t in self.library.templates() if t.id==record['drafts'][0]['template_id'])
        self.assertTrue(template_errors(t));self.assertEqual(t.state,'draft')
        Path(self.asset['path']).write_bytes(b'changed before redo')
        with self.assertRaises(ValueError):self.engine.prepare_history(undone,'REDO')

    def test_legacy_schema_migration_clock_noop_and_binding_styles_compatible(self):
        t=demo_template();d=t.to_dict()
        for s in d['slots']:s.pop('font_style')
        restored=Template.from_dict(d);self.assertTrue(all(s.font_style=='' for s in restored.slots))
        self.library.save_template(restored);before=self.library.template_snapshots()
        self.library.save_template(restored);self.assertEqual(self.library.template_snapshots(),before)
        self.library.db.execute('DROP TABLE template_edit_clocks');self.library.db.commit();self.library.close()
        self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        self.assertEqual(len(self.library.template_snapshots()),len(before))

    def test_persistent_actual_style_matches_layout_and_real_export(self):
        if ITALIC is None:self.fail('缺少實際Italic字型，不得當款式已驗證')
        asset=self.manager.import_font(ITALIC,approved=True);target=build_inventory([asset],[],[])['rows'][0]
        t=Template('Style',90,54,[Slot('name','p1',Rect(8,6,70,11),font=asset['families'][0],font_asset=asset,font_style=target['styles'][0],size_pt=18)])
        self.library.save_template(t);self.library.publish(t)
        candidate=generate(t,[{'name':'AV Wi Example'}],[],{})
        self.assertTrue(candidate.valid,candidate.issues)
        measured=analyze_font(target,'AV Wi Example',18,70,.85,target['styles'][0])
        width,height,issues=text_geometry(t.slots[0].font,18,'AV Wi Example',t.slots[0].font_style,asset)
        self.assertEqual(issues,[]);self.assertAlmostEqual(width,measured['width_mm'],places=8)
        image=render_image(candidate,96);self.assertFalse(image.isNull())
        for ext in ('png','pdf'):self.assertGreater(export(candidate,self.root/('style.'+ext),96).stat().st_size,100)
        t.slots[0].font_style='Regular'
        self.assertTrue(template_errors(t));self.assertFalse(generate(t,[{'name':'AV Wi Example'}],[],{}).valid)


@unittest.skipUnless(FONT.is_file() and MONO.is_file(),'缺少實際環境字型，GUI驗收未執行')
class FontReviewGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.window=MainWindow(Path(self.temp.name)/'gui');self.addCleanup(self.window.close)
        self.errors=[];self.window.error=lambda msg:self.errors.append(msg)
        old=self.window.font_manager.import_font(FONT,approved=True)
        self.asset=self.window.font_manager.import_font(MONO,approved=True)
        self.target=build_inventory([self.asset],[],[])['rows'][0]
        self.template=demo_template()
        for s in self.template.slots:s.font=old['families'][0];s.font_asset=copy.deepcopy(old)
        self.window.library.save_template(self.template);self.window.library.publish(self.template)
        self.dialog=FontReviewDialog(self.window,self.target,'Alex');self.addCleanup(self.dialog.close)
        self.yes=patch.object(QMessageBox,'question',return_value=QMessageBox.Yes);self.yes.start();self.addCleanup(self.yes.stop)

    def wait(self):
        deadline=time.monotonic()+10
        while (self.dialog.busy or self.window.busy) and time.monotonic()<deadline:APP.processEvents();time.sleep(.005)
        self.assertFalse(self.dialog.busy);self.assertFalse(self.window.busy);self.assertEqual(self.errors,[])

    def verify(self):
        self.dialog.table.selectRow(0);self.dialog.fill_selected();self.dialog.validate();self.wait()

    def test_real_gui_review_apply_history_undo_redo_complete_workflow(self):
        self.assertTrue(all(not self.dialog.table.cellWidget(i,0).isChecked() for i in range(4)))
        self.verify();self.assertEqual(self.dialog.report['rows'][0]['risk'],'HIGH')
        self.assertFalse(self.dialog.table.cellWidget(0,0).isEnabled())
        self.dialog.table.selectRow(0);self.dialog.review_selected();self.wait()
        self.assertIsNotNone(self.dialog.preview_data);self.assertTrue(self.dialog.table.cellWidget(0,0).isEnabled())
        self.assertFalse(self.dialog.table.cellWidget(0,0).isChecked())
        self.dialog.table.cellWidget(0,0).setChecked(True);self.dialog.apply_selected();self.wait()
        self.assertEqual(len(self.window.library.templates()),2);self.assertEqual(self.dialog.history.rowCount(),1)
        self.assertIsNone(self.dialog.report);self.assertIn('建立',self.dialog.status.text())
        self.dialog.history.selectRow(0);self.dialog.history_action('UNDO');self.wait()
        self.assertEqual(self.dialog.records[0]['phase'],'UNDONE')
        self.dialog.history.selectRow(0);self.dialog.history_action('REDO');self.wait()
        self.assertEqual(self.dialog.records[0]['phase'],'APPLIED')
        self.assertEqual(next(t for t in self.window.library.templates() if t.id==self.template.id).to_dict(),self.template.to_dict())

    def test_changed_text_clears_approval_selection_and_late_result(self):
        self.verify();self.dialog.table.selectRow(0);self.dialog.review_selected();self.wait()
        self.dialog.table.cellWidget(0,0).setChecked(True);self.dialog.table.cellWidget(0,3).setText('Changed')
        self.assertFalse(self.dialog.approved);self.assertIsNone(self.dialog.report);self.assertFalse(self.dialog.table.cellWidget(0,0).isChecked())
        jobs=[]
        with patch.object(self.window,'run_job',side_effect=lambda msg,fn,callback:jobs.append((fn,callback))):self.dialog.validate()
        self.dialog.table.cellWidget(0,3).setText('Late');jobs[0][1](jobs[0][0]())
        self.assertIn('過期',self.dialog.status.text());self.assertIsNone(self.dialog.report)

    def test_real_worker_failure_controls_recover_and_retry(self):
        self.dialog.table.cellWidget(0,3).setText('Alex')
        with patch.object(self.dialog.engine,'analyze',side_effect=OSError('failed analysis')):self.dialog.validate();self.wait()
        self.assertIn('failed analysis',self.dialog.status.text());self.assertTrue(self.dialog.check_button.isEnabled())
        self.dialog.validate();self.wait();self.assertIsNotNone(self.dialog.report)

    def test_final_decline_no_selection_and_unsaved_editor_do_not_write(self):
        self.verify();before=self.window.library.template_snapshots();self.dialog.apply_selected()
        self.assertEqual(self.window.library.template_snapshots(),before)
        self.dialog.table.selectRow(0);self.dialog.review_selected();self.wait();self.dialog.table.cellWidget(0,0).setChecked(True)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):self.dialog.apply_selected()
        self.assertEqual(self.window.library.template_snapshots(),before)
        current=copy.deepcopy(self.template);current.id='unsaved';current.family_id='unsaved';current.state='draft'
        self.window.library.save_template(current);self.window.template=current;current.name='not saved'
        self.dialog.apply_selected();self.assertIn('未保存',self.dialog.status.text());self.assertEqual(self.window.library.font_change_history(),[])

    def test_history_menu_reopens_without_a_candidate(self):
        with patch.object(FontReviewDialog,'exec',return_value=0) as execute:self.window.font_review_history();execute.assert_called_once()
        history=FontReviewDialog(self.window);self.addCleanup(history.close)
        self.assertFalse(history.check_button.isEnabled());self.assertFalse(history.undo_button.isEnabled())
