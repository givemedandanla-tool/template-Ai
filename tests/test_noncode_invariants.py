"""Normative/semantic oracles with authored data, not real-corpus qualification.

Expected owners, strings, support and match existence are authored independently
of implementation outputs. Existing helpers supply only source/font fixtures.
"""
from copy import deepcopy
from itertools import permutations
import json
from pathlib import Path
import random
import unittest

from template_ai.input_graph import InputGraph
from template_ai.design_assignment import assign_fields
from template_ai.design_family import feature_vector, train_families
from template_ai.design_synthesis import synthesize, input_facts
from template_ai.semantic_fields import recognize
from test_design_family import example
import test_design_synthesis as synthesis_fixture
import test_design_session as session_fixture


class DataMeaningOracles(unittest.TestCase):
    def test_explicit_semantic_candidates_do_not_mutate_original_strings(self):
        expected={'電子郵件: audit@example.test':'email','LINE: audit_001':'social_id',
                  '0912-345-678':'mobile','02-2345-6789':'landline','職稱: 設計師':'title'}
        for value,kind in expected.items():
            with self.subTest(value=value):self.assertEqual(recognize(value)['semantic_type'],kind)
        value='０９１２-３４５-６７８'
        graph=InputGraph.from_legacy([dict(name='00001',phone=value)],[])
        phone=next(f for f in graph.data['fields'] if f['kind']=='phone')
        self.assertEqual(phone['value'],value)
        self.assertEqual(graph.label(graph.data['people'][0]['id']),'00001')

    def test_same_text_and_shared_use_keep_distinct_identity_and_owner(self):
        graph=InputGraph.from_legacy([dict(name='PersonA',phone='0212345678'),
                                     dict(name='PersonB',phone='0212345678')],[])
        a,b=graph.data['people'];phones=[f for f in graph.data['fields'] if f['kind']=='phone']
        self.assertNotEqual(phones[0]['id'],phones[1]['id'])
        phones[0]['users'].append(b['id']);graph.validate(graph.data)
        people,_,_=graph.compile()
        self.assertEqual(people[0]['field_ids']['phone'],[phones[0]['id']])
        self.assertEqual(people[1]['field_ids']['phone'],[phones[0]['id'],phones[1]['id']])
        graph.command('edit_field',field_id=phones[0]['id'],value='0299999999',approved=True)
        self.assertEqual(graph.field(phones[0]['id'])['owner_id'],a['id'])
        self.assertEqual(graph.field(phones[1]['id'])['value'],'0212345678')
        graph.undo();self.assertEqual(graph.field(phones[0]['id'])['value'],'0212345678')
        graph.redo();self.assertEqual(graph.field(phones[0]['id'])['value'],'0299999999')

    def test_clearing_one_value_keeps_other_value_stable_id_and_position(self):
        graph=InputGraph.from_legacy([dict(name='Person',phone=['0212345678','0912345678'])],[])
        fields=[f for f in graph.data['fields'] if f['kind']=='phone'];ids=[f['id'] for f in fields]
        graph.command('edit_field',field_id=ids[0],value='')
        people,_,_=graph.compile()
        self.assertEqual(people[0]['phone'],['','0912345678'])
        self.assertEqual(people[0]['field_ids']['phone'],ids)

    def test_engineering_input_budget_rejects_without_silent_truncation(self):
        original='x'*2048;graph=InputGraph.from_legacy([dict(name='Person',address=original)],[])
        self.assertEqual(next(f for f in graph.data['fields'] if f['kind']=='address')['value'],original)
        with self.assertRaises(ValueError):InputGraph.from_legacy([dict(name='Person',address=original+'x')],[])
        self.assertEqual(next(f for f in graph.data['fields'] if f['kind']=='address')['value'],original)


class ConditionalRuleOracles(unittest.TestCase):
    def profile(self,roles,order):
        return dict(roles=roles,grammar=dict(default_order=order))

    def role(self,key,kind,container):
        return dict(key=key,kind=kind,owner_port='p1',confirmed_container_keys=[container])

    def fact(self,key,kind,identity,owner='p1',semantic=None):
        return dict(role_key=key,kind=kind,render_id=identity,owner_port=owner,
                    semantic_observation=dict(semantic_type=semantic or kind))

    def test_cross_type_permissions_do_not_create_transitive_container_access(self):
        roles=[self.role('p1:phone:0','phone','left'),self.role('p1:email:0','email','left'),
               self.role('p1:email:1','email','right'),self.role('p1:line:0','line','right')]
        profile=self.profile(roles,['p1:phone:0','p1:email:1'])
        policy=dict(allow_observed_container_substitution=True)
        options=lambda fact,key:[{'authored_source':key}]
        fields=[self.fact('p1:phone:0','phone','phone'),self.fact('p1:line:0','line','line')]
        result=assign_fields(profile,fields,policy,options)
        self.assertEqual(result['status'],'ASSIGNED')
        self.assertEqual({a['render_id']:a['container_key'] for a in result['assignments']},
                         {'phone':'left','line':'right'})
        # A phone can use only left; an email can use either. Email's access to
        # right does not authorize a second phone there.
        fields=[self.fact('p1:phone:0','phone','one'),self.fact('p1:phone:1','phone','two')]
        self.assertNotEqual(assign_fields(profile,fields,policy,options)['status'],'ASSIGNED')

    def test_semantic_default_and_owner_survive_nonsemantic_enumeration_order(self):
        roles=[self.role('p1:phone:0','phone','left'),self.role('p1:phone:1','phone','right')]
        profile=self.profile(roles,['p1:phone:0','p1:phone:1'])
        profile['grammar']['default_semantic_roles']={'p1:phone:0':'mobile','p1:phone:1':'landline'}
        fields=[self.fact('p1:phone:0','phone','landline',semantic='landline'),
                self.fact('p1:phone:1','phone','mobile',semantic='mobile')]
        options=lambda fact,key:[{'authored_source':key}]
        for permutation in permutations(fields):
            result=assign_fields(profile,list(permutation),{},options)
            self.assertEqual({a['render_id']:a['container_key'] for a in result['assignments']},
                             {'mobile':'left','landline':'right'})
        foreign=[self.fact('p2:phone:0','phone','foreign',owner='p2')]
        self.assertNotEqual(assign_fields(profile,foreign,{},options)['status'],'ASSIGNED')

    def test_small_exhaustive_matching_oracle_finds_both_sat_and_unsat(self):
        roles=[self.role('p1:phone:'+str(i),'phone',str(i)) for i in range(3)]
        profile=self.profile(roles,[r['key'] for r in roles])
        facts=[self.fact('p1:phone:'+str(i),'phone',str(i)) for i in range(3)]
        masks=[0,511,7,73,273,341,170,84,292,146,219,438,1,256,15,495]
        for mask in masks:
            allowed={(i,j) for i in range(3) for j in range(3) if mask & (1<<(3*i+j))}
            # Six complete matchings is an independent finite oracle, not a
            # call to scipy/the implementation's cost calculation.
            possible=any(all((i,p[i]) in allowed for i in range(3)) for p in permutations(range(3)))
            options=lambda fact,key:([{'authored':True}] if (int(fact['render_id']),int(key.rsplit(':',1)[1])) in allowed else [])
            result=assign_fields(profile,facts,{},options)
            self.assertEqual(result['status']=='ASSIGNED',possible,mask)
            if possible:
                chosen={(int(a['render_id']),int(a['container_key'])) for a in result['assignments']}
                self.assertTrue(chosen<=allowed);self.assertEqual(len({j for _,j in chosen}),3)


class LearningMeaningOracles(unittest.TestCase):
    def test_family_features_ignore_customer_text_and_unverified_defaults(self):
        a=example(1);b=deepcopy(a);b.update(id='00001',customer_id='private-customer',filename='00001.ai')
        for field in b['fields']:
            field.update(private_text='Entirely different',font='Unverified guess',size_pt=999,horizontal_scale=.1)
        self.assertEqual(feature_vector(a),feature_vector(b))

    def test_shared_style_is_not_one_family_per_work_and_aliases_do_not_create_support(self):
        rows=[example(i) for i in range(8)]
        artifact=train_families(rows)
        self.assertEqual(len(artifact['families']),1)
        self.assertEqual(artifact['independent_group_count'],8)
        aliases=[example(i,group='same-lineage') for i in range(8)]
        unsupported=train_families(aliases)
        self.assertEqual(unsupported['families'],[])
        self.assertEqual(unsupported['independent_group_count'],1)

    def test_holdout_cannot_be_used_to_fit_even_if_appearance_matches(self):
        rows=[example(i) for i in range(8)];rows[-1]['role']='HOLDOUT'
        with self.assertRaisesRegex(ValueError,'TRAIN'):train_families(rows)


class LayoutMeaningOracles(unittest.TestCase):
    def setUp(self):
        synthesis_fixture.DesignSynthesisTests.setUp(self)

    def signature(self,candidate):
        return sorted((i.slot.id,i.text,i.slot.owner,i.slot.rect.x,i.slot.rect.y,
                       i.slot.rect.w,i.slot.rect.h,i.slot.size_pt,i.scale) for i in candidate.items)

    def test_authored_complete_data_and_nonoverlap_are_independent_output_invariants(self):
        result=synthesize(self.profile,self.graph,90,54,self.policy)
        self.assertEqual(result['status'],'FEASIBLE_PREVIEW');candidate=result['candidates'][0]['candidate']
        self.assertEqual(sorted(i.text for i in candidate.items),['0123456789','0987654321','Alex Example'])
        for item in candidate.items:
            box=item.slot.rect
            self.assertGreaterEqual(box.x,-1e-8);self.assertGreaterEqual(box.y,-1e-8)
            self.assertLessEqual(box.x+box.w,90+1e-8);self.assertLessEqual(box.y+box.h,54+1e-8)
        for a,b in permutations(candidate.items,2):
            x,y=a.slot.rect,b.slot.rect
            self.assertTrue(x.x+x.w<=y.x+1e-8 or y.x+y.w<=x.x+1e-8 or
                            x.y+x.h<=y.y+1e-8 or y.y+y.h<=x.y+1e-8)
        self.assertFalse(candidate.valid);self.assertEqual(candidate.template.state,'draft')

    def test_profile_enumeration_order_is_not_a_new_customer_preference(self):
        original=synthesize(self.profile,self.graph,90,54,self.policy)['candidates'][0]['candidate']
        for seed in (0,7,42):
            profile=deepcopy(self.profile);random.Random(seed).shuffle(profile['roles'])
            result=synthesize(profile,self.graph,90,54,self.policy)
            self.assertEqual(result['status'],'FEASIBLE_PREVIEW')
            self.assertEqual(self.signature(result['candidates'][0]['candidate']),self.signature(original))

    def test_contradictory_relative_cycle_is_rejected_instead_of_silently_dropped(self):
        ids=[f['render_id'] for f in input_facts(self.graph) if f['kind']=='phone']
        intents=[dict(subject=ids[0],relation='ABOVE',object=ids[1]),
                 dict(subject=ids[1],relation='ABOVE',object=ids[0])]
        with self.assertRaisesRegex(ValueError,'cycle'):synthesize(self.profile,self.graph,90,54,self.policy,intents)

    def test_unfittable_string_is_kept_and_cannot_be_promoted_to_a_complete_draft(self):
        graph=self.graph.clone();field=next(f for f in graph.data['fields'] if f['kind']=='phone')
        field['value']='9'*1000
        result=synthesize(self.profile,graph,90,54,self.policy)
        self.assertNotEqual(result['status'],'FEASIBLE_PREVIEW')
        self.assertEqual(graph.field(field['id'])['value'],'9'*1000)


class SessionMeaningOracles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        session_fixture.DesignSessionTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        session_fixture.DesignSessionTests.setUp(self)

    def test_unconfirmed_and_changed_data_cannot_reuse_confirmation(self):
        target=self.root/('unconfirmed-'+self.session['id']+'.png')
        with self.assertRaises(ValueError):self.sessions.export(self.session['id'],target)
        self.assertFalse(target.exists())
        self.assertEqual(self.sessions.solve(self.session['id'],self.session['revision'])['status'],'FEASIBLE_PREVIEW')
        current=self.sessions.current(self.session['id']);confirmed=self.sessions.confirm(current['id'],current['revision'],'Author')
        graph=InputGraph(confirmed['input_graph']);phone=next(f for f in graph.data['fields'] if f['kind']=='phone')
        graph.command('edit_field',field_id=phone['id'],value='+1 202 555 0199')
        self.sessions.replace_input(confirmed['id'],confirmed['revision'],'authored-edit-'+confirmed['id'],graph)
        with self.assertRaises(ValueError):self.sessions.export(confirmed['id'],target)
        self.assertFalse(target.exists())
        current=self.sessions.current(confirmed['id']);self.assertIsNone(current['confirmation'])
        self.assertEqual(next(f for f in current['input_graph']['fields'] if f['id']==phone['id'])['value'],'+1 202 555 0199')

    def test_safe_local_production_report_contains_measurements_not_customer_text(self):
        from template_ai.production_report import save_report
        graph=InputGraph(self.session['input_graph'])
        canaries={'name':'CANARY0001','phone':'+12025550199','email':'canary@example.test'}
        for field in graph.data['fields']:
            if field['kind'] in canaries:field['value']=canaries[field['kind']]
        self.sessions.replace_input(self.session['id'],self.session['revision'],'safe-report-'+self.session['id'],graph)
        current=self.sessions.current(self.session['id'])
        self.sessions.solve(current['id'],current['revision']);current=self.sessions.current(current['id'])
        target=self.root/('safe-'+current['id']+'.json');save_report(self.sessions,current['id'],current['revision'],target)
        body=target.read_text();data=json.loads(body)
        for value in canaries.values():self.assertNotIn(value,body)
        self.assertIn('plain_summary',data);self.assertFalse(data['technical']['formal_output_allowed'])
        self.assertTrue(data['technical']['result_valid_for_current_input'])
        self.assertTrue(data['technical']['fields'])
        self.assertNotIn(str(self.root),body)
