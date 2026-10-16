import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QEvent,QCoreApplication
from shiboken6 import isValid
from PySide6.QtWidgets import QApplication,QWidget
from template_ai.storage import Library
from template_ai.runtime_supervisor import RuntimeSupervisor,KEY
from template_ai.runtime_resources import ResourceSnapshot,MiB
APP=QApplication.instance() or QApplication([])


class Monitor:
    def __init__(self,clock):self.clock=clock;self.closed=False
    def start(self):pass
    def close(self):self.closed=True
    def snapshot(self):return ResourceSnapshot(self.clock[0],int(self.clock[0]*10),16*1024*MiB,8*1024*MiB,20,4,100*1024*MiB,50*MiB,())


class RuntimeSupervisorTests(unittest.TestCase):
    def test_raw_sqlite_close_stops_probe_and_timer_without_late_ui_database_errors(self):
        self.window.library.db.close();self.clock[0]+=.25;self.service.pulse();self.assertTrue(self.service.closed_event.is_set());self.assertFalse(self.service.timer.isActive());self.assertFalse(self.service.admit().allowed)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.window=QWidget();self.window.library=Library(self.root);self.addCleanup(self.window.library.close);self.addCleanup(self.window.close);self.clock=[100.0];self.monitor=Monitor(self.clock);self.service=RuntimeSupervisor(self.window,self.monitor,lambda:self.clock[0],start=False);self.addCleanup(self.service.shutdown)

    def ready(self):self.clock[0]+=.25;self.service.pulse()

    def test_delayed_input_events_do_not_touch_destroyed_widgets_or_closed_context(self):
        child=QWidget(self.window);child.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.assertFalse(isValid(child));before=self.service.last_interaction
        self.assertFalse(self.service.eventFilter(child,QEvent(QEvent.MouseButtonPress)))
        self.assertEqual(self.service.last_interaction,before)
        self.service.shutdown();self.clock[0]+=1
        self.assertFalse(self.service.eventFilter(self.window,QEvent(QEvent.KeyPress)))
        self.assertEqual(self.service.last_interaction,before);self.assertTrue(self.monitor.closed)

    def test_gui_heartbeat_and_foreground_priority_are_measured_without_reading_key_text(self):
        self.assertIn('GUI_STARTUP_WARMUP',self.service.admit().reasons);self.ready();self.assertTrue(self.service.admit().allowed)
        self.service.eventFilter(self.window,QEvent(QEvent.KeyPress));self.assertIn('FOREGROUND_INTERACTION_PRIORITY',self.service.admit().reasons);self.assertTrue(self.service.admit(foreground=True).allowed)
        self.clock[0]+=2;self.service.pulse();self.assertGreater(self.service.gui_lag(),.5);self.assertIn('GUI_HEARTBEAT_LATE',self.service.admit().reasons)

    def test_pause_is_persisted_and_read_by_another_supervisor_without_learning_epoch_changes(self):
        from template_ai.training_store import TrainingStore
        store=TrainingStore(self.window.library);epoch=store.epoch
        self.ready();before=self.window.library.db.execute("SELECT count(*) FROM reviews").fetchone()[0];saved=self.service.set_paused(True);self.assertTrue(saved['paused']);self.assertIn('BACKGROUND_PAUSED_BY_OPERATOR',self.service.admit().reasons)
        second=RuntimeSupervisor(self.window,Monitor(self.clock),lambda:self.clock[0],start=False);self.addCleanup(second.shutdown);self.assertTrue(second.state()['background_paused']);self.assertEqual(self.window.library.db.execute('SELECT count(*) FROM reviews').fetchone()[0],before+1)
        self.service.set_paused(False);second.refresh_policy();self.assertFalse(second.state()['background_paused']);self.assertEqual(store.epoch,epoch)

    def test_failed_policy_audit_rolls_back_persistence_but_keeps_safe_unpersisted_local_pause(self):
        self.ready()
        with patch.object(self.window.library,'event',side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):self.service.set_paused(True)
        self.assertIsNone(self.window.library.db.execute('SELECT value FROM preferences WHERE key=?',(KEY,)).fetchone());self.assertTrue(self.service.state()['pause_request_not_persisted']);self.assertTrue(self.service.state()['background_paused'])

    def test_conflicting_other_window_policy_is_not_overwritten(self):
        other=RuntimeSupervisor(self.window,Monitor(self.clock),lambda:self.clock[0],start=False);self.addCleanup(other.shutdown);other.set_paused(True)
        with self.assertRaisesRegex(ValueError,'其他視窗'):self.service.set_paused(False)
        self.service.refresh_policy();self.assertTrue(self.service.state()['background_paused'])

    def test_library_close_and_project_switch_stop_admission_without_sqlite_from_worker(self):
        self.ready();self.window.library.close();self.assertTrue(self.monitor.closed);self.assertIn('PROJECT_CONTEXT_CLOSED_OR_CHANGED',self.service.admit().reasons);self.assertFalse(self.service.timer.isActive())

    def test_invalid_persisted_policy_pauses_background_without_silently_resetting_it(self):
        with self.window.library.db:self.window.library.db.execute('INSERT INTO preferences VALUES(?,?)',(KEY,'{"version":999}'))
        self.ready();self.assertTrue(self.service.policy_error);self.assertIn('RESOURCE_POLICY_UNSAFE',self.service.admit().reasons)
        with self.assertRaises(ValueError):self.service.set_paused(False)
