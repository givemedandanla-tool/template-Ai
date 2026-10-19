import unittest
from template_ai.design_assignment import assign_fields,semantic_observation


class ConditionalContainerAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.profile=dict(roles=[dict(key='p1:phone:0',owner_port='p1',kind='phone',confirmed_container_keys=['contact']),
            dict(key='p1:email:0',owner_port='p1',kind='email',confirmed_container_keys=['contact'])],
            grammar=dict(default_order=['p1:phone:0'],default_semantic_roles={'p1:phone:0':'phone'}))
    def field(self,kind,owner='p1'):
        return dict(render_id='owned-'+kind,role_key=owner+':'+kind+':0',owner_port=owner,kind=kind)
    def solve(self,fields,approved=False):
        return assign_fields(self.profile,fields,dict(allow_observed_container_substitution=approved),
            lambda field,key:[dict(source_role=key)])
    def test_cross_type_substitution_requires_policy_even_with_observed_same_container(self):
        self.assertNotEqual(self.solve([self.field('email')])['status'],'ASSIGNED')
        allowed=self.solve([self.field('email')],True)
        self.assertEqual(allowed['status'],'ASSIGNED')
        self.assertEqual(allowed['assignments'][0]['container_key'],'contact')
    def test_one_equivalent_container_cannot_be_double_allocated_or_borrowed_across_people(self):
        self.assertNotEqual(self.solve([self.field('phone'),self.field('email')],True)['status'],'ASSIGNED')
        self.assertNotEqual(self.solve([self.field('phone','p2')],True)['status'],'ASSIGNED')
    def test_validated_phone_format_subtypes_do_not_claim_person_identity(self):
        mobile=semantic_observation('phone','0912-345-678');landline=semantic_observation('phone','02-2345-6789')
        self.assertEqual(mobile['semantic_type'],'mobile');self.assertEqual(landline['semantic_type'],'landline')
        self.assertTrue(mobile['subtype_is_not_identity_or_ownership_proof'])
