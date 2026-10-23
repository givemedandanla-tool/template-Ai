from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape
from template_ai.storage import Library
from template_ai.importer import import_file
from template_ai.model import Rect,Slot
from template_ai.semantic_learning import SemanticLearning
from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog
APP=QApplication.instance() or QApplication([])


class SemanticLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.service=SemanticLearning(self.library)
        self.train=self.work('train',[('title','資深雲端工程師'),('title','資深後端工程師'),('address','台中市西區公益路10號'),('address','台中市西區中正路20號')])
        self.validation=self.work('validation',[('title','資深前端工程師'),('address','台中市西區民生路30號')]);self.roles={self.train['id']:'TRAIN',self.validation['id']:'VALIDATION'}

    def work(self,name,rows):
        path=self.root/(name+'.svg');path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect width="90" height="54" fill="white"/>'+''.join(f'<text id="t{i}" x="2" y="{8+i*9}" font-size="3">{escape(value)}</text>' for i,(kind,value) in enumerate(rows))+'</svg>')
        source=self.library.add_source(path,import_file(path,self.library.assets));slots=[asdict(Slot(kind,'p1',Rect(2,4+i*9,70,4),index=i)) for i,(kind,value) in enumerate(rows)]
        work=self.library.create_artwork(source['id'],name,dict(crop=asdict(Rect(0,0,90,54)),work_width=90,work_height=54,slots=slots,visual_confirmed=True))
        observations=[dict(id='text'+str(i),slot_id=slot['id'],text=value,object_type='TEXT',classification='FIELD',region=slot['rect']) for i,(slot,(_,value)) in enumerate(zip(slots,rows))]
        facts=self.service.store.save_facts(work['id'],observations,0,work['revision']);self.service.store.confirm_facts(work['id'],[o['id'] for o in facts['observations']],facts['revision'],facts['pins'],self.service.store.source_proof(work['id']),'SYNTHETIC_REVIEWER',True)
        return work

    def candidate(self):return self.service.train(self.service.plan(self.roles),'SYNTHETIC_OPERATOR',True)

    def test_actual_source_confirmed_training_persists_parameters_heldout_denominators_and_draft_only(self):
        row=self.candidate();self.assertEqual(row['state'],'PENDING');self.assertGreater(row['parameter_count'],10);self.assertGreater(row['vocabulary_size'],10)
        self.assertEqual(row['metrics']['title']['total'],1);self.assertEqual(row['metrics']['title']['correct'],1);self.assertEqual(row['baseline_metrics']['title']['unknown'],1)
        self.assertIsNone(self.service.active()[0]);self.assertFalse(self.library.templates());self.assertEqual(self.service.store.count('SAMPLE'),0)
        other=Library(self.library.root)
        try:self.assertEqual(SemanticLearning(other).store.get('SEMANTIC_MODEL',row['id'])['weights_digest'],row['weights_digest'])
        finally:other.close()

    def test_independent_activation_cas_inference_and_source_change_auto_abstention(self):
        row=self.candidate()
        with self.assertRaises(ValueError):self.service.activate(row['id'],row['revision'],0,'REVIEWER','not authorized')
        pointer=self.service.activate(row['id'],row['revision'],0,'REVIEWER','Synthetic independent version approval',True)
        model,context=self.service.active();self.assertEqual(context['state'],'ACTIVE');self.assertEqual(model.predict('資深前端工程師')['semantic_type'],'title')
        current=self.service.store.get('SEMANTIC_MODEL',row['id'])
        with self.assertRaises(ValueError):self.service.activate(row['id'],current['revision'],0,'REVIEWER','Synthetic stale pointer',True)
        path=Path(self.library.source(self.train['source_id'])['current_path']);path.write_bytes(path.read_bytes()+b' ');model,context=self.service.active();self.assertIsNone(model);self.assertEqual(context['state'],'STALE')

    def test_same_source_and_same_literal_cannot_leak_into_validation(self):
        duplicate=self.work('literal-duplicate',[('title','資深雲端工程師'),('address','台中市西區公益路10號')])
        with self.assertRaisesRegex(ValueError,'字串'):self.service.plan({self.train['id']:'TRAIN',duplicate['id']:'VALIDATION'})
        payload=self.train['payload'];same=self.library.create_artwork(self.train['source_id'],'same-source',payload);facts=self.service.store.facts(self.train['id']);saved=self.service.store.save_facts(same['id'],facts['observations'],0,same['revision']);self.service.store.confirm_facts(same['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.service.store.source_proof(same['id']),'REVIEWER',True)
        with self.assertRaisesRegex(ValueError,'hash'):self.service.plan({self.train['id']:'TRAIN',same['id']:'VALIDATION'})

    def test_revoked_facts_and_changed_plan_block_training_without_reusing_geometry_rights(self):
        plan=self.service.plan(self.roles);facts=self.service.store.facts(self.train['id']);self.service.store.revoke_facts(self.train['id'],facts['revision'],'Synthetic revocation')
        with self.assertRaises(ValueError):self.service.train(plan,'OPERATOR',True)
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0)
        with self.assertRaises(ValueError):self.service.train(plan,'OPERATOR',False)

    def test_late_audit_failure_rolls_back_weights_and_activation_approval(self):
        plan=self.service.plan(self.roles)
        with patch.object(self.library,'event',side_effect=OSError('Synthetic audit failure')):
            with self.assertRaises(OSError):self.service.train(plan,'OPERATOR',True)
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0)
        row=self.candidate()
        with patch.object(self.library,'event',side_effect=OSError('Synthetic audit failure')):
            with self.assertRaises(OSError):self.service.activate(row['id'],row['revision'],0,'REVIEWER','Synthetic review',True)
        self.assertEqual(self.service.store.get('SEMANTIC_MODEL',row['id'])['state'],'PENDING');self.assertIsNone(self.service.store.get('SEMANTIC_ACTIVE','local-text'))

    def test_actual_qt_preview_train_activation_and_close_reopen_preserve_exact_version(self):
        from template_ai.gui import MainWindow
        from template_ai.semantic_learning_dialog import SemanticLearningDialog
        window=MainWindow(self.library.root)
        def close():window.input_timer.stop();window.font_manager.close();window.library.close();window.deleteLater()
        self.addCleanup(close);dialog=SemanticLearningDialog(window);self.addCleanup(dialog.deleteLater);dialog.show();APP.processEvents()
        for i,work in enumerate(dialog.rows):
            role=dialog.table.cellWidget(i,2);role.setCurrentIndex(role.findData(self.roles[work['id']]))
        dialog.preview();self.assertIsNotNone(dialog.plan)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):dialog.train()
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.train()
        self.assertEqual(self.service.store.count('SEMANTIC_MODEL'),1);self.assertIn('尚未啟用',dialog.status.text());self.assertIsNone(self.service.active()[0])
        with patch.object(QInputDialog,'getText',return_value=('Synthetic explicit approval',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.activate()
        self.assertIsNotNone(self.service.active()[0]);approved=self.service.store.get('SEMANTIC_MODEL',dialog.models.currentData());self.assertEqual(approved['state'],'APPROVED');self.assertEqual(self.service.store.get('SEMANTIC_ACTIVE','local-text')['model_revision'],approved['revision'])

    def test_approved_model_is_used_by_real_inkscape_pipeline_only_for_new_pending_source(self):
        from template_ai.automatic_training import AutomaticTraining,run_automatic
        from template_ai.training_pipeline import LIVE_OWNERS
        row=self.candidate();self.service.activate(row['id'],row['revision'],0,'REVIEWER','Synthetic approval',True)
        path=self.root/'new-unseen-source.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect id="paper" width="90" height="54" fill="white"/><text id="title" x="5" y="15" font-size="4">資深前端工程師</text></svg>');before=path.read_bytes()
        service=AutomaticTraining(self.library);job=service.create(service.preflight([path]),'OPERATOR',True);claimed=service.claim(job['id'],job['revision'],True)
        try:result=run_automatic(self.library.root,claimed['id'],claimed['owner']['token'])
        finally:LIVE_OWNERS.discard(claimed['owner']['token'])
        work=self.library.artworks(result['items'][0]['source_id'])[0];evidence=work['payload']['analysis_evidence'];self.assertEqual(evidence['semantic_model']['model_id'],row['id']);self.assertTrue(any(s['kind']=='title' for s in work['payload']['slots']))
        self.assertIsNone(self.service.store.facts(work['id'])['confirmation']);self.assertEqual(path.read_bytes(),before);self.assertFalse(self.library.templates())
