from copy import deepcopy
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QInputDialog
from template_ai.semantic_fields import review_issues
import test_annotation_gui as fixture
APP=fixture.APP

class MarkerReviewTests(unittest.TestCase):
    setUp=fixture.AnnotationGuiTests.setUp
    tearDown=fixture.AnnotationGuiTests.tearDown
    job=fixture.AnnotationGuiTests.job
    run_job=fixture.AnnotationGuiTests.run_job
    window=fixture.AnnotationGuiTests.window
    ready=fixture.AnnotationGuiTests.ready

    def test_rejected_and_quarantined_marker_persists_reason_and_blocks_truth_until_explicit_restore(self):
        w,d=self.ready();o=d.session.observations[0];identity=o['id'];slot=o['slot_id'];original=deepcopy(d.session.base)
        for state in ['REJECTED','QUARANTINED']:
            d.session.review([identity],state,'SYNTHETIC wrong identity');d.session.save();facts=d.session.store.facts(original['id'])
            self.assertEqual(next(o for o in facts['observations'] if o['id']==identity)['review']['state'],state)
            self.assertTrue(any(row.get('observation_id')==identity for row in review_issues(d.session.base,facts)))
            with self.assertRaisesRegex(ValueError,'拒絕／疑義隔離'):
                d.session.store.confirm_facts(original['id'],[identity],facts['revision'],facts['pins'],d.session.store.source_proof(original['id']),'SYNTHETIC',True)
        d.session.review([identity],'HUMAN_PENDING_CONFIRMATION','Source corrected');d.session.save();facts=d.session.store.facts(original['id'])
        confirmed=d.session.store.confirm_facts(original['id'],[identity],facts['revision'],facts['pins'],d.session.store.source_proof(original['id']),'SYNTHETIC',True)
        self.assertEqual(confirmed['confirmation']['observation_ids'],[identity]);self.assertEqual(self.path.read_bytes(),self.original_bytes)
        self.assertEqual(w.library.templates(),[])

    def test_actual_gui_exact_review_cancel_and_local_undo_do_not_change_other_marker(self):
        w,d=self.ready();before=deepcopy(d.session.observations);o=before[0];d.select([o['slot_id']])
        with patch.object(QInputDialog,'getText',return_value=('synthetic ambiguous',False)):d.review_markers('QUARANTINED')
        self.assertEqual(d.session.observations,before)
        with patch.object(QInputDialog,'getText',return_value=('synthetic ambiguous',True)):d.review_markers('QUARANTINED')
        self.assertEqual([o for o in d.session.observations if o.get('review')],[dict(o,review=dict(state='QUARANTINED',reason='synthetic ambiguous',actor='LOCAL_OPERATOR'))])
        d.undo();self.assertEqual(d.session.observations,before);self.assertEqual(self.path.read_bytes(),self.original_bytes)

    def test_overview_global_status_source_page_size_and_sort_apply_before_pagination(self):
        from template_ai.work_overview_dialog import WorkOverviewDialog
        w,d=self.ready();source=d.session.base['source_id'];payload=deepcopy(d.session.base['payload'])
        for i in range(101):
            copy=deepcopy(payload);copy['segmentation_state']='SUPERSEDED';w.library.create_artwork(source,'AAA-old-'+str(i),copy)
        target=w.library.create_artwork(source,'ZZZ-target',payload)
        overview=WorkOverviewDialog(w);self.addCleanup(overview.close);overview.sort.setCurrentText('作品名稱');overview.state.setCurrentText('PENDING');overview.source_filter.setText(source);overview.page_filter.setText('1');overview.size_filter.setText('90.0x54.0');APP.processEvents()
        self.assertIn(target['id'],[row[0]['id'] for row in overview.rows]);self.assertTrue(all(row[1]=='PENDING' for row in overview.rows));self.assertNotIn('未完成',overview.status.text())
        overview.page_filter.setText('2');self.assertEqual(overview.rows,[]);overview.page_filter.setText('invalid');self.assertIn('頁次',overview.status.text())

    def test_unapplied_form_survives_selection_and_close_cancel_and_save_refuses_loss(self):
        from PySide6.QtWidgets import QMessageBox
        w,d=self.ready();ids=[s['id'] for s in d.session.payload['slots']];d.select([ids[0]]);d.value.setText('姓名：Pending Example');d.coords[0].setValue(7)
        d.select([ids[1]]);d.select([ids[0]]);self.assertEqual(d.value.text(),'姓名：Pending Example');self.assertEqual(d.coords[0].value(),7)
        with self.assertRaisesRegex(ValueError,'未套用屬性'):d.save_or_raise()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Cancel):d.reject()
        self.assertTrue(d.isVisible());self.assertEqual(d.value.text(),'姓名：Pending Example')
        d.apply_properties();d.save_or_raise();facts=d.session.store.facts(d.session.base['id']);self.assertEqual(next(o['text'] for o in facts['observations'] if o['slot_id']==ids[0]),'姓名：Pending Example');self.assertIsNone(facts['confirmation'])

    def test_canvas_noise_entry_reuses_exact_facts_context_beyond_first_page(self):
        import json
        from template_ai.training_quality_dialog import TrainingQualityDialog
        w,d=self.ready();o=d.session.observations[0];d.select([o['slot_id']])
        for i in range(201):w.library.db.execute('INSERT INTO artworks VALUES(?,?,?,?,?)',('000-context-'+str(i).zfill(4),d.session.base['source_id'],'Synthetic context',1,json.dumps(d.session.payload)))
        w.library.db.commit();captured=[]
        def inspect(dialog):
            p=dialog.facts_panel;captured.append((p.loaded['id'],[p.loaded['observations'][i]['id'] for i in p.indices()],p.offset));return 0
        with patch.object(TrainingQualityDialog,'exec',inspect):d.noise_context()
        self.assertEqual(captured[0][0],d.session.base['id']);self.assertEqual(captured[0][1],[o['id']]);self.assertGreaterEqual(captured[0][2],200);self.assertEqual(self.path.read_bytes(),self.original_bytes)
