# 作品判讀工具：原始碼啟動與版本更新

2026-10-24（Asia/Taipei）。目前維護 `feature/review-tool-v0.1.0`，不是假設 main 最新。
已發布 EXE 仍是 `review-v0.1.0-beta.2`；本輪原始碼為 `0.1.0-beta.3.dev1`，沒有新 EXE、tag 或 Release。

## 可省略哪些打包

介面、判讀規則及保存邏輯可以直接修改原始碼、重開開發版驗證，不必每次產生 EXE。
第一次仍須在 Windows 準備 64 位元 Python 3.11、固定 Python 套件及本機 Inkscape／Tesseract／語言模型。
原始碼 ZIP 不含 EXE 包內的 Python、Qt、引擎或模型；單獨下載一個 `.py` 檔不能取代初次準備。
本工具仍是本機 Qt 桌面視窗，不是瀏覽器網站。開發時 Codex 需連線；作品分析與日常啟動保持離線。

## 第一次建立開發版

建議由本機 Codex 在 `C:\TemplateAI-dev\project` 取得上述分支，先核對已有檔案與未提交修改。
不覆寫既有資料，不要求私人作品上傳，不安裝付費工具，也不使用 API key。

1. 在原始碼根目錄執行現有 `PREPARE_WINDOWS.bat`，只準備專案 `.venv` 的固定依賴。
   這是明確的首次下載步驟；已有本機 wheelhouse 時，可沿用其 `--offline` 模式。
2. 使用 `START_REVIEW_WINDOWS.bat` 啟動目前的「作品判讀與核對」小工具。
   `START_WINDOWS.bat` 是舊完整產品入口，這次不要混用。
   新入口先做不聯網的依賴預檢，再以獨立 `pythonw.exe` 開啟介面，準備視窗會退出，
   不留一個關閉後會連帶終止主介面的長駐主控台。
3. 日常可直接雙擊該入口；也可在已啟用 `.venv` 的命令列執行 `python review_app.py`。
   後者是有意使用終端機的開發模式，關閉其終端機仍可能中止由它啟動的程式。
4. 用合成作品確認加入、判讀、修正、保存與重開，再使用本機作品副本。
   預設資料仍在 `%LOCALAPPDATA%\TemplateAI\ReviewTool`，不要把它加入 Git、原始碼 ZIP 或雲端同步。
   要隔離試驗，可指定 `START_REVIEW_WINDOWS.bat --data-dir C:\TemplateAI-local-tests\review-session`。

### 沿用已下載的 Inkscape 與 OCR

不必每次更新原始碼都重下載引擎。保留完整解壓的 beta.2 下載包，或沿用明確指定的本機安裝。
以下只是在 Windows 命令提示字元中設定本次啟動的路徑範例；將 `C:\Apps\TemplateAIReview` 換成實際位置：

```bat
set "TEMPLATE_AI_INKSCAPE=C:\Apps\TemplateAIReview\engines\inkscape\bin\inkscape.exe"
set "TEMPLATE_AI_TESSERACT=C:\Apps\TemplateAIReview\engines\tesseract\tesseract.exe"
set "TEMPLATE_AI_TESSDATA=C:\Apps\TemplateAIReview\engines\ocr-models"
START_REVIEW_WINDOWS.bat
```

由本機 Codex 一次設定你的啟動捷徑或使用者環境，便不必每次輸入。不要拆開或刪掉引擎的 DLL 與授權檔。
這是原始碼模式的明確本機引擎選擇，診斷標為 `SOURCE_LOCAL`／`ENV_LOCAL`；不冒稱已通過 frozen 包內資格。
已發布 EXE 的包內校驗與禁止改用系統版本的規則不變。缺少引擎、模型或字型要明確提示，不當成判讀成功。

## 更新以一次完整提交為單位

Git 本身會傳輸需要的差異，通常不必重新下載完整原始碼或引擎。請讓 Codex 更新到指定、已驗證的提交，
而不是只覆蓋幾個看起來相關的 `.py`：相關資源、刪除／改名檔案、依賴、資料契約也可能一併改變。
可回傳給 Codex：

> 請先保存我的未提交修改，核對目前版本與資料備份，再更新 template-Ai 到指定的已驗證提交。
> 依變更清單處理依賴及資料相容性；不要覆寫作品與人工修訂。直接啟動原始碼版做相關回歸，不打包 EXE。

更新前關閉程式並備份本機核對資料。普通更新不自動重裝套件；`requirements-lock.txt` 變動時才重新準備依賴。
引擎／模型更新需獨立固定版本、完整校驗及授權處理，不能混進普通檔案替換。
資料格式有變時先檢查遷移與回退條件：只回退程式碼，不保證已遷移資料仍可被舊版讀取。
沒有 Git 時，完整下載指定提交到另一個新資料夾，比手動混合各版本檔案可靠。

## 驗證界線

本輪可在現有 Linux 執行真實原始碼 Qt 視窗、合成 PDF、背景程序及保存回歸。
Windows `pythonw`、原生字型、捷徑及 EXE GUI subsystem／管道重接需在 Windows 驗證，不能由 Linux PASS 代替。
正式發布仍需真正 EXE 啟動、背景引擎、IPC、包內路徑及下載校驗；原始碼更新可減少日常打包，但不取消這些發布檢查。
