# 本機快速開始：離線使用與手動回報

目前交付原始碼，不是 EXE 安裝包。日常啟動不會安裝套件、檢查更新或上傳資料。
本指南不代表已完成你的 Windows、字型、真實作品或硬體驗收。

## 第一次準備

1. 到 [開發分支](https://github.com/givemedandanla-tool/template-Ai/tree/dev/v0.1-first-version)，
   確認分支是 `dev/v0.1-first-version`，按 **Code → Download ZIP**。
   本輪尚未合併到 `main`。私人倉庫需要你自己的 GitHub 登入。
2. 完整解壓縮到本機資料夾，例如 `C:\TemplateAI`。
   不要直接在 ZIP 裡執行，也不要放在 OneDrive、網路磁碟或自動同步資料夾。
3. 安裝 **64 位元 Python 3.11** 與 Python Launcher。
   從 [Python 官方網站](https://www.python.org/downloads/windows/)取得；安裝到自己的帳號即可，
   本專案不要求管理員安裝或付費服務。
4. 雙擊 **PREPARE_WINDOWS.bat**。這一步會明確下載鎖定的 Python 套件到專案自己的 `.venv`，
   不修改全域 Python。看到「首次準備完成」後關閉視窗。
5. 若尚無 Inkscape，可從 [Inkscape 官方網站](https://inkscape.org/release/)另行準備合適的本機版本。
   已安裝者可沿用；非標準位置設定 `TEMPLATE_AI_INKSCAPE`。
   OCR 的 Tesseract 與語言資料是另一項本機選配，缺少時會提示，仍可使用文字提取或人工核對。

第一次下載原始碼、Python、套件或轉換工具，可以在明確準備階段連網。
**準備完成後，日常使用走下方離線啟動；軟體不會代替你補下載缺件。**

## 日常使用

雙擊 **START_WINDOWS.bat**。它只檢查已安裝依賴並啟動；缺件時會用白話說明並停止，
不會自動呼叫 pip 或連線安裝。

建議第一次先用測試資料。你可以先關閉 Wi-Fi 或拔掉網路線，再開啟軟體確認離線工作。
程式的網路阻擋是應用程式保護，並非替整台電腦設定防火牆；本機斷網也避免其他同步程式外傳檔案。

若希望資料位置固定，在 PowerShell 先切到解壓縮資料夾，再執行：

```powershell
.\START_WINDOWS.bat --data-dir "C:\TemplateAI-data"
```

這個資料夾是你的私人工作資料，與可更新的原始碼分開。
日後更新原始碼時，沿用同一個 `--data-dir`，不要刪掉或覆蓋私人資料夾。
未指定時會使用 Qt 提供的目前帳號本機應用資料位置；不知道位置時先改用明確的 `--data-dir`。

依序從「匯入與學習」「模板與圖片」「排版與輸出」操作。
進階來源核對、驗證與容量操作見[進階工作引導](GUIDED_OPERATIONS_USER_GUIDE.md)；
本機字型、OCR 與來源補救見[本地還原指南](LOCAL_LEARNING_RECOVERY_GUIDE.md)。
缺字型、未知規則或資格不足時，按畫面提示處理，不代表資料已丟失或整套程式故障。

## 遇到問題，把報告交給 Codex

1. 開啟軟體的 **問題與報告**。
2. 選「當時在做什麼」及畫面提示缺少的資訊，按 **記下這個問題**。
3. 查看白話摘要；需要時展開 **顯示技術資料**。
4. 按 **匯出問題報告**，選一個新的本機 ZIP 檔名。
   出現「已完整保存 ZIP」才代表匯出完成；取消或失敗會保留本機紀錄。
5. 回到 Codex，手動附上 ZIP，再補充「原本想完成什麼、做了哪幾步、預期與實際差異」。
   軟體本身不會替你傳送報告。你可以使用另一台可連網設備提交。

安全 ZIP 包含 `support.json`、`support.html`、`manifest.json`；
有版本指紋、操作階段、固定錯誤／缺少資訊代碼及有界量測，
預設不包含客戶原文、原稿、字型檔、資料庫、完整私人路徑或原始例外訊息。
只需要提交這份安全報告，毋須整包上傳私人工作目錄。

### 主視窗打不開時

若依賴已準備，可在同一資料位置匯出最近一次安全紀錄：

```powershell
.\.venv\Scripts\python.exe app.py --data-dir "C:\TemplateAI-data" --support-report "C:\TemplateAI-support-001.zip"
```

也可用啟動器轉交同一操作：

```powershell
.\START_WINDOWS.bat --data-dir "C:\TemplateAI-data" --support-report "C:\TemplateAI-support-002.zip"
```

目的檔必須是新的本機 ZIP，不會覆寫既有報告。
若是首次準備尚未完成，先執行下方預檢，將「缺少哪些套件」的畫面結果告訴 Codex；
不要貼私人資料，也不要因錯誤反覆重建或刪除資料庫。

## 單純檢查環境

```powershell
.\.venv\Scripts\python.exe tools\local_start.py --check
```

它只檢查 Python、鎖定套件與 Inkscape 是否存在，不開主視窗、不建立私人資料庫、不下載依賴。
這是預檢，並不代表 Qt 原生視窗、來源還原、印刷或 Windows 效能已驗收。

## 沒網路的電腦如何首次準備

在有網路、相同 Windows 架構及 Python 3.11 的電腦，先下載鎖定的 wheel 套件：

```powershell
py -3.11 -m pip download --only-binary=:all: --dest wheelhouse -r requirements-lock.txt
```

把原始碼、完整 `wheelhouse`、Python 與所需本機工具的安裝檔，以你自己的方式移到目標電腦。
Python 安裝好後執行：

```powershell
.\PREPARE_WINDOWS.bat --offline "D:\wheelhouse"
```

這條路使用 `--no-index`，只讀指定套件資料夾；缺件就停止，不連網補下載。
套件需與目標 Python／Windows 架構相符，不可直接拿本次 Linux 環境的 `.venv` 或 wheel 替代。
完整 Windows 離線安裝仍待你的本機確認。

## 私人資料備份與更新

- 使用完畢先關閉程式，確認背景工作已暫停或完成，再複製**整個私人資料資料夾**到自己的本機備份裝置。
- 原稿來源與合法字型也需保留原始本機副本；只備份程式 ZIP 或支援報告不能還原作品及模型。
- 備份不得放進公開 Git 倉庫。報告用來分析問題，不是工作資料備份。
- 更新原始碼前先備份。鎖定依賴有變動時，在明確準備階段再執行 PREPARE_WINDOWS，
  或準備新的離線 wheelhouse；日常 START 不會更新依賴或自行更換你的模型與定稿。

## Linux 開發環境的重現方式

```bash
.venv/bin/python tools/local_start.py --check
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/local_start.py --data-dir /tmp/template-ai-local-smoke --capture /tmp/template-ai-local-smoke.png
.venv/bin/python tools/local_start.py --data-dir /tmp/template-ai-local-smoke --support-report /tmp/template-ai-local-smoke-report-001.zip
```

這些是本輪可執行的 Linux 合成 smoke，不能當成 Windows 實機或真實作品驗收。
