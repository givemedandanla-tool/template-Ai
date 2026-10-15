import unittest
import xml.etree.ElementTree as ET
from template_ai.model import Rect
from template_ai.source_text_evidence import text_evidence,identity_match


class SourceTextEvidenceTests(unittest.TestCase):
    def test_effect_path_is_never_misclassified_as_outlined_text_and_unknown_native_metrics_stay_unknown(self):
        root=ET.fromstring('<svg><g id="effect" style="font-family:Example;filter:url(#shadow)" transform="scale(2)"><text id="t" font-size="12pt">Example</text><path id="p" d="M0,0L1,1"/></g></svg>')
        nodes=list(root.iter());bounds={'t':Rect(1,2,30,5)}
        rows=text_evidence({'hash':'abc','file_hashes':{'svg':'def'}},nodes,bounds)
        self.assertEqual(rows['t']['font_declarations']['font-family'],'Example')
        self.assertEqual(rows['t']['font_declarations']['font-size'],'12pt')
        self.assertEqual(rows['t']['derivative_bounds_mm']['w'],30)
        self.assertIsNone(rows['t']['source_font_size_pt'])
        self.assertEqual(rows['p']['true_outline'],'UNKNOWN')
        self.assertEqual(rows['t']['native_editability'],'UNKNOWN')
        self.assertEqual({e['attribute'] for e in rows['t']['observed_effect_attributes']},{'filter','transform'})

    def test_logo_text_is_protected_and_names_or_visual_similarity_cannot_prove_original_identity(self):
        root=ET.fromstring('<svg><g id="logo"><text id="inside">Brand</text></g><style>text {font-size:15pt}</style></svg>')
        nodes=list(root.iter());protected={id(n) for n in nodes if n.get('id') in ('logo','inside')}
        rows=text_evidence({'hash':'h'},nodes,{},protected)
        self.assertTrue(rows['inside']['logo_protected']);self.assertTrue(rows['inside']['stylesheet_unresolved'])
        self.assertEqual(identity_match({'family':'Example'},{'family':'Example'})['state'],'POSSIBLE_ALIAS')
        self.assertEqual(identity_match({'visual_score':1},{'visual_score':1})['state'],'UNIDENTIFIED')
        self.assertEqual(identity_match({'font_sha256':'a'},{'hash':'a'})['state'],'PROVEN_SAME_BYTES')
