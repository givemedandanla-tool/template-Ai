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

    def test_real_qualified_and_blocked_candidate_sections_auto_choose_and_revalidate_current_input(self):
        from template_ai.demo import demo_template
        from PySide6.QtWidgets import QTableWidgetItem
        good=demo_template();good.name='Qualified synthetic';bad=demo_template();bad.name='Narrow diagnostic';bad.slots[0].rect.w=20;self.w.library.publish(good);self.w.library.publish(bad)
        self.w.people.setRowCount(1)
        for col,value in enumerate(('Alex Example','Designer','123','a@example.test','','','','')):self.w.people.setItem(0,col,QTableWidgetItem(value))
        self.w.tabs.setCurrentIndex(2);self.w.generate();APP.processEvents();self.assertEqual(self.w.qualified_candidates.count(),1);self.assertEqual(self.w.blocked_candidates.count(),1);self.assertTrue(self.w.export_button.isEnabled());self.assertTrue(self.w.candidates[0].valid)
        view=self.w.blocked_candidates;QTest.mouseClick(view.viewport(),Qt.LeftButton,pos=view.visualItemRect(view.item(0)).center());APP.processEvents();self.assertFalse(self.w.export_button.isEnabled());self.assertIn('禁止正式',self.w.input_state.text());self.assertEqual(len(self.w.library.templates(True)),2)
        view=self.w.qualified_candidates;QTest.mouseClick(view.viewport(),Qt.LeftButton,pos=view.visualItemRect(view.item(0)).center());APP.processEvents();self.assertTrue(self.w.export_button.isEnabled())
        self.w.people.item(0,0).setText('Changed input');self.assertFalse(self.w.export_button.isEnabled());self.assertFalse(self.w.qualified_candidates.isEnabled())
