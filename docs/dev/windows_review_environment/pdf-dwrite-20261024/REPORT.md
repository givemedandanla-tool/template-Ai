# Windows PDF 與 DirectWrite 診斷結果

2026-10-24；只維護 review-tool。基底 `f7f26c52de0e6ff4a08850e12a8450dc2a142be7`，分支 `feature/review-tool-v0.1.0`，source 0.1.0-beta.3.dev1。

## PDF 重現、斷點與結果

從 GitHub 固定提交 `6fd0b1435a8ebd1f384b2f76ceaa85dcbc2fba60` 取得 beta.2 的 analysis.py，在隔離模組搭配目前共用依賴執行。相同合成英文 AI 提示頁，舊模組產生 1 件作品；目前模組拋出固定安全提示且不產生作品，原稿 SHA256 不變。這是舊判讀模組對照，並非完整舊 EXE 的重新驗收。來源模組 SHA256 與結果見 historical-pdf-comparison.json。

實際 Python bdb 中斷點設於 source_compatibility.visible_pdf_page 的分類返回行（本輪第 85 行）：英文 301 字／en、繁中 112 字／zh-Hant、正常作品 46 字／無提示標記。實際 analyse_file 在匯入前排除中英文提示頁。此產品排除邏輯已存在於基底，這輪沒有重寫或放寬簽章。

舊環境回歸的失敗另有可重現原因：Windows 使用 offscreen 產生 PDF fixture，可讀文字全部為 0；相同程式改用 windows 平台即恢復。背景 worker 讀原生平台生成的 PDF 可正確排除。修正 run_checks.py 在 Windows 使用原生平台；原生模組基線耗時 409.869 秒，測試啟動器模組上限由 150 改為 600 秒，產品工作階段逾時與判讀斷言均未修改。保留 baseline-offscreen.json 的失敗，不把空白 fixture 當產品偵測反例。

## Windows 回歸

實際執行 tools/windows_review_dev/run_checks.py：31 項 PASS、0 failure、0 error、0 skip（PDF 14、diagnostics 7、stdio 9、暗選單 1）。PDF 包含中英文提示、正常 PDF／SVG、僅 metadata 的提示字樣、混合頁雙順序、真正 worker/parent IPC、安全錯誤及原檔保護。原生啟動與獨立 pythonw 合成畫面／正常退出亦通過。詳細時間與指令結果見 windows-regression.json。

Tesseract 與模型未配置；raster 測例使用明確合成 OCR observation 驗證後置阻擋，不代表真正 OCR 辨識率或完整 OCR 可用。沒有新 EXE 測試或完整舊產品資格提升。

## DirectWrite：未能重現

同一電腦／字型環境／合成資料，加入診斷前後：原生 GUI 的 DirectWrite 與其他字型記錄皆 0；offscreen worker 的 DirectWrite 皆 0、其他字型記錄皆 1。合成 probe 的 canary 前後各捕獲 1 次，證明記錄鏈可用；測試刻意注入的 DirectWrite 字串只用於驗證分類器，未計為真實重現。原生 pythonw 啟動後也未觀察到 DirectWrite 記錄。

結論為 NOT_REPRODUCED，不能宣稱原使用者觸發情境的 DirectWrite 警告已完全消失。既有系統字型選擇策略未修改，沒有過濾或隱藏警告。worker 的非 DirectWrite 字型訊息原樣保留，沒有冒稱所有字型警告為 0。

新增 --diagnostics-dir／TEMPLATE_AI_REVIEW_DIAGNOSTICS_DIR 明確啟用；GUI／worker 均在 QApplication 前安裝 Qt handler，每程序唯一檔、2 MiB 上限、worker stdout 仍為 JSON IPC，預設不記錄、不配置黑色主控台。原始訊息可能含字型名稱／路徑，只留指定本機目錄。GitHub 僅同步匿名計數、合成證據及程式，不同步 raw log、截圖、字型、作品、資料庫。

後續若原情境再出現，使用此選項在本機重走操作，先檢查本機 JSONL；取得重現後才針對原因修正。不要以 canary 或零筆日誌取代原情境驗證。

## 重跑與接續

先依上層環境工具指南啟用 Python 3.11.9／PySide6 6.8.3、Inkscape 1.4.4；PYTHONUTF8=1，QT_QPA_PLATFORM=windows，Inkscape bin 放 PATH。執行 `.venv/Scripts/python.exe tools/windows_review_dev/run_checks.py`。

可重跑斷點／字型 probe：`.venv/Scripts/python.exe tools/windows_review_dev/probe_pdf_fonts.py --root . --output .local-dev/new-probe --integrated`；output 必須不存在。工具只使用合成資料，原始記錄及畫面不提交。若比較 offscreen，另外新建目錄，不拿該平台的空白 PDF 當 Windows 產品輸入。GUI 本機診斷示例：`.venv/Scripts/pythonw.exe review_app.py --data-dir .local-dev/new-session --diagnostics-dir .local-dev/qt-logs`。

Qt handler 依 [Qt 6.8 官方文件](https://doc.qt.io/qt-6.8/qtlogging.html#qInstallMessageHandler) 安裝；PDF 可見文字使用 [QPdfDocument](https://doc.qt.io/qt-6.8/qpdfdocument.html) 的 bounded selection。既有離線守衛、原稿與安全報告邊界不變。

checkpoint `CP-20261024-REVIEW-PDF-DWRITE-002`；收據保存後依 本目錄 STATE.json 取得精確提交。只同步此部件，不合併 main、不打包或發布；review-v0.1.0-beta.2 的下載包不變。舊完整產品治理證據過期狀態保留，需求 registry／產品功能計數變化皆 0。


自動審核要求最小化共享歷史資料；本輪保留遠端 AGENTS.md／docs/dev/STATE.json／WORK_LOG.md 原樣，最新狀態改由本目錄 STATE.json 與精簡交接保存。初次本機 PREPARED checkpoint 001 因此由 002 取代，001 僅保留本機，未宣稱已遠端驗證。
