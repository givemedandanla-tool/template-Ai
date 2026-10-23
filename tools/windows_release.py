"""Source-bound Windows packaging and bounded actual-executable acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from template_ai import __version__


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def source_commit():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def source_identity():
    sys.path.insert(0, str(ROOT / 'tools'))
    from dev_common import manifest, manifest_digest
    files = manifest(ROOT, code_only=True)
    lines = subprocess.check_output(['git', 'ls-tree', '-r', 'HEAD'], cwd=ROOT, text=True).splitlines()
    blobs = {line.split('\t', 1)[1]: line.split('\t', 1)[0].split()[2] for line in lines}
    return dict(source_commit=source_commit(), source_manifest_sha256=manifest_digest(files),
                source_matches_head=all(blobs.get(p) == row['git_blob_sha1'] for p, row in files.items()))


def make_spec():
    """Keep product .py bytes for existing immutable engine/source fingerprints."""
    target = ROOT / 'build' / 'release'
    target.mkdir(parents=True, exist_ok=True)
    engine_pin = json.loads((target / 'inkscape-runtime-pin.json').read_text(encoding='utf-8'))
    write(target / 'release-info.json', dict(version=__version__, source_commit=source_commit(),
          inkscape_runtime=engine_pin,
          architecture='windows-x64', data_schema_policy='EXISTING_LOCAL_SCHEMA_NO_FORCED_MIGRATION',
          signed=False, qualification='INTERNAL_BETA_AWAITING_USER_LOCAL_CONFIRMATION'))
    numbers = tuple(int(x) for x in __version__.split('-')[0].split('.')) + (int(__version__.rsplit('.', 1)[1]),)
    (target / 'version.txt').write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=" + repr(numbers) + ", prodvers=" + repr(numbers) +
        ", mask=0x3f, flags=0x2, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)), "
        "kids=[StringFileInfo([StringTable('040904B0', [StringStruct('FileDescription', 'Template AI internal beta'), "
        "StringStruct('FileVersion', '" + __version__ + "'), StringStruct('ProductVersion', '" + __version__ +
        "'), StringStruct('ProductName', 'Template AI')])]), VarFileInfo([VarStruct('Translation', [1033,1200])])])",
        encoding='utf-8')
    spec = '''from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, copy_metadata, collect_data_files
root = Path(SPECPATH).parent.parent
datas = [(str(path), 'template_ai') for path in sorted((root / 'template_ai').glob('*.py'))]
datas += [(str(root / 'app.py'), '.'), (str(root / 'build/release/release-info.json'), '.')]
for distribution in ['PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6', 'cryptography', 'cffi', 'pycparser',
    'pypdf', 'phonenumbers', 'kiwisolver', 'fonttools', 'psutil', 'networkx', 'scikit-learn', 'numpy', 'scipy',
    'joblib', 'threadpoolctl', 'pdfminer.six', 'charset-normalizer']:
    datas += copy_metadata(distribution)
datas += collect_data_files('PySide6', includes=['*LICENSE*', 'Qt/licenses/*'])
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.is_file(): datas += [(str(python_license), 'licenses/python')]
a = Analysis([str(root / 'app.py')], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=collect_submodules('template_ai'), hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'ruff', 'pyright', 'jscpd', 'IPython', 'matplotlib', 'tkinter'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='TemplateAI', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=True, hide_console='hide-early',
    version=str(root / 'build/release/version.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='TemplateAI')
'''
    # SPECPATH points to build/release, so the checkout root is two parents up.
    spec = spec.replace('root = Path(SPECPATH).parent.parent', 'import sys\nroot = Path(SPECPATH).parent.parent')
    (target / 'TemplateAI.spec').write_text(spec, encoding='utf-8')


def exercise(executable, output):
    """Keep fixture sources alive while two real executable processes use them."""
    source_mode = os.path.samefile(executable, sys.executable)
    identity = source_identity()
    sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools')]
    from test_design_session import DesignSessionTests
    from test_automatic_training import AutomaticTrainingTests
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    if application.platformName() not in ('windows', 'offscreen', 'xcb'):
        raise RuntimeError('Unexpected Qt acceptance platform')
    DesignSessionTests.setUpClass()
    worker = AutomaticTrainingTests()
    worker.setUp()
    try:
        output.mkdir(parents=True, exist_ok=False)
        root = DesignSessionTests.root
        (root / 'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA')
        job = worker.job()
        spec = dict(fixture='AUTHORED_RELEASE_ACCEPTANCE_V1', root=str(root), phase='exercise',
                    dataset_id=DesignSessionTests.dataset_id, worker_root=str(worker.library.root), job_id=job['id'])
        worker.library.close()
        path = root / 'release-check.json'
        write(path, spec)
        for phase in ('exercise', 'resume'):
            spec = json.loads(path.read_text(encoding='utf-8'))
            spec['phase'] = phase
            write(path, spec)
            command = [str(executable), '--release-check', str(path)]
            # On source runs, Python needs app.py before the same fixed arguments.
            if source_mode:
                command.insert(1, str(ROOT / 'app.py'))
            with (output / (phase + '.log')).open('wb') as log:
                try:
                    result = subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=240)
                finally:
                    evidence = root / 'evidence'
                    if evidence.exists():
                        shutil.copytree(evidence, output, dirs_exist_ok=True)
            if result.returncode:
                raise RuntimeError('Actual executable acceptance failed in ' + phase + '; inspect bounded evidence')
        write(output / 'summary.json', dict(status='PASS', **identity, version=__version__,
              executable_sha256=sha(executable), platform=platform.platform(), phases=['exercise', 'resume'],
              source_unchanged_during_run=identity == source_identity(),
              actual_frozen_executable=not source_mode, real_corpus_qualified=False))
    finally:
        worker.tearDown()
        DesignSessionTests.tearDownClass()


def package():
    folder = ROOT / 'dist' / 'TemplateAI'
    executable = folder / 'TemplateAI.exe'
    if os.name != 'nt' or not executable.is_file() or executable.read_bytes()[:2] != b'MZ':
        raise RuntimeError('An actual Windows executable is required')
    artifacts = ROOT / 'artifacts'
    for source, name in [('docs/dev/releases/WINDOWS_BETA_QUICK_START.md', '使用說明.md'),
                         ('docs/THIRD_PARTY.md', '第三方授權.md')]:
        shutil.copy2(ROOT / source, folder / name)
    shutil.copy2(ROOT / 'build/release/release-info.json', folder / 'release-info.json')
    # No fixture database, downloaded font, models, tooling or historical evidence.
    forbidden_dirs = {'tests', 'tools', '.git', '.venv', 'local-data', 'node_modules', '__pycache__'}
    from bundled_inkscape_build import vendor_inventory
    vendor_files = vendor_inventory(folder)
    entries = []
    for path in sorted(folder.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(folder)
        if relative.as_posix() not in vendor_files and (forbidden_dirs.intersection(relative.parts) or path.suffix.lower() in {'.sqlite3', '.sqlite', '.db', '.ttf', '.ttc', '.otf', '.ai'}):
            raise RuntimeError('Unexpected private/development/font payload: ' + relative.as_posix())
        entries.append(dict(path=relative.as_posix(), bytes=path.stat().st_size, sha256=sha(path)))
    source_tests = json.loads((artifacts / 'source-tests/summary.json').read_text(encoding='utf-8'))
    acceptance = json.loads((artifacts / 'package-check/summary.json').read_text(encoding='utf-8'))
    governance = json.loads((artifacts / 'governance-gate.json').read_text(encoding='utf-8-sig'))
    state = json.loads((ROOT / 'docs/dev/STATE.json').read_text(encoding='utf-8'))
    full_run = json.loads((ROOT / state['latest_evidence_run']).read_text(encoding='utf-8'))
    windows_scope = json.loads((ROOT / '.github/windows-release-test-scope.json').read_text(encoding='utf-8'))
    if (source_tests.get('software_execution') != 'PASS' or source_tests.get('source_commit') != source_commit()
            or not source_tests.get('source_unchanged_during_run') or source_tests.get('runtime_errors') != 0
            or acceptance.get('status') != 'PASS' or not acceptance.get('actual_frozen_executable')
            or acceptance.get('bundled_engine_acceptance') != 'PASS'
            or not acceptance.get('external_decoy_ignored')
            or not acceptance.get('system_installation_absent_during_acceptance')
            or acceptance.get('invalid_engine_scenarios') != 2
            or not acceptance.get('source_matches_head') or not acceptance.get('source_unchanged_during_run')
            or acceptance.get('source_commit') != source_commit() or acceptance.get('version') != __version__
            or acceptance.get('executable_sha256') != sha(executable)
            or governance.get('status') != 'PASS'
            or full_run.get('source_manifest_sha256') != source_identity()['source_manifest_sha256']):
        raise RuntimeError('Current exact Windows source and packaged bytes must have passed acceptance')
    source_proof = json.loads((artifacts / 'corresponding-source-verification.json').read_text(encoding='utf-8'))
    source_asset = artifacts / source_proof['asset']
    if source_proof['status'] != 'PASS' or sha(source_asset) != source_proof['sha256']:
        raise RuntimeError('Verified corresponding-source asset is required')
    manifest = dict(version=__version__, tag='v' + __version__, source_commit=source_commit(),
                    corresponding_sources=source_proof,
                    architecture='windows-x64', python=platform.python_version(), signed=False,
                    package_files=entries, package_file_count=len(entries),
                    test_summary=source_tests, packaged_acceptance=acceptance,
                    regression_matrix=dict(windows=windows_scope, linux_full_run=state['latest_evidence_run'],
                         linux_full_source_manifest=full_run['source_manifest_sha256'], governance=governance),
                    known_limits=['Real private AI corpus quality', 'User Windows hardware/performance',
                                  'Physical print qualification', 'Independent novice usability',
                                  'Authorized local fonts installed separately; Inkscape 1.4.2 is bundled'],
                    compatibility='Existing local schema; use a separate test data copy; backward opening newer data not certified')
    archive = artifacts / ('TemplateAI-v' + __version__ + '-windows-x64.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
        for row in entries:
            bundle.write(folder / row['path'], 'TemplateAI/' + row['path'])
    manifest['archive'] = dict(name=archive.name, bytes=archive.stat().st_size, sha256=sha(archive))
    write(artifacts / 'release-manifest.json', manifest)
    checksum_files = [archive, artifacts / 'release-manifest.json', source_asset]
    (artifacts / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in checksum_files), encoding='utf-8')


def verify_download(folder, expected_manifest=None):
    expected_manifest = expected_manifest or ROOT / 'artifacts/release-manifest.json'
    if sha(folder / 'release-manifest.json') != sha(expected_manifest):
        raise RuntimeError('Downloaded manifest differs from the locally tested package')
    manifest = json.loads((folder / 'release-manifest.json').read_text(encoding='utf-8'))
    archive = folder / manifest['archive']['name']
    if sha(archive) != manifest['archive']['sha256'] or manifest['source_commit'] != source_commit() or manifest['version'] != __version__:
        raise RuntimeError('Downloaded version/source/archive mismatch')
    checksum_names = []
    for row in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = row.split('  ', 1)
        checksum_names.append(name)
        if Path(name).name != name or sha(folder / name) != expected:
            raise RuntimeError('Downloaded checksum mismatch')
    source_proof = manifest.get('corresponding_sources')
    required = [archive.name, 'release-manifest.json']
    if source_proof:
        required.append(source_proof['asset'])
        if sha(folder / source_proof['asset']) != source_proof['sha256']:
            raise RuntimeError('Downloaded corresponding sources differ')
        from bundled_inkscape_build import verify_source_archive
        verify_source_archive(folder / source_proof['asset'])
    if sorted(checksum_names) != sorted(required):
        raise RuntimeError('Downloaded checksum inventory differs')
    with zipfile.ZipFile(archive) as bundle:
        expected = {'TemplateAI/' + row['path']: row for row in manifest['package_files']}
        if set(bundle.namelist()) != set(expected) or len(bundle.namelist()) != len(expected):
            raise RuntimeError('Downloaded package inventory differs')
        for name, row in expected.items():
            if hashlib.sha256(bundle.read(name)).hexdigest() != row['sha256']:
                raise RuntimeError('Downloaded package contents differ')
    write(folder / 'download-verification.json', dict(status='PASS', source_commit=source_commit(),
          version=__version__, downloaded_archive_sha256=sha(archive), checked_files=len(expected),
          verification='ACTUAL_GITHUB_RELEASE_ASSETS_DOWNLOADED_AND_CHECKED'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['spec', 'exercise', 'package', 'verify-download'])
    parser.add_argument('--executable', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'spec': make_spec()
    elif args.command == 'exercise': exercise(args.executable.absolute(), args.output.resolve())
    elif args.command == 'package': package()
    else: verify_download(args.output.resolve())
