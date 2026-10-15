import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.gui import MainWindow
from template_ai.training_store import TrainingStore
from template_ai.source_scan import register_root,configure_root,candidate_page
from template_ai.source_scan_dialog import SourceScanDialog
from template_ai.customers import CustomerStore
from template_ai.input_graph import InputGraph
from template_ai.demo import demo_template
APP=QApplication.instance() or QApplication([])
SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 900 540"><text x="40" y="80">Alex Example</text><text x="40" y="130">alex@example.org</text></svg>'


class SourceWatchCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.directory=self.root/'sources';self.directory.mkdir();self.a=self.directory/'A001.svg';self.b=self.directory/'B002.svg';self.a.write_bytes(SVG);self.b.write_bytes(SVG)
        self.window=MainWindow(self.root/'data');self.store=TrainingStore(self.window.library);self.watch=register_root(self.store,self.directory);self.dialog=SourceScanDialog(self.window);self.dialog.roots.setCurrentIndex(self.dialog.roots.findData(self.watch['id']));self.addCleanup(self.cleanup);APP.processEvents();self.window.source_watch.timer.stop()

    def wait(self,predicate=None,seconds=30):
        predicate=predicate or (lambda:not self.window.busy and not self.dialog.running)
        end=time.monotonic()+seconds
        while not predicate():
            APP.processEvents();QTest.qWait(10)
            if time.monotonic()>end:self.fail('actual watch/GUI pipeline timed out: '+self.dialog.status.text())
        APP.processEvents()

    def cleanup(self):
        self.window.source_watch.shutdown()
        child=self.dialog.training_dialog
        if child and child.running:child.cancel()
        if self.window.busy:self.wait(lambda:not self.window.busy)
        if child:child.close()
        self.dialog.dirty=False;self.dialog.close();self.window.close()

    def scan(self):self.dialog.scan();self.wait();self.dialog.render_current();return candidate_page(self.store,self.watch['id'])
    def select(self,predicate):
        self.dialog.render_current();found=[]
        for index in range(self.dialog.candidates.topLevelItemCount()):
            item=self.dialog.candidates.topLevelItem(index);candidate=item.data(0,Qt.UserRole);item.setCheckState(0,Qt.Checked if predicate(candidate) else Qt.Unchecked)
            if predicate(candidate):found.append(candidate)
        return found

    def test_real_gui_start_pause_config_and_remove_preserve_customer_styles_sources_and_candidate_history(self):
        template=demo_template();self.window.library.save_template(template);customers=CustomerStore(self.window.library);graph=InputGraph.from_legacy([dict(name=['Protected Example'])],[]);customer=customers.create_graph('KEEP-0001','Protected Example',graph.data,template.id,approved=True);before=customers.get(customer['id'])
        self.dialog.start_watch();self.window.source_watch.dispatch();self.wait(lambda:len(candidate_page(self.store))==2 and not self.window.busy)
        root=self.store.get('SCAN_ROOT',self.watch['id']);self.assertTrue(root['enabled']);self.assertEqual(root['mode'],'AUTO_PRECHECK');self.assertFalse(any(self.dialog.candidates.topLevelItem(i).checkState(0)==Qt.Checked for i in range(self.dialog.candidates.topLevelItemCount())))
        self.dialog.pause();self.assertFalse(self.store.get('SCAN_ROOT',root['id'])['enabled']);history=candidate_page(self.store)
        with patch('template_ai.source_scan_dialog.QMessageBox.question',return_value=QMessageBox.Yes):self.dialog.remove()
        self.assertTrue(self.store.get('SCAN_ROOT',root['id'])['archived']);self.assertEqual(customers.get(customer['id']),before);self.assertEqual(candidate_page(self.store),history);self.assertEqual(self.a.read_bytes(),SVG);self.assertEqual(self.b.read_bytes(),SVG)

    def test_actual_ui003_handoff_requires_explicit_start_then_keeps_two_alias_source_ids_and_real_job_receipts(self):
        self.scan();self.select(lambda c:True);self.dialog.launch();child=self.dialog.training_dialog;self.wait(lambda:not child.running and not self.window.busy)
        self.assertIsNotNone(child.report);self.assertEqual(self.store.count('AUTO_JOB'),0);self.assertEqual(len(child.report['items']),2);self.assertEqual(self.window.library.list_sources(),[])
        with patch('template_ai.automatic_training_dialog.QMessageBox.question',return_value=QMessageBox.Yes):child.start()
        self.wait(lambda:not child.running and not self.window.busy,seconds=40)
        sources=self.window.library.list_sources();self.assertEqual(len(sources),2);self.assertEqual(len({s['id'] for s in sources}),2);self.assertEqual({Path(s['original_path']).name for s in sources},{'A001.svg','B002.svg'})
        candidates=candidate_page(self.store);self.assertEqual({c['state'] for c in candidates},{'DISPATCHED'});job_ids={c['auto_job_id'] for c in candidates};self.assertEqual(len(job_ids),1);self.assertIsNotNone(self.store.get('AUTO_JOB',next(iter(job_ids))))
        self.assertEqual(self.a.read_bytes(),SVG);self.assertEqual(self.b.read_bytes(),SVG);self.assertTrue(all(t.state.lower()!='published' for t in self.window.library.templates() if t.source_id in {s['id'] for s in sources}))
        self.scan();root=self.store.get('SCAN_ROOT',self.watch['id'])
        for row in root['last_scan']['entries']:
            self.assertTrue(row['registered']);self.assertEqual(row['artwork_count'],sum(len(self.window.library.artworks(identity)) for identity in row['registered_source_ids']))
        active=self.window.library.active_source_id()
        with patch('template_ai.source_dialog.QDialog.exec',return_value=0):self.dialog.inspect_source();self.wait()
        self.assertEqual(self.window.library.active_source_id(),active);self.dialog.recheck_existing();self.assertIs(self.dialog.training_dialog,child);self.wait(lambda:not child.running and not self.window.busy)
        self.assertIsNotNone(child.report);self.assertEqual(self.store.count('AUTO_JOB'),1)

    def test_modified_version_needs_review_and_changed_bytes_during_later_preflight_never_start_a_job(self):
        self.scan();self.a.write_bytes(SVG.replace(b'Alex Example',b'Blair Example'));self.scan();selected=self.select(lambda c:c['path']==str(self.a) and c['state']=='REVIEW_REQUIRED');self.assertEqual(len(selected),1)
        with patch('template_ai.source_scan_dialog.QMessageBox.question',return_value=QMessageBox.No):self.dialog.review()
        self.assertEqual(self.store.get('SCAN_CANDIDATE',selected[0]['id'])['state'],'REVIEW_REQUIRED')
        with patch('template_ai.source_scan_dialog.QMessageBox.question',return_value=QMessageBox.Yes):self.dialog.review()
        self.wait();self.assertEqual(self.store.get('SCAN_CANDIDATE',selected[0]['id'])['state'],'REVIEWED_NEW_VERSION_CANDIDATE');self.select(lambda c:c['id']==selected[0]['id'])
        self.a.write_bytes(SVG.replace(b'Alex Example',b'Casey Example'));self.dialog.launch();child=self.dialog.training_dialog;self.wait(lambda:not child.running and not self.window.busy)
        self.assertIsNone(child.report);self.assertFalse(child.start_button.isEnabled());self.assertIn('SOURCE_CHANGED',child.status.text());self.assertEqual(self.store.count('AUTO_JOB'),0);self.assertEqual(self.window.library.list_sources(),[])

    def test_unsaved_root_input_survives_reconciliation_and_concurrent_config_is_not_overwritten(self):
        self.dialog.formats.setText('.svg');self.dialog.formats.textEdited.emit('.svg');self.assertTrue(self.dialog.dirty);self.scan();self.assertEqual(self.dialog.formats.text(),'.svg');self.assertTrue(self.dialog.dirty)
        root=self.store.get('SCAN_ROOT',self.watch['id']);configure_root(self.store,root,recursive=True)
        self.dialog.save_settings();self.assertIn('另一介面',self.dialog.status.text());self.assertTrue(self.store.get('SCAN_ROOT',root['id'])['recursive']);self.assertEqual(self.dialog.formats.text(),'.svg')

    def test_review_worker_launch_failure_releases_gui_without_losing_review_or_source_data(self):
        self.scan();self.a.write_bytes(SVG+b' ');self.scan();selected=self.select(lambda c:c['state']=='REVIEW_REQUIRED');self.assertEqual(len(selected),1)
        with patch('template_ai.source_scan_dialog.QMessageBox.question',return_value=QMessageBox.Yes),patch.object(self.window,'run_job',side_effect=RuntimeError('worker launch refused')):self.dialog.review()
        self.assertFalse(self.dialog.running);self.assertIn('worker launch refused',self.dialog.status.text());self.assertEqual(self.store.get('SCAN_CANDIDATE',selected[0]['id'])['state'],'REVIEW_REQUIRED');self.assertEqual(self.window.library.list_sources(),[])

    def test_pause_preserves_unsaved_form_and_saves_against_fresh_control_state(self):
        self.dialog.start_watch();self.window.source_watch.dispatch();self.wait(lambda:not self.window.busy)
        self.dialog.formats.setText('.svg');self.dialog.formats.textEdited.emit('.svg');self.dialog.pause()
        self.assertTrue(self.dialog.dirty);self.assertEqual(self.dialog.formats.text(),'.svg');self.dialog.save_settings();root=self.store.get('SCAN_ROOT',self.watch['id'])
        self.assertEqual(root['extensions'],['.svg']);self.assertFalse(root['enabled']);self.assertNotIn('另一介面',self.dialog.status.text())

    def test_actual_scan_and_candidate_paging_keeps_denominator_and_same_version_explicit_selection(self):
        for i in range(51):(self.directory/f'C{i:03d}.svg').write_bytes(SVG)
        self.scan();self.assertEqual(len(self.store.get('SCAN_ROOT',self.watch['id'])['last_scan']['entries']),53);self.assertEqual(self.dialog.scan_items.count(),50);self.assertEqual(self.dialog.candidates.topLevelItemCount(),50)
        first=self.dialog.candidates.topLevelItem(0).data(0,Qt.UserRole)['id'];selected=self.select(lambda c:c['id']==first);self.assertEqual(len(selected),1);self.dialog.only_changed.setChecked(True);self.assertEqual([c['id'] for c in self.dialog.selected()],[selected[0]['id']])
        self.dialog.scan_page(1);self.assertEqual(self.dialog.scan_items.count(),3);self.dialog.page(1);self.assertEqual(self.dialog.candidates.topLevelItemCount(),3);self.assertEqual(len(candidate_page(self.store,self.watch['id'],limit=100)),53)

    def test_stale_project_dialog_never_rebinds_or_writes_another_library(self):
        from template_ai.storage import Library
        self.scan();before=candidate_page(self.store);original=self.window.library;other=Library(self.root/'another-project');TrainingStore(other)
        try:
            self.window.library=other;self.window.source_watch.tick();self.dialog.service_updated(dict(root_id='SERVICE',state='FAILED',message='scope changed'));self.dialog.scan();self.dialog.launch();self.dialog.reload()
            self.assertIn('環境已切換',self.dialog.status.text());self.assertFalse(self.dialog.running);self.assertEqual(candidate_page(TrainingStore(other)),[]);self.assertEqual(candidate_page(self.store),before)
        finally:self.window.library=original;other.close()
