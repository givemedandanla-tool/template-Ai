# review-tool 手動測試失敗與繁中提示頁修正

本輪限 feature/review-tool-v0.1.0 的來源開發版 0.1.0-beta.3.dev1。使用者先回報開始判讀後無結果；短路徑重新判讀雖完成，後續畫面又證明提示頁仍被列為作品。先前「程序完成」不應當作內容正確。

## 根因與修正

1. 本次人工測試使用過深的資料目錄，匯入快取衍生路徑遇到 Windows 路徑限制；短資料／快取路徑可完成同檔處理。已改用新短路徑工作階段，保留舊資料及原稿。這是本機啟動設定修正，不宣稱任意長路徑全面支援。
2. 尚未／失敗的來源將 analysis 設為 null，選取時卻直接呼叫 get，造成 AttributeError。現在容許 null，失敗來源保留安全的重試指引；FileNotFoundError 使用固定快取／短路徑提示，不轉送子程序原始文字。
3. 繁中相容提示使用「未附帶 PDF 內容」，舊字串清單漏列。增加這一精確措辭，仍同時要求 Adobe Illustrator、建立 PDF 相容檔案與重新儲存等必要條件；未使用模糊比對、私人 AI 資料解碼或只看關鍵字的攔截。

採用既有 QtPdf 可見文字、review 相容性閘門、QProcess 安全訊息與 SessionStore；沒有新增依賴。規格與上次固定來源見 ../pdf-dwrite-20261024/REPORT.md。未擴大舊完整產品、發布、OCR 或訓練資格。

## 驗證

- 原 null／失敗來源合成重現：3 項中 1 failure、2 errors；修正後 3 PASS。
- 新繁中措辭合成重現：3 項中 2 failures；修正後全過。涵蓋重複文字區塊的真正 PDF、分行觀察資料與缺少必要條件的反例，不使用私人原稿作為 fixture。
- 本輪最終原生 Windows：30 PASS／0 skip／0 failure／0 error；PDF 完整模組 17 項，背景程序與失敗介面 13 項。正常 PDF、混合頁兩種順序、僅 metadata 含提示、正常 SVG 與安全 IPC 均保留原斷言。早先 Jobs 的 1 skip 是測試 PATH 缺 Inkscape；補正後真正引擎回歸通過，未隱藏 skip。
- 使用者已載入檔案只在本機覆驗：新規則在匯入前阻擋；實際 worker 回傳 ILLUSTRATOR_PDF_PLACEHOLDER，無 result、0 作品，原稿雜湊前後相同。原稿／雜湊值／名稱／路徑／文字／截圖／原始記錄均不發布。
- DirectWrite 本次故障未觀察到；仍是 NOT_REPRODUCED，不宣稱原始字型情境已完全修復。Qt 診斷持續供本機操作取證，原始檔只留本機。

## 使用與界線

提示頁不是實際作品。應用 Illustrator 開啟原檔，另存副本並啟用「建立 PDF 相容檔案」，再加入副本判讀；不能由提示頁還原真實作品。

舊工作階段保留，重新測試使用新短資料目錄。既有已保存的誤判作品不自動刪除，以免覆蓋人工修訂；新工作階段的提示頁應顯示處理指引與零作品。舊視窗不會熱載入新程式，需正常保存並關閉後重啟。診斷路徑亦用短目錄，私人資料不放進 checkpoint。

OCR 執行器與英繁中模型尚未配置，合成 OCR observations 不等於真正 OCR 品質驗收。不合併 main、不打包、不發布，已發布 beta.2 不變。

本輪 checkpoint 與遠端精確提交見本目錄 STATE.json；只更新部件狀態、精簡交接和匿名測試證據，共享歷史 AGENTS／STATE／WORK_LOG 保持遠端基底原樣。
