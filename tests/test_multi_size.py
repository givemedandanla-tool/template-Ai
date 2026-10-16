"""UI027：獨立尺寸Gate、真實三格式、過期與部分失敗、實際Qt總覽。"""
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox

from template_ai.customers import digest
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.input_graph import InputGraph
from template_ai.logo_store import LogoStore
from template_ai.model import Rect,Slot,Template
from template_ai.multi_size import MultiSizeWorkflow,size_key
from template_ai.multi_size_dialog import MultiSizeDialog
from template_ai.render import export,preview_footer,preview_height
from template_ai.storage import Library
from gui_wait import wait_for_gui,job_diagnostics
from runtime_fixture import controlled_resources

APP=QApplication.instance() or QApplication([])
REVIEW=dict(identity_confirmed=True,whole_mark_confirmed=True,usage_authorized=True,
    digital_quality_confirmed=True,actor='SYNTHETIC_TEST',note='Synthetic source and digital quality checked')


def approve_formats(workflow,plan,dpi=150):
    # Authored fixture review is explicit; production defaults remain unchecked.
    from template_ai.digital_review import confirm
    seen=set()
    for row in plan['items']:
        format=Path(row['path']).suffix[1:].upper();key=(row['key'],format)
        if row['mode']!='FINAL' or format=='PNG' or key in seen:continue
        seen.add(key);proof=workflow.format_proof(row['key'],format,dpi);entry=next(e for e in workflow.entries if e['key']==row['key']);candidate=workflow.revalidate(entry);receipt=confirm(candidate,proof,'SYNTHETIC_SOURCE_AUTHOR','Authored source and actual original-size format snapshot verified before fixture publication',True);workflow.set_format_review(row['key'],format,dpi,receipt)


class MultiSizeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.library=Library(self.root/'library')
        self.logos=LogoStore(self.library);company=self.logos.create_company('Synthetic Brand','Synthetic identity',True)
        path=self.root/'mark.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm"><rect width="60" height="30" fill="red"/></svg>')
        image=import_file(path,self.library.assets);self.payload=dict(image=image['image'],svg=image['svg'],source_width_mm=image['width_mm'],source_height_mm=image['height_mm'],crop=None)
        p=self.logos.propose(self.payload,90,54,company_id=company['id']);self.asset=self.logos.approve(p['id'],p['revision'],company['id'],REVIEW,True)
        self.graph=InputGraph.from_legacy([dict(name=['Alex'],company='c1')],[dict(name='Synthetic Brand')])
        self.logos.bind(self.graph.data['companies'][0]['id'],company['id'],company['name'],True)
        self.templates=[]
        for width,height,logo_x in ((90,54,3),(100,60,60)):
            t=Template('Synthetic '+str(width),width,height,[Slot('name','p1',Rect(3,3,60,8)),Slot('logo','c1',Rect(logo_x,20,30,15))],company_bindings={'p1':'c1'})
            self.library.publish(t);self.templates.append(t)
        self.inputs=self.graph.compile(self.library.logos());self.workflow=MultiSizeWorkflow(self.library,self.inputs,self.graph.data,7)
        self.entries=self.workflow.calculate([[90,54],[100,60]])
        self.output=self.root/'output';self.output.mkdir()

    def tearDown(self):self.workflow.close_format_reviews();self.library.close();self.temp.cleanup()

    def requests(self):return [dict(key=size_key(90,54),mode='FINAL',formats=['pdf','png','jpg']),dict(key=size_key(100,60),mode='PREVIEW',formats=['pdf','png','jpg'])]

    def test_sizes_keep_independent_geometry_and_missing_logo_does_not_borrow_or_block_other_size(self):
        a,b=self.entries;self.assertEqual([e['state'] for e in self.entries],['VALID','BLOCKED'])
        self.assertEqual(self.workflow.selected(a).items[-1].slot.rect.x,3)
        self.assertEqual(self.workflow.selected(b).items[-1].slot.rect.x,60)
        self.assertIsNone(self.workflow.selected(b).items[-1].logo)
        self.assertEqual(self.workflow.selected(a).items[-1].logo['id'],self.asset['id'])
        self.assertTrue(self.workflow.revalidate(a).valid);self.assertFalse(self.workflow.revalidate(b).valid)

    def test_partial_confirmation_is_required_and_real_final_preview_three_formats_are_separate(self):
        plan=self.workflow.plan(self.output,self.requests());self.assertTrue(plan['partial'])
        with self.assertRaises(ValueError):self.workflow.execute(plan,True)
        self.assertEqual(list(self.output.iterdir()),[])
        approve_formats(self.workflow,plan,96)
        results=self.workflow.execute(plan,True,acknowledge_partial=True,dpi=96)
        self.assertEqual([r['status'] for r in results],['SUCCESS']*6)
        self.assertEqual({Path(r['path']).parent.name for r in results},{'FINAL','PREVIEW'})
        for r in results:self.assertGreater(Path(r['path']).stat().st_size,100)
        preview=QImage(next(r['path'] for r in results if r['path'].endswith('_PREVIEW.png')))
        self.assertGreater(preview.height(),round(60*96/25.4))
        self.assertEqual({t.id:t.to_dict() for t in self.library.templates()},
                         {t.id:t.to_dict() for t in self.templates})

    def test_bad_final_unknown_size_duplicate_requests_and_bad_prefix_are_rejected_before_write(self):
        for requests in ([dict(key=size_key(100,60),mode='FINAL',formats=['pdf'])],
                         [dict(key='missing',mode='PREVIEW',formats=['png'])],self.requests()+self.requests()):
            with self.assertRaises(ValueError):self.workflow.plan(self.output,requests)
        with self.assertRaises(ValueError):self.workflow.plan(self.output,self.requests(),prefix='../escape')
        self.assertEqual(list(self.output.iterdir()),[])

    def test_omitted_size_and_all_known_reasons_remain_visible_in_confirmation(self):
        plan=self.workflow.plan(self.output,[self.requests()[0]])
        self.assertEqual(plan['omitted'][0]['size_mm'],[100,60]);self.assertTrue(plan['omitted'][0]['issues'])
        self.assertTrue(plan['partial'])

    def test_revoked_or_changed_logo_and_template_block_only_affected_output(self):
        plan=self.workflow.plan(self.output,self.requests())
        self.logos.revoke(self.asset['id'],digest(self.asset),'Synthetic withdrawal',True)
        results=self.workflow.execute(plan,True,True,dpi=96)
        self.assertTrue(all(r['status']=='FAILED' for r in results[:3]))
        self.assertTrue(all(r['status']=='SUCCESS' for r in results[3:]))
        self.assertFalse((self.output/'FINAL').exists())

    def test_existing_success_is_not_overwritten_and_late_failure_does_not_delete_other_files(self):
        requests=[dict(key=size_key(90,54),mode='FINAL',formats=['png','pdf'])]
        plan=self.workflow.plan(self.output,requests);target=Path(plan['items'][0]['path']);target.parent.mkdir();target.write_bytes(b'Existing synthetic success')
        approve_formats(self.workflow,plan,96)
        results=self.workflow.execute(plan,True,True,dpi=96)
        self.assertEqual([r['status'] for r in results],['FAILED','SUCCESS'])
        self.assertEqual(target.read_bytes(),b'Existing synthetic success')
        self.assertTrue(Path(results[1]['path']).is_file())

    def test_input_change_before_and_between_files_never_produces_unconfirmed_new_output(self):
        plan=self.workflow.plan(self.output,[dict(key=size_key(90,54),mode='FINAL',formats=['png','pdf'])])
        with self.assertRaises(ValueError):self.workflow.execute(plan,True,True,current_check=lambda:False)
        calls=[]
        def valid():calls.append(1);return len(calls)<=2
        approve_formats(self.workflow,plan,96)
        results=self.workflow.execute(plan,True,True,current_check=valid,dpi=96)
        self.assertEqual([r['status'] for r in results],['SUCCESS','FAILED'])

    def test_preview_footer_contains_every_issue_outside_original_body_and_pdf_text(self):
        candidate=deepcopy(self.workflow.selected(self.entries[1]));candidate.issues+=['Synthetic issue '+str(i) for i in range(30)]
        document,_,height=preview_footer(candidate)
        self.assertIn('Synthetic issue 29',document.toPlainText());self.assertGreater(height,14)
        self.assertGreater(preview_height(candidate),candidate.template.height_mm+14)
        path=self.root/'all-PREVIEW.pdf';export(candidate,path,dpi=96,preview=True)
        pdf=QPdfDocument();self.assertEqual(pdf.load(str(path)),QPdfDocument.Error.None_)
        self.assertIn('Synthetic issue 29',pdf.getAllText(0).text());pdf.close()

    def test_cancel_and_missing_template_are_explicit_not_zero_test_success(self):
        event=threading.Event();event.set()
        rows=self.workflow.calculate([[90,54],[100,60]],cancel=event)
        self.assertEqual([r['state'] for r in rows],['CANCELLED','CANCELLED'])
        with self.assertRaises(ValueError):self.workflow.plan(self.output,self.requests())
        rows=self.workflow.calculate([[80,40]])
        self.assertEqual(rows[0]['state'],'NO_TEMPLATE');self.assertIsNone(rows[0]['selected'])

    def test_actual_qt_matrix_calculates_both_sizes_and_cancel_confirmation_creates_no_files(self):
        window=MainWindow(self.library.root)
        controlled_resources(window)
        try:
            window.adopt_input_graph(self.graph.data)
            dialog=MultiSizeDialog(window);self.addCleanup(dialog.deleteLater)
            for row in range(dialog.table.rowCount()):dialog.table.item(row,0).setCheckState(Qt.Checked)
            dialog.start()
            self.assertTrue(wait_for_gui(lambda:not dialog.running,10),job_diagnostics(window,'GEOMETRY') if dialog.running else '')
            self.assertFalse(dialog.running);self.assertIsNotNone(dialog.service)
            self.assertEqual([e['state'] for e in dialog.service.entries],['VALID','BLOCKED'])
            for row in range(dialog.table.rowCount()):dialog.table.cellWidget(row,5).setCurrentText('FINAL' if row==0 else 'PREVIEW')
            with patch.object(QFileDialog,'getExistingDirectory',return_value=str(self.output)),patch.object(QMessageBox,'question',return_value=QMessageBox.No):dialog.export()
            self.assertEqual(list(self.output.iterdir()),[])
            window.invalidate();self.assertTrue(dialog.stale.is_set());self.assertFalse(dialog.export_button.isEnabled())
        finally:window.input_timer.stop();window.font_manager.close();window.library.close();window.deleteLater()
