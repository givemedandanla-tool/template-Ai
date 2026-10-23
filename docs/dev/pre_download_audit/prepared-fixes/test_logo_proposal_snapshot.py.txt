"""Actual filtered Logo proposal page retains selected metadata across SQLite writes."""
from pathlib import Path
import json,tempfile,unittest
from template_ai.storage import Library
from template_ai.logo_store import LogoStore

class LogoProposalSnapshotTests(unittest.TestCase):
    def check_snapshot(self,operation):
        with tempfile.TemporaryDirectory() as temp:
            reader=Library(Path(temp)/'data');store=LogoStore(reader);writer=Library(reader.root)
            try:
                identity='authored-logo-proposal';body=dict(width_mm=90.,height_mm=54.,origin='MANUAL',asset=dict(company='Authored Company'))
                reader.db.execute('INSERT INTO logo_proposals VALUES(?,?,?,?)',(identity,1,'PENDING',json.dumps(body)));reader.db.commit()
                expected=[dict(id=identity,revision=1,state='PENDING',**body)];self.assertEqual(store.proposals(90.,54.),expected);changed=[]
                def interleave(cursor,row):
                    if cursor.description[0][0]=='id' and not changed:
                        if operation=='delete':writer.db.execute('DELETE FROM logo_proposals WHERE id=?',(identity,))
                        else:writer.db.execute('UPDATE logo_proposals SET revision=2,payload=? WHERE id=?',(json.dumps(dict(body,width_mm=100.)),identity))
                        writer.db.commit();changed.append(True)
                    return row
                reader.db.row_factory=interleave
                try:actual=store.proposals(90.,54.)
                finally:reader.db.row_factory=None
                self.assertEqual(changed,[True]);self.assertEqual(actual,expected)
                self.assertEqual(store.proposals(90.,54.),[])
                if operation=='update':self.assertEqual(store.proposal(identity)['width_mm'],100.)
            finally:writer.close();reader.close()

    def test_selected_page_survives_concurrent_delete(self):self.check_snapshot('delete')
    def test_selected_size_page_never_includes_concurrently_resized_proposal(self):self.check_snapshot('update')
