from pathlib import Path
import unittest
from PySide6.QtCore import QSizeF
from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QPainter,QColor
from PySide6.QtCore import QMarginsF
import test_automatic_training as fixture
APP=fixture.APP

class AutomaticPagesTests(unittest.TestCase):
    setUp=fixture.AutomaticTrainingTests.setUp
    tearDown=fixture.AutomaticTrainingTests.tearDown
    run_job=fixture.AutomaticTrainingTests.run_job
    def pages(self):
        path=self.root/'all-pages.pdf';writer=QPdfWriter(str(path));writer.setResolution(96);writer.setPageSize(QPageSize(QSizeF(90,54),QPageSize.Millimeter));writer.setPageMargins(QMarginsF(0,0,0,0),QPageLayout.Millimeter);painter=QPainter(writer)
        for index,color in enumerate(('red','blue')):
            if index:self.assertTrue(writer.newPage())
            painter.fillRect(0,0,300,180,QColor(color))
        painter.end();return path
    def test_all_readable_pages_have_separate_sources_hypotheses_and_exact_second_page_retry(self):
        path=self.pages();original=path.read_bytes();report=self.service.preflight([path]);self.assertEqual([item['page'] for item in report['items']],[1,2]);self.assertEqual(report['source_file_count'],1)
        job=self.service.create(report,'SYNTHETIC',True);result=self.run_job(job);sources=[self.library.source(item['source_id']) for item in result['items']];self.assertEqual([source['page'] for source in sources],[1,2]);self.assertEqual(len({source['id'] for source in sources}),2);works=[self.library.artworks(s['id'])[0] for s in sources];self.assertNotEqual(works[0]['payload']['analysis_key'],works[1]['payload']['analysis_key'])
        first=self.service.work_unit(works[0]['id']);retry=self.service.create_retry(self.service.retry_plan([works[1]['id']]),'SYNTHETIC',True);self.run_job(retry);self.assertEqual(self.service.work_unit(works[0]['id']),first);self.assertEqual(path.read_bytes(),original)
    def test_missing_page_manifest_is_rejected_and_explicit_single_page_remains_possible(self):
        path=self.pages();report=self.service.preflight([path]);report['items'].pop()
        with self.assertRaisesRegex(ValueError,'清單不完整'):self.service.create(report,'SYNTHETIC',True)
        self.assertEqual(self.library.list_sources(),[]);single=self.service.preflight([path],page=2);self.assertFalse(single['all_pages']);self.assertEqual([i['page'] for i in single['items']],[2]);job=self.service.create(single,'SYNTHETIC',True);self.assertEqual(job['items'][0]['page'],2)
