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

    def source_dependencies(self,work_id,additional_work_ids=None):
        """Bounded directed reachability over actual current and historical IDs."""
        import networkx as nx
        from .quality_groups import QualityGroups
        work=self.library.artwork(work_id);source=self.library.source(work['source_id'])
        graph=nx.DiGraph();potential=set();missing=set()
        def rows(sql,args=()):
            result=list(self.db.execute(sql,args).fetchmany(5001))
            if len(result)>5000:raise ValueError('來源依賴掃描超過5000筆預算，未截斷／未宣稱完整')
            return result
        def edge(left,right,basis,uncertain=False):
            graph.add_edge(left,right,basis=basis)
            if uncertain:potential.add(right)
            if graph.number_of_edges()>20000:raise ValueError('來源依賴超過20000條，需縮小核對範圍')
        sources=rows('SELECT id,hash FROM sources ORDER BY id')
        additional_work_ids=additional_work_ids or []
        if not isinstance(additional_work_ids,list) or len(additional_work_ids)>200:raise ValueError('額外實際訓練／規則支持作品需明列最多200件')
        hashes={source['hash']}
        for wid in additional_work_ids:hashes.add(self.library.source(self.library.artwork(wid)['source_id'])['hash'])
        roots=['SOURCE:'+sid for sid,sha in sources if sha in hashes]
        current_works={wid:(sid,revision) for wid,sid,revision in rows('SELECT id,source_id,revision FROM artworks ORDER BY id')}
        for wid,(sid,revision) in current_works.items():edge('SOURCE:'+sid,'WORK:'+wid,'SAME_ACTUAL_SOURCE_CONTENT')
        for rid,revision,wid,state in rows("SELECT DISTINCT h.id,h.revision,json_extract(e.value,'$.work_id'),json_extract(h.after_json,'$.state') FROM training_history h,json_each(h.after_json,'$.positive_examples') e WHERE h.kind='RULE' UNION SELECT DISTINCT h.id,h.revision,json_extract(e.value,'$.work_id'),json_extract(h.after_json,'$.state') FROM training_history h,json_each(h.after_json,'$.counterexamples') e WHERE h.kind='RULE' ORDER BY 1,2,3"):
            edge('WORK:'+wid,'RULE:'+rid+':'+str(revision),'HISTORICAL_RULE_SUPPORT_OR_COUNTEREXAMPLE',state not in ('ACTIVE','ISOLATED_APPROVED_REPAIR_CANDIDATE'))
        for sid,wid in rows("SELECT DISTINCT id,json_extract(after_json,'$.work_id') FROM training_history WHERE kind='SAMPLE' ORDER BY 1,2"):
            edge('WORK:'+wid,'SAMPLE:'+sid,'HISTORICAL_CONFIRMED_SAMPLE_SOURCE')
        for sid,rid,revision in rows("SELECT DISTINCT h.id,json_extract(r.value,'$.id'),json_extract(r.value,'$.revision') FROM training_history h,json_each(h.after_json,'$.rule_dependencies') r WHERE h.kind='SAMPLE' ORDER BY 1,2,3"):
            edge('RULE:'+rid+':'+str(revision),'SAMPLE:'+sid,'EXACT_HISTORICAL_SAMPLE_RULE_VERSION')
        for did,sid,role in rows("SELECT DISTINCT h.id,json_extract(e.value,'$.sample_id'),json_extract(e.value,'$.role') FROM training_history h,json_each(h.after_json,'$.entries') e WHERE h.kind='DATASET' ORDER BY 1,2,3"):
            edge('SAMPLE:'+sid,'DATASET:'+did,'HISTORICAL_'+str(role)+'_DATASET_MEMBER')
        models=rows("SELECT DISTINCT h.id,h.revision,json_extract(s.value,'$.work_id'),json_extract(s.value,'$.role') FROM training_history h,json_each(h.after_json,'$.plan.scopes') s WHERE h.kind='SEMANTIC_MODEL' ORDER BY h.id,h.revision,3")
        model_nodes={}
        for mid,revision,wid,role in models:
            node='MODEL:'+mid+':'+str(revision);model_nodes.setdefault(mid,set()).add(node)
            edge('WORK:'+wid,node,'HISTORICAL_'+str(role)+'_MODEL_INPUT')
            if wid not in current_works:missing.add('WORK:'+wid)
        for wid,revision,mid,mrevision in rows("SELECT artwork_id,revision,json_extract(payload,'$.analysis_evidence.semantic_model.model_id'),json_extract(payload,'$.analysis_evidence.semantic_model.model_revision') FROM artwork_revisions WHERE json_type(payload,'$.analysis_evidence.semantic_model.model_id') IS NOT NULL ORDER BY artwork_id,revision"):
            targets=['MODEL:'+mid+':'+str(mrevision)] if mrevision else sorted(model_nodes.get(mid,{'MODEL:'+mid+':UNKNOWN'}))
            for model in targets:edge(model,'WORK:'+wid,'ACTUAL_HISTORICAL_AUTO_MODEL_PRODUCER',not mrevision)
            if wid not in current_works:missing.add('WORK:'+wid)
        templates=rows("SELECT id,family_id,version,json_extract(payload,'$.source_work_id') FROM templates ORDER BY id")
        for tid,family,version,wid in templates:
            if wid:
                edge('WORK:'+wid,'TEMPLATE:'+tid+':'+str(version),'EXISTING_TEMPLATE_SOURCE_WORK')
                edge('TEMPLATE:'+tid+':'+str(version),'STYLE:'+family,'EXISTING_TEMPLATE_FAMILY')
                if wid not in current_works:missing.add('WORK:'+wid)
        for tid,version,sid,did in rows("SELECT id,version,json_extract(payload,'$.training_reference.sample_id'),json_extract(payload,'$.training_reference.dataset_id') FROM templates WHERE json_type(payload,'$.training_reference.sample_id') IS NOT NULL ORDER BY id"):
            edge('SAMPLE:'+sid,'TEMPLATE:'+tid+':'+str(version),'ACTUAL_GEOMETRY_TRAINING_SAMPLE')
            if did:edge('DATASET:'+did,'TEMPLATE:'+tid+':'+str(version),'ACTUAL_GEOMETRY_TRAINING_DATASET')
        groups=QualityGroups(self.library)
        if groups.has_table('customer_source_associations'):
            for cid,wid,tid in rows('SELECT customer_id,artwork_id,template_id FROM customer_source_associations ORDER BY id'):
                edge('WORK:'+wid,'CUSTOMER:'+cid,'CONFIRMED_CUSTOMER_SOURCE_ASSOCIATION')
        if groups.has_table('customer_styles'):
            versions={tid:version for tid,family,version,wid in templates}
            for cid,tid in rows('SELECT customer_id,template_id FROM customer_styles ORDER BY id'):
                edge('TEMPLATE:'+tid+':'+str(versions.get(tid,'UNKNOWN')),'CUSTOMER:'+cid,'CONFIRMED_CUSTOMER_STYLE')
        graph.add_nodes_from(roots);reachable=set(roots)
        for root in roots:reachable.update(nx.descendants(graph,root))
        induced=graph.subgraph(reachable)
        uncertain=set()
        for node in potential.intersection(reachable):uncertain.add(node);uncertain.update(nx.descendants(induced,node))
        result=dict(work_id=work_id,source_id=source['id'],source_hash=source['hash'],additional_work_ids=sorted(set(additional_work_ids)),
                    nodes=[dict(key=node,dependency_match='POTENTIAL_MISSING_MODEL_REVISION' if node in uncertain else 'RECORDED_DEPENDENCY') for node in sorted(reachable)],
                    edges=[dict(left=a,right=b,basis=value['basis']) for a,b,value in sorted(induced.edges(data=True))],
                    missing_historical_nodes=sorted(missing.intersection(reachable)),
                    affected_work_ids=sorted(node[5:] for node in reachable if node.startswith('WORK:')),
                    unknown_unrecorded_dependencies=True,unscanned_legacy_dependencies='UNKNOWN_NOT_ASSUMED_SAFE',
                    complete_known_graph=not missing.intersection(reachable),automatic_training=False,original_and_published_data_modified=False)
        result['digest']=digest(result);return result

    def dependencies(self,pipeline_id,component,rule_id=None):
        if component not in ('PARSER','MODEL','RULE'):raise ValueError('需明列解析器／模型／規則影響種類')
        pipeline=self.store.get('QUALITY_PIPELINE',pipeline_id)
        if not pipeline or digest(pipeline['manifest'])!=pipeline['manifest_digest']:raise ValueError('實際固定版本不存在或已被修改')
        manifest=pipeline['manifest']
        rule=next((r for r in manifest['rules'] if r['id']==rule_id),None)
        if component=='MODEL' and not manifest['semantic_model_id']:raise ValueError('此版本沒有已執行語意模型')
        if component=='RULE' and not rule:raise ValueError('exact規則不在已固定版本集合')
        from .quality_trust import components
        fingerprint=next((c for c in components(manifest) if c['kind']==component and (component!='RULE' or c.get('rule_id')==rule_id)),None)
        if not fingerprint:raise ValueError('缺少可核對的實際組件版本指紋')
        model_ids=[]
        if component=='PARSER':
            direct="SELECT id FROM artworks WHERE json_extract(payload,'$.analysis_version')=? OR (json_type(payload,'$.analysis_key') IS NOT NULL AND json_type(payload,'$.analysis_version') IS NULL)";args=[manifest['analyser_version']]
            historical="json_extract(h.after_json,'$.dependency_versions.analyser_version')=? OR json_extract(h.after_json,'$.dependency_versions.source_parser_provenance_unknown')=1";hargs=[manifest['analyser_version']]
        elif component=='MODEL':
            model_ids=[r[0] for r in self.db.execute("SELECT id FROM training_records WHERE kind='SEMANTIC_MODEL' AND json_extract(payload,'$.weights_digest')=? ORDER BY id LIMIT 2001",(manifest['semantic_weights_digest'],))]
            if len(model_ids)>2000:raise ValueError('相同權重候選超過2000版本，需明確分段核對；未截斷歷史影響')
            model_ids=sorted(set(model_ids+[manifest['semantic_model_id']]))
            markers=','.join('?' for _ in model_ids)
            direct="SELECT id FROM artworks WHERE COALESCE(json_extract(payload,'$.analysis_evidence.semantic_model.model_id'),json_extract(payload,'$.evidence.semantic_model.model_id')) IN ("+markers+")";args=model_ids
            historical="json_extract(h.after_json,'$.dependency_versions.semantic_model_digest')=? OR json_extract(h.after_json,'$.dependency_versions.source_semantic_model_id') IN ("+markers+") OR json_extract(h.after_json,'$.dependency_versions.source_model_provenance_unknown')=1";hargs=[manifest['semantic_model_digest'],*model_ids]
        else:
            direct="SELECT json_extract(s.payload,'$.work_id') FROM training_records s,json_each(s.payload,'$.rule_dependencies') d WHERE s.kind='SAMPLE' AND json_extract(d.value,'$.id')=? AND json_extract(d.value,'$.revision')=?";args=[rule_id,rule['revision']]
            historical="EXISTS (SELECT 1 FROM json_each(h.after_json,'$.dependency_versions.active_rule_versions') d WHERE json_extract(d.value,'$.id')=? AND json_extract(d.value,'$.revision')=?)";hargs=[rule_id,rule['revision']]
        query=direct+" UNION SELECT json_extract(h.after_json,'$.work_id') FROM training_history h WHERE h.kind='COVERAGE_REVIEW' AND (("+historical+") OR json_type(h.after_json,'$.dependency_versions') IS NULL)"
        rows=[];missing=[]
        for (work_id,) in self.db.execute(query+' ORDER BY 1 LIMIT 10001',(*args,*hargs)):
            if len(rows)+len(missing)>=10000:raise ValueError('重大影響超過10000作品，需明確分段版本；未當完整歷史掃描')
            work=self.db.execute("SELECT revision,source_id,COALESCE(json_extract(payload,'$.analysis_evidence.semantic_model.model_id'),json_extract(payload,'$.evidence.semantic_model.model_id')),json_type(payload,'$.analysis_key') IS NOT NULL AND json_type(payload,'$.analysis_version') IS NULL FROM artworks WHERE id=?",(work_id,)).fetchone()
            if not work:missing.append(work_id);continue
            facts=self.db.execute("SELECT revision FROM training_records WHERE kind='FACTS' AND id=?",(work_id,)).fetchone()
            samples=[list(r) for r in self.db.execute("SELECT id,revision FROM training_records WHERE kind='SAMPLE' AND json_extract(payload,'$.work_id')=? ORDER BY id",(work_id,)).fetchmany(201)]
            if len(samples)>200:raise ValueError('單作品歷史樣本超過200，不截斷重大影響')
            batch_ids=[r[0] for r in self.db.execute("SELECT DISTINCT json_extract(payload,'$.batch_id') FROM training_records WHERE kind='COVERAGE_REVIEW' AND json_extract(payload,'$.work_id')=? ORDER BY 1",(work_id,)).fetchmany(201)]
            if len(batch_ids)>200:raise ValueError('單作品歷史批次超過200，不截斷重大影響')
            legacy=self.db.execute("SELECT 1 FROM training_history WHERE kind='COVERAGE_REVIEW' AND json_extract(after_json,'$.work_id')=? AND json_type(after_json,'$.dependency_versions') IS NULL LIMIT 1",(work_id,)).fetchone()
            equivalent=component=='MODEL' and work[2] in model_ids and work[2]!=manifest['semantic_model_id']
            unknown=bool(legacy or component=='PARSER' and work[3] or equivalent)
            rows.append(dict(work_id=work_id,work_revision=work[0],source_id=work[1],facts_revision=facts[0] if facts else 0,samples=samples,batch_ids=batch_ids,source_semantic_model_id=work[2],dependency_match='POTENTIAL_SAME_WEIGHTS_OTHER_MODEL_VERSION' if equivalent else 'POTENTIAL_LEGACY_VERSION_UNKNOWN' if unknown else 'RECORDED_VERSION_DEPENDENCY',legacy_dependency_versions_unknown=unknown))
        plan=dict(component=component,rule_id=rule_id,pipeline_id=pipeline['id'],
                  pipeline_digest=digest(pipeline),component_fingerprint=fingerprint,
                  rows=rows,missing_historical_work_ids=missing,complete=not missing,
                  scope='EXACT_DEPENDENCIES_AND_POTENTIAL_LEGACY_REVIEWS_WITHOUT_VERSION_SNAPSHOT_INCLUDING_CLOSED_BATCHES',
                  unknown_unrecorded_dependencies=True,original_and_published_data_modified=False)
        plan['digest']=digest(plan);return plan

    def plan(self,protocol_id,side,component,rule_id=None):
        if side not in ('BASELINE','CANDIDATE') or component not in ('PARSER','MODEL','RULE'):raise ValueError('需選明確試驗側及解析器／模型／規則版本')
        protocol=QualityProtocols(self.library).get(protocol_id);pair=self.store.get('QUALITY_PROTOCOL_JOBS',protocol_id)
        job=self.store.get('EVAL_JOB',pair['jobs'][side]) if pair else None
        result=self.store.get('QUALITY_EVAL_RESULT',job.get('result_id','')) if job else None
        if not result or digest(result)!=job.get('result_digest') or not any(result['critical_errors'].values()):raise ValueError('需實際執行且已保存的重大錯誤結果，不以猜測擴大隔離')
        pipeline=self.store.get('QUALITY_PIPELINE',protocol['scope']['pipelines'][side]['id']);manifest=pipeline['manifest']
        if pipeline['manifest_digest']!=protocol['scope']['pipelines'][side]['manifest_digest'] or digest(manifest)!=pipeline['manifest_digest']:raise ValueError('重大結果對應的實際版本已改變，未隔離其他程式冒充原版本')
        dependencies=self.dependencies(pipeline['id'],component,rule_id)
        dependencies.pop('digest')
        plan=dict(dependencies,protocol_id=protocol_id,side=side,result_id=result['id'],result_digest=digest(result),critical_errors=result['critical_errors'])
        plan['digest']=digest(plan);return plan

    def confirm(self,plan,actor,reason,approved=False):
        if 'protocol_id' not in plan or 'result_id' not in plan:raise ValueError('純影響清單不是重大錯誤憑證，不能據此隔離歷史')
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
            fingerprint=plan['component_fingerprint'];prior_component=self.store.get('QUALITY_COMPONENT_QUARANTINE',fingerprint['key'])
            self.store._write('QUALITY_COMPONENT_QUARANTINE',fingerprint['key'],dict(fingerprint=fingerprint,case_id=case_id,state='REVIEW_REQUIRED',actor=actor,reason=reason,at=time.time(),new_pipeline_id_does_not_reset_trust=True),prior_component['revision'] if prior_component else 0,'quality_actual_component_quarantined_not_display_name')
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
