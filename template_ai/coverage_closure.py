"""Fail-closed exact-batch closure. A receipt is immutable, never a publication."""
import copy
import time
from .coverage_evidence import LAYERS
from .training_store import digest, text
from .model import new_id

CLOSURE = 'COVERAGE_CLOSURE'


def evidence_digest(value):
    result=copy.deepcopy(value);result.pop('source_proofs',None)
    return digest(result)


class CoverageClosureMixin:
    def closure_plan(self, batch_id):
        batch=self.batch(batch_id)
        if batch['state'] not in ('BOUNDARY_FROZEN','OPEN') or batch.get('closure_receipt'): raise ValueError('批次已有結案／已重開，請核對其新版本')
        members=[];unresolved=[];excluded=0;reviewed=0;works=0;unknown_works=False
        layers={layer:dict(required=0,current_reviewed=0) for layer in LAYERS}
        for offset in range(0,batch['file_count'],50):
            for member in self.members(batch_id,offset)['rows']:
                evidence=self.member_evidence(member['id'])
                members.append(dict(member_id=member['id'],member_revision=member['revision'],evidence_digest=evidence_digest(evidence),source_proofs=evidence['source_proofs'],disposition=evidence['disposition']))
                if not evidence['closure_allowed']:unresolved.append(dict(member_id=member['id'],blockers=evidence['blockers']))
                excluded+=int(evidence['disposition']=='APPROVED_EXCLUSION');reviewed+=int(evidence['disposition']=='ALL_REQUIRED_LAYERS_REVIEWED')
                if evidence['actual_work_count'] is None:unknown_works=True
                else:works+=evidence['actual_work_count']
                for layer in LAYERS:
                    for key in layers[layer]:layers[layer][key]+=evidence['layer_counts'][layer][key]
        if len(members)!=batch['file_count'] or not members:raise ValueError('批次成員數異常／空集合，不能當100%結案')
        result=dict(batch_id=batch_id,batch_revision=batch['revision'],scope_digest=batch['scope_digest'],file_count=batch['file_count'],source_page_count=batch['source_page_count'],actual_work_count=None if unknown_works else works,individually_reviewed_files=reviewed,approved_excluded_files=excluded,unresolved_files=len(unresolved),layer_counts=layers,members=members,blockers=unresolved,closure_allowed=not unresolved,whole_directory_complete=False,successful_learning_claim=False,style_publication_claim=False,print_or_output_approval=False,scope_notice='僅指定來源批次；排除另列，不能宣稱全庫／整目錄成功學習或模板已核准')
        # This is bounded metadata, not image/source content or an eager model catalog.
        import json
        if len(json.dumps(result,ensure_ascii=False).encode())>32*1024*1024:raise ValueError('結案預覽超過32MiB，需明確分組；未截斷待審項')
        result['plan_digest']=digest(result);return result

    def close(self,plan,actor,approved=False):
        self.validate_plan(plan,actor,approved)
        if not plan.get('closure_allowed') or plan['unresolved_files'] or plan['blockers']:raise ValueError('仍有未核實／漏審／衝突項目，不可結案')
        with self.store.transaction():
            batch=self.batch(plan['batch_id'])
            if batch['revision']!=plan['batch_revision'] or batch['scope_digest']!=plan['scope_digest'] or batch.get('closure_receipt') or batch['state'] not in ('BOUNDARY_FROZEN','OPEN'):raise ValueError('結案批次版本已變更')
            expected_ids=[row['member_id'] for row in plan['members']]
            actual_ids=[row[0] for row in self.db.execute("SELECT id FROM training_records WHERE kind='COVERAGE_MEMBER' AND json_extract(payload,'$.batch_id')=? ORDER BY json_extract(payload,'$.ordinal')",(batch['id'],))]
            if actual_ids!=expected_ids or len(actual_ids)!=batch['file_count'] or not actual_ids:raise ValueError('結案缺少成員／重複或已換範圍')
            for pin in plan['members']:
                member=self.member(pin['member_id']);self.recheck_member_proofs(member,pin['source_proofs'])
                current=self.member_evidence(member['id'],verify_bytes=False)
                if not current['closure_allowed'] or evidence_digest(current)!=pin['evidence_digest']:raise ValueError('來源／語意／規則／審核／模板依賴已改變，不保存過期結案')
            identity=new_id()
            record=dict(batch_id=batch['id'],scope_digest=batch['scope_digest'],actor=actor,closed_at=time.time(),plan=copy.deepcopy(plan),immutable=True,publication_authorized=False,output_authorized=False)
            receipt=self.store._write(CLOSURE,identity,record,0,'coverage_exact_batch_closed_not_published')
            batch.update(state='CLOSED',closure_receipt=identity)
            self.store._write('COVERAGE_BATCH',batch['id'],batch,batch['revision'],'coverage_batch_closure_receipt_linked')
            return receipt

    def closure_status(self,batch_id):
        batch=self.batch(batch_id)
        if not batch.get('closure_receipt'):return dict(state=batch['state'],current_complete=False,receipt_id=None,reason='沒有正式結案收據')
        receipt=self.store.get(CLOSURE,batch['closure_receipt'])
        if not receipt:return dict(state='MISSING_RECEIPT',current_complete=False,receipt_id=batch['closure_receipt'],reason='收據失聯，FailClosed')
        failures=[]
        for pin in receipt['plan']['members']:
            try:
                evidence=self.member_evidence(pin['member_id'])
                if not evidence['closure_allowed'] or evidence_digest(evidence)!=pin['evidence_digest']:failures.append(pin['member_id'])
            except (OSError,ValueError,KeyError) as error:failures.append(dict(member_id=pin['member_id'],reason=str(error)))
        current=not failures and batch['state']=='CLOSED'
        return dict(state='CURRENT_AFTER_RECHECK' if current else 'STALE_REOPEN_REQUIRED',current_complete=current,receipt_id=receipt['id'],failures=failures,reason='只核對此明列批次；不聲稱新增來源或全目錄已處理',whole_directory_complete=False,publication_authorized=False)

    def reopen(self,batch_id,expected_revision,new_scope_plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需核對新範圍並明確重開')
        text(actor,'重開者',120);text(reason,'重開原因',2000)
        preview=copy.deepcopy(new_scope_plan);expected=preview.pop('scope_digest',None)
        if expected!=digest(preview):raise ValueError('新範圍預覽已變更')
        with self.store.transaction():
            previous=self.batch(batch_id)
            if previous['revision']!=expected_revision or previous['state']=='REOPENED':raise ValueError('舊批次版本已變更／已重開')
            current=self.plan_registered_sources(new_scope_plan['source_ids'])
            if current['scope_digest']!=expected:raise ValueError('重開的來源集合已變更')
            created=self._create_current(current,actor,previous_id=batch_id)
            previous.update(state='REOPENED',next_batch_id=created['id'],reopen_actor=actor,reopen_reason=reason,reopened_at=time.time())
            self.store._write('COVERAGE_BATCH',batch_id,previous,expected_revision,'coverage_batch_reopened_preserving_old_receipt')
            return created
