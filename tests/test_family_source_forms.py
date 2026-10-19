from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from PySide6.QtWidgets import QApplication,QWidget

from template_ai.family_source_dialog import FamilySourceDialog
from template_ai.fonts import FontManager
from template_ai.importer import import_file
from template_ai.model import Rect,Slot
from template_ai.storage import Library
from template_ai.training_store import TrainingStore,digest

APP=QApplication.instance() or QApplication([])


class FamilySourceFormTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        self.manager=FontManager(self.library);self.addCleanup(self.manager.close)
        self.assets=[self.manager.import_font('/usr/share/fonts/truetype/dejavu/'+name,True) for name in ('DejaVuSans.ttf','DejaVuSerif.ttf')]
        source=self.root/'owned-mixed.svg'
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><text id="given" x="25" y="14" font-family="DejaVu Sans" font-size="6.35">Alex <tspan id="family" font-family="DejaVu Serif" font-size="4.23333333333333">Example</tspan></text><text id="label" x="8" y="14" font-family="DejaVu Sans" font-size="4.23333333333333">NAME</text></svg>')
        source=self.library.add_source(source,import_file(source,self.library.assets))
        slot=Slot('name','p1',Rect(8,5,75,12));payload=dict(crop=asdict(Rect(0,0,90,54)),work_width=90,work_height=54,slots=[asdict(slot)],visual_confirmed=True)
        self.work=self.library.create_artwork(source['id'],'Authored mixed source',payload)
        self.store=TrainingStore(self.library)
        observations=[dict(id='name-fact',slot_id=slot.id,text='Alex Example',object_type='TEXT',classification='FIELD',region=asdict(slot.rect))]
        facts=self.store.save_facts(self.work['id'],observations,0,self.work['revision'])
        self.store.confirm_facts(self.work['id'],['name-fact'],facts['revision'],facts['pins'],self.store.source_proof(self.work['id']),'KNOWN_SOURCE_AUTHOR',True)
        self.parent=QWidget();self.parent.library=self.library;self.addCleanup(self.parent.deleteLater)
        self.dialog=FamilySourceDialog(self.parent,self.work['id']);self.addCleanup(self.dialog.close)
        self.dialog.basis.setText('Exact authored SVG runs and local font faces')
        self.dialog.confirmed.setChecked(True);self.dialog.metrics.setChecked(True)
        self.dialog.label_kind.setCurrentIndex(self.dialog.label_kind.findData('NO_FIXED_LABEL'))

    def add_runs(self):
        for object_id,asset in [('given',self.assets[0]),('family',self.assets[1])]:
            index=next(i for i,r in enumerate(self.dialog.runs) if r['source_locator'].get('object_id')==object_id)
            self.dialog.run_choice.setCurrentIndex(index)
            font_index=next(i for i in range(self.dialog.font.count()) if (self.dialog.font.itemData(i) or {}).get('hash')==asset['hash'])
            self.dialog.font.setCurrentIndex(font_index);self.dialog.add_span()

    def test_actual_composite_form_preserves_complete_runs_and_two_local_faces(self):
        self.add_runs();self.assertEqual([(s['start'],s['end']) for s in self.dialog.spans],[(0,5),(5,12)])
        self.dialog.prepare();self.dialog.commit()
        binding=self.store.get('DESIGN_SOURCE_BINDING',digest([self.work['id'],self.work['payload']['slots'][0]['id']]))
        self.assertEqual(len(binding['spans']),2)
        self.assertEqual(len(binding['typography']['rich_text']['segments']),2)
        self.assertEqual({s['font_asset']['hash'] for s in binding['spans']},{a['hash'] for a in self.assets})

    def test_static_label_requires_exact_source_text_and_explicit_measurement(self):
        self.add_runs();self.dialog.presentation_review.setChecked(True)
        self.dialog.label_kind.setCurrentIndex(self.dialog.label_kind.findData('SEPARATE_STATIC_LABEL'))
        index=next(i for i,r in enumerate(self.dialog.runs) if r['source_locator'].get('object_id')=='label')
        self.dialog.label_run.setCurrentIndex(self.dialog.label_run.findData(index))
        self.dialog.label_font.setCurrentIndex(1);self.dialog.label_measured.setChecked(True);self.dialog.label_pt.setValue(12)
        self.dialog.label_text.setText('WRONG')
        with self.assertRaises(ValueError):self.dialog.prepare()
        self.dialog.label_text.setText('NAME')
        for widget,value in zip(self.dialog.frames['value'],[.3,0,.7,1]):widget.setValue(value)
        for widget,value in zip(self.dialog.frames['label'],[0,0,.25,1]):widget.setValue(value)
        self.dialog.prepare();self.dialog.commit()
        binding=self.store.get('DESIGN_SOURCE_BINDING',digest([self.work['id'],self.work['payload']['slots'][0]['id']]))
        presentation=binding['source_text_flow']['presentation']
        self.assertEqual(presentation['components'][0]['text'],'NAME')
        self.assertEqual(presentation['value_frame'],[.3,0,.7,1])
