"""Quarantine actual executable/parameter identities, never display names or IDs."""
from .training_store import digest


def components(manifest):
    modules=manifest['source_modules']
    parser={name:modules.get(name) for name in ('source_analysis.py','source_text_evidence.py','quality_logo.py','semantic_fields.py')}
    ocr=manifest.get('ocr')
    if ocr:parser['quality_ocr.py']=modules.get('quality_ocr.py')
    parser.update(renderer=manifest['renderer'],fonts=manifest['environment']['fonts'],
                  semantic_parameters=manifest.get('effective_semantic_digest',manifest.get('semantic_weights_digest')),
                  ocr=dict(configuration=ocr['configuration'],runtime=ocr['runtime'],models=[{key:m[key] for key in ('language','sha256','bytes')} for m in ocr['models']]) if ocr else None)
    result=[dict(kind='PARSER',key=digest(['PARSER',parser]),behaviour=parser)]
    if manifest.get('semantic_model_id'):
        model=dict(algorithm=modules.get('semantic_fields.py'),parameters=manifest.get('effective_semantic_digest',manifest['semantic_weights_digest']))
        result.append(dict(kind='MODEL',key=digest(['MODEL',model]),behaviour=model))
    for rule in manifest.get('rule_records',[]):
        behaviour={key:rule[key] for key in ('action','literal','normalization','scope')}
        behaviour['algorithm']={name:modules.get(name) for name in ('quality_rules.py','noise_review.py','noise.py')}
        result.append(dict(kind='RULE',rule_id=rule['id'],key=digest(['RULE',behaviour]),behaviour=behaviour))
    return result


def blockers(store,pipeline):
    errors=[]
    direct=store.get('QUALITY_PIPELINE_QUARANTINE',pipeline['id'])
    if direct:errors.append(dict(kind='PIPELINE',key=pipeline['id'],case_id=direct['case_id']))
    for component in components(pipeline['manifest']):
        quarantine=store.get('QUALITY_COMPONENT_QUARANTINE',component['key'])
        if quarantine:errors.append(dict(kind=component['kind'],key=component['key'],case_id=quarantine['case_id']))
    return errors
