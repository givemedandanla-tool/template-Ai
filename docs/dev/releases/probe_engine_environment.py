"""Adversarial external environment around unchanged actual-EXE acceptance calls."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


@contextlib.contextmanager
def isolated_host(executable, output):
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Fresh authorized Windows runner only')
    actual = subprocess.run
    installed = Path(r'C:\Program Files\Inkscape')
    removed = False
    history = []
    def choco(action):
        command = ['choco', action, 'inkscape', '--yes', '--no-progress']
        if action == 'install':
            command.append('--version=1.4.2')
        result = actual(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        history.append(dict(action=action, returncode=result.returncode, output_tail=result.stdout[-1500:]))
        if output.exists():
            (output/'host-installation-control.json').write_text(json.dumps(history,indent=2)+'\n')
        if result.returncode:
            raise RuntimeError('Fresh-runner host '+action+' failed; do not claim the no-host scenario')
    with tempfile.TemporaryDirectory(prefix='template-ai-decoy-') as raw:
        decoy = Path(raw)/'inkscape.exe'
        decoy.write_bytes(b'MZ_DECOY_MUST_NEVER_BE_EXECUTED')
        def observe(command, *args, **kwargs):
            nonlocal removed
            if not isinstance(command, (list,tuple)) or not command or Path(command[0]).resolve() != executable.resolve():
                return actual(command, *args, **kwargs)
            environment = dict(kwargs.pop('env', os.environ))
            environment['TEMPLATE_AI_INKSCAPE'] = str(decoy)
            environment['PATH'] = raw+os.pathsep+environment.get('PATH','')
            if not removed:
                if not (installed/'bin/inkscape.exe').is_file():
                    raise RuntimeError('Unexpected initial host installation state')
                choco('uninstall')
                removed = True
            if installed.exists():
                raise RuntimeError('System Inkscape directory still exists after uninstall')
            started = time.monotonic()
            result = actual(command, *args, env=environment, **kwargs)
            path = output/'native-child-processes.json'
            records = json.loads(path.read_text()) if path.exists() else []
            phase = 'SUPPORT_CLI'
            if '--release-check' in command:
                phase = json.loads(Path(command[command.index('--release-check')+1]).read_text())['phase']
            records.append(dict(phase=phase,returncode=result.returncode,
                                windows_status_hex=hex(result.returncode & 0xffffffff),
                                seconds=round(time.monotonic()-started,3)))
            path.write_text(json.dumps(records,indent=2)+'\n')
            return result
        subprocess.run = observe
        try:
            yield
        finally:
            subprocess.run = actual
            if removed:
                choco('install')
                if not (installed/'bin/inkscape.exe').is_file():
                    raise RuntimeError('System-installation control was not restored')


def invalid_cases(executable, output):
    engine = executable.parent/'engines/inkscape'
    target = engine/'bin/inkscape.exe'
    dll = engine/'bin/libinkscape_base.dll'
    rows = []
    for kind, changed in [('missing-executable', target), ('corrupt-dll', dll)]:
        with tempfile.TemporaryDirectory(prefix='template-ai-invalid-bundle-') as raw:
            root = Path(raw)
            (root/'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA')
            spec = root/'release-check.json'
            spec.write_text(json.dumps(dict(fixture='AUTHORED_RELEASE_ACCEPTANCE_V1',root=str(root),phase='engine-invalid')))
            # os.rename cannot cross the runner's checkout/temp volumes.
            backup = executable.parent/('engine-probe-'+kind+'.backup')
            if backup.exists():
                raise RuntimeError('Unexpected leftover engine probe backup')
            changed.rename(backup)
            if kind == 'corrupt-dll':
                changed.write_bytes(b'SYNTHETIC_CORRUPT_DLL')
            try:
                with (output/('engine-'+kind+'.log')).open('wb') as log:
                    result = subprocess.run([str(executable),'--release-check',str(spec)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
                if result.returncode:
                    raise RuntimeError('Actual invalid-engine scenario failed: '+kind)
                evidence = json.loads((root/'evidence/invalid-engine.json').read_text())
                report = root/'safe-report.zip'
                result = subprocess.run([str(executable),'--data-dir',str(root/'empty-data'),'--support-report',str(report)],capture_output=True,timeout=45)
                if result.returncode or not report.is_file():
                    raise RuntimeError('Actual broken-engine support-report CLI failed')
                from template_ai.offline_support import read_support_bundle
                public = read_support_bundle(report.read_bytes())
                if public['environment']['inkscape_runtime']['error_code'] != 'BUNDLED_RUNTIME_INVALID':
                    raise RuntimeError('Support report lost the actual engine error')
                rows.append(dict(scenario=kind,actual_frozen_executable=True,support_report_cli=True,**evidence))
            finally:
                changed.unlink(missing_ok=True)
                backup.rename(changed)
    (output/'invalid-engine-scenarios.json').write_text(json.dumps(dict(status='PASS',checks=rows),indent=2)+'\n')


def installed_case(executable, output):
    if not Path(r'C:\Program Files\Inkscape\bin\inkscape.exe').is_file():
        raise RuntimeError('The installed-system control condition is missing')
    with tempfile.TemporaryDirectory(prefix='template-ai-installed-control-') as raw:
        root = Path(raw)
        (root/'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA')
        spec = root/'release-check.json'
        spec.write_text(json.dumps(dict(fixture='AUTHORED_RELEASE_ACCEPTANCE_V1',root=str(root),phase='engine-valid')))
        decoy = root/'inkscape.exe'
        decoy.write_bytes(b'MZ_INVALID_EXTERNAL_DECOY')
        env = os.environ.copy()
        env['TEMPLATE_AI_INKSCAPE'] = str(decoy)
        env['PATH'] = raw+os.pathsep+env['PATH']
        with (output/'engine-system-installed.log').open('wb') as log:
            result = subprocess.run([str(executable),'--release-check',str(spec)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if result.returncode:
            raise RuntimeError('Actual bundled engine failed with system Inkscape present')
        record = json.loads((root/'evidence/bundled-engine-engine-valid.json').read_text())
        record['system_installation_present'] = True
        (output/'engine-system-installed.json').write_text(json.dumps(record,indent=2)+'\n')
