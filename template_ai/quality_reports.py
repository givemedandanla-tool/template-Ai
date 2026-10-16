"""Exact predeclared pairs and append-only quality decisions, never publication."""
import copy
import time
from .training_store import TrainingStore, digest, text
from .quality_protocol import QualityProtocols, SIDES
from .model import new_id


class QualityReports:
    def __init__(self, library):
        self.library = library
        self.store = TrainingStore.bind(library)
        self.protocols = QualityProtocols(library)

    def plan(self, protocol_id):
        checked = self.protocols.validity(protocol_id, verify_sources=False)
        protocol = checked['protocol']; scope = protocol['scope']
        pair = self.store.get('QUALITY_PROTOCOL_JOBS', protocol_id)
        if not pair: raise ValueError('固定雙側工作尚未建立')
        results = {}; cases = {}; critical = {}
        for side in SIDES:
            job = self.store.get('EVAL_JOB', pair['jobs'][side])
            result = self.store.get('QUALITY_EVAL_RESULT', job.get('result_id', '')) if job else None
            if not result or job['phase'] not in ('COMPLETED', 'COMPLETED_WITH_EXCEPTIONS'):
                raise ValueError(side + '尚無完整持久結果，不比較不同進度的分母')
            if digest(result) != job.get('result_digest'):
                raise ValueError('完整結果與已完成工作的指紋不一致')
            expected = dict(protocol_id=protocol_id, side=side, dataset_id=scope['dataset_id'],
                            dataset_manifest_digest=scope['dataset_manifest_digest'],
                            protocol_scope_digest=protocol['scope_digest'],
                            pipeline_manifest_digest=scope['pipelines'][side]['manifest_digest'],
                            origin='ACTUAL_FIFO_SOURCE_EVALUATION')
            if any(result.get(key) != value for key, value in expected.items()):
                raise ValueError('結果不是同一預先固定試驗／資料／真值／環境／計算口徑')
            side_cases = {}
            for reference in result['source_results']:
                item = self.store.get('QUALITY_EVAL_ITEM', reference['id'])
                if not item or digest(item) != reference['digest']:
                    raise ValueError('來源結果缺漏或指紋已變更')
                for case in item['evaluation']['cases']:
                    failure = {key: case.get(key) for key in ('work_id', 'gold_id', 'reason', 'kind_error', 'critical_owner_error', 'gold_kind', 'predicted_kind')}
                    if not case.get('gold_id'):
                        failure.update(predicted_work_id=case.get('predicted_work_id'), prediction_id=case.get('prediction_id'))
                    key = digest([item['source_id'], failure])
                    if case.get('source_id',item['source_id'])!=item['source_id']:raise ValueError('錯誤案例與實際來源憑證不一致')
                    side_cases[key] = dict(copy.deepcopy(case),source_id=item['source_id'], item_id=item['id'])
            cases[side] = side_cases
            critical[side] = result['critical_errors']
            results[side] = dict(id=result['id'], digest=digest(result), statistics=copy.deepcopy(result['statistics']),
                                 quality_gate=result['quality_gate'], quality_pass=result['quality_pass'],
                                 source_current=result['scope_current'])
        denominator_keys = ('required_source_pages_or_unparsed_files', 'declared_logical_files',
                            'declared_physical_paths', 'declared_gold_works', 'declared_gold_objects', 'required_independent_groups')
        denominators = [{key: self.store.get('QUALITY_EVAL_RESULT', results[side]['id'])[key]
                         for key in denominator_keys} for side in SIDES]
        if denominators[0] != denominators[1]: raise ValueError('雙側分母不同，不可直接宣稱進步')
        new_critical = {key: value - critical['BASELINE'].get(key, 0)
                        for key, value in critical['CANDIDATE'].items()
                        if value > critical['BASELINE'].get(key, 0)}
        regressions = []
        for domain, baseline in results['BASELINE']['statistics']['domains'].items():
            for kind, left in baseline['classes'].items():
                right = results['CANDIDATE']['statistics']['domains'][domain]['classes'][kind]
                if right['failed_independent_groups'] > left['failed_independent_groups']:
                    regressions.append(dict(domain=domain, kind=kind, baseline=left['failed_independent_groups'], candidate=right['failed_independent_groups']))
        fair = bool(checked['valid'] and all(row['source_current'] for row in results.values()))
        eligible = bool(fair and results['CANDIDATE']['quality_pass'] and not new_critical and not regressions
                        and results['CANDIDATE']['statistics']['policy_scope'] == 'AUTHORIZED_LOCAL_QUALITY_ACCEPTANCE')
        from .quality_trust import blockers
        quarantined={side:bool(blockers(self.store,self.store.get('QUALITY_PIPELINE',scope['pipelines'][side]['id']))) for side in SIDES}
        eligible = eligible and not quarantined['CANDIDATE']
        from .quality_rules import production_current, approved_for_quality_current
        candidate_pipeline=self.store.get('QUALITY_PIPELINE',scope['pipelines']['CANDIDATE']['id'])
        rules_current=production_current(self.store,candidate_pipeline['manifest'].get('rule_records',[]))
        rules_quality_approved=approved_for_quality_current(self.store,candidate_pipeline['manifest'].get('rule_records',[]))
        eligible=eligible and rules_quality_approved
        plan = dict(protocol_id=protocol_id, protocol_scope_digest=protocol['scope_digest'],
                    fixed_conditions=copy.deepcopy(scope), results=results, denominators=denominators[0],
                    fair_comparison=fair, current_errors=checked['errors'],
                    fixed_cases=[cases['BASELINE'][key] for key in sorted(cases['BASELINE'].keys() - cases['CANDIDATE'].keys())],
                    new_cases=[cases['CANDIDATE'][key] for key in sorted(cases['CANDIDATE'].keys() - cases['BASELINE'].keys())],
                    unresolved_cases=[cases['CANDIDATE'][key] for key in sorted(cases['CANDIDATE'].keys() & cases['BASELINE'].keys())],
                    critical_errors=critical, new_critical_errors=new_critical, class_regressions=regressions,
                    version_quarantined=quarantined,
                    candidate_rules_current_for_production=rules_current,
                    candidate_rules_approved_for_quality=rules_quality_approved,
                    candidate_decision_eligible=eligible, automatic_publication=False,
                    conclusion='NEEDS_EXPLICIT_LOCAL_DECISION' if eligible else 'BLOCKED_OR_EVIDENCE_INSUFFICIENT',
                    fewer_observed_errors_is_not_statistical_superiority=True)
        plan['digest'] = digest(plan)
        return plan

    def save(self, plan, actor, approved=False):
        if approved is not True: raise ValueError('需明確保存固定雙側結果憑證')
        text(actor, '比較報告保存者', 120)
        with self.store.transaction():
            if self.plan(plan['protocol_id']) != plan: raise ValueError('比較版本或來源證據已改變')
            return self.store._write('QUALITY_PAIR_REPORT', new_id(),
                                     dict(plan=copy.deepcopy(plan), actor=actor, created=time.time(), immutable=True),
                                     0, 'quality_exact_pair_report_saved_no_publication')

    def decide(self, report_id, actor, reason, approved=False):
        if approved is not True: raise ValueError('需明確核准品質版本；不自動發布模板或訓練規則')
        text(actor, '品質決策者', 120); text(reason, '品質決策依據', 2000)
        with self.store.transaction():
            report = self.store.get('QUALITY_PAIR_REPORT', report_id)
            if not report: raise ValueError('固定比較憑證不存在')
            current = self.plan(report['plan']['protocol_id'])
            if current != report['plan'] or not current['candidate_decision_eligible']:
                raise ValueError('品質不足／重大退步／來源洩漏／僅合成自驗，不可核准正式品質推薦依據')
            pipeline_id = current['fixed_conditions']['pipelines']['CANDIDATE']['id']
            return self.store._write('QUALITY_VERSION_DECISION', new_id(),
                                     dict(report_id=report_id, pipeline_id=pipeline_id, actor=actor, reason=reason,
                                          state='ACCEPTED_QUALITY_ONLY', at=time.time(), original_and_published_data_modified=False),
                                     0, 'quality_version_explicit_decision_not_model_activation')

    def withdraw(self, decision_id, actor, reason, approved=False):
        if approved is not True: raise ValueError('需明確撤回品質決策，舊版不會自動當安全替代')
        text(actor, '撤回者', 120); text(reason, '撤回依據', 2000)
        with self.store.transaction():
            if not self.store.get('QUALITY_VERSION_DECISION', decision_id): raise ValueError('品質決策不存在')
            prior = self.store.get('QUALITY_DECISION_WITHDRAWAL', decision_id)
            return self.store._write('QUALITY_DECISION_WITHDRAWAL', decision_id,
                                     dict(actor=actor, reason=reason, at=time.time(), fallback_assumed_safe=False),
                                     prior['revision'] if prior else 0, 'quality_version_decision_withdrawn_history_retained')

    def recommendation_status(self,decision_id):
        decision=self.store.get('QUALITY_VERSION_DECISION',decision_id)
        errors=[]
        if not decision:errors.append('沒有明確品質接受憑證')
        elif self.store.get('QUALITY_DECISION_WITHDRAWAL',decision_id):errors.append('品質接受已撤回；不自動信任舊版')
        elif self.component_blocked(decision['pipeline_id']):errors.append('此實際程式／權重／規則組件重大錯誤隔離中，改名稱／ID不能恢復信任，也不自動信任回退版')
        else:
            report=self.store.get('QUALITY_PAIR_REPORT',decision['report_id'])
            try:
                current=self.plan(report['plan']['protocol_id'])
                if current!=report['plan'] or not current['candidate_decision_eligible']:errors.append('品質來源／政策／版本／獨立性證據已改變')
            except (OSError,ValueError,KeyError,TypeError) as error:errors.append(str(error))
        return dict(quality_verified_recommendation_allowed=not errors,errors=errors,
                    automatic_template_or_rule_publication=False,fallback_assumed_safe=False)

    def component_blocked(self,pipeline_id):
        from .quality_trust import blockers
        pipeline=self.store.get('QUALITY_PIPELINE',pipeline_id)
        return True if not pipeline else bool(blockers(self.store,pipeline))
