"""Scoped actual-result feedback and explicitly curated preference training.

Acceptance alone is not aesthetic truth. Only reviewed same-input comparisons
of TRAIN source data may enter preference fitting; live unknown/heldout orders
remain scoped feedback. Policies never change as a side effect of accepting.
"""
from copy import deepcopy

from .training_store import TrainingStore,digest,text
from .design_learning import CrossWorkLearning
from .design_synthesis import input_facts
from .input_graph import InputGraph
from .design_ranking import train_preferences
from .model import new_id

USE='DESIGN_PREFERENCE_TRAIN_LOCAL'


class DesignFeedback:
    def __init__(self,library):
        self.library=library
        self.store=TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)
        self.learning=CrossWorkLearning(library)

    def result(self,identity):
        row=self.store.get('DESIGN_RESULT',identity)
        if not row or digest({k:v for k,v in row.items() if k not in ('id','revision','content_digest')})!=row['content_digest']:
            raise ValueError('Exact saved feedback result missing or changed')
        return row

    def record(self,before_id,command_id,after_id,accepted,scope,actor,reason=None,category='UNKNOWN'):
        if type(accepted) is not bool or scope not in ('ORDER','CUSTOMER','REVIEWED_STYLE'):
            raise ValueError('Explicit acceptance/rejection and scope required')
        if category not in ('UNKNOWN','PREFERENCE','NECESSARY_CORRECTION','POLICY'):
            raise ValueError('Unknown feedback category')
        text(actor,'Feedback actor',120)
        if reason is not None:text(reason,'Feedback reason',2048)
        before=self.result(before_id);after=self.result(after_id);command=self.store.get('DESIGN_COMMAND',command_id)
        if (not command or before['session_id']!=after['session_id'] or command['session_id']!=after['session_id']):
            raise ValueError('Feedback must reference actual before/intent/after of the same draft')
        value=dict(before=dict(id=before_id,digest=before['content_digest']),
            intent=dict(id=command_id,digest=digest(command),command=deepcopy(command['command'])),
            after=dict(id=after_id,digest=after['content_digest']),session_id=after['session_id'],
            accepted=accepted,scope=scope,actor=actor,reason=reason,reason_status='KNOWN' if reason else 'UNKNOWN',
            category=category,same_input=before['input_digest']==after['input_digest'],global_policy_changed=False,
            preference_eligible=False,reference_status='EXACT_LOCAL_RESULT_COMMAND_REFERENCES')
        with self.store.transaction():return self.store._write('DESIGN_FEEDBACK',new_id(),value,0,'exact_scoped_design_feedback_saved')

    def curate(self,feedback_id,sample_id,actor,permission,evidence,approved=False):
        if not approved or permission.get('use')!=USE:raise ValueError('Explicit new-purpose preference training review required')
        text(actor,'Preference curator',120);text(permission.get('basis'),'Preference use basis',2048);text(evidence,'Independent preference comparison',2048)
        feedback=self.store.get('DESIGN_FEEDBACK',feedback_id)
        if not feedback or feedback.get('category')!='PREFERENCE' or not feedback.get('same_input'):
            raise ValueError('Correction/policy/unknown or different-input feedback is not preference training truth')
        before=self.result(feedback['before']['id']);after=self.result(feedback['after']['id'])
        if before['content_digest']!=feedback['before']['digest'] or after['content_digest']!=feedback['after']['digest']:
            raise ValueError('Feedback result references changed')
        model,dataset=self.learning.checked_model(after['model_id'])
        entry=next((row for row in dataset['entries'] if row['sample_id']==sample_id),None)
        if not entry or entry['role']!='TRAIN':raise ValueError('Unknown/validation/holdout data cannot enter preference fitting')
        graph=InputGraph(after.get('input_graph') or {})
        sample=self.store.get('SAMPLE',sample_id)
        actual={row['role_key']:row['value'] for row in input_facts(graph)}
        from .design_profiles import role_key
        slots={row['id']:row for row in sample['label_slots']};expected={}
        for label in sample['positive_labels']:
            slot=slots[label['slot_id']];value=label['text']
            binding=self.store.get('DESIGN_SOURCE_BINDING',digest([sample['work_id'],slot['id']]))
            prefix=(binding or {}).get('review',{}).get('label_binding',{})
            if prefix.get('kind')=='DYNAMIC_PREFIX':value=value.removeprefix(prefix['prefix'])
            expected[role_key(slot)]=value
        from .trusted_sample_pool import source_restriction
        if source_restriction(self.store,sample['pins']['source_hash'],USE):raise ValueError('Preference source use has been stopped')
        if actual!=expected:raise ValueError('Query is not the reviewed TRAIN source data;live unknown orders remain feedback only')
        if not before['selected'] or not after['selected']:raise ValueError('Two actual legal layouts required')
        winner,loser=(after,before) if feedback['accepted'] else (before,after)
        if winner['selected']['geometry_digest']==loser['selected']['geometry_digest']:
            raise ValueError('Identical layouts provide no preference evidence')
        value=dict(feedback_id=feedback_id,feedback_digest=digest(feedback),sample_id=sample_id,
            sample_revision=sample['revision'],sample_scope=sample['scope_digest'],source_group=entry['lineage_group'],
            model_id=model['id'],weights_digest=model['weights_digest'],role='TRAIN',
            query_id=digest([entry['lineage_group'],actual]),winner=deepcopy(winner['selected']['features']),
            loser=deepcopy(loser['selected']['features']),label_source='EXPLICIT_INDEPENDENT_COMPARISON',
            evidence_refs=[evidence],permission=deepcopy(permission),actor=actor)
        with self.store.transaction():return self.store._write('DESIGN_PREFERENCE_EXAMPLE',new_id(),value,0,'reviewed_actual_training_preference_saved')

    def checked_example(self,identity):
        row=self.store.get('DESIGN_PREFERENCE_EXAMPLE',identity)
        if not row:raise ValueError('Preference example missing')
        sample=self.store.get('SAMPLE',row['sample_id']);feedback=self.store.get('DESIGN_FEEDBACK',row['feedback_id'])
        if (self.store.sample_state(row['sample_id'])!='APPROVED' or sample['revision']!=row['sample_revision']
                or sample['scope_digest']!=row['sample_scope'] or not feedback or digest(feedback)!=row['feedback_digest']):
            raise ValueError('Preference source/feedback changed or withdrawn')
        from .trusted_sample_pool import source_restriction
        if source_restriction(self.store,sample['pins']['source_hash'],USE):raise ValueError('Preference source use has been stopped')
        model,_=self.learning.checked_model(row['model_id'])
        if model['weights_digest']!=row['weights_digest']:raise ValueError('Preference producing model changed')
        for ref in ('before','after'):
            result=self.result(feedback[ref]['id'])
            if result['content_digest']!=feedback[ref]['digest']:raise ValueError('Preference exact result changed')
        return row

    def train(self,example_ids,actor,approved=False):
        if not approved or not isinstance(example_ids,list) or len(set(example_ids))!=len(example_ids):
            raise ValueError('Explicit unique curated preference set required')
        text(actor,'Preference training actor',120)
        rows=[self.checked_example(identity) for identity in sorted(example_ids)]
        if len({row['source_group'] for row in rows})<2:raise ValueError('At least two independent TRAIN query groups required')
        artifact=train_preferences(rows)
        with self.store.transaction():
            if [self.checked_example(identity) for identity in sorted(example_ids)]!=rows:raise ValueError('Preference evidence changed during fitting')
            return self.store._write('DESIGN_RANKER',new_id(),dict(state='PENDING',actor=actor,artifact=artifact,
                weights_digest=digest(artifact),examples=[dict(id=row['id'],revision=row['revision'],digest=digest(row)) for row in rows],
                qualification='PREVIEW_ONLY_NOT_AESTHETIC_OR_PRODUCTION_QUALIFICATION'),0,'curated_preference_model_trained_not_activated')

    def checked_ranker(self,identity):
        model=self.store.get('DESIGN_RANKER',identity)
        if not model or digest(model['artifact'])!=model['weights_digest']:raise ValueError('Preference weights missing or changed')
        for ref in model['examples']:
            row=self.checked_example(ref['id'])
            if row['revision']!=ref['revision'] or digest(row)!=ref['digest']:raise ValueError('Preference support changed')
        return model

    def activate(self,identity,expected_revision,actor,policy,approved=False):
        if not approved or type(policy.get('production')) is not bool:raise ValueError('Explicit preference activation scope required')
        text(actor,'Preference policy reviewer',120);text(policy.get('version'),'Preference policy version',128)
        with self.store.transaction():
            model=self.checked_ranker(identity)
            if policy['production']:
                from .design_rank_qualification import RankerQualification
                RankerQualification(self.library).checked(policy.get('qualification_id','missing'),identity)
            return self.store._write('DESIGN_RANKER_ACTIVE','local-preference',dict(model_id=identity,
                weights_digest=model['weights_digest'],actor=actor,policy=deepcopy(policy)),expected_revision,
                'qualified_production_preference_model_activated' if policy['production'] else 'preview_preference_model_activated')
