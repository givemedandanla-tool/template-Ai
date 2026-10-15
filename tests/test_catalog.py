import copy
from dataclasses import asdict
from pathlib import Path
import tempfile,threading,time,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QItemSelectionModel,QTimer
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox,QPushButton
from template_ai.gui import MainWindow
from template_ai.model import Template,Slot,Rect,new_id
from template_ai.input_graph import InputGraph
from template_ai.customers import CustomerStore,digest
from template_ai.customer_catalog import CustomerStyleDialog
from template_ai.customer_dialog import CustomerDialog
from template_ai.catalog_widget import CatalogWidget
from template_ai.catalog import rows,filtered,hierarchy,preview_request,source_preview
from template_ai.importer import import_file
APP=QApplication.instance() or QApplication([])


def pump(predicate,seconds=6):
    end=time.monotonic()+seconds
    while not predicate() and time.monotonic()<end:APP.processEvents();QTest.qWait(10)
    if not predicate():raise AssertionError('bounded catalog wait exceeded')


def select(widget,ids):
    widget.selected_ids=set(ids);widget.primary_id=next(iter(ids),None);widget.rebuild();APP.processEvents()


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.w=MainWindow(self.root/'library');self.extra=[]
        self.t=Template('Example style one',90,54,[Slot('name','p1',Rect(4,4,42,9))]);self.w.library.publish(self.t)
        self.t2=Template('Example style two',100,60,[Slot('name','p1',Rect(4,4,42,9)),Slot('logo','c1',Rect(4,20,30,12))],version=2,company_bindings={'p1':['c1']});self.w.library.publish(self.t2)
        self.draft=Template('Rare one-name-box capacity two',90,54,[Slot('name','p1',Rect(4,4,42,9))],capacity=2);self.w.library.save_template(self.draft);self.w.refresh_templates();self.addCleanup(self.cleanup)
    def cleanup(self):
        for v in self.extra:
            if hasattr(v,'catalog'):v.catalog.close_previews()
            elif hasattr(v,'close_previews'):v.close_previews()
            v.hide()
        self.w.template_catalog.close_previews();self.w.pool.waitForDone(6000);APP.processEvents();self.w.input_timer.stop();self.w.library.db.close();self.w.hide();self.tmp.cleanup()
    def customer(self,code='00123'):
        store=CustomerStore(self.w.library);g=InputGraph.from_legacy([dict(name=['Alex Example'],phone=['020-000-0100','+1 (202) 555-0100'],line=['example_line'],ig=['example_ig'],company='c1')],[dict(name='Example Company')]);c=store.create_graph(code,'Example Client',g.data,self.t.id,True);return store,store.link_style(c,self.t2.id,True)
    def source_template(self,right=False):
        p=self.root/('right-reference.png' if right else 'left-reference.png');image=QImage(200,60,QImage.Format_RGB32);image.fill(QColor('red'));painter=QPainter(image);painter.fillRect(100,0,100,60,QColor('blue'));painter.end();image.save(str(p))
        source=self.w.library.add_source(p,import_file(p,self.w.library.assets));crop=Rect(50 if right else 0,0,50,30)
        t=Template('Anonymous verified source',90,54,[Slot('name','p1',Rect(4,4,42,9))],source_id=source['id'],artwork=crop)
        work=self.w.library.create_artwork(source['id'],'Anonymous Example Work',dict(crop=asdict(crop),work_width=90,work_height=54,slots=[asdict(s) for s in t.slots],visual_confirmed=True))
        t.source_work_id=work['id'];t.source_work_revision=work['revision'];self.w.library.publish(t);return t,source,work
    def test_index_uses_real_physical_size_and_capacity_not_name_box_count(self):
        entries=rows(self.w.library);tree=hierarchy(entries);self.assertEqual(tree[(90,54)][2],1);self.assertEqual(len(filtered(entries,size=(90,54),capacity=2)),1)
        self.assertEqual(filtered(entries,query='rare')[0]['template_id'],self.draft.id);self.assertEqual(len(filtered(entries,size=(54,90))),0);self.assertEqual(len(entries),3)
    def test_actual_two_views_filters_and_hidden_multiselection_survive_without_writes(self):
        c=self.w.template_catalog;before=self.w.library.db.total_changes;select(c,[self.t.id,self.draft.id]);c.query.setText('Rare');self.assertEqual(c.selected_ids,{self.t.id,self.draft.id});self.assertEqual(c.items.count(),1)
        c.mode.setCurrentIndex(1);self.assertEqual(c.query.text(),'Rare');self.assertEqual(c.selected_ids,{self.t.id,self.draft.id});self.assertIn('不在本頁',c.status.text());c.query.clear();self.assertEqual(len(c.items.selectedItems()),2)
        c.version.setCurrentIndex(c.version.findData(2));self.assertEqual(c.items.count(),1);c.mode.setCurrentIndex(0);self.assertEqual(c.version.currentData(),2);self.assertEqual(c.selected_ids,{self.t.id,self.draft.id});self.assertEqual(self.w.library.db.total_changes,before)
    def test_preview_then_explicit_edit_published_readonly_and_unsaved_guard(self):
        c=self.w.template_catalog;self.assertEqual(self.w.template_stack.currentIndex(),0);before=self.w.library.db.total_changes;select(c,[self.t.id]);self.assertEqual(self.w.template_stack.currentIndex(),0);self.assertEqual(self.w.library.db.total_changes,before)
        c.open_editor();self.assertEqual(self.w.template_stack.currentIndex(),1);self.assertEqual(self.w.template.id,self.t.id);self.assertTrue(self.w.edit_canvas.readonly)
        self.w.template.name='Unapplied local edit';self.w.template_stack.setCurrentIndex(0);select(c,[self.t2.id]);c.open_editor();self.assertIn('未保存',c.status.text());self.assertEqual(self.w.template.id,self.t.id)
    def test_customer_index_only_exact_own_links_and_stale_or_missing_versions_not_replaced(self):
        store,c=self.customer();other=store.create_graph('00999','Other Client',c['graph'],self.draft.id if self.draft.capacity==1 else self.t.id,True)
        entries=rows(self.w.library,c);self.assertEqual({e['template_id'] for e in entries},{self.t.id,self.t2.id});self.assertEqual(len(entries),2)
        changed=copy.deepcopy(self.t2);changed.name='Tampered same ID'
        with self.w.library.db:self.w.library.db.execute('UPDATE templates SET payload=? WHERE id=?',(__import__('json').dumps(changed.to_dict()),changed.id))
        changedrows=rows(self.w.library,c);self.assertEqual(next(e for e in changedrows if e['template_id']==self.t2.id)['reference_state'],'STALE')
        self.assertEqual(store.get(other['id'])['code'],'00999')
    def test_real_source_hash_checked_crop_is_correct_and_does_not_certify_visuals(self):
        t,source,work=self.source_template(True);entry=next(e for e in rows(self.w.library) if e['template_id']==t.id);before=self.w.library.db.total_changes;result=source_preview(preview_request(self.w.library,entry))
        self.assertEqual(result['status'],'VERIFIED_DERIVATIVE',result);self.assertGreater(result['image'].pixelColor(50,50).blue(),200);self.assertLess(result['image'].pixelColor(50,50).red(),20);self.assertIn('未由此認證',result['reason']);self.assertIn('UNKNOWN',result['reason']);self.assertEqual(self.w.library.db.total_changes,before)
    def test_missing_changed_original_and_cache_never_show_guessed_picture(self):
        t,s,w=self.source_template();entry=next(e for e in rows(self.w.library) if e['template_id']==t.id);request=preview_request(self.w.library,entry)
        cache=Path(s['image']);old=cache.read_bytes();cache.write_bytes(b'changed derivative');self.assertIsNone(source_preview(request)['image']);self.assertEqual(source_preview(request)['status'],'CHANGED');cache.write_bytes(old)
        original=Path(s['original_path']);original.write_bytes(b'changed original');self.assertEqual(source_preview(request)['status'],'CHANGED');original.unlink();self.assertEqual(source_preview(request)['status'],'UNAVAILABLE')
        manual=next(e for e in rows(self.w.library) if e['template_id']==self.t.id);self.assertEqual(source_preview(preview_request(self.w.library,manual))['status'],'UNKNOWN')
    def test_source_old_work_version_is_usable_history_and_absent_reference_blocks(self):
        t,s,w=self.source_template()
        with self.w.library.db:self.w.library.db.execute('UPDATE artworks SET revision=2 WHERE id=?',(w['id'],))
        entry=next(e for e in rows(self.w.library) if e['template_id']==t.id);result=source_preview(preview_request(self.w.library,entry));self.assertEqual(result['status'],'VERIFIED_DERIVATIVE');self.assertIn('歷史作品版次1',result['reason'])
        with self.w.library.db:self.w.library.db.execute('DELETE FROM artwork_revisions WHERE artwork_id=? AND revision=1',(w['id'],))
        self.assertEqual(source_preview(preview_request(self.w.library,entry))['status'],'STALE')
    def test_source_crop_bounds_budget_and_cancel_return_explicit_unknown(self):
        t,s,w=self.source_template();entry=next(e for e in rows(self.w.library) if e['template_id']==t.id);request=preview_request(self.w.library,entry);bad=copy.deepcopy(request);bad['entry']['template']['artwork']['w']=1000;self.assertEqual(source_preview(bad)['status'],'UNKNOWN')
        cancel=threading.Event();cancel.set();self.assertEqual(source_preview(request,cancel)['status'],'CANCELLED')
        with patch('template_ai.catalog.MAX_PREVIEW_PIXELS',1):self.assertEqual(source_preview(request)['status'],'UNKNOWN')
    def test_format_search_zero_code_same_phone_line_ig_are_readonly_clues(self):
        store,c=self.customer();other=store.create_graph('00999','Other Person',c['graph'],self.t.id,True);before=store.db.total_changes
        self.assertEqual(store.search('00123',field='CODE')[0]['id'],c['id']);self.assertEqual(len(store.search('０２０ ０００ ０１００',field='PHONE')),2);self.assertEqual(len(store.search('+1-202-555-0100',field='PHONE')),2)
        self.assertEqual(len(store.search('EXAMPLE_LINE',field='LINE')),2);self.assertEqual(len(store.search('example_ig',field='IG')),2);self.assertEqual(store.search(''),[]);self.assertEqual(store.search('%'),[]);self.assertEqual(store.search('2020',field='CODE'),[]);self.assertEqual(store.db.total_changes,before)
        with self.assertRaises(ValueError):store.search('555 x123',field='PHONE')
        self.assertNotEqual(other['id'],c['id']);self.assertEqual(store.get(c['id'])['fields'],c['fields'])
    def test_customer_two_sizes_compare_unknown_source_no_fake_thumb_and_cancel_reorder(self):
        store,c=self.customer();d=CustomerStyleDialog(self.w,c);self.extra.append(d);d.show();select(d.catalog,[e['id'] for e in d.catalog.entries]);comparison=d.catalog.compare();self.assertIsNotNone(comparison);self.assertIn('90',comparison.columns[0][1].toPlainText());self.assertIn('100',comparison.columns[1][1].toPlainText());self.assertIn('UNKNOWN',comparison.columns[0][0].text())
        select(d.catalog,[c['styles'][0]['id']]);before=store.get(c['id'])
        with patch('template_ai.customer_catalog.QMessageBox.question',return_value=QMessageBox.No):d.catalog.pick()
        self.assertFalse(d.adopted);self.assertIsNone(self.w.active_input_graph);self.assertEqual(store.get(c['id']),before)
    def test_exact_reorder_changes_work_only_and_missing_logo_stays_blocked(self):
        store,c=self.customer();d=CustomerStyleDialog(self.w,c);self.extra.append(d);link=next(s for s in c['styles'] if s['template_id']==self.t2.id);select(d.catalog,[link['id']])
        with patch('template_ai.customer_catalog.QMessageBox.question',return_value=QMessageBox.Yes):d.catalog.pick()
        self.assertTrue(d.adopted,d.catalog.status.text());self.assertEqual(self.w.reorder_template_id,self.t2.id);self.assertEqual(self.w.out_w.value(),100);self.assertEqual(store.get(c['id']),c);self.assertEqual(self.w.active_input_graph.data['people'],c['graph']['people']);self.w.generate();self.assertFalse(self.w.export_button.isEnabled());self.assertTrue(any('Logo' in reason for candidate in self.w.candidates for reason in candidate.issues))
    def test_master_changed_during_confirmation_cannot_replace_work(self):
        store,c=self.customer();d=CustomerStyleDialog(self.w,c);self.extra.append(d);entry=d.catalog.entries[0];select(d.catalog,[entry['id']])
        def concurrent(*args):
            f=c['fields'][0];store.writeback(c,{f['id']:'Concurrent new name'},[f['id']],True);return QMessageBox.Yes
        with patch('template_ai.customer_catalog.QMessageBox.question',side_effect=concurrent):d.catalog.pick()
        self.assertFalse(d.adopted);self.assertIsNone(self.w.active_input_graph);self.assertIn('主檔已更新',d.catalog.status.text())
    def test_actual_customer_identity_cancel_and_confirm_opens_only_own_catalog(self):
        store,c=self.customer();dialog=CustomerDialog(self.w);self.extra.append(dialog);dialog.query_kind.setCurrentIndex(dialog.query_kind.findData('PHONE'));dialog.query.setText('0200000100');dialog.search();dialog.customers.selectRow(0);APP.processEvents()
        with patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.No),patch('template_ai.customer_catalog.CustomerStyleDialog.exec') as execute:dialog.browse_styles();execute.assert_not_called()
        seen=[]
        def modal(d):seen.append({e['template_id'] for e in d.catalog.entries});return d.Rejected
        with patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes),patch.object(CustomerStyleDialog,'exec',modal):dialog.browse_styles()
        self.assertEqual(seen,[{self.t.id,self.t2.id}]);self.assertEqual(store.get(c['id']),c)
    def test_worker_start_failure_stale_epoch_and_close_recover_controls(self):
        c=self.w.template_catalog;entry=next(e for e in c.entries if e['template_id']==self.t.id)
        with patch.object(self.w.pool,'start',side_effect=RuntimeError('executor failure')):c.controller.reset([entry])
        self.assertIsNone(c.controller.active);self.assertTrue(c.refresh_button.isEnabled())
        entered=threading.Event();release=threading.Event();received=[];c.controller.result.connect(lambda m:received.append(m))
        def slow(request,cancel):entered.set();release.wait(2);return dict(status='UNKNOWN',reason='synthetic stale worker',image=None,proofs=[])
        with patch('template_ai.catalog_preview.source_preview',side_effect=slow):
            c.controller.reset([entry]);self.assertTrue(entered.wait(1));c.controller.reset([]);release.set();pump(lambda:c.controller.active is None)
        self.assertFalse(any(m['result']['reason']=='synthetic stale worker' for m in received));c.controller.reset([entry]);c.close_previews();pump(lambda:c.controller.active is None);self.assertTrue(c.controller.closed)

    def test_actual_source_thumbnail_and_changed_source_during_confirmation_never_adopt(self):
        t,s,w=self.source_template();store=CustomerStore(self.w.library);g=InputGraph.from_legacy([dict(name=['Alex Example'])],[]);customer=store.create_graph('00123','Source Example',g.data,t.id,True);d=CustomerStyleDialog(self.w,customer);self.extra.append(d);entry=d.catalog.entries[0];select(d.catalog,[entry['id']]);pump(lambda:entry['id'] in d.catalog.source_results)
        self.assertEqual(d.catalog.source_results[entry['id']]['result']['status'],'VERIFIED_DERIVATIVE');self.assertFalse(d.catalog.items.item(0).icon().isNull())
        def mutate(*args):Path(s['original_path']).write_bytes(b'synthetic changed source');return QMessageBox.Yes
        with patch('template_ai.customer_catalog.QMessageBox.question',side_effect=mutate):d.catalog.pick()
        self.assertFalse(d.adopted);self.assertIsNone(self.w.active_input_graph);self.assertIn('來源',d.catalog.status.text());d.catalog.rebuild();self.assertTrue(d.catalog.items.item(0).icon().isNull());d.catalog.reload();pump(lambda:d.catalog.controller.active is None and not d.catalog.controller.queue);self.assertTrue(d.catalog.items.item(0).icon().isNull())
    def test_pagination_and_view_switch_preserve_all_explicit_ids_no_visual_dedup(self):
        for i in range(49):self.w.library.save_template(Template(f'Look alike {i:02d}',90,54,[Slot('name','p1',Rect(4,4,42,9))]))
        c=self.w.template_catalog;c.reload();self.assertEqual(len(c.entries),52);first=c.visible[0]['id'];select(c,[first]);c.change_page(1);last=c.visible[-1]['id'];c.selected_ids.add(last);c.rebuild();c.mode.setCurrentIndex(1);c.change_page(-1);self.assertIn(first,c.selected_ids);self.assertIn(last,c.selected_ids);self.assertEqual(len(c.entries),52)
        c.selected_ids.clear();c.clear_selection();self.assertEqual(c.selected_ids,set())
    def test_missing_link_and_template_changed_while_worker_runs_clear_old_preview(self):
        store,customer=self.customer();missing=copy.deepcopy(customer);missing['styles'].append(dict(id='missing-link',template_id='absent-template',template_hash='unknown',width_mm=77,height_mm=44));entries=rows(self.w.library,missing);m=next(r for r in entries if r['id']=='missing-link');self.assertIsNone(m['template']);self.assertEqual(m['reference_state'],'MISSING')
        d=CustomerStyleDialog(self.w,customer);self.extra.append(d);entry=d.catalog.entries[0];d.catalog.selected_ids={entry['id']};old_signature=entry['signature']
        changed=copy.deepcopy(Template.from_dict(entry['template']));changed.name='New stale version'
        with self.w.library.db:self.w.library.db.execute('UPDATE templates SET payload=? WHERE id=?',(__import__('json').dumps(changed.to_dict()),changed.id))
        message=dict(epoch=d.catalog.controller.epoch,id=entry['id'],signature=old_signature,result=dict(status='VERIFIED_DERIVATIVE',reason='synthetic obsolete',image=QImage(4,4,QImage.Format_RGB32),proofs=[]));d.catalog.preview_done(message)
        self.assertEqual(d.catalog.source_results[entry['id']]['result']['status'],'STALE');self.assertTrue(d.catalog.items.item(0).icon().isNull())
        d.catalog.pick();self.assertIn('版型已更新',d.catalog.status.text());self.assertFalse(d.adopted)
    def test_empty_catalog_can_create_first_template_from_browse_without_automatic_edit(self):
        empty=MainWindow(self.root/'empty-library');self.extra.append(empty.template_catalog);self.addCleanup(empty.library.db.close);button=next(b for b in empty.template_catalog.findChildren(QPushButton) if b.text()=='新增空白矩形模板')
        with patch('template_ai.gui.QInputDialog.getText',return_value=('First Example',True)),patch('template_ai.gui.QInputDialog.getDouble',side_effect=[(90,True),(54,True)]):button.click()
        self.assertEqual(len(empty.library.templates()),1);self.assertEqual(empty.template_stack.currentIndex(),0);self.assertEqual(empty.template_catalog.items.count(),1)

    def test_browse_disables_old_property_target_until_explicit_editor(self):
        self.w.tabs.setCurrentIndex(1);self.assertEqual(self.w.template_stack.currentIndex(),0);self.assertFalse(self.w.property_panel.isEnabled());c=self.w.template_catalog;select(c,[self.t.id]);self.assertFalse(self.w.property_panel.isEnabled());c.open_editor();self.assertTrue(self.w.property_panel.isEnabled());self.w.return_catalog();self.assertFalse(self.w.property_panel.isEnabled());self.assertFalse(self.w.property_button.isEnabled())
