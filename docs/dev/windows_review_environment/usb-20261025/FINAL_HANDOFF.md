# review-tool USB 一鍵環境交接

分支 `feature/review-tool-v0.1.0`；功能碼提交 `f8bb3a135a5bd173423470583b57ffd19a3bb605`；checkpoint `CP-20261025-REVIEW-USB-003`。本檔取代此資料夾先前的 PREPARED/PENDING 進度，不修改共享歷史交接。先讀 [最終狀態](FINAL_STATE.json)、[報告](REPORT.md)、[Windows 證據](WINDOWS_VALIDATION.json)；遠端確認另見 [REMOTE_STATUS.json](REMOTE_STATUS.json) 與 checkpoint 收據，尚未存在前不宣稱遠端完成。

交付為可複製來源資料夾 `ReviewTool-USB-20261025`，不是產品 EXE 或 Release。使用者可從本機經 USB 移轉，不需在目標機安裝 Git/Python/Inkscape 或連線下載。內含指定提交來源、官方 Python 3.11.9、Inkscape 1.4.4 與 21 個固定 wheels；各檔 SHA256 見資料夾 manifest。私人作品、字型、既有資料庫與原始記錄均未加入。

雙擊 START_REVIEW.cmd：核對→新本機短路徑→離線 venv→真 Illustrator 合成 AI/PDF 驗收→通過才開啟 review-tool。首輪環境準備可能需數分鐘，畫面會顯示進度。再次啟動沿用資料，診斷另存；重測用 RETEST_ILLUSTRATOR.cmd。來源 immutable/hash 不符就停止，不能覆寫修復。GUI 使用獨立 pythonw；原稿仍由「更多→使用 Illustrator 匯入 AI（實驗性）」處理。

Windows 27/27 回歸、全新離線環境、21 依賴/pip check、隨附 Inkscape、兩頁合成 PDF 文字/頁數/來源不變、原生 Qt 擷取及正常退出、pythonw 無 console handle 均通過。重開保留合成工作資料和舊診斷。

此機無 Illustrator，實機 Adobe 成功與私人作品保真仍 NOT_VERIFIED；缺少 Illustrator 確實停止並保存診斷，此預期拒絕不能當真 Adobe 轉檔成功。完整 OCR 尚未配置。下一步在目標電腦自動合成驗收後人工比對全部畫板，再測私人檔案，資料只留本機。不合併 main、不打包發布。
