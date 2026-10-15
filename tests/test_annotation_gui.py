from copy import deepcopy
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPointF
from PySide6.QtWidgets import QMessageBox,QDialog
import test_automatic_training as fixture
from template_ai.annotation_dialog import AnnotationDialog
from template_ai.annotations import AnnotationSession
from template_ai.model import Rect
from template_ai.training_exceptions import exception_rows,exclude_work

APP=fixture.APP


class AnnotationGuiTests(unittest.TestCase):
    setUp=fixture.AutomaticTrainingTests.setUp
    tearDown=fixture.AutomaticTrainingTests.tearDown
    run_job=fixture.AutomaticTrainingTests.run_job
    job=fixture.AutomaticTrainingTests.job
    window=fixture.AutomaticTrainingGuiTests.window

    def ready(self):
        self.original_bytes=self.path.read_bytes();result=self.run_job(self.job());window=self.window();work=window.library.artworks(result['items'][0]['source_id'])[0]
        dialog=AnnotationDialog(window,work['id']);self.addCleanup(dialog.deleteLater);dialog.show();APP.processEvents();return window,dialog

    def test_actual_qt_source_canvas_selection_semantic_details_patch_undo_and_atomic_pending_save(self):
        window,dialog=self.ready();slot=next(s for s in dialog.session.payload['slots'] if s['kind']=='name');before=deepcopy(dialog.session.base)
        dialog.select([slot['id']]);self.assertIn('name',dialog.details.toPlainText());self.assertIn('PENDING',dialog.session.facts['state'])
        dialog.value.setText('姓名：Alex Revised');dialog.coords[0].setValue(slot['rect']['x']+1);dialog.apply_properties()
        self.assertEqual(window.library.artwork(before['id']),before);dialog.undo();self.assertEqual(dialog.session.payload,before['payload']);dialog.redo();dialog.save()
        self.assertEqual(window.library.artwork(before['id'])['revision'],before['revision']+1);self.assertIsNone(dialog.session.facts['confirmation']);self.assertEqual(dialog.session.observations[0]['evidence'],'USER_OBSERVATION_DRAFT')
        self.assertFalse(window.library.templates());self.assertEqual(self.path.read_bytes(),self.original_bytes)

    def test_unknown_source_observation_is_explicitly_mapped_with_same_stable_id_and_undo(self):
        self.path.write_text(self.path.read_text().replace('姓名：Alex Example','Alex Unknown'))
        window,dialog=self.ready();unknown=next(o for o in dialog.session.observations if o.get('slot_id') is None)
        self.assertEqual(unknown['semantic']['semantic_type'],'unknown');dialog.select(['observation:'+unknown['id']]);self.assertIn('unknown',dialog.details.toPlainText())
        dialog.kind.setCurrentIndex(dialog.kind.findData('name'));dialog.owner.setText('p1');dialog.bind_observation()
        mapped=next(o for o in dialog.session.observations if o['id']==unknown['id']);self.assertIsNotNone(mapped['slot_id']);dialog.undo()
        self.assertIsNone(next(o for o in dialog.session.observations if o['id']==unknown['id'])['slot_id'])

    def test_stale_save_never_continues_into_confirmation_or_shows_false_success(self):
        window,dialog=self.ready();slot=dialog.session.payload['slots'][0];dialog.select([slot['id']]);dialog.visual.setChecked(True)
        with patch.object(dialog.session,'save',side_effect=ValueError('Synthetic stale save')),patch.object(dialog.session.store,'confirm_facts') as confirm:
            dialog.confirm();confirm.assert_not_called()
        self.assertIn('Synthetic stale save',dialog.status.text());self.assertIsNone(dialog.session.store.facts(dialog.session.base['id'])['confirmation'])

    def test_mode_switch_preserves_each_selection_undo_and_canvas_view(self):
        window,dialog=self.ready();window.tabs.setCurrentIndex(0);window.slots=[__import__('template_ai.model',fromlist=['Slot']).Slot('name','p1',Rect(1,1,20,4))]
        window.select_slot(window.slots[0]);selected=window.current_slot.id;window.coords[0].setValue(7.25);window.undo_stack=[{'synthetic':True}];window.train_canvas.scale(1.25,1.25);transform=window.train_canvas.transform()
        window.tabs.setCurrentIndex(2);self.assertEqual(window.undo_stack,[]);window.tabs.setCurrentIndex(0)
        self.assertEqual(window.current_slot.id,selected);self.assertEqual(window.undo_stack,[{'synthetic':True}]);self.assertEqual(window.train_canvas.transform(),transform);self.assertEqual(window.coords[0].value(),7.25);self.assertEqual(window.slots[0].rect.x,1)

    def test_exceptions_explain_actual_impact_exclusion_retains_original_and_is_sticky(self):
        self.run_job(self.job());rows=exception_rows(self.library);self.assertTrue(rows);self.assertTrue(all(r['impact_count']==1+len(r['template_ids']) for r in rows))
        row=rows[0];unit=exclude_work(self.service,row['unit_id'],row['unit_revision'],'Synthetic explicit exclusion',True);before=self.path.read_bytes()
        work=self.library.artwork(row['work_id']);edit=AnnotationSession(self.library,work['id']);edit.payload['visual_confirmed']=True;edit.save()
        actual,reused=self.service.process_work(self.library.artwork(work['id']),{'actor':'TEST'});self.assertTrue(reused);self.assertEqual(actual['state'],'EXCLUDED');self.assertEqual(self.path.read_bytes(),before)

    def test_actual_work_overview_search_thumbnail_state_and_source_region_canvas_keep_original(self):
        from template_ai.work_overview_dialog import WorkOverviewDialog,SourceRegionsDialog
        window,dialog=self.ready();overview=WorkOverviewDialog(window);self.addCleanup(overview.deleteLater);overview.show();APP.processEvents();self.assertEqual(len(overview.rows),2)
        overview.query.setText('does-not-exist');self.assertEqual(overview.table.rowCount(),0);overview.query.clear();overview.table.selectRow(0);work=overview.current();self.assertEqual(work['source_id'],dialog.session.base['source_id'])
        regions=SourceRegionsDialog(window.library,work,dialog);self.addCleanup(regions.deleteLater);regions.show();APP.processEvents();regions.add(Rect(0,0,90,54));regions.add(Rect(100,0,90,54));self.assertEqual(len(regions.regions),2);regions.undo();self.assertEqual(len(regions.regions),1)
        regions.add(Rect(-1,0,90,54));self.assertEqual(len(regions.regions),1)
        from PySide6.QtTest import QTest
        start=regions.canvas.mapFromScene(QPointF(20,10));end=regions.canvas.mapFromScene(QPointF(50,20));QTest.mousePress(regions.canvas.viewport(),Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(regions.canvas.viewport(),end);QTest.mouseRelease(regions.canvas.viewport(),Qt.LeftButton,Qt.NoModifier,end);APP.processEvents();self.assertEqual(len(regions.regions),2);self.assertAlmostEqual(regions.regions[-1].w,30,delta=1);regions.accept();self.assertEqual(regions.result(),QDialog.DialogCode.Accepted);self.assertEqual(self.path.read_bytes(),self.original_bytes)

    def test_confirmed_correction_creates_one_pending_hint_without_rule_activation_and_can_be_deferred(self):
        from PySide6.QtWidgets import QInputDialog
        from template_ai.rule_hints_panel import RuleHintsPanel
        window,dialog=self.ready();store=dialog.session.store;work=dialog.session.base;slot=next(s for s in dialog.session.payload['slots'] if s['kind']=='name');facts=store.facts(work['id']);oid=next(o['id'] for o in facts['observations'] if o.get('slot_id')==slot['id'])
        def confirm():
            f=store.facts(work['id']);return store.confirm_facts(work['id'],[oid],f['revision'],f['pins'],store.source_proof(work['id']),'SYNTHETIC_REVIEWER',True)
        confirm();edit=AnnotationSession(window.library,work['id']);edit.change(dict(operation='PATCH',ids=[slot['id']],patch=dict(kind='title')));edit.save();confirm();self.assertEqual(store.count('RULE_HINT'),1);confirm();self.assertEqual(store.count('RULE_HINT'),1);self.assertEqual(store.count('RULE'),0)
        panel=RuleHintsPanel(window);self.addCleanup(panel.deleteLater);panel.table.selectRow(0);self.assertIn('未執行',panel.details.toPlainText());self.assertEqual(panel.rows[0]['state'],'PENDING')
        with patch.object(QInputDialog,'getText',return_value=('Synthetic defer pending counterexamples',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.decide('DEFERRED')
        self.assertEqual(panel.rows[0]['state'],'DEFERRED');self.assertEqual(store.facts_state(work['id']),'CONFIRMED');self.assertEqual(store.count('RULE'),0)

    def test_actual_verified_svg_links_sync_index_search_without_claiming_native_illustrator_mapping(self):
        from template_ai.object_index import source_structure,matching_ids
        window,dialog=self.ready();work=dialog.session.base;source=window.library.source(work['source_id']);structure=source_structure(source,work['payload']);self.assertEqual(structure['mapping'],'VERIFIED_SVG_LINKS');self.assertEqual(structure['linked_slot_ids'],sorted(s['id'] for s in work['payload']['slots']))
        source_id=next(iter(work['payload']['analysis_evidence']['slot_source_map'].values()))['svg_object_id'];self.assertTrue(matching_ids(work['payload'],source_id,structure=structure));self.assertEqual(structure['provenance'],'衍生 SVG／非 Illustrator 原生圖層')
        tampered=deepcopy(work['payload']);next(iter(tampered['analysis_evidence']['slot_source_map'].values()))['svg_hash']='0'*64;invalid=source_structure(source,tampered);self.assertLess(len(invalid['linked_slot_ids']),len(structure['linked_slot_ids']))
