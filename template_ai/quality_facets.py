"""Small fixed-gold descriptors; not inferred completeness or identity."""
from .training_store import digest


def describe(golds,manifest):
    sizes=set();people=set();logos=set();customers=set();kinds=set();groups=set()
    for gold in golds:
        sizes.add(f"{gold['width_mm']:g}x{gold['height_mm']:g}")
        people.add(str(len({o.get('owner') for o in gold['objects'] if o['kind']=='name' and o.get('owner')})))
        customer=(gold.get('mapping_truth') or {}).get('customer_id');customers.add(customer or 'UNKNOWN')
        for obj in gold['objects']:
            kinds.add(obj['kind'])
            if obj['kind']=='logo':
                truth=obj.get('component_truth') or {};text=set(truth.get('text_paint_ids',[]));other=set(truth.get('component_ids',[]))-text
                logos.add('UNKNOWN' if not truth.get('manually_verified') or not truth.get('text_content_manually_reviewed') else 'TEXT_AND_VECTOR' if text and other else 'TEXT_ONLY' if text else 'VECTOR_ONLY')
        for component in manifest['group_components']:
            if 'CONTENT:'+gold['source_hash'] in component:groups.add(digest(component))
    if not logos:logos.add('NO_LOGO' if golds and all(g['domain_truth']['whole_logo']=='MANUALLY_VERIFIED' for g in golds) else 'UNKNOWN')
    return dict(size=sorted(sizes) or ['UNKNOWN'],people=sorted(people) or ['UNKNOWN'],logo=sorted(logos),
                customer=sorted(customers) or ['UNKNOWN'],field_type=sorted(kinds),group=sorted(groups) or ['UNKNOWN'],
                role=[manifest.get('evaluation_role','HOLDOUT')],multi_work=['YES' if len(golds)>1 else 'NO'] if manifest['whole_source_gold_complete'] else ['UNKNOWN'],
                descriptors_are_fixed_gold_metadata_not_quality_pass=True)
