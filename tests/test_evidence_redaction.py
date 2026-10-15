import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from public_evidence import public_audit

class RedactionTests(unittest.TestCase):
    def test_public_view_removes_nested_lease_values_without_mutating_private_job_or_results(self):
        original={'job':{'owner':{'pid':123,'token':'synthetic-local-lease-example'},'state':'COMPLETED','results':[{'owner':{'token':'another-synthetic-lease'},'output_id':'example-draft'}]},'tests_passed':347};before=copy.deepcopy(original);public=public_audit(original)
        self.assertEqual(original,before);self.assertNotIn('synthetic-local-lease-example',json.dumps(public));self.assertNotIn('another-synthetic-lease',json.dumps(public));self.assertNotIn('token',public['job']['owner']);self.assertTrue(public['job']['owner']['local_lease_identifier_omitted']);self.assertEqual(public['job']['results'][0]['output_id'],'example-draft');self.assertEqual(public['job']['state'],'COMPLETED');self.assertEqual(public['tests_passed'],347)
