"""Check exact active-cursor list projections with real concurrent SQLite writers."""
import json,tempfile,unittest
from pathlib import Path
from template_ai.storage import Library
from template_ai.major_review_commands import execute
from template_ai.training_store import TrainingStore

class MajorCursorProbe(unittest.TestCase):
 def check(self,command,operation):
  with tempfile.TemporaryDirectory() as temp:
   reader=Library(Path(temp)/'library');TrainingStore(reader);writer=Library(reader.root)
   try:
    body=dict(state='OPEN',plan=dict(mode='SOURCE_EVIDENCE',category='AUDIT'),affected_works=['synthetic-work'],affected_templates=[],operation='MAJOR_SOURCE_RECHECK',scope=dict(case_id='synthetic-case',work_ids=['synthetic-work']),phase='READY',items=[dict(id='synthetic-source')]);kind='QUALITY_MAJOR_RECHECK' if command=='CASES' else 'AUTO_JOB';identity='synthetic-audit-record'
    reader.db.execute('INSERT INTO training_records VALUES(?,?,?,?)',(kind,identity,1,json.dumps(body)));reader.db.commit();expected=execute(reader,command,dict(case_id='synthetic-case'));changed=[]
    def interleave(cursor,row):
     names=[c[0] for c in cursor.description]
     if names and names[0]=='id' and not changed:
      if operation=='delete':writer.db.execute('DELETE FROM training_records WHERE id=?',(identity,))
      else:writer.db.execute('UPDATE training_records SET revision=2,payload=? WHERE id=?',(json.dumps(dict(body,state='UPDATED',phase='CANCELLED')),identity))
      writer.db.commit();changed.append(True)
     return row
    reader.db.row_factory=interleave
    try:actual=execute(reader,command,dict(case_id='synthetic-case'))
    finally:reader.db.row_factory=None
    self.assertEqual(changed,[True]);self.assertEqual(actual,expected)
   finally:writer.close();reader.close()
 def test_cases_delete(self):self.check('CASES','delete')
 def test_cases_update(self):self.check('CASES','update')
 def test_jobs_delete(self):self.check('JOBS','delete')
 def test_jobs_update(self):self.check('JOBS','update')

if __name__=='__main__':unittest.main(verbosity=2)
