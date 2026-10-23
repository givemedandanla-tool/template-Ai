from copy import deepcopy
import unittest
from template_ai.design_family import train_families
from template_ai.design_profiles import learn_profiles
from template_ai.design_synthesis import synthesize
from template_ai.input_graph import InputGraph
from template_ai.demo import demo_template
from authored_font_fixture import bind_authored_fonts
from test_design_family import example
import test_logo_lifecycle as logo_fixture


class SharedWholeLogoSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.fixture=logo_fixture.LogoLifecycleTests()
        self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.asset=self.fixture.approve()
        font=bind_authored_fonts(demo_template(),self.fixture.source_font_manager).slots[0].font_asset
        examples=[example(i) for i in range(8)]
        for row in examples:
            for field in row['fields']:
                field['source_typography']=dict(font_asset_ref=deepcopy(font),
                    source_pt=dict(value=10.,unit='pt',status='OBSERVED',evidence_refs=['authored']),
                    horizontal_scale=dict(value=1.,unit='ratio',status='OBSERVED',evidence_refs=['authored']),
                    tracking=dict(value=0.,unit='mm',status='OBSERVED',evidence_refs=['authored']))
                field['label_binding']=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['author'])
            row['fields'].append(dict(id='whole-logo',owner='c1',kind='logo',index=0,
                rect=dict(x=60.,y=30.,w=25.,h=15.)))
        self.profile=learn_profiles(train_families(examples),examples)['families'][0]
        self.graph=InputGraph.from_legacy([dict(name='Alex',phone=['0123456789'],company='c1')],
            [dict(name='Synthetic Brand')],{'c1':self.asset})
        entity=self.graph.data['companies'][0]['id']
        self.fixture.store.bind(entity,self.fixture.company['id'],'Synthetic Brand',True)
        self.logos={'c1':dict(self.asset,design_entity_ref=entity)}
        self.policy=dict(approved=True,version='authored-logo-source-1',candidate_budget=32)

    def test_complete_logo_carries_company_name_without_silent_omission(self):
        result=synthesize(self.profile,self.graph,90.,54.,self.policy,logos=self.logos)
        self.assertEqual(result['status'],'FEASIBLE_PREVIEW',result['issues'])
        candidate=result['candidates'][0]['candidate']
        marks=[item for item in candidate.items if item.slot.kind=='logo']
        self.assertEqual(len(marks),1);self.assertEqual(marks[0].text,'Synthetic Brand')
        self.assertEqual(marks[0].logo['id'],self.asset['id'])
        self.assertFalse(any(item.slot.kind=='company' for item in candidate.items))

    def test_missing_size_identity_or_exact_selected_version_does_not_borrow_asset(self):
        variants=[{}, {'c1':dict(self.logos['c1'],width_mm=85.)},
                  {'c1':dict(self.logos['c1'],design_entity_ref='different-company')},
                  {'c1':dict(self.logos['c1'],id='unselected-version')}]
        for logos in variants:
            with self.subTest(logos=list(logos)):
                result=synthesize(self.profile,self.graph,90.,54.,self.policy,logos=logos)
                self.assertEqual(result['candidates'],[])
