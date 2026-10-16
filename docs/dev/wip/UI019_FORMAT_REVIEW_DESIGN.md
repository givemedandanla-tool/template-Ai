# UI019 C2：同格式、成品尺寸的實際快照

015真反例：9tests/7PASS/2FAIL。可讀同尺寸blankPDF、有效但全黑JPEG仍會發布，故不能以decode/size或任意MSE分數冒充內容／Logo忠實度。

已定實作順序（不用再長篇重設計）：
1. 原render.export增加僅限preview=True的exact_preview模式。成品本體尺寸與原paint_candidate相同，略去矩形外附註；檔名、PDF title與影像metadata標記PREVIEW。它是私有診斷檔，不是新輸出器、不發布正式檔。
2. 原build_proof保留既有有附註預覽；PDF/JPG另產生exact_file。region_images優先顯示exact_file，pixel/mm保持本體原尺寸。Scope包含所有驗證code/hash／候選／輸入／來源／字型／Logo／格式／DPI。
3. digital_review提供plan/confirm/validate：具名、明確證據、literal True、current hard checks、exact-file hash與actual decode。PDF/JPG需此當次scope的明確核對；PNG仍可依目前來源與實際lossless full RGB檢查自動完成。不是永久訂單／影子審核庫，receipt留原當次session RAM，失聯不可沿用。
4. 原render.export接format_review參數。原digital_final在正式編碼前驗目前receipt，編碼後實際解碼final與已核對exact_file做全解析度RGB一致比較；PDF另比較正規化resources／vector operator histogram／image descriptors，保護向量屬性。不得用舊頁附註造成幾何取樣差異或捏造感知閾值。若出現不一致，FailClosed。
5. 原right property preflight panel增加只對PDF/JPG顯示的未預選核對控制、具名與證據；沿原run_job，前後form/context pins，變更清除receipt。Main.export_current只交付目前receipt，格式不符需回同一workbench，不加編輯器。
6. 原output_batch的PDF/JPG path需沿既有每target範圍接同一核對receipt／入口，不能放寬backend bypass。所有既有positive tests由合成資料作者明確建立目前格式核對，原內容／尺寸／Gate assertion保留；新增negative必須先建立有效receipt再注入codec錯誤，避免只測到缺核對。
7. 先test C2 API與actual original GUI，實際PDF/JPG deterministic same-format compare/structure（只略去metadata/document-specific IDs）。再複合Logo/文字/點陣/曲線/未知效果/真源字型PoC、native逐圖、原12完整mapping及immutable全來源Gate。

保留資料：012五真missingguard+兩fixture修正；01345PASS；01162PASS。015反例尚未修，不能標完成。環境無Pillow/numpy，優先用既有Qt/pypdf；若確需新開源依賴，先保存環境變更checkpoint，不啟用付費API。無EXE/main merge/代理。
