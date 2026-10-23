import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
import test_quality_gold_sets as gold_fixture
import test_quality_policy as policy_fixture
import test_quality_panel as panel_fixture
import test_quality_statistics as math_fixture
from template_ai.quality_gold import USE,DIAGNOSTIC_USE
from template_ai.quality_policy import QualityPolicies
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_protocol import QualityProtocols
from template_ai.quality_jobs import EvaluationJobs,run_evaluation
from template_ai.quality_reports import QualityReports
from template_ai.quality_diagnostics import QualityDiagnostics
from template_ai.quality_statistics import aggregate


class QualityRoleTests(unittest.TestCase):
    setUp=gold_fixture.QualityGoldSetTests.setUp

    def diagnostic_gold(self,use=DIAGNOSTIC_USE):
        base=gold_fixture.QualityGoldSetTests.plan(self)
        plan=self.gold.plan(self.work['id'],dict(base['rights'],use=use),base['domain_truth'],base['reason'],base['evidence'])
        return self.gold.confirm(plan,'Synthetic reviewer',True)

    def build_role(self,role='TRAIN'):
        gold=self.diagnostic_gold();dataset=self.sets.create(self.sets.plan('Explicit fit-role diagnostics',[gold['id']],True,True,'Reviewed source scope;not independent',evaluation_role=role),'Reviewer',True)
        policy_service=QualityPolicies(self.library);policy=policy_service.approve(policy_fixture.QualityPolicyTests.plan(SimpleNamespace(policy=lambda:policy_service)),'Reviewer',True)
        pipelines=QualityPipelines(self.library);left=pipelines.freeze('Actual fit baseline',None,'Reviewer',True);right=pipelines.freeze('Actual fit candidate',None,'Reviewer',True)
        protocols=QualityProtocols(self.library);protocol=protocols.freeze(protocols.plan('Fixed diagnostic pair',dataset['id'],policy['id'],dict(BASELINE=left['id'],CANDIDATE=right['id']),'Descriptive fit analysis only'),'Reviewer',True)
        service=EvaluationJobs(self.library);jobs=service.create_pair(protocol['id'],'Reviewer',True)
        self.protocol=protocol;self.dataset=dataset;self.service=service;self.jobs=jobs
        return jobs

    def execute_pair(self,role='TRAIN'):
        jobs=self.build_role(role)
        for job in jobs.values():
            claimed=self.service.claim(job['id'],job['revision'],True);done=run_evaluation(self.library.root,job['id'],claimed['owner_token'])
            result=self.store.get('QUALITY_EVAL_RESULT',done['result_id'])
            self.assertFalse(result['quality_pass']);self.assertEqual(result['quality_gate'],'DESCRIPTIVE_FIT_ROLE_ONLY_NOT_INDEPENDENT')
        return jobs

    def test_actual_train_diagnostics_never_admit_train_or_qualify_independent_quality(self):
        self.execute_pair()
        self.assertFalse(self.dataset['manifest']['independence_scope_ready'])
        self.assertEqual(self.store.count('SAMPLE'),0);self.assertEqual(self.store.count('SEMANTIC_MODEL'),0)
        self.assertEqual(self.store.count('QUALITY_HOLDOUT_USAGE'),0)
        report=QualityReports(self.library).plan(self.protocol['id'])
        self.assertTrue(report['fair_comparison']);self.assertFalse(report['candidate_decision_eligible'])
        self.assertEqual(report['fixed_conditions']['evaluation_role'],'TRAIN')

    def test_actual_validation_diagnostics_are_not_holdout_generalization(self):
        self.execute_pair('VALIDATION')
        self.assertEqual(self.store.get('GROUP_ROLE',self.source['hash'])['role'],'VALIDATION')

    def test_diagnostic_permission_cannot_be_reused_as_independent_holdout_or_vice_versa(self):
        diagnostic=self.diagnostic_gold()
        self.assertTrue(self.sets.plan('Invalid broadened use',[diagnostic['id']],evaluation_role='HOLDOUT')['errors'])
        independent=self.diagnostic_gold(USE)
        self.assertTrue(self.sets.plan('Invalid fit use',[independent['id']],evaluation_role='TRAIN')['errors'])

    def test_explicit_diagnostic_exposure_allows_new_fixed_fit_pair_but_cannot_wash_role(self):
        self.execute_pair();protocols=QualityProtocols(self.library)
        protocols.expose(self.protocol['id'],'Reviewer','Inspect fit error positions',True)
        self.assertIsNotNone(self.store.get('QUALITY_ANSWER_EXPOSURE',self.protocol['id']))
        self.assertIsNone(self.store.get('HOLDOUT_EXPOSED',self.dataset['id']))
        self.assertTrue(self.sets.validity(self.dataset['id'])['valid'])
        scope=self.protocol['scope'];next_plan=protocols.plan('Next fixed fit diagnostic',self.dataset['id'],scope['policy_id'],{s:r['id'] for s,r in scope['pipelines'].items()},'Fit tuning diagnostics only')
        self.assertFalse(next_plan['independence_claim'])
        fresh=self.diagnostic_gold(USE)
        plan=self.sets.plan('Cannot wash already diagnostic TRAIN source',[fresh['id']],True,True,'Still same used family',evaluation_role='HOLDOUT')
        self.assertTrue(any('角色' in error or '洩漏' in error for error in plan['errors']))

    def test_even_perfect_synthetic_fit_counts_have_no_inference_interval_or_quality_pass(self):
        rows,manifest,policy=math_fixture.QualityStatisticsTests.fixture(self)
        manifest['evaluation_role']='TRAIN';manifest['independence_scope_ready']=True
        result=aggregate(rows,manifest,policy)
        self.assertFalse(result['quality_pass'])
        self.assertEqual(result['confidence_scope'],'FIT_DATA_NOT_GENERALIZATION_EVIDENCE')
        self.assertIsNone(result['domains']['field_types']['classes']['email']['failure_rate_interval'])


class QualityRoleGuiTests(unittest.TestCase):
    setUp=QualityRoleTests.setUp
    diagnostic_gold=QualityRoleTests.diagnostic_gold
    build_role=QualityRoleTests.build_role
    execute_pair=QualityRoleTests.execute_pair
    window=panel_fixture.QualityPanelTests.window
    panel=panel_fixture.QualityPanelTests.panel
    wait=panel_fixture.QualityPanelTests.wait

    def test_actual_native_train_role_diagnosis_has_correct_filtered_rows(self):
        self.execute_pair();panel=self.panel();panel.activate();self.wait(panel)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.expose()
        self.wait(panel);panel.facets['role'].setText('TRAIN');panel.cases(0);self.wait(panel)
        self.assertGreater(panel.table.rowCount(),0)
        panel.load_status();self.wait(panel)
        self.assertIn('DESCRIPTIVE_FIT_ROLE_ONLY_NOT_INDEPENDENT',panel.status.text())
