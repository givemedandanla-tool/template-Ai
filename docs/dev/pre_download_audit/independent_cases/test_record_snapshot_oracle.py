"""Real SQLite interleaving: selected metadata must keep its read snapshot."""
from pathlib import Path
import tempfile
import unittest

from template_ai.storage import Library
from template_ai.training_store import TrainingStore


class RecordSnapshotOracleTests(unittest.TestCase):
    def test_selected_record_survives_concurrent_delete_as_a_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            reader = Library(Path(temp) / 'library')
            writer = Library(reader.root)
            try:
                reader.db.execute('PRAGMA journal_mode=WAL')
                store = TrainingStore(reader)
                with store.transaction():
                    expected = store._write('AUDIT_AUTHORED', 'audit-record-one',
                                            {'state': 'AUTHORED', 'count': 1}, 0, 'audit_created')
                deleted = []

                def interleave(cursor, row):
                    names = [column[0] for column in cursor.description]
                    if names and names[0] == 'id' and not deleted:
                        writer.db.execute('DELETE FROM training_records WHERE kind=? AND id=?',
                                          ('AUDIT_AUTHORED', 'audit-record-one'))
                        writer.db.commit()
                        deleted.append(True)
                    return row

                reader.db.row_factory = interleave
                try:
                    selected = store.records('AUDIT_AUTHORED')
                finally:
                    reader.db.row_factory = None
                self.assertEqual(deleted, [True], 'The real second-connection deletion must occur')
                self.assertEqual(selected, [expected])
                self.assertIsNone(store.get('AUDIT_AUTHORED', 'audit-record-one'))
            finally:
                writer.close()
                reader.close()
