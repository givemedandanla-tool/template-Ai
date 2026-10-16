"""Exact current size/format/dpi reviews on original batch and size workflow paths."""
import unittest
from pathlib import Path
import test_multi_size as fixture
from template_ai.output_batch import OutputBatch
from template_ai.digital_review import confirm
from template_ai.multi_size import size_key


class BatchFormatReviewTests(unittest.TestCase):
    setUp=fixture.MultiSizeTests.setUp
    requests=fixture.MultiSizeTests.requests
    def tearDown(self):
        if self.workflow._format_proofs:self.workflow._format_proofs.cleanup()
        fixture.MultiSizeTests.tearDown(self)
    def batch(self):
        batch=OutputBatch(self.workflow,self.workflow.plan(self.output,self.requests()));batch.configure({r['id']:dict(name=Path(r['path']).name,action='CREATE') for r in batch.items});return batch
    def review(self,format='PDF',dpi=150):
        key=size_key(90,54);proof=self.workflow.format_proof(key,format,dpi);candidate=self.workflow.revalidate(self.entries[0]);receipt=confirm(candidate,proof,'SYNTHETIC_SOURCE_AUTHOR','Authored exact selected size and actual format snapshot verified',True);self.workflow.set_format_review(key,format,dpi,receipt);return receipt
    def test_unreviewed_pdf_jpeg_are_blocked_while_png_and_marked_previews_complete(self):
        batch=self.batch();rows=batch.execute(approved=True,acknowledge_partial=True);self.assertEqual([r['status'] for r in rows],['BLOCKED','SUCCESS','BLOCKED','SUCCESS','SUCCESS','SUCCESS']);self.assertFalse(Path(rows[0]['path']).exists());self.assertFalse(Path(rows[2]['path']).exists())
    def test_only_exact_selected_format_review_releases_that_batch_row(self):
        self.review('PDF');batch=self.batch();rows=batch.execute(approved=True,acknowledge_partial=True);self.assertEqual([r['status'] for r in rows],['SUCCESS','SUCCESS','BLOCKED','SUCCESS','SUCCESS','SUCCESS']);self.assertTrue(Path(rows[0]['path']).is_file());self.assertFalse(Path(rows[2]['path']).exists())
    def test_dpi_change_cannot_reuse_other_sampling_review(self):
        self.review('PDF',150);batch=self.batch();rows=batch.execute(approved=True,acknowledge_partial=True,dpi=96);self.assertEqual(rows[0]['status'],'BLOCKED');self.assertEqual(rows[1]['status'],'SUCCESS')
    def test_direct_original_multisize_execution_uses_same_format_registry(self):
        self.review('PDF');self.review('JPG');plan=self.workflow.plan(self.output,self.requests());rows=self.workflow.execute(plan,True,True);self.assertEqual([r['status'] for r in rows],['SUCCESS']*6)
    def test_other_size_or_tampered_receipt_cannot_be_registered_as_current(self):
        receipt=self.review('PDF')
        with self.assertRaises(ValueError):self.workflow.set_format_review(size_key(100,60),'PDF',150,receipt)
        changed=dict(receipt,actor='Invented current actor')
        with self.assertRaises(ValueError):self.workflow.set_format_review(size_key(90,54),'PDF',150,changed)
        self.assertEqual(len(self.workflow.format_reviews),1)
    def test_changed_inputs_block_previously_reviewed_rows_without_creating_files(self):
        self.review('PDF');batch=self.batch();self.workflow.people[0]['name']=['Changed actual source value'];rows=batch.execute(approved=True,acknowledge_partial=True);self.assertTrue(all(r['status']=='BLOCKED' for r in rows));self.assertFalse(any(self.output.rglob('*.pdf')))

if __name__=='__main__':unittest.main()
