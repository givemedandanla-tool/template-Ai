"""Bounded current-component regression; raw failures remain local."""
import argparse,hashlib,json,sys,unittest
from pathlib import Path
repo=Path(__file__).resolve().parents[2];sys.path[:0]=[str(repo),str(repo/'tests')]

def run(output):
    output.mkdir(exist_ok=False)
    names=['test_review_combo_palette','test_review_native_observation','test_review_illustrator_bridge','test_review_session',
        'test_review_canvas','test_review_diagnostics','test_review_failed_source','test_review_stdio',
        'test_original_text_observation','test_source_region_hypotheses',
        'test_review_tool_gui.ReviewToolGuiTests.test_popup_menus_remain_readable_with_dark_system_palette',
        'test_review_tool_gui.ReviewToolGuiTests.test_first_window_is_visible_and_numeric_overview_is_hidden']
    suite=unittest.defaultTestLoader.loadTestsFromNames(names)
    class Result(unittest.TextTestResult):
        def addSuccess(self,test):super().addSuccess(test);passed.append(test.id())
    passed=[]
    with (output/'tests.local.txt').open('x',encoding='utf8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=Result).run(suite)
    files=[*sorted((repo/'template_ai/review_tool').rglob('*.py')),repo/'template_ai/source_analysis.py']
    files += [repo/'tests'/(name.split('.')[0]+'.py') for name in names]
    hashes={p.relative_to(repo).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    summary=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed_test_ids=passed,source_sha256=hashes,scope='Current review component; not whole repository, OCR or packaged release qualification')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('passed_test_ids','source_sha256')}))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);raise SystemExit(run(p.parse_args().output))
