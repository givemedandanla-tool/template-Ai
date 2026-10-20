# Native004：最後來源1d65dbe2的原生驗證重現

正式來源：`1d65dbe29085f3329cc35274c702445082a0a696`。
同團隊專項agent執行，只用自製／合成資料與空白暫存庫，沒有修改任何倉庫來源或依賴。

## Exact命令與結果

工作目錄 `/workspace/template-Ai`，Python3.12.14／PySide6 6.8.3。

```bash
.venv/bin/python docs/dev/gui_tooling/capture_owned_workspace.py --native --output /tmp/template-ai-owned-gui-final-004
python /tmp/native-004-owner.py
```

owner在同一原生上下文依序執行：

```bash
.venv/bin/python tools/capture_desktop_workspace.py --folder /tmp/template-ai-desktop-native-004
PYTHONPATH=tests:. .venv/bin/python -m unittest test_parent_navigation -v
```

- owned-window：3頁、3圖、3次Tab焦點移動全部PASS；exit0，5.531秒，source_unchanged=true。
- desktop：動態loader盤點確為12例，12／12 PASS，11張規定圖片；exit0。
  unittest227.026秒、工作外層227.983秒。
- parent-navigation：3／3 PASS；exit0。unittest32.244秒、工作外層32.830秒。
- 同一native owner共261.836秒；600秒整體看護未觸及。
- 前後HEAD均為1d65dbe2；每個工作與總體前後code-only manifest一致。
- runtime錯誤行為0；原log為正常OK，無skip／expected failure。
- 11張desktop圖與3張owned圖已逐張重新驗SHA-256。

## Native上下文與收尾

使用既有驗簽／hash鎖定工具root；沒有重新安裝或變更網路設定。

```text
/workspace/template-ai-gui-tools/root/usr/bin/Xvfb -displayfd <owned-write-fd> -screen 0 1600x1100x24 -nolisten tcp
QT_QPA_PLATFORM=xcb
LD_LIBRARY_PATH=/workspace/template-ai-gui-tools/root/usr/lib/x86_64-linux-gnu:<保留原有值若存在>
DISPLAY=:<displayfd動態取得的數字>
PYTHONPATH=tests:.
```

Xvfb關閉TCP，owner只清理自己建立的子程序群組，遇超時先TERM、5秒後必要時KILL。
測試ID以capture工具實際loadTestsFromTestCase目標搭配unittest loader動態取得；
沒有把12例硬寫成11例。owner記錄command、完整ID、退出碼、實際測試數、秒數、來源fence與錯誤行。
重跑前需選新的輸出資料夾，不能覆寫本次歷史證據；以下為本次實際owner全文。

```python
"""Owned native verification for source1d65; development execution only."""
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

repo = Path('/workspace/template-Ai')
native = Path('/workspace/template-ai-gui-tools/root')
folder = Path('/tmp/template-ai-desktop-native-004')
folder.mkdir(exist_ok=False)
expected = '1d65dbe29085f3329cc35274c702445082a0a696'
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

```

## 實際看圖與範圍

已看最後來源的owned製作頁、學習產稿、拖動後、0199更正後、舊稿待更新與960×640小視窗。
預覽旁的完整顯示／放大／縮小清楚可見；強化的實際測試通過，包含view-only transform與底層稿件不變。
聯絡欄位可交換相對排列，姓名／職稱維持；更正後舊確認與輸出失效，新預覽顯示0199；
小視窗保留主動作與預覽空間。footer已說明私人資料留本機、真實品質待本地核對。

圖像、完整IDs與hash詳見同資料夾的 `native-specialist-review.json`、`native-runner-result.json`、
`desktop-workspace-audit.json`，以及owned資料夾的 `owned-workspace-review.json`。
本輪未改動或抹去root保留的混合同程序候選計數失敗；fresh module原生PASS不代表那項歷史失敗已定因。
12＋3均為既有軟體測試ID，重跑只新增平台證據，不提高全回歸唯一測試數。

這是同團隊合成／Linux原生自我驗證，不是Windows／IME、真人新手、真實模型／作品或印前資格。
資料先存/tmp，由root統一複製到永久證據目錄、重驗hash並commit；此檔不虛稱/tmp已保存GitHub。
