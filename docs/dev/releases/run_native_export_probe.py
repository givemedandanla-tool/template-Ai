"""Run the unchanged three-format GUI case alone; diagnosis never builds/releases."""
from pathlib import Path
import json
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[3]
target=ROOT/'artifacts/package-check'
target.mkdir(parents=True,exist_ok=True)
def retain_startup_error(kind,value,tb):
    (target/'native-export-probe-error.log').write_text(
        ''.join(traceback.format_exception(kind,value,tb))[-64000:],encoding='utf-8')
    sys.__excepthook__(kind,value,tb)
sys.excepthook=retain_startup_error
sys.path.insert(0,str(ROOT/'tools'))
from dev_common import write_json
from evidence_modules import run_modules

expected=['test_input_learning_integration.InputLearningIntegrationTests.test_shared_learning_preview_preserves_original_pdf_png_jpg_formats']
folder=ROOT/'artifacts/native-export-probe'
result,errors,log=run_modules(expected,folder,test_root=ROOT/'tests',workers=1,module_timeout=180)
passed=result.wasSuccessful() and not errors
write_json(target/'native-export-probe.json',dict(
    status='PASS' if passed else 'FAIL',
    qualification='SINGLE_UNCHANGED_GUI_CASE_DIAGNOSIS_NOT_FROZEN_EXE_OR_RELEASE',
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    expected=expected,records=list(result.records.values()),modules=result.modules,runtime_errors=errors))
for name in ['unittest.log','stacks.log','progress.json']:
    source=folder/'modules/test_input_learning_integration'/name
    if source.is_file():(target/('export-probe-'+name)).write_bytes(source.read_bytes()[-64000:])
(target/'export-probe-owner.log').write_text(log[-64000:],encoding='utf-8')
print(json.dumps(dict(status='PASS' if passed else 'FAIL',executed=len(result.records),not_a_release=True)))
raise SystemExit(not passed)
