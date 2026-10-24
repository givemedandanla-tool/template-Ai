# 原生 AI 匯入：隔離可行性驗證

此工具只產生並讀取合成檔案，沒有接入 review-tool 產品匯入流程。當前固定上游為 `inkai 1.2.0`／`1a5f42a0b0407fc869e032420570682048810108`，上游標示 Pre-Alpha。檔案、套件與安裝資訊以 `upstream-lock.json` 為準；不自動追蹤 main。

在已建立的 Windows review 開發環境執行，先確認指定目錄不存在：

```powershell
.venv\Scripts\python.exe tools/windows_review_dev/native_ai_feasibility/prepare.py --output .local-dev/native-ai-isolated
.venv\Scripts\python.exe tools/windows_review_dev/native_ai_feasibility/probe.py --runtime .local-dev/native-ai-isolated --inkscape 'C:\Program Files\Inkscape' --output .local-dev/native-ai-run1
```

Inkscape 若安裝於其他位置，調整 `--inkscape`。已驗 Inkscape 1.4.4／內附 Python 3.12.12；它供應 inkex、zstandard、Pillow、lxml。兩個純 Python wheel 只下載並按 hash 讀取，不 pip install、不修改 Inkscape、不更動既有 venv。準備階段下載公開上游；分析階段以 `-I` 獨立程序執行並拒絕 Python socket 操作，並非 OS 層安全沙箱。

每個情境限 45 秒，輸入原樣保留，輸出目錄必須是新目錄。重新執行換用另一個新目錄；不要刪除或指向既有使用者會話。完整檔案與原始記錄只留本機，GitHub 僅保存本工具、固定版本與匿名結果。不提供私人檔案參數，禁止把私人作品或字型放到上游測試資料或 GitHub。

`probe.py` 的退出碼：0 表示這組驗收全部通過；2 表示有產品驗收失敗，尚不可整合；其他非零表示驗證工具或環境發生錯誤。不能因程式成功輸出 SVG 就認定作品完整，也不能把預期的「2」改報為全部 PASS。

目前 7 個驗收為 5 PASS／2 FAIL：矩形、顏色、尺寸與 zlib／zstd 私有資料解碼可用；純原生與 PDF 包裝的文字情境皆遺失文字。損壞來源及沒有原生資料的提示頁會拒絕。文字沒有出現在 SVG，也沒有變成其他輪廓（只剩原矩形）。因此產品整合暫未執行。

本工具遵循上游公開檔案格式及接口自行生成資料；不複製私人原稿、不內嵌字型。上游源碼 GPL-2.0-or-later 及授權檔保留在下載封存中，pypdf 為 BSD-3-Clause、pyparsing 為 MIT。本次沒有重新散布第三方程式、字型或軟體包；未來若打包仍須另做授權／依賴審核與版本授權。

完整範圍、失敗證據與下一步見 `docs/dev/windows_review_environment/native-ai-20261025/REPORT.md`。
