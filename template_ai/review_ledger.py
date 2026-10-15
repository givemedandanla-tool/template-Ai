"""Read-only source/work ledger. Analysis, human facts and customer ownership stay distinct."""
from contextlib import closing
import json,sqlite3,time
from pathlib import Path

LIMIT=50
MAX_BYTES=4*1024*1024


def read_page(root,mode='SOURCE',query='',source_id=None,offset=0):
    if mode not in ('SOURCE','WORK','PENDING') or not isinstance(query,str) or len(query)>500 or len(query.split())>20 or type(offset) is not int or offset<0:raise ValueError('審核清單需有效模式／500字搜尋／分頁')
    from .storage import Library
    from .training_store import TrainingStore
    from .automatic_training import AutomaticTraining
    from .source_links import verify_source
    from .batch_import import healthy_source
    root=Path(root);deadline=time.monotonic()+15
    with closing(sqlite3.connect((root/'library.sqlite3').resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        db.execute('PRAGMA query_only=ON');db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000);db.create_function('ledger_casefold',1,lambda v:str(v).casefold(),deterministic=True);db.execute('BEGIN')
        library=object.__new__(Library);library.root=root;library.assets=root/'assets';library.db=db;library.closed=False
        store=TrainingStore.bind(library);service=object.__new__(AutomaticTraining);service.library=library;service.db=db;service.store=store
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        active="COALESCE(json_extract(payload,'$.segmentation_state'),'')!='SUPERSEDED'"
        summary=dict(registered_source_pages=db.execute('SELECT count(*) FROM sources').fetchone()[0],registered_original_paths=db.execute('SELECT count(DISTINCT original_path) FROM sources').fetchone()[0],actual_active_works=db.execute('SELECT count(*) FROM artworks WHERE '+active).fetchone()[0],superseded_work_history=db.execute("SELECT count(*) FROM artworks WHERE json_extract(payload,'$.segmentation_state')='SUPERSEDED'").fetchone()[0],indexed_candidates=store.count('SCAN_CANDIDATE'),saved_analysis_records=store.count('AUTO_UNIT'),human_confirmation_records=db.execute("SELECT count(*) FROM training_records WHERE kind='FACTS' AND json_type(payload,'$.confirmation')='object'").fetchone()[0],current_verified_reviewed_total=None)
        pending_import=db.execute("SELECT count(*) FROM import_batches b,json_each(b.payload,'$.items') i WHERE json_extract(i.value,'$.source_id') IS NULL").fetchone()[0] if 'import_batches' in tables else 0
        pending_auto=db.execute("SELECT count(*) FROM training_records b,json_each(b.payload,'$.items') i WHERE b.kind='AUTO_JOB' AND json_extract(i.value,'$.source_id') IS NULL").fetchone()[0]
        summary['unregistered_preflight_scope_records']=pending_import+pending_auto
        # Global counts above are stored records; current validity is checked only for visible works.
        where=['1=1'];args=[];tokens=query.casefold().split()
        if mode=='SOURCE':
            text="ledger_casefold(s.id||' '||s.original_path||' '||COALESCE(l.current_path,'')||' '||s.hash)"
            for token in tokens:where.append('instr('+text+',?)>0');args.append(token)
            sql=' FROM sources s LEFT JOIN source_links l ON l.source_id=s.id WHERE '+' AND '.join(where)
            total=db.execute('SELECT count(*)'+sql,args).fetchone()[0];rows=[]
            for identity,path,current,hash_value,page in db.execute("SELECT s.id,substr(s.original_path,1,4096),substr(COALESCE(l.current_path,s.original_path),1,4096),s.hash,json_extract(s.payload,'$.page')"+sql+' ORDER BY s.rowid LIMIT ? OFFSET ?',(*args,LIMIT,offset)):
                counts=db.execute("SELECT count(*),sum(CASE WHEN json_extract(payload,'$.segmentation_state')='SUPERSEDED' THEN 1 ELSE 0 END) FROM artworks WHERE source_id=?",(identity,)).fetchone()
                links=db.execute('SELECT count(*) FROM customer_source_associations WHERE source_id=?',(identity,)).fetchone()[0] if 'customer_source_associations' in tables else 0
                rows.append(dict(id=identity,source_id=identity,original_path=path,path=current,source_hash=hash_value,page=page,actual_works=counts[0]-(counts[1] or 0),historical_superseded=counts[1] or 0,customer_association_records=links,ownership='已存關聯需按版本核對' if links else '沒有人工確認的客戶關聯紀錄',analysis_state='PENDING_ANALYSIS' if not counts[0] else 'OPEN_WORKS_FOR_CURRENT_VALIDITY',review_state='未把分析／同bytes快取當人審',next='檢視實際作品與來源證據；未分析來源從UI003預檢開始'))
        elif mode=='WORK':
            where=["COALESCE(json_extract(a.payload,'$.segmentation_state'),'')!='SUPERSEDED'"]
            if source_id:where.append('a.source_id=?');args.append(source_id)
            text="ledger_casefold(a.id||' '||a.name||' '||a.source_id||' '||s.original_path)"
            for token in tokens:where.append('instr('+text+',?)>0');args.append(token)
            sql=' FROM artworks a JOIN sources s ON s.id=a.source_id WHERE '+' AND '.join(where)
            total=db.execute('SELECT count(*)'+sql,args).fetchone()[0];rows=[];proofs={}
            for identity, in db.execute('SELECT a.id'+sql+' ORDER BY a.source_id,a.rowid LIMIT ? OFFSET ?',(*args,LIMIT,offset)).fetchall():
                work=library.artwork(identity);source=library.source(work['source_id']);key=(source['current_path'],source['hash']);source_error=None
                if key not in proofs:
                    try:proofs[key]=verify_source(*key)
                    except (OSError,ValueError) as error:proofs[key]=str(error)
                proof=proofs[key]
                if isinstance(proof,str):facts_state='STALE';source_error=proof
                else:facts_state=store.facts_state(identity,proof)
                uid,unit=service.work_unit(identity);excluded=bool(unit and unit['state']=='EXCLUDED' and unit.get('exclusion_reason') and db.execute("SELECT 1 FROM training_history WHERE kind='AUTO_UNIT' AND id=? AND revision=? AND action='automatic_work_explicitly_excluded'",(uid,unit['revision'])).fetchone())
                analysis='PENDING_ANALYSIS';analysis_valid=False
                if unit:
                    analysis=unit['state']
                    if not source_error and unit.get('input_signature')==service.work_signature(work) and healthy_source(source):analysis='VERIFIED_REUSABLE_ANALYSIS';analysis_valid=True
                    elif unit['state'] not in ('FAILED','EXCLUDED'):analysis='STALE_ANALYSIS_REQUIRES_RECHECK'
                review='EXPLICITLY_EXCLUDED' if excluded else 'CONFIRMED' if facts_state=='CONFIRMED' else 'STALE_REVIEW' if facts_state=='STALE' else 'WAITING_HUMAN_REVIEW'
                facts=store.facts(identity);confirmation=facts.get('confirmation')
                rows.append(dict(id=identity,work_id=identity,work_revision=work['revision'],name=work['name'],source_id=source['id'],path=source['current_path'],source_hash=source['hash'],page=source['page'],analysis_state=analysis,verified_analysis_cache=analysis_valid,review_state=review,exclusion_reason=unit.get('exclusion_reason') if excluded else None,source_error=source_error,unit_id=uid if unit else None,confirmation=confirmation,next='原有標記／品質中心核對；排除、失聯、待審均未算已審核',ownership='客戶歸屬須獨立核對，未由姓名／檔名／快取推定'))
        else:
            # Candidate and preflight scopes are explicit records, not extra registered files.
            sql="SELECT id,'SCAN_CANDIDATE' AS kind,json_extract(payload,'$.path') AS path,json_extract(payload,'$.source_hash') AS hash,json_extract(payload,'$.state') AS state FROM training_records WHERE kind='SCAN_CANDIDATE' UNION ALL SELECT j.id||':'||i.key,'AUTO_JOB',json_extract(i.value,'$.path'),json_extract(i.value,'$.source_hash'),json_extract(i.value,'$.state') FROM training_records j,json_each(j.payload,'$.items') i WHERE j.kind='AUTO_JOB' AND json_extract(i.value,'$.source_id') IS NULL"
            if 'import_batches' in tables:sql+=" UNION ALL SELECT b.id||':'||i.key,'IMPORT_BATCH',json_extract(i.value,'$.path'),json_extract(i.value,'$.expected_hash'),json_extract(i.value,'$.status') FROM import_batches b,json_each(b.payload,'$.items') i WHERE json_extract(i.value,'$.source_id') IS NULL"
            text="ledger_casefold(id||' '||COALESCE(path,'')||' '||COALESCE(hash,''))"
            for token in tokens:where.append('instr('+text+',?)>0');args.append(token)
            wrapper=' FROM ('+sql+') WHERE '+' AND '.join(where);total=db.execute('SELECT count(*)'+wrapper,args).fetchone()[0]
            rows=[dict(id=r[0],kind=r[1],path=r[2],source_hash=r[3],analysis_state=r[4],review_state='尚未據此核准來源／作品／客戶',next='明列範圍預檢／人工處理；此處只讀') for r in db.execute('SELECT id,kind,path,hash,state'+wrapper+' ORDER BY kind,id LIMIT ? OFFSET ?',(*args,LIMIT,offset))]
        summary['all_file_work_coverage_verified']=False
        result=dict(mode=mode,rows=rows,total=total,offset=offset,limit=LIMIT,summary=summary,scope='Declared registered source pages,recorded active works including unconfirmed hypotheses,and separately identified indexed/preflight scopes;no byte-hash deduplication;full source coverage needs independent review',read_only=True,page_reviewed=sum(row.get('review_state')=='CONFIRMED' for row in rows),page_excluded=sum(row.get('review_state')=='EXPLICITLY_EXCLUDED' for row in rows))
        if len(json.dumps(result,ensure_ascii=False,allow_nan=False).encode())>MAX_BYTES:raise ValueError('審核快照超過4MiB，請縮小搜尋範圍；未截斷分母')
        return result


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--mode',default='SOURCE');parser.add_argument('--query',default='');parser.add_argument('--source');parser.add_argument('--offset',type=int,default=0);args=parser.parse_args()
    try:print(json.dumps(read_page(args.root,args.mode,args.query,args.source,args.offset),ensure_ascii=False,allow_nan=False));return 0
    except Exception as error:print(json.dumps(dict(error=str(error)[:4000]),ensure_ascii=False));return 1


if __name__=='__main__':raise SystemExit(main())
