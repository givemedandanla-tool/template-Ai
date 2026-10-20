"""Audit reuse of the owned native verifier; LOCAL_ONLY, no remote qualification."""
import ast
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import time

repo = Path(__file__).resolve().parents[3]
native = repo.parent / 'template-ai-gui-tools/root'
folder = repo / 'docs/dev/pre_download_audit/native-gui-001'
folder.mkdir(exist_ok=False)
expected = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
if head != expected:
    raise RuntimeError('Unexpected source HEAD before native capture')
sys.path.insert(0, str(repo / 'tools'))
from dev_common import manifest, manifest_digest

before = manifest_digest(manifest(repo, code_only=True))
tree = ast.parse((repo / 'tools/capture_desktop_workspace.py').read_text())
classes = [node.args[0].id for node in ast.walk(tree)
           if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
           and node.func.attr == 'loadTestsFromTestCase' and node.args
           and isinstance(node.args[0], ast.Name)]
environment = os.environ.copy()
environment['QT_QPA_PLATFORM'] = 'xcb'
environment['PYTHONPATH'] = 'tests:.'
library = str(native / 'usr/lib/x86_64-linux-gnu')
environment['LD_LIBRARY_PATH'] = library + (':' + environment['LD_LIBRARY_PATH']
                                         if environment.get('LD_LIBRARY_PATH') else '')
rd, wr = os.pipe()
server = child = None
started = time.monotonic()
deadline = started + 600
results = []
code = 1


def stop(process):
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def remaining():
    return max(1, deadline - time.monotonic())


def ids_for(module, names=None):
    script = '''import sys,json,unittest,importlib
sys.path[:0]=['tests','.']
m=importlib.import_module(sys.argv[1]);loader=unittest.defaultTestLoader
names=json.loads(sys.argv[2])
suite=(unittest.TestSuite(loader.loadTestsFromTestCase(getattr(m,n)) for n in names)
       if names else loader.loadTestsFromModule(m))
def flatten(s):
 for test in s:
  if isinstance(test,unittest.TestSuite):yield from flatten(test)
  else:yield test.id()
print(json.dumps(list(flatten(suite))))
'''
    return json.loads(subprocess.check_output([
        str(repo / '.venv/bin/python'), '-c', script, module, json.dumps(names)],
        cwd=repo, env=environment, text=True, timeout=min(20, remaining())))


try:
    with (folder / 'xvfb.log').open('w') as log:
        server = subprocess.Popen([
            str(native / 'usr/bin/Xvfb'), '-displayfd', str(wr), '-screen', '0',
            '1600x1100x24', '-nolisten', 'tcp'], pass_fds=(wr,), env=environment,
            stdout=log, stderr=log, start_new_session=True)
    os.close(wr)
    wr = None
    if not select.select([rd], [], [], 10)[0]:
        raise RuntimeError('Xvfb readiness timed out')
    display = os.read(rd, 64).decode().strip()
    if not display.isdigit():
        raise RuntimeError('Unexpected display number')
    environment['DISPLAY'] = ':' + display
    jobs = [
        ('desktop', [str(repo / '.venv/bin/python'), 'tools/capture_desktop_workspace.py',
                     '--folder', str(folder)], 'test_desktop_workspace', classes),
        ('parent-navigation', [str(repo / '.venv/bin/python'), '-m', 'unittest',
                               'test_parent_navigation', '-v'], 'test_parent_navigation', None)]
    for name, command, module, names in jobs:
        ids = ids_for(module, names)
        phase_before = manifest_digest(manifest(repo, code_only=True))
        phase_start = time.monotonic()
        (folder / 'native-runner-progress.json').write_text(json.dumps(dict(
            phase=name, source_commit=expected, expected_test_ids=ids,
            completed_jobs=results), indent=2) + '\n')
        with (folder / (name + '.log')).open('w') as log:
            child = subprocess.Popen(command, cwd=repo, env=environment,
                                     stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:
                code = child.wait(timeout=remaining())
            except subprocess.TimeoutExpired:
                stop(child)
                code = 124
        after = manifest_digest(manifest(repo, code_only=True))
        text = (folder / (name + '.log')).read_text()
        match = re.search(r'Ran (\d+) tests? in ([0-9.]+)s', text)
        runtime = [line for line in text.splitlines() if any(pattern in line for pattern in [
            'QObject::', 'QBasicTimer::', 'QThread: Destroyed', 'already deleted',
            'Traceback (most recent call last):'])]
        result = dict(name=name, command=command, qt_platform='xcb', PYTHONPATH='tests:.',
                      exit_code=code, test_ids=ids, expected_test_count=len(ids),
                      tests_run=int(match.group(1)) if match else None,
                      unittest_seconds=float(match.group(2)) if match else None,
                      elapsed_seconds=round(time.monotonic() - phase_start, 3),
                      source_manifest_before=phase_before, source_manifest_after=after,
                      source_unchanged=phase_before == after, runtime_error_lines=runtime,
                      log=name + '.log')
        result['status'] = 'PASS' if (code == 0 and match and int(match.group(1)) == len(ids)
                                      and phase_before == after and not runtime) else 'FAIL'
        results.append(result)
        (folder / (name + '-runner-result.json')).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({key: result[key] for key in [
            'name', 'status', 'exit_code', 'tests_run', 'elapsed_seconds', 'source_unchanged']}), flush=True)
        if result['status'] != 'PASS':
            code = 1
            break
    final = manifest_digest(manifest(repo, code_only=True))
    result = dict(source_commit=expected, source_head_at_finish=subprocess.check_output([
        'git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
        source_manifest_before=before, source_manifest_after=final,
        source_unchanged=before == final, qt_platform='xcb', outer_timeout_seconds=600,
        elapsed_seconds=round(time.monotonic() - started, 3), isolated_xvfb_tcp_disabled=True,
        jobs=results, status='PASS' if len(results) == 2 and all(
            item['status'] == 'PASS' for item in results) and before == final else 'FAIL')
    (folder / 'native-runner-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in [
        'status', 'source_commit', 'source_unchanged', 'elapsed_seconds']}), flush=True)
    code = 0 if result['status'] == 'PASS' else 1
finally:
    for fd in [rd, wr]:
        if fd is not None:
            os.close(fd)
    try:
        stop(child)
    finally:
        stop(server)
raise SystemExit(code if code >= 0 else 1)
