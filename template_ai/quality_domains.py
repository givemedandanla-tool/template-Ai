"""Per-source diagnostic counts. Unknown truth/capabilities never become perfect scores."""
from collections import Counter
from .quality_gold import DOMAINS
from .quality_metrics import match_boxes,classification_metrics,counts


def unknown(reason,required=None):
    return dict(state='EVIDENCE_INSUFFICIENT',reason=reason,required_gold=required,metrics=None,critical_errors=0)


def measured(metrics,required,unit,**extras):
    return dict(state='MEASURED_DESCRIPTIVE_ONLY',metrics=metrics,required_gold=required,unit=unit,critical_errors=0,**extras)


def predicted_objects(work):
    slots={row['id']:row for row in work.get('slots',[])};result=[]
    for observation in work.get('observations',[]):
        slot=slots.get(observation.get('slot_id'));kind=slot['kind'] if slot else observation.get('classification','UNKNOWN')
        result.append(dict(id=observation['id'],kind=kind,owner=slot.get('owner') if slot else None,rect=observation['region'],object_type=observation.get('object_type'),text=observation.get('text',''),component_prediction=observation.get('component_prediction')))
    return result


def text_boxes(objects, prediction=False):
    result=[];complete=True
    for obj in objects:
        if obj['kind']=='logo':
            evidence=obj.get('component_prediction' if prediction else 'component_truth') or {}
            if not evidence.get('complete') or not prediction and not evidence.get('manually_verified'):complete=False;continue
            for identity in evidence['text_component_ids']:
                result.append(dict(id=obj['id']+':'+identity,rect=evidence['component_regions'][identity]))
        elif obj.get('object_type')=='TEXT':result.append(dict(id=obj['id'],rect=obj['rect']))
    return result,complete


def evaluate_source(golds,prediction,policy,*,complete_source_gold=False,unresolved_reason=None):
    """Model predictions are fixed before this function is given any gold labels.

    Fields are paired per matched work, so local person ROOT names cannot cross
    different works. Raw counts are conditional on the exact declared gold scope;
    incomplete full-source truth keeps all headline rates unknown.
    """
    domains={name:unknown('此來源尚無完整有效真值／必要執行證據') for name in DOMAINS}
    if unresolved_reason or not golds:
        return dict(domains=domains,required_source_pages=1,unresolved_source_pages=1,unresolved_reason=unresolved_reason or '缺少合法人工gold；來源仍留在分母',gold_work_count=len(golds),predicted_work_count=None,cases=[],critical_errors={},quality_pass=None)
    if policy.get('schema_version')!=2:raise ValueError('需有效schema2領域政策與明確配對口徑')
    if not prediction or prediction.get('prediction_origin')!='ACTUAL_EXECUTED_SOURCE_ANALYSIS_NO_GOLD_ARGUMENT':raise ValueError('此品質驗收只接受實際source-only執行結果，不能把手填分類當模型推論')
    if any(g['source_hash']!=prediction['source_hash'] or g['source_id']!=prediction['source_id'] or g['source_page']!=prediction['source_page'] for g in golds):raise ValueError('gold與預測不是同一exact來源頁／內容版本')
    works=prediction['predictions'];gold_by={g['work_id']:g for g in golds};pred_by={p['key']:p for p in works}
    paired=match_boxes([dict(id=g['work_id'],rect=g['crop']) for g in golds],[dict(id=p['key'],rect=p['crop']) for p in works],policy['matching_iou'])
    truth=lambda domain:complete_source_gold and all(g['domain_truth'][domain]=='MANUALLY_VERIFIED' for g in golds)
    cases=[];critical=Counter();class_counts={};person=[0,0,0];company=[0,0,0];owner_unknown=0;person_unknown=0;company_unknown=0;root_missing=0;mm_errors=[]
    logo_gold=0;logo_predictions=0;logo_missing_component_truth=0;logo_counts=[0,0,0];logo_unknown=0;text_counts=[0,0,0];text_unknown=False
    def add_class(kind,tp=0,fp=0,fn=0):
        row=class_counts.setdefault(kind,[0,0,0]);row[0]+=tp;row[1]+=fp;row[2]+=fn
    for pair in paired['matches']:
        gold=gold_by[pair['gold_id']];pred=pred_by[pair['prediction_id']];objects=predicted_objects(pred)
        result=classification_metrics(gold['objects'],objects,policy['matching_iou'])
        gt,gcomplete=text_boxes(gold['objects']);pt,pcomplete=text_boxes(objects,True);text_unknown|=not(gcomplete and pcomplete)
        text_match=match_boxes(gt,pt,policy['matching_iou'])
        for index,key in enumerate(('matches','false_positive_ids','false_negative_ids')):text_counts[index]+=len(text_match[key])
        for kind,m in result['per_class'].items():add_class(kind,m['tp'],m['fp'],m['fn'])
        cases += [dict(case,work_id=gold['work_id'],predicted_work_id=pred['key']) for case in result['cases']]
        gobs={o['id']:o for o in gold['objects']};pobs={o['id']:o for o in objects};matched_g=set();matched_p=set()
        for match in result['matching']['matches']:
            g,p=gobs[match['gold_id']],pobs[match['prediction_id']];matched_g.add(g['id']);matched_p.add(p['id'])
            if g['kind']=='logo' or p['kind']=='logo':
                oracle=g.get('component_truth') or {};candidate=p.get('component_prediction') or {}
                if g['kind']=='logo' and (not oracle.get('complete') or not oracle.get('manually_verified')):logo_unknown+=1
                elif p['kind']=='logo' and not candidate.get('complete'):logo_unknown+=1
                elif g['kind']!='logo':logo_counts[1]+=1
                elif p['kind']!='logo':logo_counts[2]+=1;critical['missing_whole_logo']+=int(truth('whole_logo'))
                elif set(oracle['component_ids'])==set(candidate['component_ids']) and oracle['svg_hash']==candidate['svg_hash']:logo_counts[0]+=1
                else:
                    logo_counts[1]+=1;logo_counts[2]+=1;critical['truncated_or_misgrouped_logo']+=int(truth('whole_logo'))
                    cases.append(dict(work_id=gold['work_id'],gold_id=g['id'],prediction_id=p['id'],reason='WHOLE_LOGO_COMPONENTS_DIFFER',missing_components=sorted(set(oracle['component_ids'])-set(candidate['component_ids'])),extra_components=sorted(set(candidate['component_ids'])-set(oracle['component_ids']))))
            target=person if str(g.get('owner') or '').startswith('p') else company if str(g.get('owner') or '').startswith('c') else None
            if target is None:continue
            mapped=result['root_correspondence'].get(p.get('owner'))
            if mapped is None:
                owner_unknown+=1
                if target is person:person_unknown+=1
                else:company_unknown+=1
            elif mapped==g['owner']:target[0]+=1
            else:
                target[1]+=1;target[2]+=1
                if truth('person_ownership' if target is person else 'company_ownership'):critical['person_owner_mismatch' if target is person else 'company_owner_mismatch']+=1
        for obj in gold['objects']:
            if obj['id'] not in matched_g:
                if obj['kind']=='logo':
                    if (obj.get('component_truth') or {}).get('manually_verified'):logo_counts[2]+=1;critical['missing_whole_logo']+=int(truth('whole_logo'))
                    else:logo_unknown+=1
                if str(obj.get('owner') or '').startswith('p'):person[2]+=1
                elif str(obj.get('owner') or '').startswith('c'):company[2]+=1
        for obj in objects:
            if obj['id'] not in matched_p:
                if obj['kind']=='logo':
                    if (obj.get('component_prediction') or {}).get('complete'):logo_counts[1]+=1
                    else:logo_unknown+=1
                if str(obj.get('owner') or '').startswith('p'):person[1]+=1
                elif str(obj.get('owner') or '').startswith('c'):company[1]+=1
        roots={o['owner'] for o in gold['objects'] if o['kind']=='name' and o.get('owner')};mapped_roots=set(result['root_correspondence'].values());root_missing+=len(roots-mapped_roots)
        mm_errors.append(max(abs(gold['width_mm']-pred['work_width']),abs(gold['height_mm']-pred['work_height'])))
        logo_gold+=sum(o['kind']=='logo' for o in gold['objects']);logo_predictions+=sum(o['kind']=='logo' for o in objects)
        logo_missing_component_truth+=sum(o['kind']=='logo' and not o.get('component_truth') for o in gold['objects'])
    for wid in paired['false_negative_ids']:
        gold=gold_by[wid]
        gt,gcomplete=text_boxes(gold['objects']);text_counts[2]+=len(gt);text_unknown|=not gcomplete
        for obj in gold['objects']:
            if obj['kind']=='logo':
                if (obj.get('component_truth') or {}).get('manually_verified'):logo_counts[2]+=1;critical['missing_whole_logo']+=int(truth('whole_logo'))
                else:logo_unknown+=1
        for obj in gold['objects']:
            add_class(obj['kind'],fn=1)
            if str(obj.get('owner') or '').startswith('p'):person[2]+=1
            elif str(obj.get('owner') or '').startswith('c'):company[2]+=1
        root_missing+=len({o['owner'] for o in gold['objects'] if o['kind']=='name' and o.get('owner')})
        if truth('work_segmentation'):critical['missing_work']+=1
        cases.append(dict(work_id=wid,predicted_work_id=None,reason='MISSING_WHOLE_GOLD_WORK',source_id=prediction['source_id']))
    for wid in paired['false_positive_ids']:
        extra_objects=predicted_objects(pred_by[wid]);pt,pcomplete=text_boxes(extra_objects,True);text_counts[1]+=len(pt);text_unknown|=not pcomplete
        for obj in extra_objects:
            if obj['kind']=='logo':
                if (obj.get('component_prediction') or {}).get('complete'):logo_counts[1]+=1
                else:logo_unknown+=1
            add_class(obj['kind'],fp=1)
            if str(obj.get('owner') or '').startswith('p'):person[1]+=1
            elif str(obj.get('owner') or '').startswith('c'):company[1]+=1
        cases.append(dict(work_id=None,predicted_work_id=wid,reason='EXTRA_PREDICTED_WORK',source_id=prediction['source_id']))
    per_class={kind:counts(*values) for kind,values in sorted(class_counts.items())};gold_objects=sum(len(g['objects']) for g in golds)
    if truth('source_readability'):domains['source_readability']=measured(counts(1,0,0),1,'SOURCE_PAGE_READABILITY;FILES_AGGREGATED_SEPARATELY')
    if truth('work_segmentation'):domains['work_segmentation']=measured(counts(len(paired['matches']),len(paired['false_positive_ids']),len(paired['false_negative_ids'])),len(golds),'ACTUAL_WORK_BOXES',matching=paired)
    if truth('field_types'):domains['field_types']=measured(None,gold_objects,'PER_CLASS_OBSERVATIONS;NO_SCALAR_ACCURACY',per_class=per_class,required_classes=policy['thresholds']['field_types']['required_classes'])
    # Detection TP includes misclassified spatial matches; semantic errors are scored separately.
    tp=sum(v['tp'] for v in per_class.values());fp=sum(v['fp'] for v in per_class.values());fn=sum(v['fn'] for v in per_class.values())
    wrong_kinds=sum(case.get('kind_error',False) for case in cases)
    if truth('text_candidates'):domains['text_candidates']=measured(counts(*text_counts),text_counts[0]+text_counts[2],'ACTUAL_TEXT_BOXES_INCLUDING_ANNOTATION_AND_REVIEWED_LOGO_TEXT')
    if truth('text_candidates') and text_unknown:domains['text_candidates']=unknown('Logo圖文構件中的文字真值不完整；已知bbox統計不能冒充所有文字候選完整率',gold_objects)
    if truth('person_ownership') and not person_unknown:domains['person_ownership']=measured(counts(*person),sum(str(o.get('owner') or '').startswith('p') for g in golds for o in g['objects']),'PERSON_OWNED_OBJECT_ASSIGNMENTS')
    if truth('company_ownership') and not company_unknown:domains['company_ownership']=measured(counts(*company),sum(str(o.get('owner') or '').startswith('c') for g in golds for o in g['objects']),'COMPANY_OWNED_OBJECT_ASSIGNMENTS')
    if truth('person_ownership') and root_missing:critical['missing_person_root']+=root_missing
    if truth('physical_size') and len(mm_errors)==len(golds):
        tolerance=policy['thresholds']['physical_size']['maximum_absolute_error_mm'];domains['physical_size']=measured(None,len(mm_errors),'WORK_MAX_ABSOLUTE_MM_ERROR',errors_mm=mm_errors,maximum_absolute_error_mm=max(mm_errors,default=None),mean_absolute_error_mm=sum(mm_errors)/len(mm_errors) if mm_errors else None,within_explicit_tolerance=sum(error<=tolerance for error in mm_errors),tolerance_mm=tolerance)
    logo_gold=sum(o['kind']=='logo' for g in golds for o in g['objects']);logo_predictions=sum(o['kind']=='logo' for p in works for o in predicted_objects(p))
    domains['whole_logo']=measured(counts(*logo_counts),logo_gold,'MANUALLY_REVIEWED_WHOLE_SOURCE_LOGO_COMPONENT_SETS') if truth('whole_logo') and not logo_unknown and (logo_gold or logo_predictions) else unknown('完整Logo需要原始群組／構件與圖文真值，bbox相符不能證實完整；未當100%',logo_gold)
    domains['whole_logo'].update(recorded_logo_candidates=logo_predictions,missing_component_truth=logo_missing_component_truth)
    domains['customer_style_mapping']=unknown('目前source-only解析器未產生已確認客戶／版型版本推論；不能拿既有人工關聯冒充模型預測')
    for name,domain in domains.items():
        if not truth(name):domain['reason']='此層真值或全來源分母尚未完整核實；未解析／缺gold來源不被排除'
    return dict(domains=domains,conditional_per_class=per_class,required_source_pages=1,unresolved_source_pages=0,gold_work_count=len(golds),predicted_work_count=len(works),gold_object_count=gold_objects,work_matching=paired,unknown_owner_mappings=owner_unknown,missing_person_roots=root_missing,cases=cases,critical_errors=dict(critical),quality_pass=None)
