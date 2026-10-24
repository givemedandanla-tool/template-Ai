review-tool 隨身碟一鍵準備與啟動（Windows x64）

1. 將整個 ReviewTool-USB 資料夾複製到隨身碟，再帶到已安裝並啟用 Illustrator 的電腦。
2. 先啟動一次 Illustrator、完成授權/首次啟動提示，保存未保存文件。
3. 雙擊 START_REVIEW.cmd。不要單獨複製這個檔案。

不需要 Git、系統 Python、系統 Inkscape，也不需要從 GitHub 或 PyPI 下載。
這是 feature/review-tool-v0.1.0 的固定提交來源副本，不會自動更新成未測試的新版本。
精確提交與所有檔案 SHA256 在 transfer-manifest.json。

第一次會核對檔案、在 C:\ReviewToolLocal\r<隨機編號> 建立獨立環境，
若該位置沒有寫入權限，使用 %LOCALAPPDATA%\TR\r<隨機編號>。
不需系統管理員權限。若路徑太長或磁碟空間不足會停止，不覆寫其他安裝。
建議預留至少 4 GB 本機空間。準備時請保留隨身碟連線。

腳本先透過真實 Illustrator 產生兩畫板合成 AI（關閉 PDF 相容），
再經同一接口轉成 PDF 並判讀。成功才啟動 review-tool；
未安裝、COM 未註冊、警告卡住、逾時或判讀失敗都會停止並保留本機記錄。
請注意 Illustrator 的字型、連結、指令碼等提示視窗。沒有關閉這些原廠提示。
本開發機沒有 Illustrator，真實 Adobe 成功與保真仍需在目標電腦驗收。
自動通過不等於文字、色彩、透明度、圖片與各畫板均已人工核對。

介面開啟後：更多 → 使用 Illustrator 匯入 AI（實驗性）→ 選 AI → 開始判讀。
請先保存並關閉 Illustrator 中的同一份原稿，其他文件保持原狀。
PDF 相容提示頁類型的 AI 請使用上述入口。

第一次成功準備環境後，命令視窗會顯示本機目錄。
之後可直接雙擊本機目錄內 START_REVIEW.cmd；不需要隨身碟。
同一份來源副本重複啟動沿用同一份資料，不會重建/覆寫環境；已開啟時不開第二份。
要重新驗證（例如 Illustrator 更新後），先關閉 review-tool，再雙擊 RETEST_ILLUSTRATOR.cmd。
重測失敗會停止；不以舊通過紀錄略過失敗。所有舊合成資料與記錄仍保留。

本機環境的子目錄：
  data          工作進度、私人匯入副本與 Inkscape 獨立設定
  diagnostics   每次啟動的準備/錯誤/Qt 原始診斷（可能有私人路徑或字型名稱）
  synthetic     自動產生的合成 AI、PDF 與驗收結果
  qualifications 歷次合成驗收狀態

若失敗，請記下畫面上的本機目錄並檢查 diagnostics 最新一輪。
可在檔案總管輸入 %LOCALAPPDATA%\TemplateAIReviewUSB 找到本機安裝索引。
不要刪除失敗目錄或拿舊檔覆蓋修復；先保留供排查。
若準備完成前中斷，重試會建立新目錄，舊半成品保留。

程式不包含上傳、Git 推送、雲端轉檔或自動更新功能。Adobe 自身授權連線不受此腳本控制。
私人作品、字型、客戶資料、工作資料夾與原始診斷不得上傳 GitHub。
要用隨身碟移動私人資料，請另放獨立資料夾；本腳本不自動匯入或覆蓋它們。
不要直接搬 .venv 當新電腦環境；本腳本會從乾淨依賴重建。
完整 OCR 尚未配置；此資料夾不代表已發布 EXE、完整 OCR 或私人作品保真資格。

移除準備環境的命令視窗不會關閉已啟動的 review-tool。
未執行 EXE 打包、沒有 Release、沒有合併 main。
