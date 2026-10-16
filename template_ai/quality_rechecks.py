"""Confirmed severe failures invalidate historical trust without erasing history."""
import copy
import time
from .training_store import TrainingStore, digest, text
from .quality_protocol import QualityProtocols
from .model import new_id


def blocked(store, work_id):
    return bool(store.db.execute("SELECT 1 FROM training_records WHERE kind='QUALITY_WORK_QUARANTINE' AND json_extract(payload,'$.work_id')=? AND json_extract(payload,'$.state')='REVIEW_REQUIRED' LIMIT 1",(work_id,)).fetchone())


class QualityRechecks:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library);self.db=library.db

    def plan(self,protocol_id,side,component,rule_id=None):
        if side not in ('BASELINE','CANDIDATE') or component not in ('PARSER','MODEL','RULE'):raise ValueError('需選明確試驗側及解析器／模型／規則版本')
        protocol=QualityProtocols(self.library).get(protocol_id);pair=self.store.get('QUALITY_PROTOCOL_JOBS',protocol_id)
        job=self.store.get('EVAL_JOB',pair['jobs'][side]) if pair else None
        result=self.store.get('QUALITY_EVAL_RESULT',job.get('result_id','')) if job else None
        if not result or digest(result)!=job.get('result_digest') or not any(result['critical_errors'].values()):raise ValueError('需實際執行且已保存的重大錯誤結果，不以猜測擴大隔離')
        pipeline=self.store.get('QUALITY_PIPELINE',protocol['scope']['pipelines'][side]['id']);manifest=pipeline['manifest']
        rule=next((r for r in manifest['rules'] if r['id']==rule_id),None)
        if component=='MODEL' and not manifest['semantic_model_id']:raise ValueError('此版本沒有已執行語意模型')
        if component=='RULE' and not rule:raise ValueError('exact規則不在已固定版本集合')
        if component=='PARSER':
            direct="SELECT id FROM artworks WHERE json_extract(payload,'$.analysis_version')=?";args=[manifest['analyser_version']]
            historical="json_extract(h.after_json,'$.dependency_versions.analyser_version')=?";hargs=[manifest['analyser_version']]
        elif component=='MODEL':
            direct="SELECT id FROM artworks WHERE json_extract(payload,'$.evidence.semantic_model.model_id')=?";args=[manifest['semantic_model_id']]
            historical="json_extract(h.after_json,'$.dependency_versions.semantic_model_digest')=?";hargs=[manifest['semantic_model_digest']]
        else:
            direct="SELECT json_extract(s.payload,'$.work_id') FROM training_records s,json_each(s.payload,'$.rule_dependencies') d WHERE s.kind='SAMPLE' AND json_extract(d.value,'$.id')=? AND json_extract(d.value,'$.revision')=?";args=[rule_id,rule['revision']]
            historical="EXISTS (SELECT 1 FROM json_each(h.after_json,'$.dependency_versions.active_rule_versions') d WHERE json_extract(d.value,'$.id')=? AND json_extract(d.value,'$.revision')=?)";hargs=[rule_id,rule['revision']]
        query=direct+" UNION SELECT json_extract(h.after_json,'$.work_id') FROM training_history h WHERE h.kind='COVERAGE_REVIEW' AND (("+historical+") OR json_type(h.after_json,'$.dependency_versions') IS NULL)"
        rows=[];missing=[]
        for (work_id,) in self.db.execute(query+' ORDER BY 1 LIMIT 10001',(*args,*hargs)):
            if len(rows)+len(missing)>=10000:raise ValueError('重大影響超過10000作品，需明確分段版本；未當完整歷史掃描')
            work=self.db.execute('SELECT revision,source_id FROM artworks WHERE id=?',(work_id,)).fetchone()
            if not work:missing.append(work_id);continue
            facts=self.db.execute("SELECT revision FROM training_records WHERE kind='FACTS' AND id=?",(work_id,)).fetchone()
            samples=[list(r) for r in self.db.execute("SELECT id,revision FROM training_records WHERE kind='SAMPLE' AND json_extract(payload,'$.work_id')=? ORDER BY id",(work_id,)).fetchmany(201)]
            if len(samples)>200:raise ValueError('單作品歷史樣本超過200，不截斷重大影響')
            batch_ids=[r[0] for r in self.db.execute("SELECT DISTINCT json_extract(payload,'$.batch_id') FROM training_records WHERE kind='COVERAGE_REVIEW' AND json_extract(payload,'$.work_id')=? ORDER BY 1",(work_id,)).fetchmany(201)]
            if len(batch_ids)>200:raise ValueError('單作品歷史批次超過200，不截斷重大影響')
            legacy=self.db.execute("SELECT 1 FROM training_history WHERE kind='COVERAGE_REVIEW' AND json_extract(after_json,'$.work_id')=? AND json_type(after_json,'$.dependency_versions') IS NULL LIMIT 1",(work_id,)).fetchone()
            rows.append(dict(work_id=work_id,work_revision=work[0],source_id=work[1],facts_revision=facts[0] if facts else 0,samples=samples,batch_ids=batch_ids,legacy_dependency_versions_unknown=bool(legacy)))
        plan=dict(protocol_id=protocol_id,side=side,component=component,rule_id=rule_id,pipeline_id=pipeline['id'],
                  pipeline_digest=digest(pipeline),result_id=result['id'],result_digest=digest(result),critical_errors=result['critical_errors'],
                  rows=rows,missing_historical_work_ids=missing,complete=not missing,
                  scope='EXACT_DEPENDENCIES_AND_POTENTIAL_LEGACY_REVIEWS_WITHOUT_VERSION_SNAPSHOT_INCLUDING_CLOSED_BATCHES',
                  unknown_unrecorded_dependencies=True,original_and_published_data_modified=False)
        plan['digest']=digest(plan);return plan

    def confirm(self,plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需核對重大錯誤／歷史影響並明確發起重審與隔離')
        text(actor,'重審發起人',120);text(reason,'共通嚴重錯誤確認依據',2000)
        with self.store.transaction():
            if self.plan(plan['protocol_id'],plan['side'],plan['component'],plan['rule_id'])!=plan or not plan['complete']:raise ValueError('重大影響版本／歷史範圍已變更或仍有失聯作品')
            case_id=new_id()
            for row in plan['rows']:
                self.store._write('QUALITY_WORK_QUARANTINE',digest([case_id,row['work_id']]),dict(row,case_id=case_id,state='REVIEW_REQUIRED',actor=actor,reason=reason,at=time.time()),0,'quality_major_historical_work_quarantined')
                for sample_id,revision in row['samples']:
                    sample=self.store.get('SAMPLE',sample_id)
                    if sample.get('state')=='APPROVED':
                        sample.update(state='QUARANTINED',quality_recheck_case=case_id,transition_actor=actor,transition_reason=reason)
                        self.store._write('SAMPLE',sample_id,sample,revision,'quality_major_historical_sample_quarantined')
            prior=self.store.get('QUALITY_PIPELINE_QUARANTINE',plan['pipeline_id'])
            self.store._write('QUALITY_PIPELINE_QUARANTINE',plan['pipeline_id'],dict(case_id=case_id,state='REVIEW_REQUIRED',reason=reason,actor=actor,at=time.time(),fallback_assumed_safe=False),prior['revision'] if prior else 0,'quality_major_version_quality_recommendations_blocked')
            header={key:copy.deepcopy(value) for key,value in plan.items() if key!='rows'}
            return self.store._write('QUALITY_MAJOR_RECHECK',case_id,dict(plan=header,affected_works=len(plan['rows']),actor=actor,reason=reason,state='REVIEW_REQUIRED',at=time.time(),old_closure_receipts_preserved=True,models_decontaminated=False),0,'quality_major_cross_batch_recheck_confirmed')

    def resolve(self,quarantine_id,revision,actor,reason,evidence,approved=False):
        if approved is not True:raise ValueError('需逐件完成新來源事實審核，明確解除此件隔離')
        text(actor,'重審人',120);text(reason,'逐件重審結論',2000);text(evidence,'修正及原稿對照證據',2000)
        row=self.store.get('QUALITY_WORK_QUARANTINE',quarantine_id)
        if not row:raise ValueError('作品重審項不存在')
        proof=self.store.source_proof(row['work_id'])
        with self.store.transaction():
            current=self.store.get('QUALITY_WORK_QUARANTINE',quarantine_id)
            if current!=row or current['revision']!=revision or current['state']!='REVIEW_REQUIRED':raise ValueError('重審版次已變更')
            self.store.checked(row['work_id'],proof)
            facts=self.store.facts(row['work_id'])
            if facts['revision']<=row['facts_revision'] or self.store.facts_state(row['work_id'])!='CONFIRMED':raise ValueError('需比隔離時更新且已人工確認的來源事實；保留舊版不等於已修正')
            current.update(state='RESOLVED_AFTER_NEW_HUMAN_FACTS',review_actor=actor,review_reason=reason,review_evidence=evidence,resolved_at=time.time(),resolved_facts_revision=facts['revision'])
            return self.store._write('QUALITY_WORK_QUARANTINE',quarantine_id,current,revision,'quality_single_historical_work_rereviewed_not_model_release')
