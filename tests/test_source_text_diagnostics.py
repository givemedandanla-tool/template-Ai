"""Bounded derivative evidence and real original annotation/font centre route."""
import unittest
from copy import deepcopy
from unittest.mock import patch
import xml.etree.ElementTree as ET
from PySide6.QtWidgets import QDialog
from template_ai.source_text_evidence import text_evidence,evidence_summary
from template_ai.font_dialog import FontCenterDialog
import test_annotation_gui as annotation_fixture


class SourceTextDiagnosticsTests(unittest.TestCase):
    def test_literal_tracking_transforms_and_effects_never_become_native_size_or_outline_proof(self):
        root=ET.fromstring('<svg><g id="fx" style="letter-spacing:2px;font-stretch:condensed;stroke-width:3;paint-order:stroke;transform:scale(2);opacity:0.5"><text id="t" font-family="Declared" textLength="80" lengthAdjust="spacingAndGlyphs" mask="url(#m)">Alex</text><path id="p"/></g></svg>')
        r=text_evidence({'hash':'s'},list(root.iter()),{})
        self.assertEqual(r['t']['font_declarations']['letter-spacing'],'2px')
        self.assertEqual(r['t']['font_declarations']['textLength'],'80')
        self.assertEqual({e['attribute'] for e in r['t']['observed_effect_attributes']},{'stroke-width','paint-order','transform','opacity','mask'})
        self.assertIsNone(r['t']['source_font_size_pt']);self.assertEqual(r['p']['true_outline'],'UNKNOWN')
        self.assertIn('原稿實體字級／字寬：未知',evidence_summary(r['t']))

    def test_deep_or_large_observation_has_explicit_incomplete_evidence_not_complete_proof(self):
        root=ET.Element('svg');node=root
        for i in range(80):node=ET.SubElement(node,'g',id=str(i),transform='scale(2)')
        leaf=ET.SubElement(node,'text',id='leaf',style='font-family:'+('X'*9000))
        row=text_evidence({'hash':'s'},list(root.iter()),{})['leaf']
        self.assertFalse(row['literal_evidence_complete']);self.assertIn('ANCESTRY_BUDGET_OR_CYCLE',row['evidence_limits']);self.assertIn('STYLE_BUDGET',row['evidence_limits'])
        self.assertLessEqual(len(row['observed_effect_attributes']),32);self.assertEqual(row['native_editability'],'UNKNOWN');self.assertIn('證據不完整',evidence_summary(row))

    def test_stylesheets_and_absent_source_remain_unresolved_plain_text(self):
        root=ET.fromstring('<svg><style>text{font-size:12pt}</style><text id="t">A</text></svg>')
        row=text_evidence({'hash':'s'},list(root.iter()),{})['t']
        self.assertTrue(row['stylesheet_unresolved']);self.assertIn('未解析樣式表',evidence_summary(row));self.assertIn('均未知',evidence_summary(None))


class SourceTextDiagnosticsGuiTests(unittest.TestCase):
    setUp=annotation_fixture.AnnotationGuiTests.setUp
    tearDown=annotation_fixture.AnnotationGuiTests.tearDown
    run_job=annotation_fixture.AnnotationGuiTests.run_job
    job=annotation_fixture.AnnotationGuiTests.job
    window=annotation_fixture.AnnotationGuiTests.window
    ready=annotation_fixture.AnnotationGuiTests.ready
    def test_selected_source_context_preserves_unsaved_form_source_bytes_and_published_templates(self):
        window,d=self.ready();slot=next(s for s in d.session.payload['slots'] if s['kind']=='name');d.select([slot['id']]);before=deepcopy(d.session.payload);templates=[t.to_dict() for t in window.library.templates()];d.value.setText('UNSAVED DRAFT')
        seen=[]
        def show(c):
            seen.append(c.source_context);self.assertIn(slot['id'],c.context_label.text());self.assertIn('未證實',c.context_label.text());self.assertNotEqual(c.text.text(),'UNSAVED DRAFT');self.assertEqual(c.source_reference,None);return QDialog.Rejected
        with patch.object(FontCenterDialog,'refresh'),patch.object(FontCenterDialog,'exec',show):d.source_font_diagnosis()
        self.assertEqual(len(seen),1);self.assertEqual(d.value.text(),'UNSAVED DRAFT');self.assertEqual(d.session.payload,before);self.assertEqual([t.to_dict() for t in window.library.templates()],templates);self.assertEqual(self.path.read_bytes(),self.original_bytes)
        self.assertIn('原稿實體字級／字寬：未知',d.details.toPlainText())

    def test_logo_and_ambiguous_selection_cannot_enter_general_font_replacement(self):
        window,d=self.ready();d.select([])
        with self.assertRaises(ValueError):d.source_font_context()
        logos=[s for s in d.session.payload['slots'] if s['kind']=='logo'];self.assertTrue(logos);d.select([logos[0]['id']])
        with self.assertRaisesRegex(ValueError,'Logo'):d.source_font_context()

    def test_shared_centre_rejects_overbudget_text_without_silent_truncation(self):
        window=self.window()
        center=FontCenterDialog(window,source_context={'text':'Actual','family_hint':"'DejaVu Sans', serif",'location':'Synthetic source'});self.addCleanup(center.deleteLater)
        self.assertEqual(center.query.text(),'DejaVu Sans');self.assertIsNone(center.source_reference);self.assertEqual(center.text.text(),'Actual')
        with self.assertRaisesRegex(ValueError,'未截斷'):FontCenterDialog(window,source_context={'text':'x'*4097})
