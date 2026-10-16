"""Actual persisted unsupported import and original-canvas repair entry adapters."""
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
import test_quality_repair_gui as fixtures
from template_ai.batch_import import BatchStore,preflight
from template_ai.quality_repairs import QualityRepairs
from template_ai.quality_command import run_command
from template_ai.exception_dialog import ImportExceptionDialog
from template_ai.training_navigation import locate_work

APP=QApplication.instance() or QApplication([])


class QualityRepairImportCanvasTests(unittest.TestCase):
    setUp=fixtures.QualityRepairGuiTests.setUp
    window=fixtures.QualityRepairGuiTests.window

    def failed(self):
        path=self.root/'unparsed-source.unsupported';path.write_bytes(b'Authored unsupported local source, no registered work')
        store=BatchStore(self.library);report=preflight([path],self.library.list_sources());self.assertEqual(report['items'][0]['status'],'FAILED')
        batch=store.create(report,True);return batch,batch['items'][0]

    def test_actual_import_exception_without_work_preserves_receipt_and_requires_manual_source_recovery(self):
        batch,item=self.failed();service=QualityRepairs(self.library)
        preview=run_command(self.library.root,'REPAIR_IMPORT_PLAN',dict(batch_id=batch['id'],item_id=item['id'],expected_revision=batch['revision'],description='Actual unsupported source import, no guessed work'))
        self.assertIsNone(preview['work_id']);self.assertFalse(preview['automatic_repair_allowed'])
        saved=run_command(self.library.root,'REPAIR_CONFIRM',dict(kind='ISSUE',plan=preview,actor='Reviewer',reason='Keep actual failed batch and manual recovery scope',approved=True))
        self.assertEqual(saved['state'],'MANUAL_SOURCE_RECOVERY_REQUIRED');self.assertEqual(saved['evidence']['origin_reference']['item_digest'],preview['origin_reference']['item_digest'])
        root=service.root_plan(saved['id'],'SOURCE_INCOMPLETE','Unsupported original cannot yet be parsed','No work or human truth was invented',True,False)
        self.assertFalse(root['can_prepare_candidate']);self.assertEqual(self.store.count('QUALITY_REPAIR_CANDIDATE'),0)
        with self.assertRaises(ValueError):service.impact_plan(saved['id'])
        with self.assertRaises(ValueError):service.plan_import_issue(batch['id'],item['id'],batch['revision']-1,'Stale import receipt')
        self.assertEqual(BatchStore(self.library).get(batch['id']),batch)

    def test_native_import_and_original_canvas_route_to_same_center_with_actual_scope(self):
        batch,item=self.failed();window=self.window();dialog=ImportExceptionDialog(window);self.addCleanup(dialog.deleteLater)
        index=next(index for index,row in enumerate(dialog.rows) if row['batch_id']==batch['id']);dialog.table.selectRow(index)
        with patch('template_ai.training_quality_dialog.open_repair_center') as opened:dialog.open_repair()
        self.assertEqual(opened.call_args.args[1]['origin'],'IMPORT_EXCEPTION');self.assertEqual(opened.call_args.args[1]['item_id'],item['id'])
        locate_work(window,self.work['id']);APP.processEvents()
        with patch('template_ai.training_quality_dialog.open_repair_center') as opened:window.source_repair()
        self.assertEqual(opened.call_args.args[1]['origin'],'SOURCE_FACTS');self.assertEqual(opened.call_args.args[1]['work_id'],self.work['id'])
