"""A pending external goal cannot close itself or invalidate a clean other scope."""
from copy import deepcopy
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from dev_common import contract_digest
from dev_governance import verify_acceptance


class IndependentScopeEvidenceTests(unittest.TestCase):
    def fixture(self):
        identity='test_subject.Subject.test_behavior'
        row=dict(id='INDEPENDENT-A',kind='topic',scope='Independent verified software',parents=[],acceptance=[dict(id='A-1',expected='Actual behavior',tests=[identity])])
        run=dict(status='FAIL',software_execution_status='PASS',test_count=1,planned_test_count=1,passed=1,not_completed_test_count=0,unhandled_runtime_errors=0,capture_exit_code=0,source_unchanged=True)
        results={identity:dict(status='PASS',seconds=.1)};claims=[dict(requirement_id=row['id'],acceptance_id='A-1',status='PASS',contract_sha256=contract_digest(row))]
        return row,run,results,claims

    def test_complete_independent_scope_does_not_change_pending_overall_goal(self):
        row,run,results,claims=self.fixture();before=deepcopy(run);verify_acceptance(row,run,results,claims);self.assertEqual(run,before);self.assertEqual(run['status'],'FAIL')
        external=dict(row,id='EXTERNAL-B',scope='Required real hardware',acceptance=[dict(id='B-1',expected='Actual reference hardware result',tests=[])])
        external_claim=[dict(requirement_id='EXTERNAL-B',acceptance_id='B-1',status='PASS',contract_sha256=contract_digest(external))]
        with self.assertRaisesRegex(ValueError,'逐項 PASS'):verify_acceptance(external,run,results,external_claim)

    def test_any_failed_skipped_incomplete_or_unhealthy_execution_blocks_scope(self):
        for key,value in [('software_execution_status','FAIL'),('test_count',0),('planned_test_count',2),('passed',0),('not_completed_test_count',1),('unhandled_runtime_errors',1),('capture_exit_code',1),('source_unchanged',False),('capture_exit_code',False)]:
            with self.subTest(key=key,value=value):
                row,run,results,claims=self.fixture();run[key]=value
                with self.assertRaises(ValueError):verify_acceptance(row,run,results,claims)
        for status in ['FAIL','ERROR','SKIP','EXPECTED_FAILURE']:
            row,run,results,claims=self.fixture();next(iter(results.values()))['status']=status
            with self.assertRaises(ValueError):verify_acceptance(row,run,results,claims)

    def test_missing_duplicate_stale_or_nonpass_clause_claims_cannot_complete_scope(self):
        for change in ['missing','duplicate','stale','nonpass']:
            with self.subTest(change=change):
                row,run,results,claims=self.fixture()
                if change=='missing':claims=[]
                elif change=='duplicate':claims*=2
                elif change=='stale':claims[0]['contract_sha256']='old'
                else:claims[0]['status']='NOT_VERIFIED'
                with self.assertRaises(ValueError):verify_acceptance(row,run,results,claims)
