"""Isolated negative controls for adoption validation; no baseline mutation."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('adoption', HERE / 'adopt_verified_execution.py')
adoption = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adoption)
source = HERE / 'execution-001/targeted-oracles-003'
current = adoption.manifest(adoption.ROOT, code_only=True)
original = {name: (source / name).read_bytes() for name in ('source.json', 'summary.json', 'tests.json', 'catalog.json')}
mutations = [
    ('wrong_manifest_hash', 'source.json', lambda d: d.update(manifest_sha256='0' * 64)),
    ('unknown_is_not_pass', 'tests.json', lambda d: d[0].update(status='UNKNOWN')),
    ('missing_result', 'tests.json', lambda d: d.pop()),
    ('duplicate_result', 'tests.json', lambda d: d.append(copy.deepcopy(d[0]))),
    ('incomplete_module', 'summary.json', lambda d: d.update(healthy_modules=0)),
    ('changed_source', 'source.json', lambda d: d['source_manifest'].pop(next(iter(d['source_manifest'])))),
]
rows = []
with tempfile.TemporaryDirectory(prefix='noncode-evidence-controls-') as raw:
    folder = Path(raw)
    for name, content in original.items():
        (folder / name).write_bytes(content)
    adoption.checked_execution(folder, current)
    rows.append(dict(id='valid_actual_execution', status='PASS'))
    for label, name, mutate in mutations:
        data = json.loads(original[name]); mutate(data)
        (folder / name).write_text(json.dumps(data))
        rejected = False
        try:
            adoption.checked_execution(folder, current)
        except ValueError as error:
            rejected = True
            rows.append(dict(id=label, status='PASS', observed_rejection=str(error)))
        finally:
            (folder / name).write_bytes(original[name])
        if not rejected:
            raise AssertionError('Invalid evidence accepted: ' + label)
assert all((source / name).read_bytes() == content for name, content in original.items())
report = dict(kind='ISOLATED_DEMONSTRATION_NOT_ADDITIONAL_PRODUCT_TESTS', status='PASS', controls=rows,
              original_evidence_unchanged=True, validator_sha256=adoption.digest((HERE / 'adopt_verified_execution.py').read_bytes()))
(HERE / 'execution-001/evidence-negative-controls.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(status='PASS', checks=len(rows), original_evidence_unchanged=True)))
