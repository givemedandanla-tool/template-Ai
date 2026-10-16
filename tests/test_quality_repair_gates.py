"""Actual frozen faulty/repaired parsers and mandatory ordered repair gates."""
import shutil,unittest
from pathlib import Path
from unittest.mock import patch
import test_quality_gold_sets as gold_fixture
from quality_acceptance_fixture import actual_positive_pair
from template_ai import quality_pipeline
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_protocol import QualityProtocols
from template_ai.quality_jobs import EvaluationJobs,run_evaluation
from template_ai.quality_repairs import QualityRepairs
from template_ai.quality_diagnostics import QualityDiagnostics
from template_ai.quality_reports import QualityReports
from template_ai.quality_repair_gates import QualityRepairGates,STAGES
from template_ai.quality_sets import QualitySets
from test_noise_authoring import confirmed
from training_fixture import source_work


class QualityRepairGateTests(unittest.TestCase):
    setUp=gold_fixture.QualityGoldSetTests.setUp

    def prepare(self,full_chain=False):
        fixture=actual_positive_pair(self,execute=False);self.fixture=fixture;scope=fixture['protocol']['scope']
        package=Path(quality_pipeline.__file__).parent;faulty=self.root/'authored-faulty-parser';faulty.mkdir()
        for file in package.glob('*.py'):shutil.copyfile(file,faulty/file.name)
        parser=faulty/'source_analysis.py';parser.write_text(parser.read_text()+"\n_actual_analyse_source=analyse_source\ndef analyse_source(source,assets,semantic_model=None,model_context=None):\n    if source['hash']=="+repr(fixture['sources'][0]['hash'])+":return []\n    return _actual_analyse_source(source,assets,semantic_model,model_context)\n")
        config=self.store.get('QUALITY_PIPELINE',scope['pipelines']['BASELINE']['id'])['manifest']['mapping_configuration']
        good_id=scope['pipelines']['CANDIDATE']['id']
        if full_chain:
            from quality_repair_acceptance_fixture import group
            self.controls=group(self,'controls',multi=True);self.independent=group(self,'independent',portrait=True)
            config=dict(config,customer_ids=config['customer_ids']+self.controls['customer_ids']+self.independent['customer_ids'])
            good_id=QualityPipelines(self.library).freeze('Actual complete-scope repaired parser',None,'Reviewer',True,mapping_config=config,rule_versions=[])['id']
        with patch.object(quality_pipeline,'__file__',str(faulty/'quality_pipeline.py')):
            bad=QualityPipelines(self.library).freeze('Authored reproducible omitted-source defect',None,'Synthetic author',True,mapping_config=config,rule_versions=[])
        protocols=QualityProtocols(self.library);origin=protocols.freeze(protocols.plan('Actual faulty source run',scope['dataset_id'],scope['policy_id'],dict(BASELINE=bad['id'],CANDIDATE=bad['id']),'Run actual controlled faulty parser, no invented predictions'),'Reviewer',True)
        service=EvaluationJobs(self.library);jobs=service.create_pair(origin['id'],'Reviewer',True);job=jobs['BASELINE'];claimed=service.claim(job['id'],job['revision'],True);done=run_evaluation(self.library.root,job['id'],claimed['owner_token'])
        self.assertTrue(self.store.get('QUALITY_EVAL_RESULT',done['result_id'])['critical_errors'])
        protocols.expose(origin['id'],'Reviewer','Inspect actual missing source work',True)
        row=QualityDiagnostics(self.library).page(origin['id'],'BASELINE',severity='CRITICAL')['rows'][0]
        repairs=QualityRepairs(self.library);plan=repairs.plan_quality_issue(origin['id'],'BASELINE',row)
        issue=repairs.create_quality_issue(plan,'Reviewer','Actual frozen parser loses one authored source',True)
        root=repairs.root_plan(issue['id'],'WORK_SEGMENTATION','Conditional parser branch returns no works for this source','Actual original, whole-source gold and conditional source branch reviewed',True,True)
        self.review=repairs.confirm_root(root,'Reviewer',True);self.gates=QualityRepairGates(self.library)
        candidate_plan=self.gates.candidate_plan(self.review['id'],good_id)
        self.candidate=self.gates.register(candidate_plan,'Reviewer','Actual normal frozen parser removes the conditional source loss',True)
        self.policy_id=scope['policy_id'];self.dataset_id=scope['dataset_id']

    def run_stage(self,plan):
        protocol=QualityProtocols(self.library).freeze(plan,'Reviewer',True)
        service=EvaluationJobs(self.library)
        for job in service.create_pair(protocol['id'],'Reviewer',True).values():
            claimed=service.claim(job['id'],job['revision'],True);done=run_evaluation(self.library.root,job['id'],claimed['owner_token']);self.assertEqual(done['phase'],'COMPLETED')
        reports=QualityReports(self.library);report=reports.save(reports.plan(protocol['id']),'Reviewer',True)
        result=self.gates.plan(report['id']);return self.gates.confirm(result,'Reviewer',True)

    def test_actual_root_is_fixed_without_independent_pass_and_cannot_skip_controls(self):
        self.prepare()
        with self.assertRaises(ValueError):self.gates.protocol_plan(self.candidate['id'],STAGES[1],self.dataset_id,self.policy_id,'Cannot plan before root receipt')
        gate=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[0],self.dataset_id,self.policy_id,'Actual bad parser versus repaired parser on exposed original'))
        self.assertTrue(gate['plan']['passed'],gate['plan']['blockers']);self.assertFalse(gate['plan']['independence_claim']);self.assertFalse(gate['plan']['production_active'])
        self.assertEqual(self.gates.checked_gate(gate['id']),gate)
        with self.assertRaises(ValueError):self.gates.protocol_plan(self.candidate['id'],STAGES[2],self.dataset_id,self.policy_id,'Cannot skip unaffected controls',gate['id'])
        with self.assertRaises(ValueError):self.gates.protocol_plan(self.candidate['id'],STAGES[1],self.dataset_id,self.policy_id,'Cannot reuse exposed root groups as unaffected controls',gate['id'])

    def test_sparse_unaffected_controls_save_failed_receipt_and_block_new_acceptance(self):
        self.prepare();root=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[0],self.dataset_id,self.policy_id,'Actual root reproduction first'))
        source,work=source_work(self.library,self.root,'unaffected-control.svg');confirmed(self.store,work)
        gold=self.gold.confirm(gold_fixture.QualityGoldSetTests.plan(self,work),'Reviewer',True)
        sets=QualitySets(self.library);dataset=sets.create(sets.plan('Sparse unrelated control',[gold['id']],True,True,'Separate source and no related family'),'Reviewer',True)
        controls=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[1],dataset['id'],self.policy_id,'Run real sparse controls to prove missing coverage blocks',root['id']))
        self.assertFalse(controls['plan']['passed']);self.assertTrue(any('對照' in error for error in controls['plan']['blockers']))
        with self.assertRaises(ValueError):self.gates.checked_gate(controls['id'])
        with self.assertRaises(ValueError):self.gates.protocol_plan(self.candidate['id'],STAGES[2],dataset['id'],self.policy_id,'No acceptance after failed controls',controls['id'])
        self.assertIsNone(self.store.get('QUALITY_PIPELINE_ACTIVE','automatic-source'))

    def test_identical_actual_pipeline_cannot_be_registered_as_repair_by_renaming(self):
        self.prepare();issue=self.store.get('QUALITY_REPAIR_ISSUE',self.review['plan']['issue_id'])
        with self.assertRaisesRegex(ValueError,'沒有變更'):self.gates.candidate_plan(self.review['id'],issue['evidence']['pipeline_id'])

    def test_full_actual_ordered_control_independent_chain_and_repair_deployment(self):
        from template_ai.quality_repair_releases import QualityRepairReleases
        self.prepare(full_chain=True)
        root=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[0],self.dataset_id,self.policy_id,'Actual root correction first'))
        self.assertTrue(root['plan']['passed'],root['plan']['blockers'])
        controls=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[1],self.controls['dataset']['id'],self.policy_id,'Unrelated two-column actual phone/person/logo/mm/customer and multi-panel controls',root['id']))
        self.assertTrue(controls['plan']['passed'],controls['plan']['blockers'])
        final=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[2],self.independent['dataset']['id'],self.policy_id,'New authored portrait HOLDOUT, software state-machine safety only',controls['id']))
        self.assertTrue(final['plan']['passed'],final['plan']['blockers']);self.assertTrue(final['plan']['independence_claim'])
        decision=QualityReports(self.library).decide(final['plan']['report_id'],'Reviewer','Explicit intentionally lenient authored synthetic safety test; not production accuracy',True)
        release=QualityRepairReleases(self.library);impact=release.confirm_impact(release.impact_plan(self.candidate['id']),'Reviewer','Inspect known impact and explicitly retain unknown history; no pending confirmed highrisk',True)
        plan=release.plan(decision['id'],0,gate_id=final['id'],impact_review_id=impact['id'])
        installed=release.confirm(plan,'Reviewer','Exact candidate passed ordered actual safety checks, remains human-review source recommendation',True)
        self.assertEqual(release.pin()['event_id'],installed['event']['id']);self.assertEqual(release.pin()['pipeline_id'],self.candidate['plan']['pipeline_id'])
