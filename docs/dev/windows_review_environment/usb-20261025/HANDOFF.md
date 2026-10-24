# 當前：review-tool 隨身碟一鍵環境準備與啟動

指定 `feature/review-tool-v0.1.0`。本輪需求 `REVIEW-USB-START-01`；先讀 [部件 STATE](windows_review_environment/usb-20261025/STATE.json)、[契約](windows_review_environment/usb-20261025/CONTRACT.json) 和 [隨身碟指南](../../tools/windows_review_dev/usb/README.txt)。checkpoint `CP-20261025-REVIEW-USB-001`。

已實作來源副本匯出、逐檔完整性校驗、離線 Python/固定 wheels/Inkscape 準備、Illustrator 合成驗收通過後才啟動、獨立 pythonw 與本機診斷。20 項 Windows 合成邊界測試通過。公開依賴下載與真正離線環境驗證尚在進行，尚未交付可使用資料夾。

此機沒有 Illustrator，真實 Adobe 成功與私人作品保真仍未驗證。既有 Illustrator 接口的 Windows 56 PASS 是前一輪證據；本輪不修改產品判讀邏輯。完整 OCR 未配置。下一步完成乾淨環境與合成 UI/失敗關卡驗證，再交付 USB 來源資料夾。

原稿、字型、客戶資料、資料庫及原始記錄只留本機。新環境建立於唯一短路徑，已存在檔案拒絕覆寫；共享歷史 AGENTS/STATE/WORK_LOG 不改。不合併 main、不製作產品 EXE、不發布。來源仍 0.1.0-beta.3.dev1。
