# Template AI Windows x64 實測版

這是內部測試版，不是已完成真實作品／正式印刷資格認證的正式版。

1. [下載 TemplateAI-v0.2.0-beta.2-windows-x64.zip](https://github.com/givemedandanla-tool/template-Ai/releases/download/v0.2.0-beta.2/TemplateAI-v0.2.0-beta.2-windows-x64.zip)，完整解壓到本機資料夾。
2. 開啟資料夾中的 TemplateAI.exe；不必另裝Python，請保留旁邊的_internal、engines資料夾與所有檔案。
3. 初次先用測試副本，不直接使用唯一客戶資料庫。程式資料預設存在%LOCALAPPDATA%\TemplateAI\TemplateAI，與程式分開；可用TemplateAI.exe --data-dir "D:\TemplateAI-Test"指定獨立測試目錄。
4. 本版隨包附帶 Inkscape 1.4.2，不需另外安裝。完整 Illustrator 私有內容還原仍有邊界。
5. 字型使用您本機已合法安裝／匯入的檔案；本包不附私人或商業字型。缺字、來源不足與正式資格未通過時，程式仍會阻擋相關操作。
6. 從「學習作品」開始匯入、檢查分析／雜訊與來源；再到「製作稿件」輸入、產稿、預覽、拖動修正、重新確認及輸出。進階來源審查／容量／資格仍有後台流程，不是全自動認證。

## 沒有安裝 Inkscape，可以使用嗎？

可以。本版已附帶固定版本，不讀取電腦另裝的版本或環境變數。請完整解壓，包內元件損壞時重新下載解壓；不會默默改用外部版本。

| 用途 | 是否需要另外準備 |
| --- | --- |
| 啟動 EXE、既有模板輸入／排版／預覽 | 不需要 Inkscape 或 Python |
| 既有模板輸出 | 不強制依賴 Inkscape；仍須通過該稿件的字型、來源及輸出檢查 |
| PDF 相容 `.ai`／PDF、SVG、PNG／JPG 讀取 | 有內建備援；能讀取不等於已完整還原或能完成自動分析 |
| 自動作品結構／幾何分析、Logo 群組發現 | 使用包內 Inkscape；包內檔案缺少或損壞時清楚阻擋 |
| 原稿文字與字型核對 | 需要您本機相符且有權使用的字型；本包不附私人／商業字型 |
| OCR 輔助 | 工具與語言模型未附，相關 Windows 能力待本機條件驗證 |

本包已含 Inkscape 1.4.2。Inkscape 是本機免費工具，安裝後不需為作品分析訂閱服務，也不保證完整還原所有 Illustrator 私有內容。程式日常使用不需 API key，不自動上傳作品。

## 遇到問題

從「問題與報告」手動匯出安全ZIP，回Codex附上報告，說明版本v0.2.0-beta.2、您按到哪一步、預期與實際結果。程式不自動上傳，也不需要API key或聯網；作品、字型、資料庫與模型留在您的電腦。若主視窗無法啟動，可執行TemplateAI.exe --support-report "D:\TemplateAI-support.zip"；若用了自訂資料目錄，請同時帶--data-dir。

本包未做付費程式簽章。若Windows顯示不認識的發行者，先核對GitHub來源與SHA256，不要停用防毒。

## 資料與已知限制

沿用既有本機資料格式，本次沒有授權強制資料遷移；新版建立的資料回舊版能否開啟尚未完整驗證。請在更新前做本機備份，以獨立副本試用，回復時使用對應舊程式及舊資料副本。舊定稿／模型／版本不應被新學習默默改寫。

真實作品學習品質、完整私人.ai還原、您的Windows硬體效能、實體印刷與獨立新手易用性待您本機回饋。網頁／手機、教學與外部知識庫草案尚未列入本次成品。Linux來源測試不等於Windows包驗證；實際Windows結果請以同次Release的release-manifest.json為準。

本包亦未附Tesseract與OCR語言模型；OCR輔助須使用您本機就緒的合法工具與模型。WindowsOCR安裝與真實辨識品質尚待本機實測，缺少時應顯示需要補足資訊，不能當已識別。

開源元件授權與對應來源見包內 engines/inkscape/TEMPLATE_AI_REDISTRIBUTION.md。Release 的來源 ZIP 為開發者選用附件，日常只需下載 Windows 程式 ZIP。
