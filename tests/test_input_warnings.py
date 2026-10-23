from pathlib import Path
import tempfile,unittest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.demo import demo_template
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.model import Slot,Rect
APP=QApplication.instance() or QApplication([])

class InputWarningsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.w=MainWindow(Path(self.temp.name)/'data');self.addCleanup(self.w.library.close);self.addCleanup(self.w.input_timer.stop);self.addCleanup(self.w.font_manager.close);self.t=demo_template();self.w.library.publish(self.t)
    def test_typing_has_inline_warning_and_exact_navigation_without_focus_loss_or_adoption(self):
        graph=InputGraph.from_legacy([dict(name=['Alex'],title=['Designer'])],[]);d=InputGraphDialog(self.w,graph.data);self.addCleanup(d.deleteLater);self.addCleanup(d.warning_timer.stop);d.show();APP.processEvents();fid=next(f['id'] for f in graph.data['fields'] if f['kind']=='name');editor=d.field_editors[fid];editor.setFocus();editor.selectAll();QTest.keyClicks(editor,'W'*200);QTest.qWait(220);APP.processEvents()
        self.assertTrue(editor.hasFocus());self.assertEqual(d.graph.field(fid)['value'],'Alex');self.assertIn('預估風險',d.summary.text());self.assertTrue(any(label.text() for label in d.field_warnings[fid]));self.assertEqual(d.warning_report['issues'][0]['field_id'],fid);self.assertFalse(d.warning_report['global_unsolvable']);d.locate_warning(d.problems.item(0));self.assertTrue(editor.hasFocus());self.assertIsNone(self.w.active_input_graph)
    def test_company_warning_uses_company_field_identity_and_fixed_point_measurement(self):
        self.t.state='draft';self.t.family_id='synthetic-warning-company';self.t.id='synthetic-company-warning';self.t.slots.append(Slot('company','c1',Rect(4,48,40,5),font=self.t.slots[0].font,size_pt=10));self.t.company_bindings={'p1':['c1']};self.w.library.publish(self.t)
        graph=InputGraph.from_legacy([dict(name=['Alex'],company='c1')],[dict(name='Brand')]);d=InputGraphDialog(self.w,graph.data);self.addCleanup(d.deleteLater);self.addCleanup(d.warning_timer.stop);fid=next(f['id'] for f in graph.data['fields'] if f['owner_id']==graph.data['companies'][0]['id'] and f['kind']=='name');d.pending_input[fid]='W'*200;d.refresh_warnings();issues=[i for i in d.warning_report['issues'] if i.get('field_id')==fid];self.assertTrue(issues);self.assertEqual(issues[0]['owner'],'c1');self.assertEqual(issues[0]['parameters']['size_pt'],10);self.assertTrue(d.field_warnings[fid][0].text());self.assertEqual(graph.field(fid)['value'],'Brand')

    def test_closed_library_stops_pending_warning_callback_without_false_pass(self):
        graph=InputGraph.from_legacy([dict(name=['Alex'])],[]);d=InputGraphDialog(self.w,graph.data);self.addCleanup(d.deleteLater);d.warning_timer.start(1);self.w.library.close();d.refresh_warnings();self.assertFalse(d.warning_timer.isActive());self.assertIn('資料庫已關閉',d.summary.text())
