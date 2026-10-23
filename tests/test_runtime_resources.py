import tempfile,threading,time,unittest
from dataclasses import replace
from types import SimpleNamespace as NS
from template_ai.runtime_resources import ResourceSampler,ResourceSnapshot,ResourceMonitor,AdmissionControl,MiB


def provider():return NS(virtual_memory=lambda:NS(total=16*1024*MiB,available=10*1024*MiB),cpu_percent=lambda interval=None:20,cpu_count=lambda logical=True:8,Process=lambda:NS(memory_info=lambda:NS(rss=50*MiB),cpu_affinity=lambda:[0,1,2,3]),disk_usage=lambda path:NS(free=100*1024*MiB))
def snapshot(sequence=1):return ResourceSnapshot(100,sequence,16*1024*MiB,8*1024*MiB,20,4,100*1024*MiB,50*MiB,())


class RuntimeResourcesTests(unittest.TestCase):
    def test_io_rates_are_measured_deltas_and_high_io_wait_pauses_new_work(self):
        from dataclasses import replace
        api=provider();api.cpu_times_percent=lambda interval=None:NS(iowait=70);counts=[1000,2000];api.disk_io_counters=lambda:NS(read_bytes=counts[0],write_bytes=counts[1]);clock=[100.0]
        sampler=ResourceSampler(api,lambda:dict(applicable=False),lambda:clock[0]);first=sampler.sample('.')
        self.assertIsNone(first.io_read_bytes_per_second);self.assertIsNone(first.io_wait_percent)
        clock[0]+=2;counts[:]=[5000,8000];value=sampler.sample('.')
        self.assertEqual(value.io_read_bytes_per_second,2000);self.assertEqual(value.io_write_bytes_per_second,3000)
        control=AdmissionControl(clock=lambda:clock[0]);self.assertIn('IO_WAIT_PRESSURE',control.decide(value,'SCAN').reasons)
    def test_host_and_container_memory_cpu_affinity_are_clamped_and_first_cpu_is_unknown(self):
        clock=[100];usage=[2_000_000]
        def group():return dict(applicable=True,memory_max=str(4*1024*MiB),memory_current=str(3*1024*MiB),cpu_max='200000 100000',cpu_stat='usage_usec '+str(usage[0]))
        sampler=ResourceSampler(provider(),group,lambda:clock[0]);first=sampler.sample('.')
        self.assertEqual(first.memory_total,4*1024*MiB);self.assertEqual(first.memory_available,1024*MiB);self.assertEqual(first.effective_cpus,2);self.assertIsNone(first.cpu_percent)
        clock[0]+=1;usage[0]+=1_000_000;second=sampler.sample('.');self.assertEqual(second.cpu_percent,50);self.assertEqual(second.sequence,2);self.assertIn('NOT_REFERENCE_HARDWARE',second.basis)

    def test_applicable_unknown_container_limits_do_not_borrow_host_available_memory(self):
        sampler=ResourceSampler(provider(),lambda:dict(applicable=True,errors=['denied']),lambda:100);value=sampler.sample('.')
        self.assertIsNone(value.memory_available);decision=AdmissionControl(clock=lambda:100).decide(value);self.assertFalse(decision.allowed);self.assertIn('AVAILABLE_MEMORY_UNKNOWN',decision.reasons)

    def test_first_cpu_sample_can_only_admit_one_bounded_worker_with_known_memory_and_disk(self):
        value=ResourceSampler(provider(),lambda:dict(applicable=False),lambda:100).sample('.')
        decision=AdmissionControl(clock=lambda:100).decide(value);self.assertTrue(decision.allowed);self.assertEqual(decision.state,'ALLOW_SINGLE_WORKER');self.assertIsNone(value.cpu_percent)

    def test_hysteresis_counts_fresh_samples_not_repeated_checks_and_is_per_workload(self):
        control=AdmissionControl(clock=lambda:100);low=replace(snapshot(),memory_available=200*MiB,memory_total=1024*MiB)
        self.assertFalse(control.decide(low,'ANALYSIS').allowed);self.assertTrue(control.decide(low,'SCAN').allowed)
        good=replace(snapshot(2),memory_total=1024*MiB)
        for _ in range(5):self.assertFalse(control.decide(good,'ANALYSIS').allowed)
        self.assertFalse(control.decide(replace(good,sequence=3),'ANALYSIS').allowed);self.assertTrue(control.decide(replace(good,sequence=4),'ANALYSIS').allowed)

    def test_disk_cpu_gui_interaction_stale_and_unknown_resources_pause_instead_of_fake_completion(self):
        cases=[(replace(snapshot(),disk_free=1),{},'DISK_HEADROOM_LOW'),(replace(snapshot(),cpu_percent=95),{},'CPU_PRESSURE'),(snapshot(),dict(gui_lag=.8),'GUI_HEARTBEAT_LATE'),(snapshot(),dict(interactive=True),'FOREGROUND_INTERACTION_PRIORITY'),(replace(snapshot(),sampled_at=90),{},'RESOURCE_SAMPLE_STALE'),(None,{},'RESOURCE_SAMPLE_PENDING')]
        for value,kwargs,reason in cases:
            with self.subTest(reason=reason):
                result=AdmissionControl(clock=lambda:100).decide(value,**kwargs);self.assertFalse(result.allowed);self.assertEqual(result.state,'PAUSED_RESOURCES');self.assertIn(reason,result.reasons)
        with self.assertRaises(ValueError):AdmissionControl(recovery_samples=0)
        with self.assertRaises(ValueError):AdmissionControl().decide(snapshot(),estimated_peak_bytes=-1)

    def test_monitor_is_daemon_and_close_discards_late_blocked_volume_result(self):
        entered=threading.Event();release=threading.Event()
        class Slow:
            def sample(self,root):entered.set();release.wait(2);return snapshot()
        monitor=ResourceMonitor('.',Slow());monitor.start();self.assertTrue(entered.wait(1));self.assertTrue(monitor.thread.daemon);monitor.close();release.set();monitor.thread.join(1);self.assertIsNone(monitor.snapshot());self.assertFalse(monitor.thread.is_alive())

    def test_probe_failure_publishes_unknown_metrics_and_never_an_uncaught_worker_exception(self):
        class Broken:
            sequence=1
            def sample(self,root):raise OSError('probe unavailable')
        monitor=ResourceMonitor('.',Broken());monitor.start();deadline=time.monotonic()+1
        while monitor.snapshot() is None and time.monotonic()<deadline:time.sleep(.01)
        monitor.close();monitor.thread.join(1);value=monitor.snapshot();self.assertIsNotNone(value);self.assertIsNone(value.memory_available);self.assertIn('probe-failed:OSError',value.unknown)

    def test_actual_runtime_probe_returns_finite_metrics_without_claiming_reference_hardware(self):
        with tempfile.TemporaryDirectory() as root:value=ResourceSampler().sample(root)
        self.assertIsNotNone(value.memory_total);self.assertIsNotNone(value.memory_available);self.assertGreaterEqual(value.memory_total,value.memory_available);self.assertGreaterEqual(value.memory_available,0);self.assertGreater(value.disk_free,0);self.assertEqual(value.basis,'CURRENT_RUNTIME_ONLY_NOT_REFERENCE_HARDWARE')
