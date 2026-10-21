# Windows實測版已發佈且下載校驗完成

來源8b95b10b300dbead4c51264100af7bdd644433ce；run39638803778；tag v0.2.0-beta.1。原生Git回執RELEASE_PUBLISHED_DOWNLOAD_VERIFIED精確讀回，獨立Git原始commit及全tree核對亦PASS，證據分支commit見native-git-proof.json。

原176/176 Windows來源案例PASS，16healthy、49新Qt程序、0runtime、source unchanged。實際frozen EXE原14+7兩階段PASS，utf8_mode1；source_matches_head／source_unchanged均true。包含輸入、學習、預覽、真滑鼠拖動、更正、確認、允許輸出／不合格正式拒絕、暫停邊界、明確重啟接續、不重做已完成單位、已確認稿重播與安全報告。包建置前只移除83個已知第三方tests資料，原最終inventory Gate不變，精確清單見build-payload-filter。

工作流程先實際下載草稿全部資產並校驗，才公開prerelease，再實際重新下載所有資產，逐一核對ZIP內1220檔hash／清單與manifest／checksums。download-verification.json是最後公開下載實測；先前草稿校驗成功是發布步驟必要前置。雲端另外以未登入公開URL取得manifest與checksums，HTTP200且與原生Git證據逐byte相同，tag解參照來源亦相同；沒有重複第三次大型ZIP下載。

下載：https://github.com/givemedandanla-tool/template-Ai/releases/download/v0.2.0-beta.1/TemplateAI-v0.2.0-beta.1-windows-x64.zip

ZIP125923070bytes；SHA256 0429fcbf0d4b2edb17a459b90ab6c04903a577570a739bc6247f33424ec0d526。完整解壓，保留_internal，執行TemplateAI.exe；不需另裝Python。使用獨立測試資料副本，回報版本與手動匯出安全ZIP，私人作品、字型、模型留本機。

本版沒有內附Inkscape（原生驗證使用本機1.4.2）、OCR工具或私人／商業字型，也尚未串接Illustrator。啟動／既有模板不強制依賴Inkscape；完整自動作品結構／Logo分析目前需要它，部分格式備援不等於全部分析可用。隨包Inkscape與本機Illustrator適配器提案分開保存，非本版已實作能力。

實際私人作品、使用者Windows硬體效能、實體印刷、新手資格與OS級完全斷網測試仍依既有外部資格；本次原生來源與EXE驗證不自動升級這些項目。核心manifest仍0c4c11c8bd6a899cff6f10822f7af018a9998c5440ec05dc3b44d77075a14274；原Linux1963資格、172要求／166scoped／75父題及延後項未改。原始失敗／取消證據保留。沒有合併main、覆寫版本、啟用新收費服務／試用或子代理；未稽核帳戶總帳單。
