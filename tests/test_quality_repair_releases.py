"""Actual accepted runtime, immutable CAS, no unsafe fallback and encrypted restore."""
import unittest
from contextlib import closing
from unittest.mock import patch
import test_quality_gold_sets as fixtures
import test_quality_rechecks as recheck_fixture
from quality_acceptance_fixture import actual_positive_pair
from template_ai.quality_reports import QualityReports
from template_ai.quality_repair_releases import QualityRepairReleases,ACTIVE,EVENT,KEY
from template_ai.automatic_training import AutomaticTraining
from template_ai.runtime_queue import RuntimeQueue
from template_ai.runtime_worker import run_isolated
from template_ai.model import new_id
from test_runtime_execution import ALLOW


class QualityRepairReleaseTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp
    build=recheck_fixture.QualityRecheckTests.build
    critical=recheck_fixture.QualityRecheckTests.critical

    def accepted(self):
        fixture=actual_positive_pair(self);reports=QualityReports(self.library)
        report=reports.save(reports.plan(fixture['protocol']['id']),'Reviewer',True)
        self.decision=reports.decide(report['id'],'Reviewer','Authored lenient synthetic safety fixture only, not production quality',True)
        self.releases=QualityRepairReleases(self.library);return self.decision

    def install(self):
        self.accepted();plan=self.releases.plan(self.decision['id'],0,'INITIAL_BASELINE')
        return self.releases.confirm(plan,'Reviewer','Exact authored frozen runtime baseline, no native Illustrator certification',True)

    def path(self):
        path=self.root/'new-runtime-source.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect id="card" width="90" height="54" fill="white"/><text id="name" x="6" y="12" font-size="4">Name: Synthetic Runtime New</text><text id="phone" x="6" y="24" font-size="4">Phone: +1 202 555 0199</text></svg>');return path

    def test_actual_owned_fifo_new_source_uses_job_pinned_frozen_pipeline_after_pointer_change(self):
        first=self.install();path=self.path();before=path.read_bytes();auto=AutomaticTraining(self.library)
        report=auto.preflight([path]);job=auto.create(report,'Operator',True)
        rollback=self.releases.plan(self.decision['id'],1,'ROLLBACK',target_event_id=first['event']['id'])
        second=self.releases.confirm(rollback,'Reviewer','Revalidate same safe historical deployment to test version-pinned queued work',True)
        self.assertNotEqual(first['event']['id'],second['event']['id'])
        queue=RuntimeQueue(self.library);session=new_id();request=queue.enqueue('AUTO_JOB',job['id'],'Operator',session,True);claimed=queue.claim(request,session)
        result=run_isolated(self.library.root,'AUTO_JOB',claimed['id'],claimed['owner']['token'],admission=lambda:ALLOW);queue.finish(request['id'],claimed['owner']['token'],result)
        self.assertEqual(result['phase'],'COMPLETED_WITH_EXCEPTIONS');works=self.library.artworks(result['items'][0]['source_id']);self.assertTrue(works)
        evidence=works[0]['payload']['analysis_evidence']['quality_deployment']
        self.assertEqual(evidence['event_id'],first['event']['id']);self.assertEqual(evidence['pipeline_id'],self.decision['pipeline_id'])
        self.assertIsNone(self.store.facts(works[0]['id'])['confirmation']);self.assertEqual(path.read_bytes(),before)
        self.assertIsNone(self.store.get('SEMANTIC_ACTIVE','local-text'))
        self.assertEqual(self.store.get(ACTIVE,KEY)['event_id'],second['event']['id'])

    def test_changed_preflight_cas_and_late_pointer_audit_do_not_create_partial_activation(self):
        self.accepted();auto=AutomaticTraining(self.library);report=auto.preflight([self.path()]);plan=self.releases.plan(self.decision['id'],0,'INITIAL_BASELINE');event=self.library.event
        def fail(identity,action,*args,**kwargs):
            if action=='training_quality_runtime_pointer_cas_committed':raise OSError('Synthetic late pointer audit failure')
            return event(identity,action,*args,**kwargs)
        with patch.object(self.library,'event',side_effect=fail):
            with self.assertRaises(OSError):self.releases.confirm(plan,'Reviewer','No partial event or pointer',True)
        self.assertIsNone(self.store.get(ACTIVE,KEY));self.assertEqual(self.store.count(EVENT),0)
        self.releases.confirm(plan,'Reviewer','Explicit actual baseline',True)
        with self.assertRaises(ValueError):auto.create(report,'Operator',True)
        with self.assertRaises(ValueError):self.releases.confirm(plan,'Reviewer','Stale pointer preview',True)
        self.assertEqual(self.store.count(EVENT),1)

    def test_withdrawn_evidence_blocks_runtime_and_same_old_version_cannot_be_safe_rollback(self):
        installed=self.install();QualityReports(self.library).withdraw(self.decision['id'],'Reviewer','Synthetic quality evidence withdrawn',True)
        with self.assertRaises(ValueError):self.releases.pin()
        with self.assertRaises(ValueError):AutomaticTraining(self.library).preflight([self.path()])
        with self.assertRaises(ValueError):self.releases.plan(self.decision['id'],1,'ROLLBACK',target_event_id=installed['event']['id'])
        self.assertEqual(self.store.get(ACTIVE,KEY)['revision'],1)

    def test_actual_critical_recheck_quarantines_same_parser_and_no_old_fallback_is_assumed_safe(self):
        installed=self.install();plan=self.critical();self.rechecks.confirm(plan,'Reviewer','Actual separate source revealed a critical parser failure',True)
        with self.assertRaises(ValueError):self.releases.pin()
        with self.assertRaises(ValueError):self.releases.plan(self.decision['id'],1,'ROLLBACK',target_event_id=installed['event']['id'])
        self.assertEqual(self.store.get(ACTIVE,KEY)['event_id'],installed['event']['id'])

    def test_actual_encrypted_restore_marks_active_runtime_for_explicit_revalidation(self):
        from template_ai import relational_backup as backup
        from template_ai.storage import Library
        from template_ai.training_store import TrainingStore
        installed=self.install();archive=self.root/'qualified-runtime.tabi';preview=backup.plan_backup(self.library,include_sources=True)
        self.assertTrue(preview['complete'],preview.get('notes'));backup.create_backup(self.library,archive,'synthetic qualified runtime backup password',preview,True)
        restored=backup.restore_bundle(archive,self.root/'restored-runtime','synthetic qualified runtime backup password',True)
        with closing(Library(restored['library_root'])) as library:
            pointer=TrainingStore(library).get(ACTIVE,KEY);self.assertEqual(pointer['restore_state'],'EXPLICIT_DEPLOYMENT_REVALIDATION_REQUIRED')
            with self.assertRaises(ValueError):QualityRepairReleases(library).pin()
