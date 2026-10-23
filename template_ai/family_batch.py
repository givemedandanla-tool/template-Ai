"""Family review batches use the existing durable job lease and per-item ledger."""
from collections import Counter
from copy import deepcopy

from .family_workspace import FamilyWorkspace
from .family_rules import FamilyRuleDrafts, apply_rule
from .family_scenarios import FamilyScenarios
from .design_jobs import DesignJobs
from .training_store import digest, text


class FamilyBatches:
    def __init__(self, library):
        self.workspace = FamilyWorkspace(library)
        self.library = library
        self.rules = FamilyRuleDrafts(library)
        self.jobs = DesignJobs(library)

    def plan_rules(self, refs, operation):
        if not isinstance(refs, list) or not refs or len(refs) > 10000 or len({digest(r) for r in refs}) != len(refs):
            raise ValueError('Select distinct exact family versions')
        items = []
        for ref in refs:
            try:
                _, _, profile = self.workspace.resolve(ref)
                changed = apply_rule(profile, operation)
                state, reason = ('READY', None) if changed != profile else ('NO_CHANGE', 'No effective difference')
                after = digest(changed)
            except (ValueError, KeyError) as error:
                state, reason, after = 'BLOCKED', str(error), None
            items.append(dict(ref=deepcopy(ref), operation=deepcopy(operation), precheck=state,
                              reason=reason, proposed_profile_digest=after))
        plan = dict(kind='FAMILY_RULE_BATCH', items=items, scope='NEW_RULE_DRAFTS_ONLY_NOT_SOURCE_OR_PUBLICATION')
        plan['digest'] = digest(plan)
        return plan

    def submit(self, plan, actor, approved=False):
        text(actor, 'Batch author', 120)
        if not approved or digest({k:v for k,v in plan.items() if k != 'digest'}) != plan.get('digest'):
            raise ValueError('Review and explicitly approve the exact batch differences')
        if plan.get('kind') != 'FAMILY_RULE_BATCH':
            raise ValueError('Unsupported family batch plan')
        return self.jobs.create('FAMILY_RULE_BATCH', dict(items=deepcopy(plan['items']),
                                reviewed_plan_digest=plan['digest']), actor, True)

    def cases(self, case_ids, actor, draft_id=None):
        if not isinstance(case_ids, list) or not case_ids or len(set(case_ids)) != len(case_ids):
            raise ValueError('Select distinct saved scenarios')
        scenarios = FamilyScenarios(self.library)
        draft = self.rules.current(draft_id) if draft_id else None
        items = []
        for identity in case_ids:
            case = scenarios.current(identity)
            if draft and case['ref'] != draft['base_ref']:
                raise ValueError('Scenario and draft family versions differ')
            items.append(dict(ref=case['ref'], case_id=identity, case_revision=case['revision'],
                              draft_id=draft_id, draft_revision=draft['revision'] if draft else None))
        return self.jobs.create('FAMILY_CASE_REVIEW', dict(items=items), actor, True)

    def undo(self, job_id, actor):
        job = self.jobs.current(job_id)
        if job['kind'] != 'FAMILY_RULE_BATCH':
            raise ValueError('Choose a rule batch to undo')
        items = [dict(ref=result['ref'], draft_id=result['draft_id'], draft_revision=result['draft_revision'])
                 for result in self.jobs.results(job_id) if result.get('status') in ('APPLIED', 'ALREADY_APPLIED')]
        if not items:
            raise ValueError('No committed rule edits in this batch')
        return self.jobs.create('FAMILY_RULE_UNDO', dict(items=items, original_job=job_id), actor, True)

    def review_sources(self,refs,actor,*,representative_only=False):
        frozen=self.workspace.freeze_selection(refs)
        items=[]
        for i,ref in enumerate(frozen['refs']):
            _,_,profile=self.workspace.resolve(ref)
            members=[r['example_id'] for r in self.workspace.representatives(ref)['selected']] if representative_only else profile['source_members']
            items.extend(dict(ref_index=i,sample_id=sample) for sample in sorted(members))
            if not representative_only:
                from .family_workspace import records
                for case in records(self.workspace.store,'FAMILY_CASE'):
                    if case['ref']==ref:items.append(dict(ref_index=i,case_id=case['id'],case_revision=case['revision']))
        return self.jobs.create('FAMILY_SOURCE_REVIEW',dict(items=items,refs=frozen['refs'],
            scope='REPRESENTATIVE_TRAIN_REPLAYS' if representative_only else 'ALL_SELECTED_TRAIN_MEMBERS_AND_SAVED_CASES',
            aesthetic_qualification=False),actor,True)


def execute_family_item(library, job, index):
    item = job['plan']['items'][index]
    if 'ref_index' in item:item=dict(item,ref=job['plan']['refs'][item['ref_index']])
    key = digest([job['id'], index]); workspace = FamilyWorkspace(library)
    try:
        workspace.resolve(item['ref'])
        if job['kind']=='FAMILY_SOURCE_REVIEW':
            scenarios=FamilyScenarios(library)
            case=scenarios.from_source(item['ref'],item['sample_id'],job['actor']) if 'sample_id' in item else scenarios.current(item['case_id'],item['case_revision'])
            run=scenarios.run(case['id'],case['revision'],request_id=key)
            return dict(status=run['status'],ref=item['ref'],run_id=run['id'],integrity=run['integrity'],
                        placement_digest=run['placement_digest'],source_replay=True,aesthetic_qualification=False)
        if job['kind'] == 'FAMILY_CASE_REVIEW':
            run = FamilyScenarios(library).run(item['case_id'], item['case_revision'], draft_id=item['draft_id'],
                    draft_revision=item['draft_revision'], request_id=key)
            return dict(status=run['status'], ref=item['ref'], run_id=run['id'],
                        integrity=run['integrity'], placement_digest=run['placement_digest'])
        rules = FamilyRuleDrafts(library)
        if job['kind'] == 'FAMILY_RULE_BATCH':
            if item['precheck'] != 'READY':
                return dict(status='SKIPPED_'+item['precheck'], ref=item['ref'], reason=item['reason'])
            _, _, profile = workspace.resolve(item['ref'])
            if digest(apply_rule(profile, item['operation'])) != item['proposed_profile_digest']:
                raise ValueError('Batch preflight differences changed')
            identity = 'batch-draft-'+key[:40]
            draft = rules.store.get('FAMILY_DRAFT', identity)
            if not draft:
                draft = rules.create(item['ref'], job['actor'], 'Batch rule draft', draft_id=identity)
            if draft['base_ref'] != item['ref']:
                raise ValueError('Existing batch draft refers to a different family')
            result = rules.command(identity, 1, key, 'APPLY', job['actor'], item['operation'])
            state = 'ALREADY_APPLIED' if result.get('replayed') else 'APPLIED'
            if result.get('original_revision', result['revision']) != result['revision']:
                state = 'APPLIED_CURRENT_CHANGED'
            return dict(status=state, ref=item['ref'], draft_id=identity, draft_revision=result['revision'],
                        content_digest=result['content_digest'], source_or_model_changed=False)
        result = rules.command(item['draft_id'], item['draft_revision'], key, 'UNDO', job['actor'])
        state='UNDONE_CURRENT_CHANGED' if result.get('original_revision',result['revision']) != result['revision'] else 'UNDONE'
        return dict(status=state, ref=item['ref'], draft_id=result['id'], draft_revision=result['revision'])
    except (ValueError, KeyError, OSError) as error:
        return dict(status='STALE_OR_BLOCKED', ref=item['ref'], reason=str(error), wrote_unchecked_changes=False)


def summarize_family_job(results):
    return dict(items=len(results), outcomes=dict(Counter(r['status'] for r in results)),
                scope='LOCAL_ENGINEERING_REVIEW_NOT_PRODUCTION_OR_AESTHETIC_APPROVAL',
                all_hard_checks_pass=bool(results) and all(r.get('integrity', {}).get('status') == 'PASS' for r in results if isinstance(r.get('integrity'), dict))
                                    and all(r['status'] == 'FEASIBLE_PREVIEW' for r in results),
                published_templates=0, private_data_uploaded=False)
