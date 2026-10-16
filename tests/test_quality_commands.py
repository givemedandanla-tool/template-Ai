import threading
import unittest
import test_quality_gold_sets as fixtures
from template_ai.quality_command import run_command


class QualityCommandTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp

    def test_actual_cancelled_owned_command_does_not_commit_gold_or_leave_busy_connection(self):
        plan=fixtures.QualityGoldSetTests.plan(self);cancel=threading.Event();timer=threading.Timer(.15,cancel.set)
        self.library.db.execute('BEGIN IMMEDIATE');timer.start()
        try:
            with self.assertRaisesRegex(ValueError,'停止|取消'):
                run_command(self.library.root,'CONFIRM',dict(kind='GOLD',plan=plan,actor='Synthetic reviewer',approved=True),cancel=cancel)
        finally:
            timer.cancel();timer.join();self.library.db.rollback()
        self.assertEqual(self.store.count('QUALITY_GOLD'),0)
        result=run_command(self.library.root,'LIST',dict(kind='QUALITY_GOLD'))
        self.assertEqual(result['rows'],[])

    def test_actual_worker_refuses_unsupported_directory_and_oversized_input_without_mutation(self):
        before=self.store.epoch
        with self.assertRaises(ValueError):run_command(self.library.root,'LIST',dict(kind='CUSTOMER_PRIVATE_DATA'))
        with self.assertRaisesRegex(ValueError,'32MiB'):run_command(self.library.root,'LIST',dict(kind='QUALITY_GOLD',query='x'*(32*1024*1024)))
        self.assertEqual(self.store.epoch,before)

    def test_actual_empty_directory_paging_is_bounded_and_not_a_quality_pass(self):
        result=run_command(self.library.root,'LIST',dict(kind='QUALITY_PROTOCOL',offset=50))
        self.assertEqual(result['total'],0);self.assertEqual(result['rows'],[]);self.assertFalse(result['images_loaded'])
        self.assertNotIn('quality_pass',result)
