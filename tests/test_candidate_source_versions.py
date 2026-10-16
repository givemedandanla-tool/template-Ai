"""Real source SHA proof and mutable catalog changes cannot reuse old approval labels."""
import copy,json,unittest
from pathlib import Path
import test_candidate_risk as fixture
from training_fixture import source_work
from template_ai.candidate_risk import bind_source,verify_original_source
from template_ai.layout_recovery import LayoutRecovery,encode_candidate
from template_ai.layout import generate
from template_ai.training_store import digest

class CandidateSourceVersionTests(unittest.TestCase):
    setUp=fixture.CandidateRiskTests.setUp
    people=fixture.CandidateRiskTests.people
    candidate=fixture.CandidateRiskTests.candidate
    def source_candidate(self):
        source,work=source_work(self.library,self.root,'authored-layout-source.svg');self.template.source_id=source['id'];self.template.source_work_id=work['id'];self.template.source_work_revision=work['revision'];self.library.publish(self.template);candidate=self.candidate();return candidate,self.library.source(source['id'])
    def test_missing_actual_source_proof_is_unknown_and_real_sha_proof_turns_current_manual_template_safe(self):
        candidate,source=self.source_candidate();self.assertFalse(candidate.formal_eligible);bind_source(candidate,self.library,require_registered=True);self.assertFalse(candidate.formal_eligible);self.assertEqual(candidate.risk['state'],'EVIDENCE_REQUIRED');verify_original_source(candidate,self.library);bind_source(candidate,self.library,require_registered=True);self.assertTrue(candidate.formal_eligible);self.assertEqual(candidate.risk_context['original_source_proof']['hash'],source['hash'])
    def test_actual_source_bytes_changed_after_check_invalidate_current_label_without_an_accept_risk_bypass(self):
        candidate,source=self.source_candidate();verify_original_source(candidate,self.library);bind_source(candidate,self.library,require_registered=True);self.assertTrue(candidate.formal_eligible);path=Path(source['current_path']);path.write_bytes(path.read_bytes()+b'\n');candidate.risk_context['accept_risk']=True;candidate.score=1e9;self.assertFalse(candidate.formal_eligible);self.assertEqual(candidate.risk['state'],'EVIDENCE_REQUIRED');bind_source(candidate,self.library,require_registered=True);self.assertFalse(candidate.risk['known_hard_conditions_passed'])
    def test_changed_catalog_version_does_not_silently_refresh_old_pin(self):
        candidate,source=self.source_candidate();verify_original_source(candidate,self.library);bind_source(candidate,self.library,require_registered=True);before=copy.deepcopy(candidate.risk_context['source_template_pin']);changed=candidate.template.to_dict();changed['name']='Changed catalog version'
        self.library.db.execute('UPDATE templates SET payload=? WHERE id=?',(json.dumps(changed),candidate.template.id));self.library.db.commit();bind_source(candidate,self.library,require_registered=True);self.assertEqual(candidate.risk_context['source_template_pin'],before);self.assertFalse(candidate.formal_eligible)
    def test_legal_transient_geometry_is_restored_against_exact_base_without_overwriting_catalog(self):
        candidate,source=self.source_candidate();verify_original_source(candidate,self.library);bind_source(candidate,self.library,require_registered=True);local=copy.deepcopy(candidate.template);local.slots[0].rect.x+=1;edited=generate(local,self.people(),[],{},7);edited.risk_context['source_template_pin']=copy.deepcopy(candidate.risk_context['source_template_pin']);edited.risk_context['original_source_proof']=copy.deepcopy(candidate.risk_context['original_source_proof']);edited.risk_context['manual_edit_receipt']=dict(scope='ONLY_THIS_CANDIDATE_SIZE',before_digest=digest(candidate.template.to_dict()));bind_source(edited,self.library,require_registered=True);self.assertTrue(edited.formal_eligible);rows=LayoutRecovery(self.library.root).validate(self.library,dict(rows=[dict(template_id=edited.template.id,candidate=encode_candidate(edited))]));self.assertIsNotNone(rows[0]['candidate']);self.assertEqual(rows[0]['candidate'].template.slots[0].rect.x,local.slots[0].rect.x);self.assertEqual(self.library.object_snapshot('TEMPLATE',local.id)['payload'],candidate.template.to_dict())
