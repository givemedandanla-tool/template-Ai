"""Documents lacking size clues must not initialize the optional clustering stack."""
import builtins
import unittest
from unittest.mock import patch
from template_ai.source_region_hypotheses import region_hypotheses
from template_ai.model import Rect


class NoClusteringNeededTests(unittest.TestCase):
    def assert_no_clustering(self,texts):
        original=builtins.__import__
        def import_local(name,*args,**kwargs):
            if name=='sklearn' or name.startswith('sklearn.'):
                raise AssertionError('Clustering is unnecessary without both size clues and content')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=import_local):
            result=region_hypotheses(texts,Rect(0,0,90,54))
        self.assertEqual(result['state'],'NO_UNAMBIGUOUS_SIZE_REGION')
        self.assertEqual(result['candidates'],[])
        self.assertTrue(result['review_required'])

    def test_empty_document_does_not_load_clustering(self):self.assert_no_clustering([])
    def test_plain_contact_data_does_not_load_clustering(self):
        self.assert_no_clustering([('name','Alex Example',Rect(1,1,30,5)),('email','alex@example.org',Rect(1,8,40,5))])
    def test_size_clue_without_content_does_not_load_clustering(self):
        self.assert_no_clustering([('size','90x54mm',Rect(1,1,20,5))])
