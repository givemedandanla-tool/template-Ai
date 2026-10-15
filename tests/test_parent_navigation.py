from pathlib import Path
import tempfile,threading,unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtTest import QTest
from template_ai.gui import MainWindow
APP=QApplication.instance() or QApplication([])

class ParentNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.w=MainWindow(Path(self.temp.name)/'data');self.addCleanup(self.w.deleteLater);self.addCleanup(self.w.library.close);self.addCleanup(self.w.font_manager.close);self.addCleanup(self.w.input_timer.stop);self.w.show();APP.processEvents()
    def test_three_mode_function_rail_and_collapsible_panels_keep_background_job_once(self):
        self.assertEqual(self.w.tabs.count(),3);entered=threading.Event();release=threading.Event();done=[];calls=[]
        def work():calls.append(1);entered.set();release.wait(3);return 'complete'
        self.w.run_job('SYNTHETIC ongoing work',work,done.append);self.assertTrue(entered.wait(1))
        for mode in [1,2,0]:self.w.tabs.setCurrentIndex(mode);self.assertEqual(self.w.function_stack.currentIndex(),mode);self.assertTrue(self.w.busy);self.assertEqual(len(self.w._background_jobs),1)
        for text,panel in [('功能導覽 顯示／收合',self.w.function_rail),('屬性面板 顯示／收合',self.w.property_panel)]:
            button=next(b for b in self.w.findChildren(QPushButton) if b.text()==text);panel.setVisible(True);QTest.mouseClick(button,Qt.LeftButton);self.assertFalse(panel.isVisible());QTest.mouseClick(button,Qt.LeftButton);self.assertTrue(panel.isVisible())
        release.set()
        for _ in range(200):
            APP.processEvents();QTest.qWait(5)
            if not self.w.busy:break
        self.assertEqual(calls,[1]);self.assertEqual(done,['complete']);self.assertEqual(self.w._background_jobs,{});self.assertFalse(self.w.busy);self.assertEqual(self.w.tabs.count(),3)
