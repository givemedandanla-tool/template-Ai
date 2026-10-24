# USB 來源環境與 Windows 驗證報告

需求 REVIEW-USB-START-01：在另一台已安裝 Illustrator 的 Windows x64 電腦一鍵準備並啟動 review-tool，可用隨身碟移轉，不依賴 GitHub 下載、不覆寫既有資料。功能碼 `f8bb3a135a5bd173423470583b57ffd19a3bb605`，checkpoint `CP-20261025-REVIEW-USB-003`。

已交付 `tools/windows_review_dev/usb/`：官方依賴固定來源、嚴格來源匯出器、離線啟動器、獨立 GUI host、一般/重測 CMD 入口與操作指南。匯出只取提交清單內且 blob 相符的本機程式，避開 partial clone 的歷史下載；圖示與授權採明確範圍。完整 USB 資料夾含 13778 個清單檔、1006556387 bytes，manifest SHA256 `ebf12d4f00187ed451744caa1bb4a1f876c085214d34f33f92a7ca8a8a2abcfc`。原始依賴與 manifest 只留本機交付，不上傳 GitHub。

安裝以唯一短路徑建立環境，目標不需管理員、Git、系統 Python/Inkscape 或網路下載。由已驗 hash 的 wheels 用 no-index/require-hashes 安裝，不搬舊 venv。清單外額外 USB 檔案不複製；既有路徑拒絕覆寫、links/junction/path traversal 拒絕；複製與校驗最多 8 workers。失敗保留本機記錄、部分結果與舊工作進度。Adobe 原廠授權/警告由使用者處理，不修改其偏好或警告設定。

驗證：27 項 Windows 邊界測試 0 fail/skip；包含384檔並行建立與真 Windows junction。用交付資料夾在新本機環境完成 21 wheels 安裝與 pip check；再啟動沿用環境與原資料，保留兩輪診斷，真 CMD 清單檢查通過。隔離 runtime 使用隨附 Inkscape 判讀正常兩頁合成 PDF，頁數、預期文字與來源不變通過；原生 Windows Qt 空白工作階段擷取並正常退出，獨立 pythonw console handle 為零。此組測試未使用任何私人原稿或字型副本。詳細結果見 WINDOWS_VALIDATION.json。

界線：此機沒有 Illustrator，完整一鍵成功路徑中的真 Adobe 合成轉檔尚未執行；入口在缺少 Adobe 時正確停止，不偽造 PASS。另一台機器第一次必須先通過 smoke.py，人工核對各畫板/文字/圖片/顏色/透明度；自動 PASS 不等於私人文件保真。OCR 未配置。全專案 dev_governance 在修改前及結束均因既有完整產品證據過期失敗；本輪不修改全產品治理或將窄驗證升為全產品合格。

持久化：只同步本部件程式、合成測試及匿名摘要；原始記錄、作品、字型、資料庫、工具 binaries/wheels 均不進 Git。共享 AGENTS/STATE/WORK_LOG/ACTIVE_DEVELOPMENT_HANDOFF 保留；新增 docs/dev/REVIEW_TOOL_USB_HANDOFF.md 作入口。已拒絕的覆寫風險操作改用排他建立與獨立交接，沒有因此覆寫舊資料。所有先前失敗副本保留本機；未合併 main、未建立產品 EXE、未發布。
