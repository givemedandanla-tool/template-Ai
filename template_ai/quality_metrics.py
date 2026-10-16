"""Explicit detection/classification metrics; no production acceptance thresholds.

Pair boxes without their semantic labels, maximizing cardinality then total IoU.
This avoids a correct-label preference hiding misclassification. Integer-weight
Edmonds matching is supplied by NetworkX; undefined denominators stay unknown.
"""
import math
from statistics import NormalDist
import networkx as nx

VERSION='BOX_IOU_MAX_CARDINALITY_INT12_CLASS_AGNOSTIC_VERIFIED_LOGO_ROOT_V2'
MAX_OBJECTS=200


def box(value):
    if not isinstance(value,dict) or set(value)!={'x','y','w','h'} or any(type(v) not in (float,int) or not math.isfinite(v) for v in value.values()) or value['w']<=0 or value['h']<=0:raise ValueError('框位需完整有限座標及正寬高，壞框不能靜默排除分母')
    if not all(math.isfinite(v) for v in (value['x']+value['w'],value['y']+value['h'],value['w']*value['h'])) or value['w']*value['h']<=0:raise ValueError('框位面積／邊界超出可核對數值範圍')
    return value


def iou(left,right):
    a,b=box(left),box(right)
    width=max(0,min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x']))
    height=max(0,min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y']))
    intersection=width*height
    scale=max(a['w']*a['h'],b['w']*b['h']);fraction=intersection/scale
    return fraction/(a['w']*a['h']/scale+b['w']*b['h']/scale-fraction)


def checked_rows(rows):
    if not isinstance(rows,list) or len(rows)>MAX_OBJECTS:raise ValueError('單作品最多200個明列物件；未截斷當完整')
    if any(not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or len(row['id'])>128 for row in rows) or len({row['id'] for row in rows})!=len(rows):raise ValueError('物件需不重複的exact ID')
    for row in rows:box(row.get('rect'))
    return sorted(rows,key=lambda row:row['id'])


def match_boxes(gold,predictions,minimum_iou):
    if type(minimum_iou) not in (float,int) or not math.isfinite(minimum_iou) or not 0<minimum_iou<=1:raise ValueError('需明確核准0<IoU≤1的配對口徑；沒有預設經驗門檻')
    actual=checked_rows(gold);predicted=checked_rows(predictions);graph=nx.Graph();overlaps={}
    for g in actual:graph.add_node(('G',g['id']))
    for p in predicted:graph.add_node(('P',p['id']))
    for g in actual:
        for p in predicted:
            overlap=iou(g['rect'],p['rect'])
            if overlap>=minimum_iou:
                graph.add_edge(('G',g['id']),('P',p['id']),weight=round(overlap*10**12));overlaps[(g['id'],p['id'])]=overlap
    paired=[]
    for left,right in nx.max_weight_matching(graph,maxcardinality=True,weight='weight'):
        g,p=(left,right) if left[0]=='G' else (right,left);paired.append(dict(gold_id=g[1],prediction_id=p[1],iou=overlaps[(g[1],p[1])]))
    paired.sort(key=lambda row:(row['gold_id'],row['prediction_id']))
    gs={row['gold_id'] for row in paired};ps={row['prediction_id'] for row in paired}
    return dict(version=VERSION,minimum_iou=minimum_iou,matching_uses_semantic_labels=False,matches=paired,false_negative_ids=[r['id'] for r in actual if r['id'] not in gs],false_positive_ids=[r['id'] for r in predicted if r['id'] not in ps])


def counts(tp,fp,fn):
    if any(type(value) is not int or value<0 for value in (tp,fp,fn)):raise ValueError('TP/FP/FN需非負整數')
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def classification_metrics(gold,predictions,minimum_iou):
    matching=match_boxes(gold,predictions,minimum_iou);actual={r['id']:r for r in gold};predicted={r['id']:r for r in predictions}
    if any(not isinstance(row.get('kind'),str) or not row['kind'] or len(row['kind'])>120 for row in gold+predictions):raise ValueError('分類指標需明確類別，沒有把未知猜成正解')
    classes={kind:[0,0,0] for kind in sorted({r['kind'] for r in gold+predictions})};cases=[];root_candidates={};inverse={}
    for pair in matching['matches']:
        g,p=actual[pair['gold_id']],predicted[pair['prediction_id']]
        oracle=g.get('component_truth') or {};candidate=p.get('component_prediction') or {}
        logo_anchor=(g['kind']=='logo' and oracle.get('manually_verified') and oracle.get('complete') and candidate.get('complete') and oracle.get('svg_hash')==candidate.get('svg_hash') and set(oracle.get('component_ids',[]))==set(candidate.get('component_ids',[])))
        if g['kind']==p['kind'] and (g['kind'] in ('name','company') or logo_anchor) and g.get('owner') and p.get('owner'):
            root_candidates.setdefault(p['owner'],set()).add(g['owner']);inverse.setdefault(g['owner'],set()).add(p['owner'])
    root_map={p:next(iter(gs)) for p,gs in root_candidates.items() if len(gs)==1 and len(inverse[next(iter(gs))])==1}
    critical=0;unknown_owners=0;known_owner_pairs=0
    for pair in matching['matches']:
        g,p=actual[pair['gold_id']],predicted[pair['prediction_id']];kind_error=g['kind']!=p['kind']
        if kind_error:classes[g['kind']][2]+=1;classes[p['kind']][1]+=1
        else:classes[g['kind']][0]+=1
        mapped=root_map.get(p.get('owner'));owner_error=None
        if g.get('owner') or p.get('owner'):
            if mapped is None:unknown_owners+=1
            else:owner_error=mapped!=g.get('owner');critical+=int(owner_error);known_owner_pairs+=1
        if kind_error or owner_error is True or mapped is None and (g.get('owner') or p.get('owner')):cases.append(dict(gold_id=g['id'],prediction_id=p['id'],gold_kind=g['kind'],predicted_kind=p['kind'],gold_owner=g.get('owner'),predicted_owner=p.get('owner'),mapped_owner=mapped,kind_error=kind_error,critical_owner_error=owner_error,iou=pair['iou']))
    for identity in matching['false_negative_ids']:classes[actual[identity]['kind']][2]+=1;cases.append(dict(gold_id=identity,prediction_id=None,gold_kind=actual[identity]['kind'],gold_rect=actual[identity]['rect'],gold_owner=actual[identity].get('owner'),reason='MISSING_GOLD_OBJECT'))
    for identity in matching['false_positive_ids']:classes[predicted[identity]['kind']][1]+=1;cases.append(dict(gold_id=None,prediction_id=identity,predicted_kind=predicted[identity]['kind'],predicted_rect=predicted[identity]['rect'],predicted_owner=predicted[identity].get('owner'),reason='EXTRA_PREDICTED_OBJECT'))
    return dict(matching=matching,per_class={kind:counts(*values) for kind,values in classes.items()},detection=counts(len(matching['matches']),len(matching['false_positive_ids']),len(matching['false_negative_ids'])),critical_owner_errors=critical,unknown_owner_mappings=unknown_owners,known_owner_pairs=known_owner_pairs,root_correspondence=root_map,cases=cases,quality_pass=None,reason='僅定義口徑的描述指標；正式品質還需合法獨立樣本、完整真值、核准門檻與版本條件')


def wilson_interval(successes,total,confidence):
    if type(successes) is not int or type(total) is not int or not 0<=successes<=total or type(confidence) not in (float,int) or not math.isfinite(confidence) or not 0<confidence<1:raise ValueError('區間需明確成功數／獨立群組總數及信賴水準')
    if total==0:return None
    z=-NormalDist().inv_cdf((1-confidence)/2)
    if not math.isfinite(z) or z<=0:raise ValueError('信賴水準超出可核對浮點口徑')
    p=successes/total;denominator=1+z*z/total
    middle=(p+z*z/(2*total))/denominator;radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    return dict(lower=max(0,middle-radius),upper=min(1,middle+radius),confidence=confidence,independent_groups=total,successes=successes,method='WILSON_SCORE_BINOMIAL_GROUP_OUTCOMES',not_per_field_independence_claim=True)
