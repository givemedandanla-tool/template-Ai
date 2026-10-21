# Template AI Windows x64 實測版

這是內部測試版，不是已完成真實作品／正式印刷資格認證的正式版。

1. 從GitHub Release下載 TemplateAI-v0.2.0-beta.1-windows-x64.zip，完整解壓到本機資料夾。
2. 開啟資料夾中的 TemplateAI.exe；不必另裝Python，請保留旁邊的_internal資料夾與所有檔案。
3. 初次先用測試副本，不直接使用唯一客戶資料庫。程式資料預設存在%LOCALAPPDATA%\TemplateAI\TemplateAI，與程式分開；可用TemplateAI.exe --data-dir "D:\TemplateAI-Test"指定獨立測試目錄。
4. 沒有安裝Inkscape也能啟動EXE，使用既有模板輸入、排版、預覽及符合既有資格的輸出。PDF相容.ai／PDF、SVG與PNG／JPG有內建備援讀取；可讀取不代表已完整取得可編輯文字、原稿字型或通過訓練／正式輸出資格。目前自動作品結構／幾何分析與Logo群組發現也依賴Inkscape；缺少時保持待人工。因此要測試「匯入作品→完整自動分析→學習規則」，仍須安裝Inkscape。要擴大作品轉換支援範圍，再另外安裝免費的[Inkscape](https://inkscape.org/release/)；建置驗證使用1.4.2，包內未附。無PDF相容內容的.ai需要可用的轉換器或另存支援格式；即使安裝Inkscape，也不保證完整還原所有Illustrator私有內容。
5. 字型使用您本機已合法安裝／匯入的檔案；本包不附私人或商業字型。缺字、來源不足與正式資格未通過時，程式仍會阻擋相關操作。
6. 從「學習作品」開始匯入、檢查分析／雜訊與來源；再到「製作稿件」輸入、產稿、預覽、拖動修正、重新確認及輸出。進階來源審查／容量／資格仍有後台流程，不是全自動認證。

## 遇到問題

從「問題與報告」手動匯出安全ZIP，回Codex附上報告，說明版本v0.2.0-beta.1、您按到哪一步、預期與實際結果。程式不自動上傳，也不需要API key或聯網；作品、字型、資料庫與模型留在您的電腦。若主視窗無法啟動，可執行TemplateAI.exe --support-report "D:\TemplateAI-support.zip"；若用了自訂資料目錄，請同時帶--data-dir。

本包未做付費程式簽章。若Windows顯示不認識的發行者，先核對GitHub來源與SHA256，不要停用防毒。

## 資料與已知限制

沿用既有本機資料格式，本次沒有授權強制資料遷移；新版建立的資料回舊版能否開啟尚未完整驗證。請在更新前做本機備份，以獨立副本試用，回復時使用對應舊程式及舊資料副本。舊定稿／模型／版本不應被新學習默默改寫。

真實作品學習品質、完整私人.ai還原、您的Windows硬體效能、實體印刷與獨立新手易用性待您本機回饋。網頁／手機、教學與外部知識庫草案尚未列入本次成品。Linux來源測試不等於Windows包驗證；實際Windows結果請以同次Release的release-manifest.json為準。

本包亦未附Tesseract與OCR語言模型；OCR輔助須使用您本機就緒的合法工具與模型。WindowsOCR安裝與真實辨識品質尚待本機實測，缺少時應顯示需要補足資訊，不能當已識別。
