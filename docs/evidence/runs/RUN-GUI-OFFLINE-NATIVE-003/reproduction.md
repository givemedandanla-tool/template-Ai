# Native003：來源80a40511的完整重現紀錄

本輪使用同團隊專項 agent 執行；沒有修改程式、測試、工具或依賴。
全部資料為自製／合成來源，沒有私人作品、客戶資料、字型原檔或既有私人資料庫。

## 來源與實際結果

- 正式來源：`80a40511d04757750746c534c9257e2d9b611c3a`。
- 平台：原生 Linux `QT_QPA_PLATFORM=xcb`，既有 `.venv` Python3.12.14／PySide6 6.8.3。
- owned-window：3頁、3次真Tab移動、3張1280×860圖片；exit0、5.097秒、來源未變。
- 桌面互動：動態盤點確為12例，12／12 PASS、11張規定圖片；exit0。
  unittest234.735秒、工作外層235.542秒。
- 原parent navigation：3／3 PASS；exit0。unittest31.816秒、工作外層32.226秒。
- 同一原生owner總計268.602秒，600秒看護未觸及。
- 兩個工作各自前後code-only manifest一致，總體前後一致，runtime錯誤行為0。
- code-only manifest：`31cb3f2505d6cdaaeea453a6d45ceed655268b05ea5b8d2e0cddac56069aade4`。
- 11張桌面圖＋3張owned圖 SHA-256 已逐張重新核對。

## 本次exact命令

工作目錄是 `/workspace/template-Ai`。

```bash
.venv/bin/python docs/dev/gui_tooling/capture_owned_workspace.py --native --output /tmp/template-ai-owned-gui-final-003
.venv/bin/python tools/capture_desktop_workspace.py --folder /tmp/template-ai-desktop-native-003
PYTHONPATH=tests:. .venv/bin/python -m unittest test_parent_navigation -v
```

後兩個工作在同一個隔離Xvfb上下文依序執行：

```text
/workspace/template-ai-gui-tools/root/usr/bin/Xvfb -displayfd <owned-write-fd> -screen 0 1600x1100x24 -nolisten tcp
QT_QPA_PLATFORM=xcb
LD_LIBRARY_PATH=/workspace/template-ai-gui-tools/root/usr/lib/x86_64-linux-gnu:<原有值若存在>
DISPLAY=:<displayfd選出的數字>
PYTHONPATH=tests:.
```

使用的是既有驗簽／hash鎖定工具root，沒有重裝套件或改網路設定。
Xvfb關閉TCP，只用本機通道；owner只停止自己建立的子程序群組。
owned-window工具會自己建立／清理顯示器，並以明確winId啟用自有MainWindow後檢查Tab。

## 可重跑的雙工作owner

重跑必須選新輸出目錄以保留既有證據。此範例保留本次的動態test IDs盤點、來源fence、
600秒整體預算與有界清理；沒有建立worktree、改HEAD或修改原測試斷言。

```python
import ast, json, os, select, signal, subprocess, sys, time
from pathlib import Path

repo = Path('/workspace/template-Ai')
native = Path('/workspace/template-ai-gui-tools/root')
folder = Path('/tmp/template-ai-desktop-native-reproduction-new')
folder.mkdir()
expected = '80a40511d04757750746c534c9257e2d9b611c3a'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() == expected
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

def actual_ids(module, names):
    script = '''import sys,json,unittest,importlib
sys.path[:0]=['tests','.']
m=importlib.import_module(sys.argv[1]);loader=unittest.defaultTestLoader
names=json.loads(sys.argv[2])
suite=(unittest.TestSuite(loader.loadTestsFromTestCase(getattr(m,n)) for n in names)
       if names else loader.loadTestsFromModule(m))
def flatten(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from flatten(t)
  else:yield t.id()
print(json.dumps(list(flatten(suite))))
'''
    return json.loads(subprocess.check_output([
        str(repo / '.venv/bin/python'), '-c', script, module, json.dumps(names)],
        cwd=repo, env=environment, text=True, timeout=min(20, remaining())))

try:
    with (folder / 'xvfb.log').open('w') as log:
        server = subprocess.Popen([
            str(native / 'usr/bin/Xvfb'), '-displayfd', str(wr),
            '-screen', '0', '1600x1100x24', '-nolisten', 'tcp'],
            pass_fds=(wr,), env=environment, stdout=log, stderr=log,
            start_new_session=True)
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
        ids = actual_ids(module, names)
        phase_before = manifest_digest(manifest(repo, code_only=True))
        phase_start = time.monotonic()
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
        results.append(dict(name=name, command=command, exit_code=code, test_ids=ids,
                            source_unchanged=phase_before == after,
                            elapsed_seconds=round(time.monotonic() - phase_start, 3)))
        if code != 0 or phase_before != after:
            break
    (folder / 'native-owner-result.json').write_text(json.dumps(dict(
        source_commit=expected, jobs=results, elapsed_seconds=time.monotonic()-started,
        source_unchanged=before == manifest_digest(manifest(repo, code_only=True))), indent=2))
finally:
    for fd in [rd, wr]:
        if fd is not None:
            os.close(fd)
    try:
        stop(child)
    finally:
        stop(server)
```

實際本輪owner另核對log的實際測試數與動態IDs數一致、檢查QObject/QTimer／已刪除物件等
runtime錯誤行，產生 `desktop-runner-result.json`、`parent-navigation-runner-result.json`、
`native-runner-result.json`。重現後仍應檢查原始log、capture audit、實際測試數與每圖hash，
不能只以子程序退出或圖片存在宣稱通過。

## 證據與實際看圖

`/tmp/template-ai-desktop-native-003/native-specialist-review.json` 匯總兩個suite的完整test IDs、
exact命令、退出碼、秒數、source fence、0 runtime錯誤與11張圖片hash。
`/tmp/template-ai-owned-gui-final-003/owned-workspace-review.json` 保存owned視窗3圖與3次焦點檢查。

已看80a40511來源的拖動後、0199更正後預覽、舊稿失效、小視窗與離線報告圖片：
拖動能交換聯絡欄位的相對排列；更正後要求更新並禁用舊輸出；新電話呈現在新預覽；
960×640下主要動作完整可見；手動ZIP報告分享與私密內容排除的說明清楚。
原parent-navigation三例實測固定候選點選／重新核對、來源properties schema、舊面板toggle與背景工作唯一性。

這15個ID均屬既有軟體測試；原生重跑只增加平台證據，不新增全回歸唯一測試數。
此為同團隊合成／Linux自我驗證，不冒稱真人新手、Windows/IME、真實模型品質或印前資格。
檔案由主代理統一複製到永久證據目錄、驗hash並commit；/tmp路徑本身不代表已保存GitHub。
