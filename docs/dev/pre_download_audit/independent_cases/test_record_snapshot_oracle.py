"""Real SQLite interleavings, authored metadata, no mocked query results."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.runtime_queue import RuntimeQueue
from template_ai.customer_candidates import CustomerCandidates
from template_ai.customers import CustomerStore
from template_ai.batch_import import BatchStore
from template_ai.training_pipeline import LIVE_OWNERS


class RecordSnapshotOracleTests(unittest.TestCase):
    def interleaving(self, kind, operation):
        with tempfile.TemporaryDirectory() as temp:
            reader = Library(Path(temp) / 'library')
            writer = Library(reader.root)
            token = 'audit-snapshot-owner'
            LIVE_OWNERS.add(token)
            try:
                identity = 'audit-record-one'
                body = {'id': identity, 'revision': 1, 'state': 'WAITING', 'count': 1,
                        'consent_session': 'authored-audit-session',
                        'consent_owner': {'pid': os.getpid(), 'token': token}}
                if kind == 'training':
                    service = TrainingStore(reader)
                    table = 'training_records'
                    reader.db.execute('INSERT INTO training_records VALUES(?,?,?,?)',
                                      ('AUDIT_AUTHORED', identity, 1, json.dumps(body)))
                    collection = lambda: service.records('AUDIT_AUTHORED')
                    lookup = lambda: service.get('AUDIT_AUTHORED', identity)
                elif kind in ('queue_page', 'queue_eligible'):
                    service = RuntimeQueue(reader)
                    table = 'runtime_requests'
                    reader.db.execute('INSERT INTO runtime_requests(id,revision,payload) VALUES(?,?,?)',
                                      (identity, 1, json.dumps(body)))
                    collection = service.page if kind == 'queue_page' else lambda: service.eligible('authored-audit-session')
                    lookup = lambda: service.get(identity)
                elif kind == 'customer_candidates':
                    service = CustomerCandidates(CustomerStore(reader))
                    table = 'customer_import_candidates'
                    body = {key: value for key, value in body.items()
                            if key not in ('id', 'revision', 'state')}
                    reader.db.execute('INSERT INTO customer_import_candidates VALUES(?,?,?,?)',
                                      (identity, 1, 'WAITING', json.dumps(body)))
                    collection = service.list
                    lookup = lambda: service.get(identity)
                else:
                    service = BatchStore(reader)
                    table = 'import_batches'
                    reader.db.execute('INSERT INTO import_batches VALUES(?,?,?)',
                                      (identity, 1, json.dumps(body)))
                    collection = service.list
                    lookup = lambda: service.get(identity)
                reader.db.commit()
                expected = lookup()
                changed = []
                update = dict(body, count=99)
                if kind != 'customer_candidates':
                    update['revision'] = 2

                def interleave(cursor, row):
                    names = [column[0] for column in cursor.description]
                    if names and names[0] == 'id' and not changed:
                        if operation == 'delete':
                            writer.db.execute('DELETE FROM '+table+' WHERE id=?', (identity,))
                        else:
                            writer.db.execute('UPDATE '+table+' SET revision=2,payload=? WHERE id=?',
                                              (json.dumps(update), identity))
                        writer.db.commit()
                        changed.append(True)
                    return row

                reader.db.row_factory = interleave
                try:
                    selected = collection()
                finally:
                    reader.db.row_factory = None
                self.assertEqual(changed, [True], 'The real second-connection write must occur')
                self.assertEqual(selected, [expected], 'Selected rows must retain their complete original snapshot')
                if operation == 'delete':
                    if kind in ('customer_candidates', 'batch'):
                        with self.assertRaises(ValueError):lookup()
                    else:self.assertIsNone(lookup())
                else:
                    latest = lookup()
                    self.assertEqual((latest['revision'], latest['count']), (2, 99))
            finally:
                LIVE_OWNERS.discard(token)
                writer.close()
                reader.close()

    def test_training_records_snapshot_survives_concurrent_delete(self):
        self.interleaving('training', 'delete')

    def test_training_records_snapshot_does_not_mix_concurrent_update(self):
        self.interleaving('training', 'update')

    def test_queue_page_snapshot_survives_concurrent_delete(self):
        self.interleaving('queue_page', 'delete')

    def test_queue_page_snapshot_does_not_mix_concurrent_update(self):
        self.interleaving('queue_page', 'update')

    def test_eligible_queue_snapshot_survives_concurrent_delete(self):
        self.interleaving('queue_eligible', 'delete')

    def test_eligible_queue_snapshot_does_not_mix_concurrent_update(self):
        self.interleaving('queue_eligible', 'update')

    def test_customer_candidates_snapshot_survives_concurrent_delete(self):
        self.interleaving('customer_candidates', 'delete')

    def test_customer_candidates_snapshot_does_not_mix_concurrent_update(self):
        self.interleaving('customer_candidates', 'update')

    def test_import_batches_snapshot_survives_concurrent_delete(self):
        self.interleaving('batch', 'delete')

    def test_import_batches_snapshot_does_not_mix_concurrent_update(self):
        self.interleaving('batch', 'update')

    def test_import_batch_list_preserves_revision_integrity_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            library = Library(Path(temp)/'library')
            try:
                service = BatchStore(library)
                library.db.execute('INSERT INTO import_batches VALUES(?,?,?)',
                                   ('audit-bad-revision', 2, json.dumps({'id':'audit-bad-revision','revision':1})))
                library.db.commit()
                with self.assertRaisesRegex(ValueError, 'revision'):
                    service.list()
            finally:library.close()

    def test_write_readback_remains_inside_real_sqlite_write_transaction(self):
        with tempfile.TemporaryDirectory() as temp:
            reader = Library(Path(temp)/'library')
            writer = Library(reader.root)
            try:
                service = TrainingStore(reader)
                writer.db.execute('PRAGMA busy_timeout=50')
                attempts = []
                def interleave(cursor, row):
                    if cursor.description[0][0] == 'revision' and not attempts:
                        try:
                            writer.db.execute('DELETE FROM training_records WHERE id=?', ('audit-write-readback',))
                            writer.db.commit()
                        except sqlite3.OperationalError as error:
                            self.assertIn('locked',str(error));writer.db.rollback();attempts.append('WRITE_LOCKED')
                        else:attempts.append('UNEXPECTED_WRITE')
                    return row
                reader.db.row_factory = interleave
                try:
                    with service.transaction():
                        written = service._write('AUDIT_AUTHORED','audit-write-readback',{'count':1},0,'audit_created')
                finally:reader.db.row_factory = None
                self.assertEqual(attempts,['WRITE_LOCKED'])
                self.assertEqual(written['count'],1)
                self.assertEqual(service.get('AUDIT_AUTHORED','audit-write-readback'),written)
            finally:
                writer.close();reader.close()
