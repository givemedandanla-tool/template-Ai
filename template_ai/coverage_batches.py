"""Exact registered-source boundary in the existing versioned SQLite store.

File, page, content and work denominators are separate. A source-byte check is
never an attestation of complete segmentation, human review, or publication.
"""
import copy,hashlib,json,os,time
from pathlib import Path
from .model import new_id
from .training_store import TrainingStore,digest,text
from .source_links import verify_source,check_verified
from .coverage_review import CoverageReviewMixin
from .coverage_closure import CoverageClosureMixin
from .coverage_scope import CoverageScopeMixin
from .coverage_rules import CoverageRuleMixin

BATCH='COVERAGE_BATCH'
MEMBER='COVERAGE_MEMBER'
MAX_SOURCES=10000
MAX_PLAN_BYTES=32*1024*1024


def logical_path(value):return os.path.normcase(os.path.normpath(str(value)))


class CoverageBatches(CoverageReviewMixin,CoverageClosureMixin,CoverageScopeMixin,CoverageRuleMixin):
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library);self.db=library.db

    def source_pin(self,identity):
        source=self.library.source(identity)
        work_rows=self.db.execute("SELECT id,revision FROM artworks WHERE source_id=? AND COALESCE(json_extract(payload,'$.segmentation_state'),'')!='SUPERSEDED' ORDER BY id LIMIT 2001",(identity,)).fetchall()
        if len(work_rows)>2000:raise ValueError('單來源超過2000件作品紀錄；請明確分組，未截斷範圍')
        works=[]
        for work_id,revision in work_rows:
            row=self.db.execute('SELECT CASE WHEN length(CAST(payload AS BLOB))<=1048576 THEN payload END FROM artworks WHERE id=?',(work_id,)).fetchone()
            if row[0] is None:raise ValueError('作品metadata超過1MiB，未當完整範圍')
            works.append(dict(id=work_id,revision=revision,payload_sha256=hashlib.sha256(row[0].encode()).hexdigest()))
        return dict(source_id=identity,original_path=source['original_path'],current_path=source['current_path'],source_hash=source['hash'],byte_size=source['byte_size'],page=source['page'],page_count=source.get('page_count'),link_revision=source['link_revision'],derivative_signature=digest(source.get('file_hashes',{})),works=works)

    def plan_registered_sources(self,source_ids):
        if not isinstance(source_ids,list) or not 1<=len(source_ids)<=MAX_SOURCES or any(not isinstance(identity,str) for identity in source_ids) or len(set(source_ids))!=len(source_ids):raise ValueError('需明列1～10000個不重複來源頁ID；沒有默認選全庫')
        groups={}
        for identity in sorted(source_ids):
            pin=self.source_pin(identity);key=logical_path(pin['original_path']);member=groups.setdefault(key,dict(logical_file_key=key,original_path=pin['original_path'],source_pins=[]));member['source_pins'].append(pin)
        members=[]
        for key,value in sorted(groups.items()):
            value['expected_hashes']=sorted({pin['source_hash'] for pin in value['source_pins']});value['source_page_count']=len(value['source_pins']);value['recorded_work_count']=sum(len(pin['works']) for pin in value['source_pins']);value['member_scope_digest']=digest(value)
            if len(json.dumps(value,ensure_ascii=False).encode())>900000:raise ValueError('單檔批次證據超過有界metadata，需明確分組；未遺漏來源頁')
            members.append(value)
        result=dict(schema_version=1,scope_kind='EXACT_REGISTERED_SOURCE_PAGES',source_ids=sorted(source_ids),source_page_count=len(source_ids),file_count=len(members),members=members,whole_directory_claim=False,all_file_work_coverage_verified=False)
        if len(json.dumps(result,ensure_ascii=False).encode())>MAX_PLAN_BYTES:raise ValueError('範圍快照超過32MiB，請分組；沒有靜默截斷來源')
        result['scope_digest']=digest(result);return result

    def create(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需先核對exact來源批次邊界並明確建立')
        text(actor,'批次建立者',120)
        if not isinstance(plan,dict) or 'source_ids' not in plan:raise ValueError('需要來源範圍預覽')
        preview=copy.deepcopy(plan);expected=preview.pop('scope_digest',None)
        if expected!=digest(preview):raise ValueError('批次預覽已被修改，請重新核對')
        # Metadata is checked under one write lock; no originals/models are opened here.
        with self.store.transaction():
            current=self.rebuild_scope_plan(plan)
            if current['scope_digest']!=expected:raise ValueError('來源位置／版本／作品集合已改變，未建立過期批次')
            return self._create_current(current,actor)

    def _create_current(self,current,actor,previous_id=None):
        identity=new_id();member_digests=[]
        for ordinal,member in enumerate(current['members']):
            mid=digest(['coverage-member',identity,member['logical_file_key']]);member_digests.append(member['member_scope_digest'])
            self.store._write(MEMBER,mid,dict(batch_id=identity,ordinal=ordinal,frozen=member,check_state='DECLARED_PENDING_PROOF',last_check=None,source_error=None,review_state='UNKNOWN_NOT_YET_REVIEWED'),0,'coverage_member_boundary_declared')
        details={key:copy.deepcopy(current[key]) for key in ('declared_paths','selected_source_ids','root_snapshot') if key in current}
        return self.store._write(BATCH,identity,dict(schema_version=1,scope_kind=current['scope_kind'],scope_digest=current['scope_digest'],scope_details=details,member_manifest_digest=digest(member_digests),file_count=current['file_count'],source_page_count=current['source_page_count'],source_ids=current['source_ids'],state='BOUNDARY_FROZEN',actor=actor,created=time.time(),previous_batch_id=previous_id,whole_directory_claim=False,all_file_work_coverage_verified=False,closure_receipt=None),0,'coverage_batch_exact_boundary_created')

    def batch(self,identity):
        value=self.store.get(BATCH,identity)
        if not value:raise ValueError('批次已失聯')
        return value

    def members(self,batch_id,offset=0,limit=50,query='',group_by='file'):
        self.batch(batch_id)
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=200 or not isinstance(query,str) or len(query)>500:raise ValueError('批次成員需有效分頁／搜尋，最多200項')
        self.db.create_function('coverage_casefold',1,lambda value:str(value).casefold(),deterministic=True)
        groups={'file':"json_extract(m.payload,'$.frozen.original_path')",'directory':"json_extract(a.payload,'$.directory')",'work':"json_extract(a.payload,'$.works')",'risk':"json_extract(a.payload,'$.risks')",'method':"json_extract(a.payload,'$.review_methods')",'blocker':"json_extract(a.payload,'$.blocker_reasons')",'style':"json_extract(a.payload,'$.style_versions')"}
        if group_by not in groups:raise ValueError('分組方式不支援')
        source="training_records m LEFT JOIN training_records a ON a.kind='COVERAGE_ASSESSMENT' AND a.id=m.id"
        where="m.kind=? AND json_extract(m.payload,'$.batch_id')=?";args=[MEMBER,batch_id]
        for token in query.casefold().split():where+=" AND instr(coverage_casefold(json_extract(m.payload,'$.frozen.original_path')||' '||m.id||' '||COALESCE(a.payload,'')),?)>0";args.append(token)
        total=self.db.execute('SELECT count(*) FROM '+source+' WHERE '+where,args).fetchone()[0]
        rows=[]
        order="json_extract(m.payload,'$.ordinal')" if group_by=='file' else groups[group_by]+",json_extract(m.payload,'$.ordinal')"
        for identity,label in self.db.execute('SELECT m.id,'+groups[group_by]+' FROM '+source+' WHERE '+where+" ORDER BY "+order+" LIMIT ? OFFSET ?",(*args,limit,offset)):
            row=self.store.get(MEMBER,identity);row['last_assessment_group']=label or '未保存此分組核對；當前有效數未知';rows.append(row)
        return dict(rows=rows,total=total,offset=offset,limit=limit)

    def check_member_sources(self,member_id,expected_revision):
        member=self.store.get(MEMBER,member_id)
        if not member or member['revision']!=expected_revision:raise ValueError('批次成員版次已改變')
        batch=self.batch(member['batch_id'])
        if batch.get('closure_receipt'):raise ValueError('已有結案憑證，需先明確重開；不覆寫舊結論')
        frozen=member['frozen'];proofs={};error=None;state='SOURCE_BYTES_VERIFIED_AWAITING_REVIEW'
        if not frozen['expected_hashes']:error='來源未登錄／未解析，仍保留在檔案分母；需先經來源預檢與分析';state='SOURCE_UNREGISTERED'
        elif len(frozen['expected_hashes'])!=1:error='同一原始檔名納入互相矛盾的內容版本，需明確選擇';state='SOURCE_VERSION_CONFLICT'
        try:
            if not error:
                for pin in frozen['source_pins']:
                    if self.source_pin(pin['source_id'])!=pin:raise ValueError('來源位置／版本或作品集合已改變')
                    key=(pin['current_path'],pin['source_hash'])
                    if key not in proofs:proofs[key]=verify_source(*key)
        except (OSError,ValueError) as failure:error=str(failure);state='SOURCE_UNRESOLVED'
        with self.store.transaction():
            current=self.store.get(MEMBER,member_id);now=self.batch(member['batch_id'])
            if current['revision']!=expected_revision or now['scope_digest']!=batch['scope_digest'] or now.get('closure_receipt'):raise ValueError('批次／成員已改變，不保存過期核實結果')
            if not error:
                for pin in frozen['source_pins']:
                    if self.source_pin(pin['source_id'])!=pin:raise ValueError('核實後來源依賴已改變')
                for (path,sha),proof in proofs.items():check_verified(proof,sha)
            current.update(check_state=state,source_error=error,last_check=dict(at=time.time(),source_proofs=[dict(path=p.path,hash=p.hash,stat=list(p.stat)) for p in proofs.values()],only_bytes_checked=True,does_not_approve_segmentation_facts_customer_or_style=True))
            return self.store._write(MEMBER,member_id,current,expected_revision,'coverage_source_bytes_checked_not_reviewed')

    def boundary_summary(self,batch_id):
        batch=self.batch(batch_id);counts={state:count for state,count in self.db.execute("SELECT json_extract(payload,'$.check_state'),count(*) FROM training_records WHERE kind=? AND json_extract(payload,'$.batch_id')=? GROUP BY 1",(MEMBER,batch_id))}
        return dict(batch_id=batch_id,scope_kind=batch['scope_kind'],declared_files=batch['file_count'],declared_source_pages=batch['source_page_count'],check_record_counts=counts,current_reviewed_files=None,actual_all_source_work_count=None,source_coverage_rate=None,whole_directory_complete=False,closure_allowed=False,note='僅固定來源邊界及位元核對；來源切分／人物公司Logo／語意／歸屬／版型必要驗證尚未結案')
