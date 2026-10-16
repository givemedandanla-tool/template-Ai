import copy
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
import test_quality_gold_sets as fixtures
from template_ai import quality_engine
from template_ai.quality_pipeline import QualityPipelines


class QualityEngineTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp

    def test_actual_distinct_source_versions_execute_their_own_frozen_code(self):
        package=Path(quality_engine.__file__).parent
        baseline=quality_engine.freeze(self.library.assets,package)
        candidate_root=self.root/'candidate-app';candidate_root.mkdir()
        for file in package.glob('*.py'):shutil.copyfile(file,candidate_root/file.name)
        with (candidate_root/'source_analysis.py').open('a') as file:
            file.write('\n_original_analysis=analyse_source\ndef analyse_source(*args,**kwargs):\n    rows=_original_analysis(*args,**kwargs)\n    for row in rows:row["evidence"]["synthetic_version_counterexample"]="CANDIDATE_EXECUTED"\n    return rows\n')
        candidate=quality_engine.freeze(self.library.assets,candidate_root)
        source=self.library.source(self.source['id'])
        left=quality_engine.execute(baseline,source,self.library.assets,None,None)
        right=quality_engine.execute(candidate,source,self.library.assets,None,None)
        self.assertNotEqual(baseline['code_digest'],candidate['code_digest'])
        self.assertNotIn('synthetic_version_counterexample',left[0]['evidence'])
        self.assertEqual(right[0]['evidence']['synthetic_version_counterexample'],'CANDIDATE_EXECUTED')
        self.assertFalse(any(name.startswith('_template_ai_quality_') for name in sys.modules))
        self.assertFalse(list(Path(baseline['files']['__init__.py']['path']).parent.glob('__pycache__')))

    def test_actual_pipeline_does_not_call_later_live_parser_implementation(self):
        service=QualityPipelines(self.library);pipeline=service.freeze('Frozen actual parser',None,'Synthetic reviewer',True)
        with patch('template_ai.quality_pipeline.analyse_source',side_effect=AssertionError('live parser must not replace frozen version')):
            prediction=service.predict_source(pipeline['id'],self.source['id'])
        self.assertTrue(prediction['predictions'])

    def test_tampered_or_missing_snapshot_cannot_execute_or_report_quality(self):
        service=QualityPipelines(self.library);pipeline=service.freeze('Frozen parser integrity',None,'Synthetic reviewer',True)
        path=Path(pipeline['manifest']['engine']['files']['source_analysis.py']['path']);path.write_text(path.read_text()+'\n# synthetic tamper\n')
        self.assertFalse(service.validity(pipeline['id'])['valid'])
        with self.assertRaises(ValueError):service.predict_source(pipeline['id'],self.source['id'])

    def test_freeze_reuses_exact_immutable_code_without_capturing_private_library_data(self):
        package=Path(quality_engine.__file__).parent
        first=quality_engine.freeze(self.library.assets,package);second=quality_engine.freeze(self.library.assets,package)
        self.assertEqual(first,second)
        self.assertTrue(all(name.endswith('.py') for name in first['files']))
        self.assertNotIn('library.sqlite3',first['files'])
