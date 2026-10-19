"""Stable minimum-cost field/container assignment with explicit source support."""
from collections import defaultdict
from copy import deepcopy
import math

from .training_store import digest


def semantic_observation(kind,value):
    from .semantic_fields import recognize
    row=recognize(value)
    subtype=row['semantic_type'] if row['slot_kind']==kind and row['semantic_type']!='unknown' else kind
    if subtype=='social_id':subtype=kind  # Preserve platform-specific field permission.
    return dict(semantic_type=subtype,basis='DERIVED_FORMAT_CANDIDATE' if subtype!=kind else 'CONFIRMED_FIELD_ROLE',
                subtype_is_not_identity_or_ownership_proof=True,recognizer_version=row['version'])


def assign_fields(profile,facts,policy,options_for):
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    roles={row['key']:row for row in profile['roles'] if row['kind']!='logo'}
    if len(roles)>256:raise ValueError('Source role budget exceeded;not a learned capacity verdict')
    columns=defaultdict(list)
    for key,role in sorted(roles.items()):
        containers=role.get('confirmed_container_keys',[])
        target=containers[0] if len(containers)==1 else key
        columns[target].append(key)
    targets=sorted(columns);text_facts=[row for row in facts if row['kind']!='logo']
    if not text_facts:return dict(status='ASSIGNED',assignments=[],basis='NO_TEXT_FIELDS')
    if len(text_facts)>len(targets):return dict(status='UNSUPPORTED_FIELD_CAPACITY',assignments=[])
    default=set(profile['grammar']['default_order']);cost=np.full((len(text_facts),len(targets)),1e9);selected={}
    for i,fact in enumerate(text_facts):
        for j,target in enumerate(targets):
            keys=columns[target]
            kinds={roles[key]['kind'] for key in keys}
            for key in keys:
                role=roles[key]
                if role['owner_port']!=fact['owner_port'] or role['kind']!=fact['kind']:continue
                if (len(kinds)>1 and key not in default and policy.get('allow_observed_container_substitution') is not True):continue
                options=options_for(fact,key)
                if not options:continue
                # Same semantic port first; alternate same-owner ports are finite,
                # and an explicit relative intent is applied by the later solver.
                preferred_semantics=profile['grammar'].get('default_semantic_roles',{})
                semantic=fact.get('semantic_observation',{}).get('semantic_type',fact['kind'])
                known_targets=[target_key for target_key,value in preferred_semantics.items() if value==semantic]
                semantic_cost=0. if not known_targets or key in known_targets else 2.
                preference=semantic_cost+(0. if key==fact['role_key'] else .5)+j*(.5**(i+1))*1e-4
                if preference<cost[i,j]:cost[i,j]=preference;selected[i,j]=(key,options)
    row_indices,column_indices=linear_sum_assignment(cost)
    if len(row_indices)!=len(text_facts) or any(cost[i,j]>=1e8 for i,j in zip(row_indices,column_indices)):
        return dict(status='NO_SOURCE_SUPPORTED_CONDITIONAL_ASSIGNMENT',assignments=[])
    result=[]
    for i,j in zip(row_indices,column_indices):
        key,options=selected[i,j]
        result.append(dict(render_id=text_facts[i]['render_id'],source_role_key=key,container_key=targets[j],options=options))
    return dict(status='ASSIGNED',assignments=result,
        basis='SCIPY_MIN_COST_ASSIGNMENT_SAME_OWNER_SUPPORTED_SEMANTICS_STABLE_PORT_DEFAULT',
        global_optimal_layout_claim=False)
