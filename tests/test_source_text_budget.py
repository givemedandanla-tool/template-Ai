from pathlib import Path
import unittest
from template_ai.annotation_dialog import AnnotationDialog
from template_ai.demo import demo_template
import test_automatic_training as fixture
APP=fixture.APP

class SourceTextBudgetTests(unittest.TestCase):
    setUp=fixture.AutomaticTrainingTests.setUp
    tearDown=fixture.AutomaticTrainingTests.tearDown
    job=fixture.AutomaticTrainingTests.job
    run_job=fixture.AutomaticTrainingTests.run_job
    window=fixture.AutomaticTrainingGuiTests.window
    def document(self,count):
        text='姓名：'+'W'*count;self.path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="190mm" height="60mm" viewBox="0 0 190 60"><rect id="frameA" width="90" height="54" fill="white"/><text id="longName" x="5" y="12" font-size="0.01">'+text+'</text><g transform="translate(100 0)"><rect id="frameB" width="90" height="54" fill="white"/><text id="normalName" x="5" y="12" font-size="4">姓名：Blair Example</text></g></svg>');return text
    def test_supported_long_source_text_survives_analysis_property_edit_and_atomic_save_without_truncation(self):
        full=self.document(600);result=self.run_job(self.job());source=self.library.source(result['items'][0]['source_id']);work=min(self.library.artworks(source['id']),key=lambda row:row['payload']['crop']['x']);facts=self.service.store.facts(work['id']);observation=next(o for o in facts['observations'] if o['text'].startswith('姓名：W'));self.assertEqual(observation['text'],full)
        window=self.window();dialog=AnnotationDialog(window,work['id']);self.addCleanup(dialog.deleteLater);dialog.select([observation['slot_id']]);self.assertEqual(dialog.value.text(),full);dialog.coords[0].setValue(dialog.coords[0].value()+1);dialog.apply_properties();dialog.save_or_raise();self.assertEqual(next(o['text'] for o in dialog.session.facts['observations'] if o['id']==observation['id']),full)
    def test_oversized_text_is_explicitly_blocked_in_one_work_without_partial_observation_or_unsafe_publish(self):
        full=self.document(2200);result=self.run_job(self.job());source=self.library.source(result['items'][0]['source_id']);a,b=sorted(self.library.artworks(source['id']),key=lambda row:row['payload']['crop']['x']);unit=self.service.work_unit(a['id'])[1];self.assertTrue(any(issue['code']=='SOURCE_TEXT_BUDGET' and issue['severity']=='BLOCK' for issue in unit['issues']));self.assertFalse(any(issue['code']=='SOURCE_TEXT_BUDGET' for issue in self.service.work_unit(b['id'])[1]['issues']));self.assertEqual(self.service.store.facts(a['id'])['observations'],[]);self.assertEqual(a['payload']['analysis_evidence']['oversized_text'][0]['characters'],len(full))
        template=demo_template();template.source_id=source['id'];template.source_work_id=a['id'];template.source_work_revision=a['revision']
        with self.assertRaisesRegex(ValueError,'資源預算'):self.library.publish(template)
        self.assertEqual(self.library.templates(),[])
