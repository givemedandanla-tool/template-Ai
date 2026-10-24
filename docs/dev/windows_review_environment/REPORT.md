# Windows review 開發環境與同步紀錄

2026-10-24（Asia/Taipei）。來源基底 `684ebb0bb5f18e8b171180661c69f1b633c22b48`，分支 `feature/review-tool-v0.1.0`，原始碼版 `0.1.0-beta.3.dev1`。目前已發布成品仍是 `review-v0.1.0-beta.2`。

## 實際結果

原生 Windows review 主視窗、debugpy 在 `review_app.py:78` 命中斷點後繼續／正常退出，以及獨立 pythonw 日常啟動均通過。離線保護仍啟用；測試只使用空白或合成資料。20 個鎖定依賴與 pip 檢查通過；Python 3.11.9 x64、VS Code 1.143.1 portable、debugpy 1.8.22、Inkscape 1.4.4 已檢查。固定品質工具可執行，未將此稱為全專案 lint 通過。

- stdio/pythonw：9 個測試通過，含 Windows 無 console 測例。
- 暗 palette 選單：1 個測試通過。
- PDF 提示頁：14 個測例，`failures=2, errors=4, skipped=5`；同一測例可能在 cleanup 再出錯，數字不可相減推算通過數。包含 `KeyError: image`、繁中提示分類、背景程序逾時／檔案占用與 QTimer 生命週期問題。
- 首次 PDF 測試 PATH 未包含 Inkscape，造成部分略過；後來設定已補上，但沒有重跑此模組。失敗與略過仍保留。
- Tesseract 與英文／繁中模型尚未配置，完整 OCR 未就緒。不能宣稱三項回饋完整通過，也不能替代 Windows frozen EXE 或私人作品驗收。

原始產品程式與測試邏輯均未修改；新增產品功能 0 項。要求登錄與完成數不變，進度基準及差異另存。新增內容是可攜式開發設定、安全檢查結果與交接。

## 環境重建

依 [工具指南](../../../tools/windows_review_dev/README.md) 重建。產生器拒絕覆寫既有設定，以相對路徑／本機參數生成獨立 VS Code workspace 與 CRLF 批次入口。原工作區的 START_DEV／OPEN_VSCODE 等本機檔保留；跨機使用新的可攜式產生器。UTF-8 模式修正繁中 Windows 預設編碼造成的治理讀檔錯誤。Git `core.longpaths=true` 用於歷史證據；Python 工具掃描該長路徑證據時使用 Windows 延伸長路徑格式，未修改系統登錄。

## 證據與保存邊界

`environment-report.json`、匿名化 logs、debugger-validation、test-summary 保存此次實測及失敗。真實畫面只保存必要 metadata／hash；圖片留本機，未把 hash 當可下載證據。歷史正式 `RUN-BUNDLED-INKSCAPE-BETA2-004` 已發布附件保持原樣，checkpoint 仍涵蓋其完整列舉附件，沒有用本輪窄驗證升級原產品資格。

GitHub 同步已由使用者核准，範圍為此次環境、結果與交接。來源提交與收據分兩次保存，遠端逐檔讀回完成才標 REMOTE_VERIFIED。大型 recursive tree 可能被 API 截斷；分段取得原始回應後合併完整樹，重算每個目錄 Git tree SHA，拒絕缺漏或不一致。

不合併 main、不打包、不發布、不改舊 tag；私人作品、字型、客戶資料、資料庫、工具二進位與密鑰不上傳。

## 下一步

從本 checkpoint 恢復後，先處理 PDF 測試的 Windows 失敗與缺少 OCR 引擎，相關調查另按使用者工作指令進行。本輪沒有修復這些產品問題。使用者私人作品實測與新 EXE 驗收仍是獨立範圍。

## 同步前設定驗證

新的可攜式設定已在本機實際執行：語法、既有設定拒絕覆寫且雜湊不變、CRLF、固定依賴與 pip、獨立 pythonw 合成啟動均 PASS，見 portable-validation.json。這沒有重跑 PDF 模組。

修改前的完整舊治理檢查仍為 FAIL：既有正式證據指向較早產品來源，與目前程式／測試／fixture manifest 不同，回報「證據已過期」。本輪保留該結果，沒有放寬規則或改寫舊證據成 PASS；遠端保存驗證與完整產品治理資格分開。
