"""Measured, verified-input release pipeline; publication is explicit and immutable."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import http.client
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from release_cache import ROOT, cache_key, install_dependencies, load_locks, prepare, sha, write
from release_impact import make_plan


class Stages:
    def __init__(self, path, mode):
        self.path = Path(path)
        self.data = dict(schema_version=1, mode=mode,
                         source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                         started_utc=datetime.now(timezone.utc).isoformat(), stages=[], status='RUNNING')
        self.save()

    def save(self):
        write(self.path, self.data)

    @contextmanager
    def stage(self, name):
        row = dict(name=name, status='RUNNING')
        self.data['stages'].append(row)
        start = time.perf_counter()
        try:
            yield row
        except BaseException as error:
            row.update(status='FAIL', error_type=type(error).__name__)
            raise
        else:
            row['status'] = 'PASS'
        finally:
            row['seconds'] = round(time.perf_counter()-start, 6)
            self.save()


def run(command, name, *, output=Path('artifacts'), stdout=None):
    output = ROOT/output
    output.mkdir(parents=True, exist_ok=True)
    with (output/(name+'.log')).open('wb') as log:
        result = subprocess.run([str(x) for x in command], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if stdout:
        shutil.copy2(output/(name+'.log'), ROOT/stdout)
    if result.returncode:
        raise RuntimeError(name+' failed with exit '+str(result.returncode)+'; inspect bounded evidence')
    return result.returncode


def link_sources(folder):
    _, assets = load_locks()
    source = ROOT/'artifacts'/assets['sources']['filename']
    target = folder/source.name
    if target.exists():
        raise FileExistsError('Do not overwrite downloaded sources')
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def public_source_access():
    _, assets = load_locks()
    source = assets['sources']
    with urllib.request.urlopen(urllib.request.Request(source['url'], method='HEAD'), timeout=60) as response:
        length = response.headers.get('Content-Length')
        if response.status != 200 or length is not None and int(length) != source['bytes']:
            raise ValueError('Public corresponding-source URL is unavailable or differs')
    return dict(url=source['url'], method='PUBLIC_HEAD_NOT_A_FRESH_SOURCE_DOWNLOAD', status='PASS')


def loopback_download_verify():
    """Exercise the original byte verifier without publishing an unrequested EXE."""
    artifacts = ROOT/'artifacts'
    manifest = json.loads((artifacts/'release-manifest.json').read_text())
    destination = artifacts/'download'
    destination.mkdir(exist_ok=False)
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(artifacts), **kwargs)
        def log_message(self, *args):
            return
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for name in (manifest['archive']['name'], 'release-manifest.json', 'SHA256SUMS.txt'):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=120)
            try:
                connection.request('GET', '/'+name)
                response = connection.getresponse()
                if response.status != 200:
                    raise ValueError('Loopback transfer failed')
                with (destination/name).open('xb') as dest:
                    for block in iter(lambda: response.read(1048576), b''):
                        dest.write(block)
            finally:
                connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
    link_sources(destination)
    run([sys.executable, 'tools/windows_release.py', 'verify-download', '--output', destination], 'verify-loopback')
    path = destination/'download-verification.json'
    report = json.loads(path.read_text())
    report['verification'] = 'ACTUAL_LOOPBACK_PACKAGE_TRANSFER_NOT_A_PUBLISHED_RELEASE'
    report['source_reuse'] = public_source_access()
    write(path, report)


def publication_preflight(version, mode):
    if mode != 'publish':
        return
    ref = os.environ.get('GITHUB_REF', '')
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or ref != 'refs/heads/release-request/v'+version
            or os.environ.get('RELEASE_SPEED_PUBLISH_ALLOWED') != 'true'):
        raise ValueError('Publication requires the exact explicitly requested new-version branch')
    rows = subprocess.check_output(['git', 'ls-remote', '--tags', 'origin', 'refs/tags/v'+version], cwd=ROOT, text=True)
    if rows.strip():
        raise FileExistsError('Immutable version already exists; never replace old tags/assets')
    state = json.loads((ROOT/'docs/dev/STATE.json').read_text())
    request = state.get('release_speed_optimization', {}).get('release_request') or {}
    authorization = request.get('authorization', {})
    if (request.get('version') != version or request.get('published') is not False
            or authorization.get('scope') != 'PUBLISH_WINDOWS_INTERNAL_BETA'
            or not isinstance(authorization.get('user_request'), str)
            or not authorization['user_request'].strip()):
        raise ValueError('A new explicit version-specific release authorization is required; beta2 history is insufficient')
    result = subprocess.run(['gh', 'release', 'view', 'v'+version], cwd=ROOT, capture_output=True)
    if result.returncode == 0:
        raise FileExistsError('A Release already exists for this version')
    if not any(text in result.stderr.decode(errors='replace').lower() for text in ('not found', 'http 404')):
        raise RuntimeError('Release absence could not be established; stop publication')
    # ls-remote is authoritative for tags; gh auth errors may not establish absence.
    subprocess.run(['gh', 'api', 'repos/givemedandanla-tool/template-Ai', '--jq', '.private'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def publish(version, recorder):
    artifacts = ROOT/'artifacts'
    manifest = json.loads((artifacts/'release-manifest.json').read_text())
    _, assets = load_locks()
    links = dict(schema_version=1, corresponding_sources=assets['sources'], reuse_release=assets['source_release'])
    write(artifacts/'SOURCE_DOWNLOADS.json', links)
    notes = artifacts/'release-notes.md'
    notes.write_text('Windows內部實測版。完整解壓程式ZIP，保留_internal與engines。\n\n'
                     'Inkscape1.4.2已附帶，私人字型／作品留本機。正式印刷與私人作品品質仍待本地驗證。\n\n'
                     '未變更開源元件的對應原始碼免費下載：'+assets['sources']['url']+'\n'
                     '版本、SHA及來源位置另見SOURCE_DOWNLOADS.json；日常不需下載原始碼ZIP。\n')
    with recorder.stage('create_tag_and_draft'):
        for command in (['git','config','user.name','github-actions[bot]'],
                        ['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],
                        ['git','tag','-a','v'+version,'-m','Authorized verified-input Windows internal beta'],
                        ['git','push','origin','v'+version],
                        ['gh','release','create','v'+version,'--verify-tag','--draft','--prerelease',
                         '--title','Template AI v'+version,'--notes-file',str(notes),
                         str(artifacts/manifest['archive']['name']), str(artifacts/'release-manifest.json'),
                         str(artifacts/'SHA256SUMS.txt'), str(artifacts/'SOURCE_DOWNLOADS.json')]):
            subprocess.run(command, cwd=ROOT, check=True)
    for phase in ('draft', 'public'):
        with recorder.stage('actual_'+phase+'_download_verify'):
            if phase == 'public':
                subprocess.run(['gh','release','edit','v'+version,'--draft=false','--prerelease'], cwd=ROOT, check=True)
            destination = artifacts/('download-'+phase)
            destination.mkdir(exist_ok=False)
            subprocess.run(['gh','release','download','v'+version,'--dir',str(destination)], cwd=ROOT, check=True)
            if json.loads((destination/'SOURCE_DOWNLOADS.json').read_text()) != links:
                raise ValueError('Downloaded source link metadata differs')
            link_sources(destination)
            run([sys.executable,'tools/windows_release.py','verify-download','--output',destination], 'verify-'+phase)
            report = json.loads((destination/'download-verification.json').read_text())
            report['source_reuse'] = public_source_access()
            report['verification'] = 'ACTUAL_CURRENT_GITHUB_ASSETS_DOWNLOADED_SOURCE_ZIP_REUSED_AND_FULLY_VERIFIED'
            write(destination/'download-verification.json', report)


def execute(args):
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('Authorized standard Windows runner required')
    sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
    from template_ai import __version__
    publication_preflight(__version__, args.mode)
    output = ROOT/'artifacts'
    output.mkdir(exist_ok=True)
    recorder = Stages(output/'release-timings.json', args.mode)
    scratch = Path(os.environ['RUNNER_TEMP']).resolve()/'template-ai-ci'
    scratch.mkdir(exist_ok=True)
    os.environ['TMP'] = os.environ['TEMP'] = str(scratch.resolve())
    tempfile.tempdir = None
    os.environ['TEMPLATE_AI_ALLOW_INITIAL_ABSENCE'] = 'true'
    try:
        with recorder.stage('verified_input_prepare') as stage:
            report = prepare(args.cache, output/'cache-inputs.json')
            stage.update(downloaded_bytes=report['downloaded_bytes'], objects=report['files'])
            if args.warm_check_only and (report['downloaded_bytes'] or any(r['state'] != 'HIT_VALIDATED' for r in report['records'])):
                raise ValueError('Warm cache was not actually restored in full')
        if args.warm_check_only:
            recorder.data['status'] = 'WARM_REMOTE_CACHE_VERIFIED_NOT_AN_EXE_BUILD'
            return
        with recorder.stage('local_warm_revalidation') as stage:
            warm = prepare(args.cache, output/'cache-local-warm.json')
            if warm['downloaded_bytes'] or any(r['state'] != 'HIT_VALIDATED' for r in warm['records']):
                raise ValueError('Local warm revalidation was not a genuine full cache hit')
            stage.update(downloaded_bytes=0, objects=warm['files'])
        with recorder.stage('offline_pinned_dependency_install'):
            install_dependencies(args.cache)
            with (output/'installed-dependencies.txt').open('wb') as stream:
                subprocess.run([sys.executable,'-m','pip','freeze'],stdout=stream,check=True)
            run([sys.executable,'-c',
                 'import platform; from PySide6 import __version__; print(platform.platform()); print("PySide6",__version__)'],
                'windows-runtime', stdout=Path('artifacts/WINDOWS_RUNTIME.txt'))
        with recorder.stage('impact_plan'):
            plan = make_plan(args.base, output/'release-impact-plan.json', force_build=True)
            if not plan['selected_windows_modules']:
                raise ValueError('Explicit build cannot have an empty test scope')
        with recorder.stage('release_tool_regressions'):
            run([sys.executable,'docs/dev/releases/run_release_speed_tests.py','artifacts'],'admin-tests')
        with recorder.stage('source_governance'):
            run([sys.executable,'tools/dev_governance.py','check','--require-evidence','--publication-scope'],
                'source-governance', stdout=Path('artifacts/governance-gate.json'))
        os.environ['TEMPLATE_AI_INKSCAPE'] = str(ROOT/'build/inkscape-staged/bin/inkscape.exe')
        with recorder.stage('original_windows_regression'):
            command = [sys.executable,'docs/dev/releases/run_windows_case_audit.py','--output','artifacts/source-tests','--workers','1']
            for module in plan['selected_windows_modules']:
                command += ['--module',module]
            run(command,'windows-source-tests')
        with recorder.stage('clean_pyinstaller_build'):
            run([sys.executable,'tools/windows_release.py','spec'],'spec')
            run([sys.executable,'docs/dev/releases/configure_frozen_utf8.py'],'utf8-build-policy')
            run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','build/release/TemplateAI.spec'],'pyinstaller')
            run([sys.executable,'tools/bundled_inkscape_build.py','install'],'engine-install')
        with recorder.stage('actual_frozen_exe21_engine5'):
            run([sys.executable,'docs/dev/releases/run_frozen_probe.py','--executable','dist/TemplateAI/TemplateAI.exe',
                 '--output','artifacts/package-check'],'actual-exe')
        with recorder.stage('package_inventory_and_checksums'):
            run([sys.executable,'tools/windows_release.py','package'],'package')
        if args.mode == 'publish':
            publish(__version__, recorder)
            recorder.data['status'] = 'RELEASE_PUBLISHED_DOWNLOAD_VERIFIED'
        else:
            with recorder.stage('actual_loopback_transfer_and_original_verifier'):
                loopback_download_verify()
            recorder.data['status'] = 'VALIDATION_PASS_NO_TAG_OR_RELEASE_CREATED'
    except BaseException:
        recorder.data['status'] = 'FAILED_NOT_VERIFIED'
        raise
    finally:
        recorder.data['finished_utc'] = datetime.now(timezone.utc).isoformat()
        recorder.save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['validate','publish'], default='validate')
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--base', default='auto')
    parser.add_argument('--warm-check-only', action='store_true')
    execute(parser.parse_args())
