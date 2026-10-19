"""Authored cross-work model checks; not independent real-corpus qualification."""
from copy import deepcopy
import unittest

from template_ai.design_family import feature_vector, train_families
from template_ai.design_profiles import learn_profiles, conditional_match


def example(index, *, group=None, shift=0., role='TRAIN', extra=False):
    fields = [dict(id='name-'+str(index), owner='p1', kind='name', index=0,
        rect=dict(x=8+shift, y=5, w=40, h=8), private_text='Person '+str(index)),
        dict(id='phone-'+str(index), owner='p1', kind='phone', index=0,
        rect=dict(x=8+shift, y=22, w=38, h=6), private_text='Number '+str(index))]
    if extra:
        fields.append(dict(id='email-'+str(index), owner='p1', kind='email', index=0,
                           rect=dict(x=8+shift,y=35,w=55,h=6)))
    return dict(id='example-'+str(index), lineage_group=group or 'lineage-'+str(index),
                role=role, width_mm=90, height_mm=54, fields=fields)


class DesignFamilyTests(unittest.TestCase):
    def test_private_values_identifiers_and_slot_defaults_are_not_features(self):
        a=example(1); b=deepcopy(a); b.update(id='different', customer_id='secret')
        for field in b['fields']:
            field.update(id='new-'+field['id'],private_text='Different text',font='Guess',size_pt=99)
        self.assertEqual(feature_vector(a),feature_vector(b))

    def test_train_requires_explicit_training_role_and_heldout_never_fits_scaler(self):
        rows=[example(i) for i in range(8)]; rows[-1]['role']='HOLDOUT'
        with self.assertRaises(ValueError):train_families(rows)
        rows[-1]['role']='VALIDATION'
        with self.assertRaises(ValueError):train_families(rows)

    def test_same_geometry_from_distinct_designs_learns_shared_family_not_templates(self):
        artifact=train_families([example(i) for i in range(8)])
        self.assertEqual(len(artifact['families']),1)
        self.assertEqual(artifact['families'][0]['independent_support'],8)
        self.assertEqual(artifact['actual_template_objects_created'],0)

    def test_correlated_copies_cannot_satisfy_independent_support(self):
        rows=[example(i,group='one-source') for i in range(20)]
        artifact=train_families(rows)
        self.assertEqual(artifact['families'],[])
        self.assertEqual(len(artifact['unclassified']),20)
        self.assertEqual(artifact['independent_group_count'],1)

    def test_batch_reestimation_is_deterministic_and_preserves_rare_observations(self):
        rows=[example(i) for i in range(8)]
        rare=example(100); rare['fields'][0]['rect'].update(x=50,w=30)
        rows.append(rare)
        a=train_families(rows); b=train_families(list(reversed(rows)))
        self.assertEqual(a,b)
        self.assertEqual(set(a['assignment']),{row['id'] for row in rows})
        self.assertNotIn('partial_fit',a['algorithm'])

    def test_default_typography_stays_missing_in_preprocessing(self):
        rows=[example(i) for i in range(8)]; a=train_families(rows)
        from template_ai.design_family import FEATURES
        index=FEATURES.index('name_pt')
        self.assertIsNone(feature_vector(rows[0])[index])
        self.assertEqual(a['preprocessing']['centres'][index],0)


class DesignProfileTests(unittest.TestCase):
    def model(self, rows=None):
        rows=rows or [example(i) for i in range(8)]
        family=train_families(rows)
        return rows,family,learn_profiles(family,rows)

    def test_shared_profiles_use_multiple_sources_and_do_not_invent_font_capacity(self):
        _,_,artifact=self.model(); family=artifact['families'][0]
        self.assertEqual(family['independent_support'],8)
        self.assertTrue(all(row['typography_known_examples']==0 for row in family['roles']))
        self.assertTrue(all(row['validated_admission'] is None for row in family['field_capability_profiles']))
        self.assertIsNone(family['grammar']['repeated_groups']['p1:phone']['validated_capacity'])

    def test_training_distribution_changes_grammar_and_defaults(self):
        _,_,a=self.model()
        rows=[example(i,extra=True) for i in range(8)]
        _,_,b=self.model(rows)
        self.assertNotEqual(a['families'][0]['grammar'],b['families'][0]['grammar'])
        self.assertIn('p1:email:0',b['families'][0]['grammar']['default_order'])

    def test_source_supported_joint_vectors_are_not_independent_ranges(self):
        rows=[example(i) for i in range(8)]
        for i,row in enumerate(rows):
            for field in row['fields']:
                field['source_typography']={'source_pt':dict(value=12 if i%2 else 10,
                    unit='pt',status='OBSERVED',evidence_refs=['authored:'+str(i)]),
                    'horizontal_scale':dict(value=.9 if i%2 else 1.,unit='ratio',
                    status='OBSERVED',evidence_refs=['authored:'+str(i)])}
        _,_,artifact=self.model(rows)
        self.assertTrue(artifact['families'])
        for family in artifact['families']:
            for role in family['roles']:
                self.assertEqual(role['joint_region'],'OBSERVED_CONFIGURATIONS_NOT_INDEPENDENT_MINMAX')
                for configuration in role['joint_configurations']:
                    self.assertIn((configuration['source_pt'],configuration['horizontal_scale']),[(10,1.),(12,.9)])

    def test_semantic_support_policy_and_current_feasibility_are_separate(self):
        _,_,artifact=self.model(); family=artifact['families'][0]
        cap=next(c for c in family['field_capability_profiles'] if 'phone' in c['observed_semantic_types'])
        context=dict(family_id=family['family_id'],owner_port='p1',font_policy_version='1',asset_version='1')
        data=dict(family_id=family['family_id'],semantic_type='phone')
        policy=dict(approved=True,version='1',allowed_types=['phone'])
        match=conditional_match(data,cap,context,policy)
        self.assertEqual(match['evidence_status'],'SUPPORTED')
        self.assertEqual(match['policy_status'],'UNKNOWN')
        self.assertEqual(match['feasibility_status'],'NOT_EVALUATED')
        cap['label_bindings']=[dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['author'])]
        self.assertEqual(conditional_match(data,cap,context,policy)['policy_status'],'ALLOWED')
        self.assertEqual(conditional_match(data,cap,dict(context,owner_port='p2'),policy)['policy_status'],'FORBIDDEN')
        self.assertEqual(conditional_match(data,cap,dict(context,family_id='other'),policy)['policy_status'],'FORBIDDEN')

    def test_profiles_reject_tampered_family_and_validation_rows(self):
        rows,family,_=self.model(); changed=deepcopy(family); changed['families'][0]['independent_support']=100
        with self.assertRaises(ValueError):learn_profiles(changed,rows)
        rows[0]['role']='VALIDATION'
        with self.assertRaises(ValueError):learn_profiles(family,rows)
