"""UI043：真實來源、人工事實、客戶候選與 SQLite 原子入庫。"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from template_ai.customer_candidates import CustomerCandidates
from template_ai.customer_candidates_dialog import CustomerCandidatesDialog
from template_ai.customers import CustomerStore
from template_ai.gui import MainWindow
from template_ai.input_graph import InputGraph
from template_ai.model import Slot, Rect, learn_from_labels
from template_ai.storage import Library
from training_fixture import source_work, observations

APP = QApplication.instance() or QApplication([])


class CustomerCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = Library(self.root / 'library')
        self.store = CustomerStore(self.library)
        self.candidates = CustomerCandidates(self.store)
        self.source, self.work, self.template = self.make_source('00001.svg')

    def tearDown(self):
        self.library.close()
        self.temp.cleanup()

    def make_source(self, filename):
        source, work = source_work(self.library, self.root, filename)
        facts = self.candidates.training.save_facts(work['id'], observations(work), 0, work['revision'])
        self.candidates.training.confirm_facts(work['id'], [o['id'] for o in facts['observations']],
            facts['revision'], facts['pins'], self.candidates.training.source_proof(work['id']), 'SYNTHETIC_TEST', True)
        slots = [Slot(**{**s, 'rect': Rect(**s['rect'])}) for s in work['payload']['slots']]
        template = learn_from_labels('Synthetic source template', 90, 54, slots, source['id'],
                                     Rect(0, 0, 90, 54), {}, work['id'], work['revision'])
        self.library.save_template(template)
        return source, work, template

    def reviewed(self, candidate, code=None):
        return self.candidates.review(candidate['id'], candidate['revision'], candidate['graph'],
            code or candidate['code_candidate'], 'NEW_SEPARATE', 'SYNTHETIC_TEST',
            'Confirmed synthetic source identity and exact associations', approved=True)

    def commit(self, rows):
        return self.candidates.commit([{'id': r['id'], 'revision': r['revision']} for r in rows], True)

    def test_filename_full_rule_and_actual_facts_propose_only_without_master_writes(self):
        candidate = self.candidates.propose(self.source['id'])[0]
        self.assertEqual(candidate['code_candidate'], '00001')
        self.assertEqual(candidate['pins']['artwork_id'], self.work['id'])
        self.assertEqual(candidate['pins']['template_id'], self.template.id)
        self.assertEqual(InputGraph(candidate['graph']).label(candidate['graph']['people'][0]['id']), 'Alex Example')
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM customers').fetchone()[0], 0)
        self.assertEqual(candidate['state'], 'PENDING_REVIEW')
        self.assertEqual(self.candidates.propose(self.source['id'], r'(?P<code>[0-9]+)')[0]['code_candidate'], '00001')
        with self.assertRaisesRegex(ValueError, '任意正則'):
            self.candidates.propose(self.source['id'], r'(?P<code>(a+)+)')

    def test_review_and_commit_keep_leading_zeros_exact_versions_and_source_scope(self):
        candidate = self.reviewed(self.candidates.propose(self.source['id'])[0])
        with self.assertRaises(ValueError):
            self.candidates.commit([{'id': candidate['id'], 'revision': candidate['revision']}])
        result = self.commit([candidate])[0]
        customer = self.store.get(result['customer_id'])
        self.assertEqual(customer['code'], '00001')
        self.assertEqual(customer['styles'][0]['template_id'], self.template.id)
        row = self.library.db.execute('SELECT source_id,artwork_id,person_scope FROM customer_source_associations').fetchone()
        self.assertEqual(row[:2], (self.source['id'], self.work['id']))
        import json
        self.assertEqual(json.loads(row[2]), [p['id'] for p in customer['graph']['people']])
        self.assertNotIn('purchased', str(customer).lower())
        self.assertEqual(self.candidates.get(candidate['id'])['state'], 'COMMITTED')
        with self.assertRaises(ValueError):
            self.commit([candidate])
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM customers').fetchone()[0], 1)

    def test_pending_rejected_deferred_and_duplicate_selection_cannot_enter_master(self):
        candidate = self.candidates.propose(self.source['id'])[0]
        with self.assertRaises(ValueError):
            self.commit([candidate])
        deferred = self.candidates.review(candidate['id'], candidate['revision'], {}, '', 'DEFER',
            'SYNTHETIC_TEST', 'Identity remains unknown', approved=True)
        self.assertEqual(deferred['state'], 'DEFER')
        rejected = self.candidates.review(deferred['id'], deferred['revision'], {}, '', 'REJECT',
            'SYNTHETIC_TEST', 'Rejected source identity', approved=True)
        with self.assertRaises(ValueError):
            self.commit([rejected])
        with self.assertRaises(ValueError):
            self.commit([candidate, candidate])
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM customers').fetchone()[0], 0)

    def test_same_content_different_source_codes_keep_two_customers_and_independent_entities(self):
        other, _, _ = self.make_source('00999.svg')
        self.assertEqual(self.source['hash'], other['hash'])
        rows = [self.candidates.propose(s['id'])[0] for s in (self.source, other)]
        self.assertTrue(all('異名同內容' in ' '.join(r['issues']) for r in rows))
        output = self.commit([self.reviewed(r) for r in rows])
        left, right = [self.store.get(r['customer_id']) for r in output]
        self.assertNotEqual(left['id'], right['id'])
        self.assertNotEqual(left['graph']['people'][0]['id'], right['graph']['people'][0]['id'])
        self.assertEqual({left['code'], right['code']}, {'00001', '00999'})
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM customer_source_associations').fetchone()[0], 2)

    def test_code_collision_and_late_database_failure_roll_back_entire_batch(self):
        other, _, _ = self.make_source('00002.svg')
        rows = [self.reviewed(self.candidates.propose(s['id'])[0], 'same-code')
                for s in (self.source, other)]
        with self.assertRaisesRegex(ValueError, '同編號衝突'):
            self.commit(rows)
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM customers').fetchone()[0], 0)
        self.assertTrue(all(self.candidates.get(r['id'])['state'] == 'REVIEWED' for r in rows))
        rows = [self.reviewed(self.candidates.propose(s['id'])[0]) for s in (self.source, other)]
        old_event = self.library.event
        counter = []
        def fail_late(entity, action):
            old_event(entity, action)
            if action == 'customer_source_association_manually_confirmed':
                counter.append(entity)
                if len(counter) == 2:
                    raise OSError('simulated late disk failure')
        with patch.object(self.library, 'event', side_effect=fail_late):
            with self.assertRaises(OSError):
                self.commit(rows)
        for table in ('customers', 'customer_fields', 'customer_entities', 'customer_styles', 'customer_source_associations'):
            self.assertEqual(self.library.db.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
        self.assertEqual(self.library.db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_source_bytes_work_revision_facts_and_template_mutations_invalidate_review(self):
        candidate = self.reviewed(self.candidates.propose(self.source['id'])[0])
        path = Path(self.source['original_path'])
        old = path.read_bytes()
        path.write_bytes(old + b'\n')
        with self.assertRaises(ValueError):
            self.commit([candidate])
        path.write_bytes(old)
        facts = self.candidates.training.facts(self.work['id'])
        self.candidates.training.revoke_facts(self.work['id'], facts['revision'], 'Synthetic review revoked')
        with self.assertRaisesRegex(ValueError, '已更新'):
            self.commit([candidate])
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM customers').fetchone()[0], 0)

    def test_existing_customer_link_requires_explicit_identity_scope_and_cas_without_overwriting(self):
        first = self.reviewed(self.candidates.propose(self.source['id'])[0])
        customer = self.store.get(self.commit([first])[0]['customer_id'])
        other, _, second_template = self.make_source('00001_second.svg')
        row = self.candidates.propose(other['id'], r'(?P<code>[^_]+)_.+')[0]
        self.assertIn(customer['id'], row['existing_code_ids'])
        with self.assertRaisesRegex(ValueError, '人物範圍'):
            self.candidates.review(row['id'], row['revision'], row['graph'], customer['code'],
                'LINK_EXISTING', 'SYNTHETIC_TEST', 'Confirmed source association', customer, [], True)
        reviewed = self.candidates.review(row['id'], row['revision'], row['graph'], customer['code'],
            'LINK_EXISTING', 'SYNTHETIC_TEST', 'Confirmed source association', customer,
            [customer['graph']['people'][0]['id']], True)
        self.commit([reviewed])
        updated = self.store.get(customer['id'])
        self.assertEqual(updated['fields'], customer['fields'])
        self.assertEqual(updated['revision'], customer['revision'] + 1)
        self.assertEqual({s['template_id'] for s in updated['styles']}, {self.template.id, second_template.id})

    def test_actual_qt_background_proposal_and_cancelled_batch_do_not_create_customer(self):
        window = MainWindow(self.library.root)
        try:
            dialog = CustomerCandidatesDialog(window)
            dialog.propose()
            for _ in range(1000):
                APP.processEvents()
                if not dialog.running:
                    break
                QTest.qWait(10)
            self.assertFalse(dialog.running, 'background candidate scan did not finish')
            self.assertEqual(len(dialog.rows), 1)
            self.assertEqual(dialog.table.item(0, 0).checkState(), Qt.Unchecked)
            dialog.table.item(0, 0).setCheckState(Qt.Checked)
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
                dialog.commit()
            self.assertEqual(self.library.db.execute('SELECT count(*) FROM customers').fetchone()[0], 0)
            dialog.close()
        finally:
            window.library.close()
            window.deleteLater()
