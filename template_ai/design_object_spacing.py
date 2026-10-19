"""Independent-lineage evidence for equal object gaps, separate from text gaps."""
from collections import defaultdict
from statistics import median

from .training_store import digest


def learn_object_spacing(examples, *, tolerance=.005, minimum_support=5):
    if not 0<=tolerance<=.05 or type(minimum_support) is not int or minimum_support<5:
        raise ValueError('Invalid object-spacing learning policy')
    observations=defaultdict(list)
    for example in examples:
        if example.get('role')!='TRAIN':raise ValueError('Object spacing fits TRAIN only')
        if len(example['fields'])>64:raise ValueError('Object spacing field budget exceeded')
        owners=defaultdict(list)
        for field in example['fields']:owners[field['owner']].append(field)
        for owner,fields in owners.items():
            for axis,perpendicular,size,other_size in [('x','y','w','h'),('y','x','h','w')]:
                tracks=[]
                for field in sorted(fields,key=lambda f:(f['rect'][perpendicular],f['id'])):
                    rect=field['rect'];lo=rect[perpendicular];hi=lo+rect[other_size]
                    match=next((track for track in tracks if min(hi,track['hi'])>max(lo,track['lo'])),None)
                    if match is None:tracks.append(dict(lo=lo,hi=hi,fields=[field]))
                    else:match['lo']=max(match['lo'],lo);match['hi']=min(match['hi'],hi);match['fields'].append(field)
                for track in tracks:
                    if len(track['fields'])<3:continue
                    ordered=sorted(track['fields'],key=lambda f:(f['rect'][axis],f['id']))
                    roles=tuple(f['owner']+':'+f['kind']+':'+str(f.get('index',0)) for f in ordered)
                    dimension=example['width_mm'] if axis=='x' else example['height_mm']
                    gaps=[(b['rect'][axis]-a['rect'][axis]-a['rect'][size])/dimension for a,b in zip(ordered,ordered[1:])]
                    observations[(axis,owner,roles)].append(dict(group=example['lineage_group'],source=example['id'],gaps=gaps,
                        equal=min(gaps)>=0 and max(gaps)-min(gaps)<=tolerance))
    rules=[]
    for (axis,owner,roles),rows in sorted(observations.items()):
        groups=defaultdict(list)
        for row in rows:groups[row['group']].append(row)
        positive={g for g,items in groups.items() if all(item['equal'] for item in items)}
        negative=set(groups)-positive
        gap=median([median([median(item['gaps']) for item in items]) for group,items in groups.items() if group in positive]) if positive else None
        rule=dict(axis=axis,owner_port=owner,roles=list(roles),independent_support=len(positive),
            counterexample_groups=sorted(negative),source_refs=sorted(row['source'] for row in rows),
            normalized_gap=gap,tolerance=tolerance,
            status='SHARED_SOFT_EQUAL_GAP' if len(positive)>=minimum_support and not negative else 'UNKNOWN_OR_CONTRADICTED',
            scope='OBJECT_GAPS_NOT_WORD_OR_CHARACTER_SPACING;SOFT_NOT_PRINT_TOLERANCE')
        rule['id']=digest(rule);rules.append(rule)
    return rules


def apply_object_spacing(solver,variables,facts,rules,width,height):
    import kiwisolver as kiwi
    by_role={fact['role_key']:fact['render_id'] for fact in facts}
    for rule in rules:
        if rule['status']!='SHARED_SOFT_EQUAL_GAP' or not all(role in by_role for role in rule['roles']):continue
        axis=0 if rule['axis']=='x' else 1;size=2 if axis==0 else 3
        dimension=width if axis==0 else height
        shared=kiwi.Variable('object-gap-'+rule['id'])
        solver.addConstraint((shared==rule['normalized_gap']*dimension)|kiwi.strength.weak)
        for left,right in zip(rule['roles'],rule['roles'][1:]):
            a=variables[by_role[left]];b=variables[by_role[right]]
            solver.addConstraint((b[axis]-a[axis]-a[size]==shared)|kiwi.strength.medium)
