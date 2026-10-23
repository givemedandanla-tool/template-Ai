"""Immutable Windows release for the independent, offline artwork review tool.

This is a component release, not qualification of the older Template AI editor,
training system or a private artwork corpus. Existing release paths are untouched.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/review-release'
BUILD = ROOT / 'build/review-release'
PRODUCT = ROOT / 'dist/TemplateAIReview'
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'docs/dev/releases')]
REUSED_TESTS = ('test_import_pages', 'test_import_exceptions', 'test_original_pdf_glyphs',
    'test_original_text_observation', 'test_source_region_hypotheses', 'test_semantic_fields',
    'test_inkscape_cache_identity', 'test_bundled_inkscape')


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def version():
    tree = ast.parse((ROOT / 'template_ai/review_tool/__init__.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets):
            value = ast.literal_eval(node.value)
            import re
            if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+-beta\.\d+', value):
                raise ValueError('Review tool requires an explicit beta component version')
            return value
    raise ValueError('Review tool version is not declared')


def tag():
    return 'review-v' + version()


def commit():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def identity():
    """Bind all shipped Python and locks to exact committed bytes, not a label."""
    files = sorted((ROOT / 'template_ai').rglob('*.py'))
    files += sorted(p for p in (ROOT / 'template_ai/review_tool/icons').rglob('*') if p.is_file())
    files += [ROOT / name for name in ['review_app.py', 'requirements-lock.txt',
        '.github/windows-wheels-lock.json', '.github/release-assets-lock.json',
        'tools/inkscape_distribution_lock.json', 'tools/review_release.py', 'tools/bundled_inkscape_build.py',
        'tools/install_ocr_models.py', 'docs/dev/releases/release_cache.py',
        'docs/dev/releases/release_actions_support.py', '.github/workflows/review-release.yml']]
    files += sorted((ROOT / 'tests').glob('test_review_*.py'))
    files += [ROOT / 'tests' / (name + '.py') for name in REUSED_TESTS]
    tree = subprocess.check_output(['git', 'ls-tree', '-r', 'HEAD'], cwd=ROOT, text=True).splitlines()
    blobs = {line.split('\t', 1)[1]: line.split('\t', 1)[0].split()[2] for line in tree}
    rows = []
    for path in files:
        data = path.read_bytes()
        relative = path.relative_to(ROOT).as_posix()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != blobs.get(relative):
            raise ValueError('Shipped source differs from committed bytes: ' + relative)
        rows.append(dict(path=relative, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), git_blob_sha1=blob))
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return dict(source_commit=commit(), source_manifest_sha256=digest, source_matches_head=True, source_files=rows)


@contextmanager
def stage(name):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / 'release-timings.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(schema_version=1, source_commit=commit(), stages=[])
    if data['source_commit'] != commit():
        raise ValueError('Do not mix release timing evidence from different commits')
    row = dict(name=name, started_utc=datetime.now(timezone.utc).isoformat(), status='RUNNING')
    data['stages'].append(row)
    write(path, data)
    start = time.perf_counter()
    try:
        yield
    except BaseException as error:
        row.update(status='FAIL', error_type=type(error).__name__, message=str(error)[:500])
        raise
    else:
        row['status'] = 'PASS'
    finally:
        row['seconds'] = round(time.perf_counter() - start, 6)
        write(path, data)


def prepare(cache):
    if os.name != 'nt':
        raise ValueError('Windows release preparation must run on native Windows')
    from release_cache import prepare as prepare_inputs, install_dependencies
    with stage('verified_fixed_inputs'):
        prepare_inputs(Path(cache), OUTPUT / 'verified-inputs.json')
        install_dependencies(Path(cache))
    # Public OCR language data is separately pinned by official Git object IDs.
    # This does not claim that an OCR executable is included.
    from install_ocr_models import install
    with stage('pinned_public_ocr_models'):
        install(BUILD / 'ocr-models')


def filter_upstream_test_data(datas, report_path):
    """Exclude only the confirmed hook-collected sklearn dataset test fixtures."""
    import importlib.metadata
    import importlib.util
    distribution = importlib.metadata.distribution('scikit-learn')
    origin = importlib.util.find_spec('sklearn')
    package = Path(distribution.locate_file('sklearn')).resolve(strict=True)
    if origin is None or not origin.origin or Path(origin.origin).resolve(strict=True).parent != package:
        raise ValueError('Installed sklearn import origin differs from distribution metadata')
    wheels = json.loads((ROOT / '.github/windows-wheels-lock.json').read_text(encoding='utf-8'))['wheels']
    pins = [row for row in wheels if row['name'] == 'scikit-learn']
    if len(pins) != 1 or distribution.version != pins[0]['version']:
        raise ValueError('Installed sklearn differs from the fixed build dependency version')
    tests_root = (package / 'datasets/tests').resolve(strict=True)
    if not tests_root.is_dir() or not tests_root.is_relative_to(package):
        raise ValueError('Installed sklearn dataset test directory is invalid')
    kept, removed = [], []
    for row in datas:
        destination = PurePosixPath(str(row[0]).replace('\\', '/'))
        if destination.parts[:3] != ('sklearn', 'datasets', 'tests') or len(destination.parts) < 4:
            kept.append(row)
            continue
        if '..' in destination.parts or len(row) != 3 or row[2] != 'DATA':
            raise ValueError('Unexpected sklearn dataset test data destination/type')
        source = Path(row[1])
        if source.is_symlink() or not source.is_file():
            raise ValueError('Sklearn test fixture source must be an installed regular file')
        source = source.resolve(strict=True)
        if (not source.is_relative_to(tests_root)
                or source.relative_to(tests_root).parts != destination.parts[3:]):
            raise ValueError('Sklearn test fixture source differs from its installed dataset test path: '+destination.as_posix())
        removed.append(dict(destination=destination.as_posix(), source_relative='sklearn/'+source.relative_to(package).as_posix(),
            bytes=source.stat().st_size, sha256=sha(source), type=row[2]))
    write(report_path, dict(schema_version=1, status='PASS', policy='EXCLUDE_CONFIRMED_UPSTREAM_DATASET_TEST_FIXTURES_ONLY',
        reason='PyInstaller sklearn hook collected development fixtures; runtime data and the private-payload guard stay unchanged.',
        distribution=dict(name='scikit-learn', version=distribution.version, locked_wheel_sha256=pins[0]['sha256'],
            import_origin_matches_installed_distribution=True),
        input_entries=len(datas), kept_entries=len(kept), removed_entries=len(removed), removed=removed))
    return kept


def make_spec():
    BUILD.mkdir(parents=True, exist_ok=True)
    pin = json.loads((ROOT / 'build/release/inkscape-runtime-pin.json').read_text(encoding='utf-8'))
    write(BUILD / 'release-info.json', dict(component='TemplateAIReview', version=version(), tag=tag(),
        source_commit=commit(), inkscape_runtime=pin, architecture='windows-x64', signed=False,
        data_schema_policy='INDEPENDENT_REVIEW_SESSION_NO_LEGACY_DATABASE_MIGRATION',
        qualification='INTERNAL_BETA_AWAITING_USER_LOCAL_CONFIRMATION',
        ocr=dict(runtime='OPTIONAL_LOCAL_TESSERACT_NOT_BUNDLED', public_models='BUNDLED_ENG_CHI_TRA')))
    spec = r'''from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata, collect_data_files
import sys
root = Path(SPECPATH).parent.parent
sys.path.insert(0, str(root/'tools'))
from review_release import filter_upstream_test_data
datas = [(str(p), p.parent.relative_to(root).as_posix()) for p in sorted((root/'template_ai').rglob('*.py'))]
datas += [(str(p), p.parent.relative_to(root).as_posix()) for p in sorted((root/'template_ai/review_tool/icons').rglob('*')) if p.is_file()]
datas += [(str(root/'review_app.py'), '.'), (str(root/'build/review-release/release-info.json'), '.')]
for name in ['PySide6','PySide6_Addons','PySide6_Essentials','shiboken6','cryptography','cffi','pycparser','pypdf',
    'phonenumbers','kiwisolver','fonttools','psutil','networkx','scikit-learn','numpy','scipy','joblib',
    'threadpoolctl','pdfminer.six','charset-normalizer']:
    datas += copy_metadata(name)
datas += collect_data_files('PySide6', includes=['*LICENSE*','Qt/licenses/*'])
python_license = Path(sys.base_prefix)/'LICENSE.txt'
if python_license.is_file(): datas += [(str(python_license), 'licenses/python')]
a = Analysis([str(root/'review_app.py')], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=collect_submodules('template_ai.review_tool'), hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest','ruff','pyright','jscpd','IPython','matplotlib','tkinter'], noarchive=False)
a.datas = filter_upstream_test_data(a.datas, root/'artifacts/review-release/upstream-build-exclusions.json')
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='TemplateAIReview',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=True,hide_console='hide-early')
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='TemplateAIReview')
'''
    (BUILD / 'TemplateAIReview.spec').write_text(spec, encoding='utf-8')


def build():
    if os.name != 'nt':
        raise ValueError('Build must run on native Windows')
    identity()
    make_spec()
    if PRODUCT.exists():
        raise FileExistsError('Refuse to reuse or overwrite an earlier application build')
    with stage('clean_pyinstaller_build'):
        with (OUTPUT / 'pyinstaller.log').open('wb') as log:
            result = subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
                str(BUILD / 'TemplateAIReview.spec')], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
        if result.returncode:
            raise RuntimeError('PyInstaller failed; see pyinstaller.log')
    with stage('verified_engine_and_models_install'):
        from release_cache import validate_engine, load_locks
        _, assets = load_locks()
        validate_engine(ROOT / 'build/inkscape-staged', assets['engine'])
        shutil.copytree(ROOT / 'build/inkscape-staged', PRODUCT / 'engines/inkscape')
        shutil.copytree(BUILD / 'ocr-models', PRODUCT / 'engines/ocr-models')
        for src, name in [('docs/dev/releases/' + tag() + '/QUICK_START.md', '使用說明.md'),
                          ('docs/THIRD_PARTY.md', '第三方授權.md')]:
            shutil.copy2(ROOT / src, PRODUCT / name)
        shutil.copy2(BUILD / 'release-info.json', PRODUCT / 'release-info.json')


class ImmediateTraceResult(unittest.TextTestResult):
    """Keep the original failure even when a later Qt cleanup never returns."""
    def _write_immediate(self, kind, test, error):
        self.stream.write('\nIMMEDIATE_' + kind + ': ' + self.getDescription(test) + '\n')
        self.stream.write(self._exc_info_to_string(error, test))
        self.stream.flush()

    def addFailure(self, test, err):
        self._write_immediate('FAILURE', test, err)
        super().addFailure(test, err)

    def addError(self, test, err):
        self._write_immediate('ERROR', test, err)
        super().addError(test, err)


def test_one(module, output):
    sys.path.insert(0, str(ROOT / 'tests'))
    suite = unittest.defaultTestLoader.loadTestsFromName(module)
    result = unittest.TextTestRunner(verbosity=2, resultclass=ImmediateTraceResult).run(suite)
    report = dict(module=module, tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=[dict(test=str(t), reason=reason) for t, reason in result.skipped],
        status='PASS' if result.wasSuccessful() and result.testsRun > len(result.skipped) else 'FAIL')
    write(output, report)
    return 0 if report['status'] == 'PASS' else 1


def stop_owned_test_tree(process):
    """Terminate only this isolated test process and its observed descendants."""
    import psutil
    try:
        parent = psutil.Process(process.pid)
        descendants = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        process.wait(timeout=10)
        return dict(status='STOPPED', root_pid=process.pid, observed_descendants=0)
    owned = [parent] + descendants
    # Stop the root first so it cannot create more children during cleanup.
    for item in owned:
        try:item.kill()
        except psutil.NoSuchProcess:pass
    _, alive = psutil.wait_procs(owned, timeout=10)
    process.wait(timeout=10)
    remaining = []
    for item in alive:
        try:
            if item.is_running() and item.status() != psutil.STATUS_ZOMBIE:remaining.append(item)
        except psutil.NoSuchProcess:pass
    return dict(status='STOPPED' if not remaining else 'FAILED', root_pid=process.pid,
        observed_descendants=len(descendants), remaining_pids=[item.pid for item in remaining])


def run_isolated_test(module, command, output, log_path, *, cwd, env, timeout=240):
    """A timeout is evidence of ERROR, never a passing or skipped module."""
    output, log_path = Path(output), Path(log_path)
    options = dict(start_new_session=True) if os.name != 'nt' else dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    start = time.perf_counter()
    timed_out = False
    cleanup = None
    with log_path.open('wb') as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, **options)
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:cleanup = stop_owned_test_tree(process)
            except Exception as error:
                cleanup = dict(status='FAILED', error_type=type(error).__name__, message=str(error)[:300])
            exit_code = process.poll()
            log.write(('\nRELEASE_MODULE_TIMEOUT: ' + json.dumps(dict(module=module, timeout_seconds=timeout,
                process_tree_cleanup=cleanup), sort_keys=True) + '\n').encode())
            log.flush()
    if timed_out:
        row = dict(module=module, status='ERROR', termination='TIMEOUT', tests_run=0,
            tests_run_complete=False, failures=0, errors=1, skipped=[], timeout_seconds=timeout,
            process_tree_cleanup=cleanup)
    else:
        try:
            row = json.loads(output.read_text(encoding='utf-8'))
            if row.get('module') != module or row.get('status') not in {'PASS', 'FAIL'}:
                raise ValueError('Unexpected module result identity/status')
        except (OSError, ValueError, TypeError) as error:
            row = dict(module=module, status='ERROR', termination='MISSING_OR_INVALID_RESULT', tests_run=0,
                tests_run_complete=False, failures=0, errors=1, skipped=[], error_type=type(error).__name__)
    row.update(exit_code=exit_code, seconds=round(time.perf_counter()-start, 6))
    write(output, row)
    return row


def source_tests():
    start = identity()
    component_modules = sorted(p.stem for p in (ROOT / 'tests').glob('test_review_*.py'))
    if not component_modules:
        raise ValueError('No component tests found; empty discovery is not a pass')
    modules = sorted(set(component_modules) | set(REUSED_TESTS))
    if any(not (ROOT / 'tests' / (name + '.py')).is_file() for name in modules):
        raise ValueError('Required reused-core test module is missing')
    folder = OUTPUT / 'source-tests'
    folder.mkdir(parents=True, exist_ok=True)
    reports = []
    env = os.environ.copy()
    env['TEMPLATE_AI_INKSCAPE'] = str(ROOT / 'build/inkscape-staged/bin/inkscape.exe') if os.name == 'nt' else env.get('TEMPLATE_AI_INKSCAPE', shutil.which('inkscape') or '')
    if os.name == 'nt':
        env['PATH'] = str(ROOT / 'build/inkscape-staged/bin') + os.pathsep + env.get('PATH', '')
    env['TEMPLATE_AI_TESSDATA'] = str(BUILD / 'ocr-models')
    with stage('isolated_current_component_tests'):
        for module in modules:
            out = folder / (module + '.json')
            row = run_isolated_test(module, [sys.executable, str(Path(__file__)), 'test-one', '--module', module,
                '--output', str(out)], out, folder / (module + '.log'), cwd=ROOT, env=env)
            reports.append(row)
            if row.get('process_tree_cleanup', {}).get('status') == 'FAILED':break
        summary = dict(status='PASS' if len(reports) == len(modules) and all(r['status'] == 'PASS' and r['exit_code'] == 0 for r in reports) else 'FAIL',
            scope='INDEPENDENT_REVIEW_COMPONENT_NOT_OLDER_FULL_PRODUCT', modules=reports,
            modules_not_run=modules[len(reports):], timeout_modules=[r['module'] for r in reports if r.get('termination') == 'TIMEOUT'],
            required_reused_core_modules=list(REUSED_TESTS), component_modules=component_modules,
            test_counts_complete=all(r.get('tests_run_complete', True) for r in reports),
            tests_run=sum(r['tests_run'] for r in reports), failures=sum(r['failures'] for r in reports),
            errors=sum(r['errors'] for r in reports), skipped=sum(len(r['skipped']) for r in reports),
            source_commit=start['source_commit'], source_manifest_sha256=start['source_manifest_sha256'],
            source_unchanged_during_run=start == identity(), platform=platform.platform(), real_corpus_qualified=False)
        write(OUTPUT / 'source-tests.json', summary)
        if summary['status'] != 'PASS' or not summary['source_unchanged_during_run']:
            raise RuntimeError('Component tests failed; original per-module results retained')


def exercise(executable):
    executable = Path(executable).resolve()
    if os.name != 'nt' or not executable.is_file() or executable.read_bytes()[:2] != b'MZ':
        raise ValueError('A real frozen Windows executable is required')
    start = identity()
    out = OUTPUT / 'actual-exe'
    out.mkdir(parents=True, exist_ok=False)
    result_path = out / 'result.json'
    capture = out / 'empty-startup.png'
    with stage('actual_normal_startup_and_visible_window'):
        start_time = time.perf_counter()
        with (out / 'normal-startup.log').open('wb') as log:
            startup = subprocess.run([str(executable), '--data-dir', str(out / 'startup-data'),
                '--capture', str(capture)], cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=90)
        if (startup.returncode or not capture.is_file() or capture.stat().st_size < 128
                or capture.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n'):
            raise RuntimeError('Actual normal startup did not produce a visible-window capture')
        startup_proof = dict(status='PASS', normal_entrypoint=True, exit_code=startup.returncode,
            seconds=round(time.perf_counter()-start_time,6), capture=capture.name,
            capture_sha256=sha(capture), data_scope='ISOLATED_SYNTHETIC_EMPTY_DATA')
        write(out / 'normal-startup.json', startup_proof)
    with stage('actual_exe_ui_worker_and_reopen'):
        with (out / 'process.log').open('wb') as log:
            result = subprocess.run([str(executable), '--release-check', str(result_path)], cwd=out,
                stdout=log, stderr=subprocess.STDOUT, timeout=300)
        if not result_path.exists():
            raise RuntimeError('Actual executable did not write its acceptance result')
        value = json.loads(result_path.read_text(encoding='utf-8'))
        if (result.returncode or value.get('status') != 'PASS' or not value.get('actual_frozen_executable')
                or not value.get('source_unchanged') or value.get('private_data_included') is not False
                or value.get('worker_mode') != 'ACTUAL_QPROCESS'
                or 'actual_worker_uses_bundled_inkscape' not in value.get('checks', [])):
            raise RuntimeError('Actual executable acceptance failed; preserve its diagnostics')
        proof = dict(status='PASS', version=version(), source_commit=start['source_commit'],
            source_manifest_sha256=start['source_manifest_sha256'], source_unchanged_during_run=start == identity(),
            actual_frozen_executable=True, executable_sha256=sha(executable), normal_startup=startup_proof, acceptance=value)
        write(OUTPUT / 'actual-exe.json', proof)
        if not proof['source_unchanged_during_run']:
            raise RuntimeError('Source changed while testing actual executable')


def safe_member(name):
    value = PurePosixPath(name)
    if (not name or '\\' in name or value.is_absolute() or value.as_posix() != name
            or any(part in ('..', '.', '') for part in value.parts) or ':' in name):
        raise ValueError('Unsafe archive member')
    return value.as_posix()


def package_preflight():
    current = identity()
    tests = json.loads((OUTPUT / 'source-tests.json').read_text(encoding='utf-8'))
    acceptance = json.loads((OUTPUT / 'actual-exe.json').read_text(encoding='utf-8'))
    for report in [tests, acceptance]:
        if (report.get('status') != 'PASS' or report.get('source_commit') != current['source_commit']
                or report.get('source_manifest_sha256') != current['source_manifest_sha256']
                or not report.get('source_unchanged_during_run')):
            raise ValueError('Current exact source and actual executable must pass before packaging')
    exe = PRODUCT / 'TemplateAIReview.exe'
    if sha(exe) != acceptance['executable_sha256']:
        raise ValueError('Accepted executable bytes changed')
    from bundled_inkscape_build import vendor_inventory
    vendor = vendor_inventory(PRODUCT)
    model_manifest = json.loads((PRODUCT / 'engines/ocr-models/MODEL_MANIFEST.json').read_text(encoding='utf-8'))
    from install_ocr_models import COMMIT as MODEL_COMMIT, FILES as MODEL_FILES
    if (model_manifest.get('commit') != MODEL_COMMIT
            or {row['name'] for row in model_manifest['files']} != set(MODEL_FILES)
            or len(model_manifest['files']) != len(MODEL_FILES)):
        raise ValueError('OCR model inventory differs from pinned official objects')
    models = {'engines/ocr-models/MODEL_MANIFEST.json'}
    for row in model_manifest['files']:
        name = 'engines/ocr-models/' + safe_member(row['name'])
        if sha(PRODUCT / name) != row['sha256'] or (PRODUCT / name).stat().st_size != row['bytes']:
            raise ValueError('OCR model or license changed after installation')
        data = (PRODUCT / name).read_bytes()
        if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != MODEL_FILES[row['name']]:
            raise ValueError('OCR model is not the pinned official Git object')
        models.add(name)
    entries = []
    forbidden = {'tests', 'tools', '.git', '.venv', 'local-data', '__pycache__', 'node_modules'}
    for p in sorted(PRODUCT.rglob('*')):
        if p.is_symlink():
            raise ValueError('Symlink in release package')
        if not p.is_file():
            continue
        rel = p.relative_to(PRODUCT).as_posix()
        if rel not in vendor | models and (forbidden.intersection(p.relative_to(PRODUCT).parts)
                or p.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.ttf', '.otf', '.ttc', '.ai', '.traineddata'}):
            raise ValueError('Unexpected private/development payload: ' + rel)
        entries.append(dict(path=rel, bytes=p.stat().st_size, sha256=sha(p)))
    source = json.loads((ROOT / 'artifacts/corresponding-source-verification.json').read_text(encoding='utf-8'))
    if source['status'] != 'PASS' or source.get('archives_verified') != 125:
        raise ValueError('Verified Inkscape corresponding sources required')
    if sha(ROOT / 'artifacts' / source['asset']) != source['sha256']:
        raise ValueError('Verified corresponding-source archive changed before packaging')
    return current, tests, acceptance, entries, source


def package():
    with stage('package_preflight'):
        current, tests, acceptance, entries, source = package_preflight()
    archive = OUTPUT / ('TemplateAIReview-v' + version() + '-windows-x64.zip')
    with stage('package_and_inventory'):
        with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for row in entries:
                z.write(PRODUCT / row['path'], 'TemplateAIReview/' + row['path'])
        manifest = dict(schema_version=1, component='TemplateAIReview', version=version(), tag=tag(),
            source_commit=current['source_commit'], source_manifest_sha256=current['source_manifest_sha256'],
            platform='windows-x64', signed=False, package_files=entries, package_file_count=len(entries),
            archive=dict(name=archive.name, bytes=archive.stat().st_size, sha256=sha(archive)),
            source_tests=tests, actual_exe=acceptance, corresponding_sources=source,
            ocr=dict(runtime='OPTIONAL_LOCAL_TESSERACT_NOT_BUNDLED', public_models='BUNDLED_ENG_CHI_TRA'),
            compatibility='Separate review-tool local data. Does not migrate or open older production database.',
            qualification='INTERNAL_BETA_PUBLISHED_AWAITING_USER_LOCAL_CONFIRMATION',
            known_limits=['Private AI fidelity and user Windows hardware remain unqualified.',
                'Ambiguous font/spacing/structure stay unknown; review is not model training.',
                'Tesseract executable is optional and not bundled; original-text and manual routes work offline.'])
        write(OUTPUT / 'release-manifest.json', manifest)
        write(OUTPUT / 'SOURCE_DOWNLOADS.json', dict(schema_version=1, sources=[source],
            method='REUSED_UNCHANGED_PUBLIC_CORRESPONDING_SOURCE_ARCHIVE_FULL_125_OBJECT_VERIFICATION'))
        write(OUTPUT / 'validation-summary.json', dict(status='PASS', component='TemplateAIReview',
            version=version(), source_commit=commit(), source_tests=tests, actual_exe=acceptance,
            product_scope='ARTWORK_ANALYSIS_REVIEW_ONLY_NOT_OLDER_TRAINING_OR_LAYOUT_PRODUCT',
            private_data_included=False, real_corpus_qualified=False))
        files = [archive, OUTPUT / 'release-manifest.json', OUTPUT / 'SOURCE_DOWNLOADS.json', OUTPUT / 'validation-summary.json']
        (OUTPUT / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in files), encoding='utf-8')


def verify_download(folder, expected_manifest=None):
    folder = Path(folder)
    expected_manifest = Path(expected_manifest or OUTPUT / 'release-manifest.json')
    reference = json.loads(expected_manifest.read_text(encoding='utf-8'))
    raw = (folder / 'release-manifest.json').read_bytes()
    if raw != expected_manifest.read_bytes():
        raise ValueError('Downloaded manifest differs from verified build manifest')
    value = json.loads(raw)
    if value['source_commit'] != commit() or value['tag'] != tag() or value['version'] != version():
        raise ValueError('Downloaded source or component version differs')
    archive = folder / value['archive']['name']
    if sha(archive) != value['archive']['sha256'] or archive.stat().st_size != value['archive']['bytes']:
        raise ValueError('Downloaded archive hash/size differs')
    expected = {'TemplateAIReview/' + safe_member(r['path']): r for r in value['package_files']}
    if len(expected) != value['package_file_count'] or not expected:
        raise ValueError('Empty or duplicate package inventory')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('Downloaded ZIP inventory differs')
        for name in names:
            safe_member(name)
            row = expected[name]
            h = hashlib.sha256()
            with z.open(name) as stream:
                for block in iter(lambda: stream.read(1048576), b''):
                    h.update(block)
            if z.getinfo(name).file_size != row['bytes'] or h.hexdigest() != row['sha256']:
                raise ValueError('Downloaded member bytes differ: ' + name)
    for name in ['SOURCE_DOWNLOADS.json', 'validation-summary.json', 'SHA256SUMS.txt']:
        if (folder / name).read_bytes() != (OUTPUT / name).read_bytes():
            raise ValueError('Downloaded companion file differs: ' + name)
    write(folder / 'download-verification.json', dict(status='PASS', component='TemplateAIReview', version=version(),
        source_commit=commit(), archive_sha256=sha(archive), verified_files=len(expected),
        corresponding_sources=reference['corresponding_sources'], real_corpus_qualified=False))


def validate_request(request, version_text, source_sha):
    """A pre-commit request may leave its source null; the CI manifest binds HEAD."""
    if (request.get('version') != version_text or request.get('tag') != 'review-v' + version_text
            or request.get('scope') != 'PUBLISH_WINDOWS_INTERNAL_BETA' or not request.get('user_request')
            or request.get('published') is not False or request.get('source_commit') not in (None, source_sha)):
        raise ValueError('Missing current component release authorization or mismatched explicit source pin')


def publish():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('REVIEW_RELEASE_PUBLISH_ALLOWED') != 'true':
        raise ValueError('Only explicitly authorized fresh Windows workflow can publish')
    state = json.loads((ROOT / 'docs/dev/STATE.json').read_text(encoding='utf-8'))
    request = state.get('review_tool_release_request', {})
    validate_request(request, version(), commit())
    ref = os.environ.get('GITHUB_REF')
    if ref != 'refs/heads/release-request/' + tag():
        raise ValueError('Publish ref must be the exact explicit review component request')
    repository = 'givemedandanla-tool/template-Ai'
    def gh(*args):
        options = [] if args[0] == 'api' else ['--repo', repository]
        return subprocess.run(['gh', *args, *options], cwd=ROOT, capture_output=True, text=True, timeout=180)
    # Existing release OR existing tag is immutable. Any API error other than a
    # positively observed 404 blocks publication; authentication errors never pass.
    existing = gh('api', 'repos/' + repository + '/releases/tags/' + tag())
    if existing.returncode == 0 or '404' not in existing.stderr:
        raise ValueError('Release exists or absence cannot be established')
    refs = subprocess.run(['git', 'ls-remote', '--tags', 'https://github.com/' + repository + '.git',
        'refs/tags/' + tag()], capture_output=True, text=True, timeout=60)
    if refs.returncode or refs.stdout.strip():
        raise ValueError('Tag exists or absence cannot be established')
    manifest = json.loads((OUTPUT / 'release-manifest.json').read_text(encoding='utf-8'))
    if manifest['source_commit'] != commit():
        raise ValueError('Package is not from this exact commit')
    names = [manifest['archive']['name'], 'release-manifest.json', 'SOURCE_DOWNLOADS.json', 'validation-summary.json', 'SHA256SUMS.txt']
    with stage('draft_release_download_publish_download'):
        subprocess.run(['git', 'tag', tag(), commit()], cwd=ROOT, check=True)
        subprocess.run(['git', 'push', 'https://github.com/' + repository + '.git', 'refs/tags/' + tag()], cwd=ROOT, check=True, timeout=90)
        result = gh('release', 'create', tag(), '--verify-tag', '--draft', '--prerelease', '--title',
            '作品判讀與核對工具 ' + version() + ' — Windows 實測版', '--notes-file',
            str(ROOT / 'docs/dev/releases' / tag() / 'RELEASE_NOTES.md'),
            *[str(OUTPUT / n) for n in names])
        if result.returncode:
            raise RuntimeError('Draft creation failed; retained tag must be investigated, never overwritten')
        for phase in ['draft', 'public']:
            dest = OUTPUT / (phase + '-download');dest.mkdir(exist_ok=False)
            result = gh('release', 'download', tag(), '--dir', str(dest), *sum([['--pattern', n] for n in names], []))
            if result.returncode:
                raise RuntimeError('Actual GitHub download failed: ' + phase)
            verify_download(dest)
            if phase == 'draft':
                result = gh('release', 'edit', tag(), '--draft=false', '--prerelease')
                if result.returncode:
                    raise RuntimeError('Draft verified but public release update failed')
        write(OUTPUT / 'delivery.json', dict(status='RELEASE_PUBLISHED_DOWNLOAD_VERIFIED', tag=tag(), version=version(),
            source_commit=commit(), url='https://github.com/' + repository + '/releases/tag/' + tag(),
            downloads=['draft', 'public'], archive=manifest['archive'], user_local_confirmation=False))


def persist_evidence():
    """Append public synthetic metadata/captures, never product or user data."""
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('Evidence branch writes run only in the authorized workflow')
    import tempfile
    import re
    version_text = version()
    run = os.environ.get('GITHUB_RUN_ID', '') + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '')
    if not re.fullmatch(r'\d+-\d+', run):
        raise ValueError('Expected immutable Actions run/attempt identity')
    branch = 'review-release-evidence/v' + version_text
    remote = 'https://github.com/givemedandanla-tool/template-Ai.git'
    prefix = 'runs/' + run + '-' + commit()[:12] + '/'
    selected = []
    for path in sorted(OUTPUT.rglob('*')):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in {'.json', '.log', '.png'}:
            continue
        rel = path.relative_to(OUTPUT)
        if any(part in {'draft-download', 'public-download'} for part in rel.parts):
            # Retain the two exact verification reports, not duplicate manifests.
            if path.name != 'download-verification.json':continue
        if path.stat().st_size > 8 * 1048576:
            raise ValueError('Evidence exceeds bounded text/image publication size')
        selected.append(path)
    if not selected:
        raise ValueError('No actual evidence to preserve')
    # An isolated Git index leaves the source checkout and its HEAD unchanged.
    with tempfile.TemporaryDirectory(prefix='review-evidence-') as raw:
        env = os.environ.copy()
        env.update(GIT_INDEX_FILE=str(Path(raw) / 'index'), GIT_AUTHOR_NAME='Codex review evidence',
            GIT_AUTHOR_EMAIL='review-evidence@users.noreply.github.com', GIT_COMMITTER_NAME='Codex review evidence',
            GIT_COMMITTER_EMAIL='review-evidence@users.noreply.github.com')
        def git(*args, input=None):
            return subprocess.run(['git', *args], cwd=ROOT, env=env, input=input, capture_output=True,
                check=True, timeout=90).stdout.decode().strip()
        previous = git('ls-remote', remote, 'refs/heads/' + branch)
        parent = previous.split()[0] if previous else None
        if parent:
            git('fetch', '--no-tags', '--depth=1', remote, 'refs/heads/' + branch)
            git('read-tree', parent)
        else:
            git('read-tree', '--empty')
        inventory = []
        for path in selected:
            name = prefix + path.relative_to(OUTPUT).as_posix()
            blob = git('hash-object', '-w', '--stdin', input=path.read_bytes())
            git('update-index', '--add', '--cacheinfo', '100644', blob, name)
            inventory.append(dict(path=name, bytes=path.stat().st_size, sha256=sha(path), git_blob_sha1=blob))
        record = dict(scope='PUBLIC_SYNTHETIC_REVIEW_RELEASE_EVIDENCE', source_commit=commit(), run=run,
            files=inventory, user_data_included=False, external_qualification_unchanged=True)
        blob = git('hash-object', '-w', '--stdin', input=(json.dumps(record, ensure_ascii=False, indent=2)+'\n').encode())
        git('update-index', '--add', '--cacheinfo', '100644', blob, prefix + 'EVIDENCE_MANIFEST.json')
        tree = git('write-tree')
        args = ['commit-tree', tree]
        if parent:args += ['-p', parent]
        evidence_commit = git(*args, '-m', 'Preserve review Windows evidence ' + run)
        git('push', remote, evidence_commit + ':refs/heads/' + branch)
        actual = git('ls-remote', remote, 'refs/heads/' + branch).split()[0]
        if actual != evidence_commit:
            raise ValueError('Evidence branch ref did not read back exactly')
        write(OUTPUT / 'evidence-persistence.json', dict(status='PUSHED_REF_READBACK_NOT_FULL_CHECKPOINT_ACK',
            branch=branch, commit=evidence_commit, tree=tree, source_commit=commit(), files=len(inventory)+1))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'build', 'test', 'test-one', 'exercise', 'package', 'verify-download', 'publish', 'persist-evidence'])
    p.add_argument('--cache', type=Path)
    p.add_argument('--executable', type=Path, default=PRODUCT / 'TemplateAIReview.exe')
    p.add_argument('--output', type=Path)
    p.add_argument('--expected-manifest', type=Path)
    p.add_argument('--module')
    args = p.parse_args(argv)
    if args.command == 'prepare':
        if args.cache is None:p.error('prepare requires --cache')
        prepare(args.cache)
    elif args.command == 'build':build()
    elif args.command == 'test':source_tests()
    elif args.command == 'test-one':
        if not args.module or args.output is None:p.error('test-one requires --module and --output')
        return test_one(args.module, args.output)
    elif args.command == 'exercise':exercise(args.executable)
    elif args.command == 'package':package()
    elif args.command == 'verify-download':
        if args.output is None:p.error('verify-download requires --output')
        verify_download(args.output,args.expected_manifest)
    elif args.command == 'publish':publish()
    elif args.command == 'persist-evidence':persist_evidence()
    return 0


def public_failure_text(value):
    """Retain exception/stack evidence without signed URL queries or tokens."""
    import re
    value = re.sub(r'(https?://[^\s\'"<>?]+)\?[^\s\'"<>]+', r'\1?[REDACTED_QUERY]', value)
    value = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b', '[REDACTED_TOKEN]', value)
    return re.sub(r'(?i)(authorization\s*:\s*(?:bearer|token)\s+)\S+', r'\1[REDACTED_TOKEN]', value)


def save_command_error(command, error):
    """Only the public synthetic Actions pipeline publishes command failures."""
    import traceback
    known = {'prepare', 'build', 'test', 'test-one', 'exercise', 'package', 'verify-download', 'publish', 'persist-evidence'}
    command = command if command in known else 'cli'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    trace = public_failure_text(''.join(traceback.format_exception(type(error), error, error.__traceback__)))
    (OUTPUT / (command + '-command-error.log')).write_text(trace, encoding='utf-8')
    write(OUTPUT / (command + '-command-error.json'), dict(status='ERROR', command=command,
        source_commit=commit(), error_type=type(error).__name__, message=public_failure_text(str(error))[:1000],
        traceback_log=command+'-command-error.log', redaction='SIGNED_URL_QUERIES_AND_CREDENTIAL_PATTERNS',
        scope='PUBLIC_SYNTHETIC_RELEASE_PIPELINE_ONLY', exception_preserved=True))


def entrypoint(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        return main(arguments)
    except Exception as error:
        if os.environ.get('GITHUB_ACTIONS') == 'true':
            try:save_command_error(arguments[0] if arguments else 'cli', error)
            except Exception as recording_error:
                print('Release error evidence could not be saved: '+type(recording_error).__name__, file=sys.stderr)
        raise


if __name__ == '__main__':
    raise SystemExit(entrypoint())
