from copy import deepcopy
from unittest.mock import patch

from family_fixture import FamilyFixture
from template_ai.family_scenarios import FamilyScenarios
from template_ai.family_batch import FamilyBatches
from template_ai.design_jobs import run_design_job
from template_ai.design_synthesis import synthesize, _font_options
from template_ai.input_graph import InputGraph
from template_ai.training_store import digest
from template_ai.family_rules import apply_rule
from template_ai.design_evaluation import check_layout


class FamilyReviewExtensionTests(FamilyFixture):
    def graph(self):
        return InputGraph.from_legacy([dict(name='Alex Example',title='Designer',phone='+1 202 555 0100',email='alex@example.test')],[])

    def test_hard_source_relation_is_solved_and_independently_rechecked_after_geometry_tamper(self):
        relation=next(r for r in self.profile['relations'] if r['residuals']['left_delta'].get('support',0)>=5)
        profile=apply_rule(self.profile,dict(kind='RELATION_STRENGTH',left=relation['left'],right=relation['right'],metric='left_delta',strength='HARD'))
        graph=self.graph();result=synthesize(profile,graph,90,54,dict(version='authored-hard',approved=True))
        self.assertTrue(result['candidates']);candidate=result['candidates'][0]['candidate']
        self.assertEqual(check_layout(candidate,graph)['status'],'PASS')
        applied=next(r for r in candidate.risk_context['design_geometry_basis']['soft_relations'] if r['strength']=='HARD')
        next(i for i in candidate.items if i.slot.id==applied['right']).slot.rect.x+=1
        self.assertIn('FAMILY_HARD_RELATION_VIOLATED',check_layout(candidate,graph)['errors'])

    def test_optional_and_joint_pattern_restrictions_reject_without_losing_input(self):
        profile=apply_rule(self.profile,dict(kind='OPTIONAL_ROLES',roles=[]))
        graph=InputGraph.from_legacy([dict(name='Alex Example',phone='+1 202 555 0100',email='alex@example.test')],[])
        before=deepcopy(graph.data);result=synthesize(profile,graph,90,54,dict(version='authored-required',approved=True))
        self.assertFalse(result['candidates']);self.assertEqual(graph.data,before)
        self.assertIn('EDITOR_REQUIRED_ROLE_MISSING',{r['reason'] for r in result['issues']})

    def test_source_replay_uses_reviewed_text_and_ports_without_creating_training_labels(self):
        scenarios=FamilyScenarios(self.library)
        members=self.workspace.sources(self.ref)
        before=self.workspace.store.count('SAMPLE')
        case=scenarios.from_source(self.ref,members[0]['sample_id'],'Authored reviewer')
        self.assertEqual(case['role'],'ENGINEERING_CASE_NOT_TRAIN_GOLD')
        self.assertEqual(case['width_mm'],90)
        self.assertEqual(len(case['input_graph']['people']),1)
        self.assertEqual({r['value'] for r in case['input_graph']['fields']},
                         {'Alex Example','Designer','+1 202 555 0100','alex@example.test'})
        self.assertEqual(scenarios.from_source(self.ref,members[0]['sample_id'],'Authored reviewer')['id'],case['id'])
        self.assertEqual(self.workspace.store.count('SAMPLE'),before)
        _,dataset,_=self.workspace.resolve(self.ref)
        sealed=next(e for e in dataset['entries'] if e['role']=='HOLDOUT')
        with self.assertRaises(ValueError):scenarios.from_source(self.ref,sealed['sample_id'],'Reviewer')

    def test_full_source_review_freezes_all_members_and_resumes_after_actual_first_layout(self):
        batches=FamilyBatches(self.library)
        job=batches.review_sources([self.ref],'Authored reviewer')
        self.assertEqual(job['item_count'],len(self.profile['source_members']))
        calls=[0]
        def stop():
            calls[0]+=1;return calls[0]>1
        claimed=batches.jobs.claim(job['id'],job['revision'])
        paused=run_design_job(self.library.root,job['id'],claimed['owner']['token'],stop)
        self.assertEqual(paused['phase'],'PAUSED');self.assertEqual(paused['next_index'],1)
        first=batches.jobs.results(job['id'])[0]
        self.assertEqual(first['status'],'FEASIBLE_PREVIEW')
        self.assertFalse(first['aesthetic_qualification'])
        claimed=batches.jobs.claim(job['id'],paused['revision'])
        done=run_design_job(self.library.root,job['id'],claimed['owner']['token'])
        self.assertEqual(done['phase'],'COMPLETE')
        self.assertTrue(done['summary']['all_hard_checks_pass'])
        self.assertEqual(len(batches.jobs.results(job['id'])),job['item_count'])

    def test_font_impact_includes_other_versions_and_refuses_unrelated_font(self):
        draft=self.apply(self.draft(),self.reorder())
        candidate=self.rules.create_candidate(draft['id'],draft['revision'],'Reviewer',True)
        asset=next(s['source_font_ref'] for d in self.profile['data_requirement_profiles'] for s in d['presentation_evidence'] if s['source_font_ref'])
        impact=self.workspace.impact(self.ref,font_hashes=[asset['hash']])
        self.assertTrue({self.model['id'],candidate['id']}<=set(impact['models']))
        self.assertEqual(impact['font_hashes'],[asset['hash']])
        self.assertFalse(impact['accepted_output_bytes_changed'])
        with self.assertRaises(ValueError):self.workspace.impact(self.ref,font_hashes=['unknown'])

    def test_explicit_joint_style_default_precedes_lexical_config_id_among_legal_results(self):
        profile=deepcopy(self.profile);key=profile['roles'][0]['key']
        samples=[s for d in profile['data_requirement_profiles'] for s in d['presentation_evidence'] if s['role_key']==key]
        preferred,alternate=samples[0]['example_id'],samples[1]['example_id']
        profile['editor_preferred_sources']={key:preferred}
        def options(p,k,*args,**kwargs):
            rows=_font_options(p,k,*args,**kwargs)
            if k!=key:return rows
            a=deepcopy(rows[0]);b=deepcopy(rows[0])
            a.update(id='a-alternate',source_refs=[alternate]);b.update(id='z-preferred',source_refs=[preferred])
            return [a,b]
        graph=InputGraph.from_legacy([dict(name='Alex Example',title='Designer',phone='+1 202 555 0100',email='alex@example.test')],[])
        with patch('template_ai.design_synthesis._font_options',side_effect=options):
            result=synthesize(profile,graph,90,54,dict(version='authored-default-test',approved=True,candidate_budget=32))
        self.assertTrue(result['candidates'])
        self.assertIn('z-preferred',result['candidates'][0]['configuration_ids'])
        self.assertEqual(result['candidates'][0]['default_preference_cost'],0)
