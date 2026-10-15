from copy import deepcopy
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
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
        window.select_slot(window.slots[0]);selected=window.current_slot.id;window.undo_stack=[{'synthetic':True}];window.train_canvas.scale(1.25,1.25);transform=window.train_canvas.transform()
        window.tabs.setCurrentIndex(2);self.assertEqual(window.undo_stack,[]);window.tabs.setCurrentIndex(0)
        self.assertEqual(window.current_slot.id,selected);self.assertEqual(window.undo_stack,[{'synthetic':True}]);self.assertEqual(window.train_canvas.transform(),transform)

    def test_exceptions_explain_actual_impact_exclusion_retains_original_and_is_sticky(self):
        self.run_job(self.job());rows=exception_rows(self.library);self.assertTrue(rows);self.assertTrue(all(r['impact_count']==1+len(r['template_ids']) for r in rows))
        row=rows[0];unit=exclude_work(self.service,row['unit_id'],row['unit_revision'],'Synthetic explicit exclusion',True);before=self.path.read_bytes()
        work=self.library.artwork(row['work_id']);edit=AnnotationSession(self.library,work['id']);edit.payload['visual_confirmed']=True;edit.save()
        actual,reused=self.service.process_work(self.library.artwork(work['id']),{'actor':'TEST'});self.assertTrue(reused);self.assertEqual(actual['state'],'EXCLUDED');self.assertEqual(self.path.read_bytes(),before)
