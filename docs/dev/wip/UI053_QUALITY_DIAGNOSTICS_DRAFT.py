"""Paged local diagnosis. Revealing gold consumes the holdout explicitly."""
import json
from .training_store import TrainingStore,digest
from .quality_protocol import QualityProtocols
from .quality_gold import QualityGold


class QualityDiagnostics:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library)

    def page(self,protocol_id,side,offset=0,limit=50,query='',severity='ALL',domain='ALL',field_type='ALL'):
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=50 or not isinstance(query,str) or len(query)>500:raise ValueError('診斷查詢需有界分頁，每頁最多50列')
        protocol=QualityProtocols(self.library).get(protocol_id)
        if not self.store.get('HOLDOUT_EXPOSED',protocol['scope']['dataset_id']):raise ValueError('逐案人工答案尚未明確揭露；先核對保留集失效邊界')
        if side not in ('BASELINE','CANDIDATE'):raise ValueError('需明確固定側別')
        pair=self.store.get('QUALITY_PROTOCOL_JOBS',protocol_id)
        if not pair:raise ValueError('固定品質工作不存在')
        job_id=pair['jobs'][side]
        base="""WITH cases AS (
          SELECT r.id item_id,r.revision item_revision,json_extract(r.payload,'$.source_id') source_id,
            CAST(c.key AS TEXT) ordinal,c.value case_payload,
            CASE WHEN json_extract(c.value,'$.critical_owner_error')=1 OR json_extract(c.value,'$.reason') IN ('MISSING_WHOLE_GOLD_WORK','WHOLE_LOGO_COMPONENTS_DIFFER','CUSTOMER_STYLE_MAPPING_WRONG_EXACT_VERSION') THEN 'CRITICAL' ELSE 'ERROR' END severity,
            COALESCE(json_extract(c.value,'$.domain'),'CASE') domain
          FROM training_records r,json_each(r.payload,'$.evaluation.cases') c
          WHERE r.kind='QUALITY_EVAL_ITEM' AND json_extract(r.payload,'$.job_id')=?
          UNION ALL
          SELECT r.id,r.revision,json_extract(r.payload,'$.source_id'),'DOMAIN:'||d.key,
            json_object('reason',json_extract(d.value,'$.reason'),'domain',d.key),'UNKNOWN',d.key
          FROM training_records r,json_each(r.payload,'$.evaluation.domains') d
          WHERE r.kind='QUALITY_EVAL_ITEM' AND json_extract(r.payload,'$.job_id')=?
            AND json_extract(d.value,'$.state')!='MEASURED_DESCRIPTIVE_ONLY'
        ) """
        args=[job_id,job_id];where=' WHERE 1=1'
        for key,value in (('severity',severity),('domain',domain)):
            if value!='ALL':where+=' AND '+key+'=?';args.append(value)
        if field_type!='ALL':
            where+=" AND (json_extract(case_payload,'$.gold_kind')=? OR json_extract(case_payload,'$.predicted_kind')=?)";args.extend([field_type,field_type])
        for token in query.casefold().split():
            where+=" AND instr(training_casefold(coalesce(source_id,'')||' '||case_payload),?)>0";args.append(token)
        total=self.library.db.execute(base+'SELECT count(*) FROM cases'+where,args).fetchone()[0]
        rows=[]
        for row in self.library.db.execute(base+'SELECT item_id,item_revision,source_id,ordinal,case_payload,severity,domain FROM cases'+where+' ORDER BY item_id,ordinal LIMIT ? OFFSET ?',(*args,limit,offset)):
            rows.append(dict(item_id=row[0],item_revision=row[1],source_id=row[2],ordinal=row[3],case=json.loads(row[4]),severity=row[5],domain=row[6]))
        return dict(rows=rows,total=total,offset=offset,limit=limit,whole_source_units=self.store.get('EVAL_JOB',job_id)['items'].__len__(),
                    diagnostic_case_count_is_not_source_quality_denominator=True,source_images_loaded=False)

    def detail(self,protocol_id,side,row):
        protocol=QualityProtocols(self.library).get(protocol_id)
        if not self.store.get('HOLDOUT_EXPOSED',protocol['scope']['dataset_id']):raise ValueError('需明確揭露答案後才能對照原稿')
        pair=self.store.get('QUALITY_PROTOCOL_JOBS',protocol_id);job=self.store.get('EVAL_JOB',pair['jobs'][side])
        item=self.store.get('QUALITY_EVAL_ITEM',row['item_id'])
        if not item or item['revision']!=row['item_revision'] or item['job_id']!=job['id']:raise ValueError('診斷列版次／試驗範圍已改變')
        result=self.store.get('QUALITY_EVAL_RESULT',job.get('result_id',''))
        if not result or digest(result)!=job.get('result_digest') or not any(r['id']==item['id'] and r['digest']==digest(item) for r in result['source_results']):raise ValueError('逐案結果正式收據缺漏或已變更')
        unit=next((i for i in job['items'] if i['id']==item['item_id']),None)
        if not unit:raise ValueError('來源單位失聯')
        golds=[]
        for identity in unit['gold_ids']:
            checked=QualityGold(self.library).validity(identity,verify_bytes=False)
            if not checked['valid']:raise ValueError('真值／原稿或本機用途已失效，未重新讀原稿：'+'；'.join(checked['errors']))
            golds.append(checked['gold'])
        predictions=[]
        for identity in item['prediction_ids']:
            record=self.store.get('QUALITY_PREDICTED_WORK',identity)
            if not record or record['job_id']!=job['id'] or record['item_id']!=item['item_id']:raise ValueError('實際模型預測失聯')
            predictions.append(record['prediction'])
        return dict(source_id=item['source_id'],source_hash=item['source_hash'],source_proof=item.get('source_proof'),golds=golds,predictions=predictions,
                    case=row['case'],protocol_scope_digest=protocol['scope_digest'],pipeline_manifest_digest=item['pipeline_manifest_digest'],
                    local_only=True,original_and_published_data_modified=False)
