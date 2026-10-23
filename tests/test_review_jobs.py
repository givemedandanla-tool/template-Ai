"""Actual QProcess protocol tests plus a real Inkscape review-worker round trip.

The controlled worker is a synthetic protocol fixture, not an analysis-engine
substitute.  The final test starts the distributed entry and actual importer.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
import psutil

from template_ai.review_tool.jobs import AnalysisJobs


FIXTURE = r'''
import hashlib,json,pathlib,subprocess,sys,time
req=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
cache=pathlib.Path(req['cache_dir']); mode=pathlib.Path(req['path']).stem
def emit(**event): print(json.dumps(event,ensure_ascii=False),flush=True)
packet={'source':{'hash':'synthetic-protocol-only'},'pages':[{'page':1}],
        'works':[{'id':'fixture-work'}],'status':'COMPLETE'}
emit(type='progress',stage='import',page=1,phase_timeout=1 if mode in ('slow','heartbeat') else 20,
     message='合成程序協定驗證，非作品辨識結果')
if mode in ('partial','escape'):
    folder=cache/'observations' if mode=='partial' else cache.parent/'outside-cache'
    folder.mkdir(parents=True,exist_ok=True)
    p=folder/'partial.json';raw=json.dumps(packet).encode();p.write_bytes(raw)
    emit(type='progress',stage='assemble',page=1,phase_timeout=10,
         checkpoint_path=str(p),checkpoint_sha256=hashlib.sha256(raw).hexdigest())
    print('PRIVATE_CUSTOMER_TEXT_MUST_STAY_LOCAL',file=sys.stderr,flush=True)
    emit(type='error',message='PRIVATE_CUSTOMER_TEXT_MUST_NOT_BE_FORWARDED')
    sys.exit(3)
elif mode=='heartbeat':
    for i in range(150):
        emit(type='progress',stage='import',page=1,phase_timeout=1,message='same stage')
        time.sleep(.03)
elif mode=='total':
    for i in range(150):
        emit(type='progress',stage='phase'+str(i),page=i,phase_timeout=20,message='stage')
        time.sleep(.03)
elif mode=='slow':time.sleep(20)
elif mode=='overflow':print('x'*10000,flush=True);time.sleep(20)
elif mode=='child':
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (cache/'owned-child.pid').write_text(str(child.pid))
    emit(type='progress',stage='child_ready',page=1,phase_timeout=20,message='child ready')
    time.sleep(60)
else:time.sleep(.08)
emit(type='result',result=packet)
'''


class FixtureJobs(AnalysisJobs):
    def __init__(self, cache_dir, fixture):
        super().__init__(cache_dir)
        self.fixture = fixture
        self._timer.setInterval(20)

    def _command(self, request_path):
        return sys.executable, [str(self.fixture), str(request_path)]


class ReviewJobsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['review-jobs-tests'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='review-jobs-synthetic-')
        self.root = Path(self.temp.name)
        self.fixture = self.root/'protocol_fixture.py'
        self.fixture.write_text(FIXTURE, encoding='utf-8')
        self.jobs = FixtureJobs(self.root/'cache', self.fixture)
        self.events = []
        self.results = []
        self.failures = []
        self.finished = []
        self.jobs.progress.connect(lambda key, event: self.events.append((key, event)))
        self.jobs.result.connect(lambda key, value: self.results.append((key, value)))
        self.jobs.failure.connect(lambda key, value: self.failures.append((key, value)))
        self.jobs.finished.connect(lambda: self.finished.append(True))

    def tearDown(self):
        if self.jobs.is_running():
            self.jobs.stop()
            self.wait_until(lambda: not self.jobs.is_running(), timeout=5000)
        self.jobs.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def sources(self, *modes):
        rows=[]
        for index, mode in enumerate(modes):
            path=self.root/(mode+'.svg')
            path.write_text('<svg/>')
            rows.append({'id':'registered-'+str(index),'path':str(path)})
        return rows

    def wait_until(self, predicate, timeout=6000):
        if predicate():
            return
        loop=QEventLoop()
        poll=QTimer()
        poll.setInterval(15)
        poll.timeout.connect(lambda: loop.quit() if predicate() else None)
        watchdog=QTimer()
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(loop.quit)
        poll.start();watchdog.start(timeout);loop.exec();poll.stop();watchdog.stop()
        self.assertTrue(predicate(), 'Actual Qt event-loop condition did not complete')

    def test_pause_waits_for_real_file_result_then_resumes_remaining_queue(self):
        def pause_first(key,event):
            if key=='registered-0' and event.get('stage')=='import':
                self.jobs.pause()
        self.jobs.progress.connect(pause_first)
        self.jobs.start(self.sources('success','second'))
        self.wait_until(lambda:self.jobs.paused)
        self.assertTrue(self.jobs.is_running())
        self.assertFalse(self.jobs.busy)
        self.assertEqual([key for key,_ in self.results],['registered-0'])
        self.assertEqual(self.finished,[])
        self.assertTrue(any(event['stage']=='pausing' for _,event in self.events))
        self.jobs.resume()
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual([key for key,_ in self.results],['registered-0','registered-1'])
        self.assertEqual(self.failures,[])
        self.assertEqual(len(self.finished),1)

    def test_checkpoint_is_recovered_before_failure_and_raw_error_is_not_forwarded(self):
        ordering=[]
        self.jobs.result.connect(lambda *_:ordering.append('result'))
        self.jobs.failure.connect(lambda *_:ordering.append('failure'))
        self.jobs.start(self.sources('partial'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(ordering,['result','failure'])
        self.assertEqual(self.results[0][1]['status'],'PARTIAL')
        self.assertTrue(self.results[0][1]['recovered_after_interruption'])
        self.assertNotIn('PRIVATE_CUSTOMER',self.failures[0][1])
        logs=list((self.root/'cache/jobs').glob('*.stderr.local.log'))
        self.assertEqual(len(logs),1)
        self.assertIn('PRIVATE_CUSTOMER',logs[0].read_text())

    def test_checkpoint_outside_owned_cache_is_not_read_even_with_matching_hash(self):
        self.jobs.start(self.sources('escape'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(self.results,[])
        self.assertEqual(len(self.failures),1)

    def test_repeated_messages_cannot_extend_stage_deadline(self):
        started=time.monotonic()
        self.jobs.start(self.sources('heartbeat'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(len(self.failures),1)
        self.assertLess(time.monotonic()-started,4)
        self.assertTrue(any(event['stage']=='timeout' for _,event in self.events))

    def test_real_stage_changes_cannot_bypass_whole_file_budget(self):
        self.jobs.TOTAL_TIMEOUT_SECONDS=.4
        self.jobs.start(self.sources('total'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(len(self.failures),1)
        self.assertIn('整體判讀時間',self.failures[0][1])

    def test_oversized_line_is_rejected_without_stalling_ui(self):
        self.jobs.MAX_LINE_BYTES=2048
        self.jobs.start(self.sources('overflow'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(len(self.failures),1)
        self.assertEqual(self.results,[])

    def test_failed_start_emits_once_and_controller_can_start_again(self):
        real_command=self.jobs._command
        self.jobs._command=lambda request:('/not-a-real-review-worker-executable',[])
        self.jobs.start(self.sources('success'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(len(self.failures),1)
        self.assertEqual(len(self.finished),1)
        self.jobs._command=real_command
        self.finished.clear();self.failures.clear()
        self.jobs.start(self.sources('success'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(len(self.results),1)
        self.assertEqual(self.failures,[])

    def test_unwritable_request_location_reports_failure_without_stalling_queue(self):
        self.jobs._request_dir.rmdir()
        self.jobs._request_dir.write_text('blocked local directory')
        self.jobs.start(self.sources('success'))
        self.wait_until(lambda:bool(self.finished))
        self.assertEqual(len(self.failures),1)
        self.assertIn('保存位置',self.failures[0][1])
        self.assertEqual(self.results,[])
        self.assertFalse(self.jobs.is_running())

    def test_stop_terminates_owned_worker_descendant_and_does_not_start_next_file(self):
        self.jobs.start(self.sources('child','second'))
        pidfile=self.root/'cache/owned-child.pid'
        self.wait_until(pidfile.exists)
        pid=int(pidfile.read_text())
        self.assertTrue(psutil.pid_exists(pid))
        self.jobs.stop()
        self.wait_until(lambda:bool(self.finished))
        def gone():
            try:
                return not psutil.Process(pid).is_running() or psutil.Process(pid).status()==psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                return True
        self.wait_until(gone)
        self.assertEqual(self.results,[])
        self.assertEqual(self.failures,[])
        stopped=[key for key,event in self.events if event['stage']=='stopped']
        self.assertIn('registered-0',stopped)
        self.assertIn('registered-1',stopped)

    @unittest.skipUnless(shutil.which('inkscape') or Path(os.environ.get('TEMPLATE_AI_INKSCAPE','/not-present-review-inkscape')).is_file(),
                         'real Inkscape is required for engine round trip')
    def test_actual_distributed_entry_runs_real_local_analysis_and_preserves_source(self):
        self.jobs.deleteLater()
        self.jobs=AnalysisJobs(self.root/'actual-cache')
        self.jobs.progress.connect(lambda key,event:self.events.append((key,event)))
        self.jobs.result.connect(lambda key,value:self.results.append((key,value)))
        self.jobs.failure.connect(lambda key,value:self.failures.append((key,value)))
        self.jobs.finished.connect(lambda:self.finished.append(True))
        source=self.root/'中文範例.ai'
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" viewBox="0 0 60 30">'
                          '<rect x="0" y="0" width="60" height="30" fill="white" stroke="black"/>'
                          '<text x="5" y="10" font-size="4">hello@example.com</text></svg>',encoding='utf-8')
        expected=hashlib.sha256(source.read_bytes()).hexdigest()
        self.jobs.start([{'id':'registered-original-id','path':str(source)}],ocr=False)
        self.wait_until(lambda:bool(self.finished),timeout=120000)
        self.assertEqual(self.failures,[])
        self.assertEqual(self.results[0][0],'registered-original-id')
        self.assertTrue(self.results[0][1]['pages'])
        self.assertTrue(self.results[0][1]['works'])
        self.assertTrue(any(event.get('stage')=='import' for _,event in self.events))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),expected)


if __name__=='__main__':
    unittest.main()
