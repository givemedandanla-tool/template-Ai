# Windows review 工具開發環境

適用 `feature/review-tool-v0.1.0` 的 `review_app.py`。此設定重建原始碼開發環境，不建置 EXE。先讀 `AGENTS.md`、`docs/dev/STATE.json` 及精簡交接，核對已確認提交和 checkpoint。完整舊產品的 `app.py` 不是此入口。

## 在另一台 Windows 恢復

1. 以 Git 取得指定分支到**不存在的新目錄**，核對交接所列提交。不覆寫既有資料、不使用 `reset --hard`。本倉庫歷史證據含長路徑；建議短工作路徑，並在 clone 時使用 `git -c core.longpaths=true -c core.autocrlf=false clone --single-branch --branch feature/review-tool-v0.1.0 <repository-url> <new-directory>`，進入後設定 `git config core.longpaths true`、`git config core.autocrlf false`。完整歷史證據很大；sparse checkout 能啟動 review 工具，但不是全治理驗收。
2. 安裝或準備 Python 3.11.9 x64。可使用 `toolchain-lock.json` 中的官方 NuGet ZIP，下載到新的本機檔案，先用 `Get-FileHash -Algorithm SHA256` 比對固定雜湊，再解壓至**不存在的** `.tools/python311`。不要把 ZIP、工具或私人資料提交 Git。
3. 在專案根目錄執行下列明確的連線準備命令；若 `.venv` 已存在，先檢查用途與版本，不覆寫別的環境。之後正常啟動不下載、不更新套件。

```powershell
$env:PYTHONUTF8 = '1'
& '.tools/python311/tools/python.exe' -m venv .venv
& '.venv/Scripts/python.exe' -m pip install --only-binary=:all: -r requirements-lock.txt -r tools/windows_review_dev/requirements-debug.txt
& '.venv/Scripts/python.exe' tools/local_start.py --check
& '.venv/Scripts/python.exe' -m pip check
```

4. 若使用 portable VS Code，依 lock 的官方 URL／SHA256 解壓到新的 `.tools/vscode`，建立 `data` 子目錄，啟用 portable 模式。安裝 Python 與 debugpy 擴充；本輪實測版本記於 lock。可用 `.tools/vscode/bin/code.cmd --install-extension ms-python.python@2026.10.0` 及 `ms-python.debugpy@2026.6.0`，其他已觀察的擴充依需要安裝。這些工具只在本機。
5. 執行 `.venv/Scripts/python.exe tools/windows_review_dev/configure.py`。若 Git／Inkscape／VS Code 不在 PATH，以 `--git`、`--inkscape`、`--code` 指定本機執行檔。設定產生器先檢查所有衝突，遇到既有檔案就停止並保留，不改 `.vscode` 或產品程式。機器專屬輸出自動加入 `.git/info/exclude`。
6. 開啟 `review-dev.code-workspace` 或雙擊 `OPEN_REVIEW_DEV.cmd`。在 `review_app.py` 設中斷點，按 F5。debugpy 只在明確除錯操作時使用 localhost；保留程式離線保護，停用子程序自動附加以避免與 worker 保護衝突。

## 日常使用

- `START_REVIEW_DEV.cmd`：先檢查固定依賴，再以獨立 `pythonw` 啟動。批次檔由產生器寫入 CRLF，避免 Windows 將 LF 批次解析錯誤；不依賴修改已追蹤的舊批次檔。
- `CHECK_REVIEW_DEV.cmd`：依賴與 pip 檢查。
- `DEBUG_REVIEW_DEV.cmd`：等待本機 127.0.0.1:5678 附加；VS Code 另有對應組態。此除錯視窗關閉會中斷除錯程序，日常操作使用前述 pythonw 入口。
- `TEST_REVIEW_DEV.cmd`：只跑 stdio、PDF 提示頁與暗 palette 三組相關測試，使用空白／合成資料；任一失敗或逾時即非零退出。不是完整產品資格。

資料位於 `local-data/review-debug`；不要指向既有私人資料庫。OCR 尚未配置；需明確準備 Tesseract 與英／繁中模型，或依原始碼指南沿用 beta.2 包內引擎，才能測完整 OCR。Inkscape 1.4.4 是本次本機版本，不等於 beta.2 包內引擎版本。

品質工具沿用 `docs/dev/debug_tooling/bootstrap.py` 與既有固定 pin。需要時依 lock 準備 Node 24.19.0 並加入目前程序 PATH，再按既有指南 bootstrap；正常執行不得自動連線安裝。Ruff 0.17.1、Pyright 1.1.414、jscpd 5.4.1 已在本輪環境確認可執行。

使用 PowerShell 跑治理工具前設定 `$env:PYTHONUTF8='1'`，或使用 `python -X utf8`；繁中 Windows 預設 cp950 會讓部分既有交接工具讀 UTF-8 JSON 失敗。維持非批次檔原始 LF，避免固定工具檔雜湊失配。

## 驗證邊界與同步

本輪來源啟動／中斷點／pythonw 已通過，stdio 9 項與暗選單 1 項測試通過；PDF 模組有 2 個 failure 事件、4 個 error 事件、5 個 skip（14 測例，包含同一測例 cleanup 再失敗，不能直接相減算成功數）。首次該模組測試的 PATH 未含 Inkscape；後續設定已補上，並未重跑 PDF 模組。沒有宣稱三項回饋完整驗收。

同步只包含此可攜式設定、固定版本、匿名文字結果、STATE／交接與 checkpoint；`.tools`、`.venv`、快取、local-data、私人字型與作品留在本機。原始碼同步不產生新版軟體；已發布 `review-v0.1.0-beta.2` 保持不變。完整結果見 `docs/dev/windows_review_environment/REPORT.md`。


## 後續 Windows PDF／DirectWrite 驗證（2026-10-24）

上節初次失敗保留為歷史。最新 run_checks.py 改為 Windows 原生平台並增加診斷測試；31項通過（PDF14、診斷7、stdio9、暗選單1）。PDF模組上限600秒（實測基線410秒），未改產品逾時或判讀斷言。詳見 [本輪報告](../../docs/dev/windows_review_environment/pdf-dwrite-20261024/REPORT.md)。

以 --diagnostics-dir .local-dev/qt-logs 或 TEMPLATE_AI_REVIEW_DIAGNOSTICS_DIR 明確開啟 Qt 記錄，GUI與worker在 QApplication 前安裝；預設關閉、不配置主控台。每程序新建受限大小JSONL，可能含字型名稱／路徑，原始檔不得上傳。合成 probe_pdf_fonts.py 的 --root . --output .local-dev/new-probe --integrated 可重跑斷點與canary；輸出目錄必須不存在。此次真實 DirectWrite 前後皆0，記為未重現；不宣稱原情境已修復。
