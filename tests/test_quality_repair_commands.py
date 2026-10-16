"""Existing owned quality transport, role-disabled paged metadata and explicit receipts."""
import unittest
import test_quality_gold_sets as fixtures
from template_ai.quality_command import execute,run_command
from template_ai.training_store import TrainingStore


class QualityRepairCommandTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp

    def test_actual_owned_command_preview_confirm_and_readback_no_second_transport(self):
        preview=run_command(self.library.root,'REPAIR_SOURCE_PLAN',dict(work_id=self.work['id'],origin='SOURCE_FACTS',origin_id=self.work['id'],description='Actual original source investigation'))
        with self.assertRaises(ValueError):run_command(self.library.root,'REPAIR_CONFIRM',dict(kind='ISSUE',plan=preview,actor='Reviewer',reason='No implicit confirmation'))
        saved=run_command(self.library.root,'REPAIR_CONFIRM',dict(kind='ISSUE',plan=preview,actor='Reviewer',reason='Actual source and bounded repair scope reviewed',approved=True))
        self.assertEqual(execute(self.library.root,'REPAIR_GET',dict(kind='QUALITY_REPAIR_ISSUE',id=saved['id'])),saved)
        root=execute(self.library.root,'REPAIR_ROOT_PLAN',dict(identity=saved['id'],layer='NOISE_RULE',hypothesis='Possible bounded annotation ambiguity',evidence='Not yet reviewed original and truth flags'))
        self.assertFalse(root['can_prepare_candidate']);self.assertEqual(self.library.templates(),[])

    def test_holdout_and_related_source_work_catalog_is_disabled_unselected_and_fifty_paged(self):
        gold=self.gold.confirm(fixtures.QualityGoldSetTests.plan(self),'Reviewer',True)
        self.sets.create(self.sets.plan('Actual heldout role lock',[gold['id']],True,True,'One related whole source group'),'Reviewer',True)
        for index in range(54):self.library.create_artwork(self.source['id'],'Catalog row '+str(index)+(' ONLY_TARGET_FIFTY_THREE' if index==53 else ''),self.work['payload'])
        before=self.library.db.total_changes;first=execute(self.library.root,'REPAIR_WORKS',dict(offset=0));second=execute(self.library.root,'REPAIR_WORKS',dict(offset=50))
        self.assertEqual((first['total'],len(first['rows']),len(second['rows'])),(55,50,5))
        self.assertTrue(all(not row['default_selected'] and not row['allowed_roles'] and row['locked_role']=='HOLDOUT' for row in first['rows']+second['rows']))
        self.assertFalse(first['images_loaded']);self.assertFalse(first['model_weights_loaded']);self.assertEqual(self.library.db.total_changes,before)
        found=execute(self.library.root,'REPAIR_WORKS',dict(query='ONLY_TARGET_FIFTY_THREE'));self.assertEqual(found['total'],1)

    def test_status_lists_and_invalid_commands_remain_metadata_only_and_do_not_activate(self):
        status=run_command(self.library.root,'REPAIR_STATUS',{});self.assertEqual(status['active_revision'],0);self.assertIsNone(status['pin']);self.assertFalse(status['automatic_fallback'])
        for kind in ('QUALITY_REPAIR_ROOT_REVIEW','QUALITY_REPAIR_GATE','QUALITY_PIPELINE_DEPLOYMENT','AUTO_JOB','RULE'):
            result=execute(self.library.root,'LIST',dict(kind=kind));self.assertEqual(result['rows'],[])
        with self.assertRaises(ValueError):execute(self.library.root,'REPAIR_GET',dict(kind='SEMANTIC_MODEL',id='not-a-weight-loader'))
        with self.assertRaises(ValueError):execute(self.library.root,'REPAIR_WORKS',dict(offset=-1))
        with self.assertRaises(ValueError):execute(self.library.root,'REPAIR_NOT_A_COMMAND',{})
        self.assertIsNone(TrainingStore.bind(self.library).get('QUALITY_PIPELINE_ACTIVE','automatic-source'))
