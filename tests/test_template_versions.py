from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from template_ai.demo import demo_template
from template_ai.storage import Library
from template_ai.template_versions import TemplateVersions,differences
from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog
APP=QApplication.instance() or QApplication([])


class TemplateVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.t=demo_template();self.library.save_template(self.t);self.library.publish(self.t);self.service=TemplateVersions(self.library)

    def test_restore_published_version_as_same_family_new_draft_with_complete_difference_and_provenance(self):
        original=self.library.object_snapshot('TEMPLATE',self.t.id);draft=self.service.clone(self.service.plan(self.t.id),'REVIEWER','Synthetic new draft',True);draft.slots[0].rect.x+=1;draft.slots[0].color='#123456';self.library.save_template(draft)
        other=self.library.object_snapshot('TEMPLATE',draft.id);diff=differences(original['payload'],other['payload']);self.assertEqual(diff[0]['id'],draft.slots[0].id);self.assertIn('rect',diff[0]['after']);self.assertEqual(diff[0]['after']['color'],'#123456')
        restored=self.service.clone(self.service.plan(self.t.id),'REVIEWER','Synthetic rollback',True,rollback=True)
        self.assertEqual((restored.family_id,restored.version,restored.state),(self.t.family_id,3,'draft'));self.assertEqual(restored.slots,self.t.slots);self.assertEqual(self.library.object_snapshot('TEMPLATE',self.t.id),original);self.assertEqual(self.library.object_snapshot('TEMPLATE',draft.id),other)
        records=self.service.store.records('TEMPLATE_VERSION');self.assertEqual(len(records),2);self.assertTrue(any(r['action']=='ROLLBACK_AS_NEW_DRAFT' and r['source_template_id']==self.t.id for r in records))

    def test_stale_family_version_and_unapproved_restore_write_nothing(self):
        plan=self.service.plan(self.t.id)
        with self.assertRaises(ValueError):self.service.clone(plan,'REVIEWER','Synthetic no approval')
        self.service.clone(plan,'REVIEWER','Synthetic concurrent version',True)
        with self.assertRaisesRegex(ValueError,'變更'):self.service.clone(plan,'REVIEWER','Synthetic stale version',True)
        self.assertEqual(len(self.library.templates()),2)

    def test_late_audit_failure_rolls_back_new_version_and_its_clock(self):
        before=list(self.library.db.execute('SELECT * FROM template_edit_clocks'))
        with patch.object(self.library,'event',side_effect=OSError('Synthetic audit failure')):
            with self.assertRaises(OSError):self.service.clone(self.service.plan(self.t.id),'REVIEWER','Synthetic rollback',True,rollback=True)
        self.assertEqual(len(self.library.templates()),1);self.assertEqual(list(self.library.db.execute('SELECT * FROM template_edit_clocks')),before);self.assertEqual(self.service.store.count('TEMPLATE_VERSION'),0)

    def test_actual_qt_difference_review_cancel_then_explicit_restore_keeps_published_usable(self):
        from template_ai.gui import MainWindow
        from template_ai.template_versions_dialog import TemplateVersionsDialog
        draft=self.service.clone(self.service.plan(self.t.id),'REVIEWER','Synthetic new draft',True);draft.slots[0].rect.x+=1;self.library.save_template(draft)
        window=MainWindow(self.library.root)
        def close():window.input_timer.stop();window.font_manager.close();window.library.close();window.deleteLater()
        self.addCleanup(close);window.refresh_templates(draft.id);dialog=TemplateVersionsDialog(window);self.addCleanup(dialog.deleteLater);dialog.show();APP.processEvents();self.assertIn('OBJECT',dialog.details.toPlainText());dialog.left.setCurrentIndex(dialog.left.findData(self.t.id));dialog.right.setCurrentIndex(dialog.right.findData(draft.id))
        with patch.object(QInputDialog,'getText',return_value=('Synthetic explicit restore',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.No):dialog.restore()
        self.assertEqual(len(self.library.templates()),2)
        with patch.object(QInputDialog,'getText',return_value=('Synthetic explicit restore',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.restore()
        self.assertEqual(len(self.library.templates()),3,dialog.status.text());self.assertEqual(window.template.state,'draft');self.assertEqual(self.library.templates(published_only=True)[0].id,self.t.id)
