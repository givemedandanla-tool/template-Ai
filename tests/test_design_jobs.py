from pathlib import Path
import tempfile
import unittest
from template_ai.storage import Library
from template_ai.design_jobs import DesignJobs,run_design_job
from template_ai.training_pipeline import LIVE_OWNERS


class PersistentDesignJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'data';self.library=Library(self.root);self.addCleanup(self.library.close)
        self.jobs=DesignJobs(self.library)

    def create(self,count=18):
        return self.jobs.create('OWNED_DESCRIPTOR_BENCHMARK',dict(items=list(range(count)),origin='AUTHORED_SYNTHETIC'),
            'Authored workload',True)

    def test_pause_reopen_resume_commits_each_item_exactly_once(self):
        job=self.create();claimed=self.jobs.claim(job['id'],job['revision'])
        progress=[]
        paused=run_design_job(self.root,job['id'],claimed['owner']['token'],
            cancel=lambda:len(progress)>=7,progress=lambda item:progress.append(item))
        self.assertEqual(paused['phase'],'PAUSED');self.assertEqual(paused['next_index'],7)
        first=self.jobs.results(job['id'])
        reopened=Library(self.root)
        try:
            jobs=DesignJobs(reopened);current=jobs.current(job['id']);claimed=jobs.claim(job['id'],current['revision'])
            completed=run_design_job(self.root,job['id'],claimed['owner']['token'])
            self.assertEqual(completed['phase'],'COMPLETE');self.assertEqual(completed['next_index'],18)
            self.assertEqual(jobs.results(job['id'])[:7],first)
            self.assertEqual(jobs.store.count('DESIGN_JOB_ITEM'),18)
            self.assertNotIn('plan',jobs.store.get('DESIGN_JOB',job['id']))
            self.assertIn('AUTHORED_DESCRIPTOR',completed['summary']['scope'])
        finally:reopened.close()

    def test_live_worker_cannot_be_taken_over_but_interrupted_owner_is_recoverable(self):
        job=self.create();claimed=self.jobs.claim(job['id'],job['revision'])
        with self.assertRaises(ValueError):self.jobs.claim(job['id'],claimed['revision'])
        LIVE_OWNERS.discard(claimed['owner']['token'])
        self.assertEqual(self.jobs.state(job['id']),'INTERRUPTED')
        resumed=self.jobs.claim(job['id'],claimed['revision'])
        self.jobs.finish(job['id'],resumed['owner']['token'],'PAUSED')

    def test_late_duplicate_result_and_incomplete_completion_are_rejected(self):
        job=self.create();claimed=self.jobs.claim(job['id'],job['revision']);token=claimed['owner']['token']
        self.jobs.save_item(job['id'],token,0,dict(actual='owned'),.01)
        with self.assertRaises(ValueError):self.jobs.save_item(job['id'],token,0,dict(actual='late'),.01)
        with self.assertRaises(ValueError):self.jobs.finish(job['id'],token,'COMPLETE')
        self.jobs.finish(job['id'],token,'PAUSED')

    def test_plan_tampering_and_committed_evidence_tampering_are_rejected(self):
        job=self.create();claimed=self.jobs.claim(job['id'],job['revision']);token=claimed['owner']['token']
        self.jobs.save_item(job['id'],token,0,dict(actual='owned'),.01)
        self.library.db.execute("UPDATE training_records SET payload=json_set(payload,'$.result.actual','tampered') WHERE kind='DESIGN_JOB_ITEM'")
        self.library.db.commit()
        with self.assertRaises(ValueError):self.jobs.results(job['id'])
        self.jobs.finish(job['id'],token,'PAUSED')
        self.library.db.execute("UPDATE training_records SET payload=json_set(payload,'$.plan.items[0]',500) WHERE kind='DESIGN_JOB_PLAN'")
        self.library.db.commit()
        with self.assertRaises(ValueError):self.jobs.current(job['id'])
