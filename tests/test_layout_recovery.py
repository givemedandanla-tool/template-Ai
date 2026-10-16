"""Actual authenticated files, restart, tampering, bounded scope and partial validity."""
import copy,json,unittest,os
from pathlib import Path
from unittest.mock import patch
import test_candidate_risk as fixture
from template_ai.layout_recovery import LayoutRecovery,encode_candidate,decode_candidate,TTL_SECONDS
from template_ai.training_store import digest
from template_ai.layout import generate

class LayoutRecoveryTests(unittest.TestCase):
    setUp=fixture.CandidateRiskTests.setUp
    people=fixture.CandidateRiskTests.people
    candidate=fixture.CandidateRiskTests.candidate
    def payload(self):
        c=self.candidate()
        return dict(state='CANCELLED',generation=7,people=self.people(),companies=[],logos={},size=[90,54],templates=[c.template.to_dict()],rows=[dict(template_id=c.template.id,state='CALCULATED_PENDING_ADOPTION',candidate=encode_candidate(c))])
    def test_real_encrypted_restart_preserves_exact_computed_candidate_without_plain_pii_or_auto_adoption(self):
        payload=self.payload();r=LayoutRecovery(self.library.root);receipt=r.save(payload,'synthetic-test-password');self.assertTrue(receipt['saved']);self.assertTrue(r.pending());blob=r.path.read_bytes();self.assertNotIn(b'Alex Example',blob);self.assertNotIn(b'qa@example.test',blob);restored=LayoutRecovery(self.library.root).load('synthetic-test-password');c=decode_candidate(restored['rows'][0]['candidate']);self.assertTrue(c.formal_eligible);self.assertEqual(c.risk['input_digest'],digest(c.risk_context['input_snapshot']));self.assertEqual(self.library.templates(),[])
    def test_wrong_password_ciphertext_tamper_and_exclusive_conflict_leave_business_data_untouched(self):
        r=LayoutRecovery(self.library.root);payload=self.payload();r.save(payload,'synthetic-test-password');before=r.path.read_bytes()
        with self.assertRaises(ValueError):r.load('incorrect-password')
        with self.assertRaises(FileExistsError):r.save(payload,'synthetic-test-password')
        self.assertEqual(r.path.read_bytes(),before);r.path.write_bytes(before[:-1]+bytes([before[-1]^1]))
        with self.assertRaises(ValueError):r.load('synthetic-test-password')
        self.assertEqual(self.library.templates(),[])
    def test_expiration_and_engine_change_purge_only_local_recovery(self):
        r=LayoutRecovery(self.library.root);payload=self.payload();r.save(payload,'synthetic-test-password');future=LayoutRecovery(self.library.root,clock=lambda:__import__('time').time()+TTL_SECONDS+5);self.assertFalse(future.pending());self.assertFalse(r.path.exists());r.save(payload,'synthetic-test-password')
        with patch('template_ai.layout_recovery.engine_pins',return_value={'changed':True}):
            with self.assertRaisesRegex(ValueError,'引擎'):r.load('synthetic-test-password')
        self.assertFalse(r.path.exists());self.assertEqual(self.library.templates(),[])
    def test_injected_disk_publish_failure_does_not_claim_saved_or_leave_partial_target(self):
        r=LayoutRecovery(self.library.root)
        with patch('template_ai.layout_recovery.publish_complete',side_effect=OSError('synthetic disk full')):
            with self.assertRaises(OSError):r.save(self.payload(),'synthetic-test-password')
        self.assertFalse(r.path.exists());self.assertEqual(list(r.root.iterdir()),[])
    def test_bounded_payload_normal_completion_and_symlink_rejected(self):
        r=LayoutRecovery(self.library.root);payload=self.payload();payload['state']='COMPLETED'
        with self.assertRaises(ValueError):r.save(payload,'synthetic-test-password')
        payload['state']='CANCELLED';payload['oversized']='x'*(4*1024*1024)
        with self.assertRaisesRegex(ValueError,'4MiB'):r.save(payload,'synthetic-test-password')
        r.root.mkdir();target=self.root/'unrelated';target.write_text('retain');r.path.symlink_to(target)
        with self.assertRaises(ValueError):r.pending()
        r.clear();self.assertEqual(target.read_text(),'retain')
    def test_restore_invalidates_only_changed_template_and_never_copies_old_safe_label(self):
        self.library.publish(self.template);first=self.library.templates(True)[0];second=copy.deepcopy(first);from template_ai.model import new_id;second.id=new_id();second.family_id=new_id();self.library.publish(second)
        a=generate(first,self.people(),[],{},7);b=generate(second,self.people(),[],{},7);payload=self.payload();payload['rows']=[dict(template_id=c.template.id,candidate=encode_candidate(c),state='CALCULATED_PENDING_ADOPTION') for c in (a,b)]
        changed=copy.deepcopy(second);changed.width_mm+=1
        with patch.object(self.library,'templates',return_value=[first,changed]):rows=LayoutRecovery(self.library.root).validate(self.library,payload)
        self.assertIsNotNone(rows[0]['candidate']);self.assertTrue(rows[0]['candidate'].formal_eligible);self.assertIsNone(rows[1]['candidate']);self.assertEqual(rows[1]['state'],'STALE_RECALCULATE')
