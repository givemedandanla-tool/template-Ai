"""Hand-authored small assignment oracles, independent of solver implementation."""
from copy import deepcopy
from itertools import permutations
import unittest

from template_ai.design_assignment import assign_fields


def profile(roles):
    return {'roles': roles, 'grammar': {'default_order': [r['key'] for r in roles]}}


def role(key, owner='p1', kind='phone', container=None):
    return {'key': key, 'owner_port': owner, 'kind': kind,
            'confirmed_container_keys': [container or key]}


def fact(identity, key, owner='p1', kind='phone', semantic=None):
    result = {'render_id': identity, 'role_key': key, 'owner_port': owner, 'kind': kind}
    if semantic:
        result['semantic_observation'] = {'semantic_type': semantic}
    return result


class IndependentAssignmentOracleTests(unittest.TestCase):
    def test_unique_feasible_assignment_avoids_greedy_dead_end(self):
        # A may use left or right; B may only use left. There is exactly one
        # feasible bijection, regardless of the preferred port of A.
        data = profile([role('left'), role('right')])
        fields = [fact('A', 'left'), fact('B', 'right')]
        allowed = {'A': {'left', 'right'}, 'B': {'left'}}
        output = assign_fields(data, fields, {}, lambda f, key:
                               [{'allowed': True}] if key in allowed[f['render_id']] else [])
        self.assertEqual(output['status'], 'ASSIGNED')
        self.assertEqual({r['render_id']: r['source_role_key'] for r in output['assignments']},
                         {'A': 'right', 'B': 'left'})

    def test_phone_subtype_default_wins_over_input_port_order(self):
        data = profile([role('left'), role('right')])
        data['grammar']['default_semantic_roles'] = {'left': 'landline', 'right': 'mobile'}
        fields = [fact('mobile', 'left', semantic='mobile'),
                  fact('office', 'right', semantic='landline')]
        for order in permutations(fields):
            output = assign_fields(data, list(order), {}, lambda f, key: [{'allowed': True}])
            self.assertEqual({r['render_id']: r['container_key'] for r in output['assignments']},
                             {'mobile': 'right', 'office': 'left'})

    def test_roles_cannot_cross_ownership_even_when_all_font_options_fit(self):
        data = profile([role('first', owner='p1'), role('second', owner='p2')])
        fields = [fact('only-first', 'first', owner='p1'),
                  fact('also-first', 'second', owner='p1')]
        result = assign_fields(data, fields, {}, lambda f, key: [{'allowed': True}])
        self.assertNotEqual(result['status'], 'ASSIGNED')
        self.assertEqual(result['assignments'], [])

    def test_role_source_order_does_not_change_finite_default(self):
        original = profile([role('alpha'), role('beta'), role('gamma')])
        fields = [fact('A', 'alpha'), fact('B', 'gamma')]
        expected = {'A': 'alpha', 'B': 'gamma'}
        for roles in permutations(original['roles']):
            data = deepcopy(original)
            data['roles'] = list(roles)
            result = assign_fields(data, deepcopy(fields), {}, lambda f, key: [{'allowed': True}])
            self.assertEqual(result['status'], 'ASSIGNED')
            self.assertEqual({r['render_id']: r['source_role_key'] for r in result['assignments']}, expected)

    def test_same_physical_container_cannot_be_used_by_two_people(self):
        data = profile([role('first', owner='p1', container='shared-space'),
                        role('second', owner='p2', container='shared-space')])
        fields = [fact('A', 'first', owner='p1'), fact('B', 'second', owner='p2')]
        result = assign_fields(data, fields, {}, lambda f, key: [{'allowed': True}])
        self.assertEqual(result['status'], 'UNSUPPORTED_FIELD_CAPACITY')
        self.assertEqual(result['assignments'], [])
