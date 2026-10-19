"""Persist independent graded relevance for actual heldout layout slates.

Incomplete/unlabelled queries remain unknown. NDCG uses sklearn's standard tie
handling; uncertainty resamples independent source groups, not correlated rows.
"""
from collections import defaultdict
from .training_store import digest,text
from .design_evaluation import DesignEvaluation


class RankingEvaluation(DesignEvaluation):
    def review(self,job_id,index,relevance,actor,evidence,approved=False):
        if not approved:raise ValueError('Explicit independent relevance review is required')
        text(actor,'Ranking reviewer',120);text(evidence,'Ranking evidence',2048)
        job=self.jobs.current(job_id);row=self.store.get('DESIGN_JOB_ITEM',self.jobs.item_key(job_id,index))
        if job['kind']!='EVALUATE_LAYOUTS' or not row:raise ValueError('Actual heldout outputs must exist first')
        slate=row['result']['learned'].get('ranking_slate',[]);identities={item['id'] for item in slate}
        if (not isinstance(relevance,dict) or set(relevance)!=identities or not identities
                or any(type(value) is not int or not 0<=value<=3 for value in relevance.values())):
            raise ValueError('Every actual candidate needs an independent relevance grade from 0 to 3')
        value=dict(job_id=job_id,index=index,result_digest=row['result_digest'],relevance=dict(relevance),
            actor=actor,evidence=evidence,label_source='EXPLICIT_INDEPENDENT_GRADED_REVIEW',role=row['result']['role'])
        identity=digest([job_id,index,row['result_digest']])
        with self.store.transaction():
            if self.store.get('DESIGN_RANK_REVIEW',identity):raise ValueError('Frozen ranking review already exists')
            return self.store._write('DESIGN_RANK_REVIEW',identity,value,0,'actual_heldout_slate_independently_graded')

    def report(self,job_id,k=3):
        import numpy as np
        from sklearn.metrics import ndcg_score
        if type(k) is not int or not 1<=k<=10:raise ValueError('Ranking k must be from 1 to 10')
        job=self.jobs.current(job_id);rows=self.jobs.results(job_id);groups=defaultdict(list);unknown=0;queries=[]
        if job['kind']!='EVALUATE_LAYOUTS':raise ValueError('Ranking report requires actual layout evaluation')
        for index,result in enumerate(rows):
            row=self.store.get('DESIGN_JOB_ITEM',self.jobs.item_key(job_id,index))
            slate=result['learned'].get('ranking_slate',[])
            review=self.store.get('DESIGN_RANK_REVIEW',digest([job_id,index,row['result_digest']]))
            if (not review or review['result_digest']!=row['result_digest'] or len(slate)<2
                    or not any(review['relevance'].values())):
                unknown+=1;continue
            grades=[review['relevance'][item['id']] for item in slate]
            scores=list(range(len(slate),0,-1))
            metric=float(ndcg_score([grades],[scores],k=k))
            baseline=[review['relevance'][identity] for identity in result['learned'].get('baseline_order',[item['id'] for item in slate])]
            baseline_metric=float(ndcg_score([baseline],[scores],k=k))
            hit=int(max(grades[:k])==max(grades))
            group=result['lineage_group'];groups[group].append((metric,hit,baseline_metric))
            queries.append(dict(case_id=result['case_id'],lineage_group=group,ndcg_at_k=metric,
                baseline_ndcg_at_k=baseline_metric,top_k_best_hit=hit))
        means=[sum(value[0] for value in items)/len(items) for items in groups.values()]
        hits=[sum(value[1] for value in items)/len(items) for items in groups.values()]
        interval=None
        if len(means)>=2:
            rng=np.random.default_rng(0);a=np.asarray(means)
            boot=np.asarray([rng.choice(a,len(a),replace=True).mean() for _ in range(2000)])
            interval=np.quantile(boot,[.025,.975]).tolist()
        report=dict(job_id=job_id,k=k,origin=job['plan']['origin'],queries=queries,
            denominator=len(rows),known_queries=len(queries),unknown_queries=unknown,independent_groups=len(groups),
            group_macro_ndcg_at_k=sum(means)/len(means) if means else None,
            group_macro_top_k_best_hit=sum(hits)/len(hits) if hits else None,
            baseline_group_macro_ndcg_at_k=(sum(sum(v[2] for v in items)/len(items) for items in groups.values())/len(groups)
                if groups else None),
            ndcg_group_bootstrap_95=interval,bootstrap_seed=0,bootstrap_replicates=2000,
            uncertainty='KNOWN_LINEAGE_GROUP_BOOTSTRAP;FEW_GROUPS_AND_INCOMPLETE_LABELS_LIMIT_INFERENCE',
            scope='SEARCHED_TOP_10_ACTUAL_LAYOUTS_ONLY;NO_AESTHETIC_LABEL_INFERRED_FROM_GEOMETRY',
            production_qualification='NOT_GRANTED_BY_THIS_REPORT')
        report['digest']=digest(report)
        with self.store.transaction():
            if not self.store.get('DESIGN_RANK_REPORT',report['digest']):
                self.store._write('DESIGN_RANK_REPORT',report['digest'],report,0,'heldout_ranking_metrics_saved_no_fit')
        return report
