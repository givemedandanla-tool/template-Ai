# 9f6e7f66 原生 GUI 驗證重現紀錄

本輪由同團隊專項 agent `/root/gui_tooling_research` 執行。只用自製／合成資料與隔離暫存庫，
沒有讀私人作品、字型或客戶資料；沒有變更程式、測試、工具或依賴來源。

- 倉庫：`/workspace/template-Ai`
- 正式來源：`9f6e7f66cdc558475fe3dd65a0e8dc114bb8ac95`
- 工具：既有 `.venv/bin/python`、PySide6／QTest、已驗證的
  `/workspace/template-ai-gui-tools/root/usr/bin/Xvfb`。
- 實際版本：Python `3.12.14`、PySide6 `6.8.3`。
- 原生平台：`QT_QPA_PLATFORM=xcb`，不採 offscreen 畫面冒充原生。
- Linux Xvfb 是開發測試工具；這不是 Windows、輸入法、真人新手或實體印刷資格。

## 1. 自有視窗與鍵盤工具

本次實際執行：

```bash
cd /workspace/template-Ai
.venv/bin/python docs/dev/gui_tooling/capture_owned_workspace.py --native --output /tmp/template-ai-owned-gui-final-002
```

exit 0，5.407秒；3頁、3張1280×860圖片；每頁真實 Tab 焦點移動均為 true。
`source_unchanged=true`，正式來源 SHA 正確。工具自己建立與清理隔離 Xvfb，
以明確的 owned winId 呼叫原始 OpenAI screenshot helper；沒有開啟 screenshot test mode。

該工具在自有 MainWindow 映射後執行既有
`root/usr/bin/xdotool windowfocus --sync <owned-winId>` 並處理 Qt 事件。
這是沒有 window manager 的 Xvfb 環境前提；產品與工具的 Tab 原斷言沒有放寬。

原始報告：`/tmp/template-ai-owned-gui-final-002/owned-workspace-review.json`。
它保存應用 Python 來源的逐檔 hash、圖片 SHA-256、焦點檢查與限制。

## 2. 11例完整桌面互動

本次工作程序的 exact 命令：

```bash
.venv/bin/python tools/capture_desktop_workspace.py --folder /tmp/template-ai-desktop-native-002
```

工作程序在下述 owner 建立的原生上下文中執行。`DISPLAY` 由 `-displayfd` 動態選擇，
未假設某固定顯示器可用；`LD_LIBRARY_PATH` 前置既有驗證工具 root 的依賴目錄，保留其他值。
Xvfb 使用 `-nolisten tcp`，只用本機顯示通道。沒有 window manager 或對外伺服器。

實際啟動參數：

```text
/workspace/template-ai-gui-tools/root/usr/bin/Xvfb -displayfd <owned-write-fd> -screen 0 1600x1100x24 -nolisten tcp
```

以下是可直接重現的 owner。重跑需選一個新的輸出目錄，避免覆寫本次證據。
工作程序有600秒看護；顯示器就緒最多10秒、owner收尾等待最多5秒。

```python
import json, os, select, signal, subprocess, time
from pathlib import Path

repo = Path('/workspace/template-Ai')
native = Path('/workspace/template-ai-gui-tools/root')
folder = Path('/tmp/template-ai-desktop-native-reproduction-new')
folder.mkdir()  # 既存目錄會拒絕，保留歷史證據。
expected = '9f6e7f66cdc558475fe3dd65a0e8dc114bb8ac95'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip() == expected
environment = os.environ.copy()
environment['QT_QPA_PLATFORM'] = 'xcb'
library = str(native / 'usr/lib/x86_64-linux-gnu')
environment['LD_LIBRARY_PATH'] = library + (':' + environment['LD_LIBRARY_PATH']
                                         if environment.get('LD_LIBRARY_PATH') else '')
read_fd, write_fd = os.pipe()
server = child = None
code = 1
started = time.monotonic()
try:
    with (folder / 'xvfb.log').open('w') as log:
        server = subprocess.Popen([
            str(native / 'usr/bin/Xvfb'), '-displayfd', str(write_fd),
            '-screen', '0', '1600x1100x24', '-nolisten', 'tcp'],
            pass_fds=(write_fd,), env=environment, stdout=log, stderr=log,
            start_new_session=True)
    os.close(write_fd)
    write_fd = None
    if not select.select([read_fd], [], [], 10)[0]:
        raise RuntimeError('Xvfb readiness timed out')
    display = os.read(read_fd, 64).decode().strip()
    if not display.isdigit():
        raise RuntimeError('Unexpected display number')
    environment['DISPLAY'] = ':' + display
    with (folder / 'native-capture.log').open('w') as log:
        child = subprocess.Popen([
            str(repo / '.venv/bin/python'), 'tools/capture_desktop_workspace.py',
            '--folder', str(folder)], cwd=repo, env=environment,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = child.wait(timeout=600)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=5)
            code = 124
    print(json.dumps(dict(exit_code=code, qt_platform='xcb',
                         elapsed_seconds=round(time.monotonic() - started, 3))))
finally:
    for fd in [read_fd, write_fd]:
        if fd is not None:
            os.close(fd)
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        child.wait(timeout=5)
    if server is not None and server.poll() is None:
        os.killpg(server.pid, signal.SIGTERM)
        server.wait(timeout=5)
raise SystemExit(code if code >= 0 else 1)
```

只停止 owner 自己建立的子程序群組；不停止既有 X server、主代理全回歸或他人工作。
本次233.853秒內正常完成，沒有逾時或強制終止。

## 結果與完整性

- native desktop：11／11測試 PASS、11張實際GUI圖片、exit 0。
- unittest耗時232.872秒；包含隔離Xvfb啟動的owner耗時233.853秒。
- `source_unchanged=true`、`source_head_unchanged=true`，來源保持9f6e7f66。
- `desktop-workspace-audit.json` 保存 code-only source manifest SHA-256、11圖hash與平台。
- `native-runner-result.json` 保存 exact命令、11個完整測試ID、退出碼及看護／耗時。
- `native-specialist-review.json` 匯總上述資料、owned-window結果、看圖結論；11圖hash已逐張重算。
- 這11個ID已包含於正式全回歸；原生重跑不增加唯一測試數。
- 全部原始資料在 `/tmp/template-ai-desktop-native-002/`，由主代理統一複製到永久證據目錄、
  驗hash並commit。此紀錄本身不虛稱/tmp檔案已經完成GitHub保存。

## 實際看圖結論

已看 owned模板／製作頁，以及正式native的工作引導、離線問題報告、小視窗、
學習產稿、拖動後、確認後、更正後待更新及重新產生預覽。

1. 製作畫面以完整稿件為主，聯絡欄位的可拖動範圍可辨識。拖動後電話／郵件順序交換，
   姓名與職稱維持位置；測試另驗實際相對意圖與資料，沒有只靠圖片判斷核心正確。
2. 確認後主要動作改成儲存預覽稿。更正內容後舊確認／輸出失效，畫面明確要求更新；
   重新產稿可見電話從0100變成0199。保留舊畫面時有明確的待更新說明。
3. 960×640下主要動作完整可見，資料區可獨立捲動，預覽仍保留操作空間。
4. 四步進階引導會說明本機目前沒有規則／資料條件，沒有自動宣稱訓練完成或正式合格。
5. 離線報告清楚說明手動匯出ZIP、貼回Codex，以及不含私人原稿、字型或資料庫。
6. 模板的專業工作區仍保留來源縮圖 UNKNOWN 等技術metadata；本次不把它當產品或模型錯誤。

這是同團隊對已測流程的專項視覺審查；沒有真人新手訪測、完整無障礙認證、Windows／IME、
真實作品泛化、硬體效能或實體印刷資格。
