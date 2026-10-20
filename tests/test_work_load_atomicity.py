"""Real window/navigation preserves the current work when a stored draft is unreadable."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile,unittest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.model import Rect
from runtime_fixture import controlled_resources
from gui_wait import dispose_main_window
APP=QApplication.instance() or QApplication([])

class WorkLoadAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.w=MainWindow(self.root/'data');controlled_resources(self.w);self.addCleanup(dispose_main_window,self.w)
        self.sources=[];self.works=[]
        for i in range(2):
            path=self.root/f'authored-{i}.png';image=QImage(360,216,QImage.Format_RGB32);image.fill(0xffaabbcc);self.assertTrue(image.save(str(path),'PNG'))
            source=self.w.library.add_source(path,import_file(path,self.w.library.assets));payload=dict(crop=asdict(Rect(0,0,source['width_mm'],source['height_mm'])),work_width=90.,work_height=54.,slots=[],visual_confirmed=False)
            self.sources.append(source);self.works.append(self.w.library.create_artwork(source['id'],'Authored work',payload))
        self.w.refresh_sources(self.sources[0]['id']);APP.processEvents();self.assertEqual(self.w.work['id'],self.works[0]['id'])
        self.before=self.state();self.addCleanup(self.restore_readable_context)

    def state(self):
        return dict(source=self.w.source['id'] if self.w.source else None,work=self.w.work['id'] if self.w.work else None,crop=asdict(self.w.crop) if self.w.crop else None,slots=[asdict(s) for s in self.w.slots],size=(self.w.work_width,self.w.work_height))

    def restore_readable_context(self):
        self.w.source=self.sources[0];self.w.load_work(self.works[0])

    def unreadable(self,work):
        payload=deepcopy(work['payload']);payload['slots']=[dict(kind='name',owner='p1',rect=None)]
        return self.w.library.save_artwork(work['id'],payload,work['revision'])

    def dismiss_error(self,action):
        seen=[];timer=QTimer()
        def close_message():
            modal=APP.activeModalWidget()
            if isinstance(modal,QMessageBox):seen.append(True);modal.reject()
        timer.timeout.connect(close_message);timer.start(10)
        try:action()
        finally:timer.stop()
        self.assertTrue(seen,'Use the actual error dialog, not a substituted window')

    def test_unreadable_work_does_not_partially_replace_live_state(self):
        bad=self.unreadable(self.works[1])
        with self.assertRaises((TypeError,ValueError)):self.w.load_work(bad)
        self.assertEqual(self.state(),self.before)

    def test_source_navigation_failure_retains_original_source_and_work(self):
        bad=self.unreadable(self.works[1]);self.w.refresh_sources(self.sources[0]['id'])
        index=next(i for i,s in enumerate(self.w.sources) if s['id']==self.sources[1]['id'])
        self.dismiss_error(lambda:self.w.choose_source(index))
        self.assertEqual(self.state(),self.before);self.assertEqual(self.w.library.artwork(bad['id']),bad)

    def test_work_navigation_failure_does_not_persist_failed_selection(self):
        good=self.works[0];bad=self.w.library.create_artwork(good['source_id'],'Unreadable second work',good['payload']);bad=self.unreadable(bad);self.w.library.select_artwork(good['source_id'],good['id']);self.assertEqual(self.w.library.active_artwork(good['source_id'])['id'],good['id']);self.w.refresh_works();index=next(i for i,w in enumerate(self.w.works) if w['id']==bad['id'])
        self.dismiss_error(lambda:self.w.choose_work(index))
        self.assertEqual(self.state(),self.before);self.assertEqual(self.w.library.active_artwork(good['source_id'])['id'],good['id']);self.assertEqual(self.w.library.artwork(bad['id']),bad)

    def test_direct_foreign_work_cannot_be_mixed_with_current_source(self):
        with self.assertRaisesRegex(ValueError,'不屬於'):
            self.w.load_work(self.works[1])
        self.assertEqual(self.state(),self.before)
