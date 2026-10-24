# beta.2：隨包OCR實作與驗證範圍

使用者2026-10-24明確要求「加入ocr執行器，然後再次發佈」。依既有元件／維護規則增號review-v0.1.0-beta.2，不覆寫beta.1、不合併main。

1. 固定官方推薦Windows Tesseract發行包／hash／授權，僅在建置下載、安全抽取；使用者不需安裝或聯網。
2. 執行器與DLL放engines/tesseract，固定官方中／英文模型維持engines/ocr-models單份。完整清單與release-info pin，凍結版只用包內且失敗明示；來源開發仍可用明確local配置。
3. 檢查範圍：runtime取得／完整性、logo_ocr核心與模型能力、review分析／worker／UI與保存、實際EXE合成英文及繁中外框／點陣OCR、缺／壞引擎人工退路；既有16隔離模組保留，新增相關模組。純OCR加包不改AI訓練／模板／其他產品規則。
4. 發布前來源identity含新增工具／鎖／測試與workflow；真正Windows cleanbuild，不依賴主機預裝OCR，包內確切版本／兩語言及非零正確辨識須PASS。舊private payload gate保留；取得OCR可信清單後才加入精確vendor inventory。
5. 保留固定依賴及Inkscape／來源附件快取；每階段耗時；新tag草稿與公開兩次實際下載逐檔校驗；安全證據與精簡交接GitHub持久化、獨立原生Git讀回。

不得把OCR失敗後人工補標當OCR正向驗收；缺／壞OCR退路另外驗。無私人作品、不增加付費服務。執行結果與可信來源／授權細節後補於同版本資料夾。
