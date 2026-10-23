# 判讀核對工具獨立測試版發布規則

使用者2026-10-23要求將已討論的最小工具製作第一版並發布GitHub，取代先前僅設計／未授權實作的階段。主代理保存本次原文授權於 `STATE.review_tool_release_request`。

這是獨立「作品判讀與核對」交付物，不是舊完整Template AI編輯／訓練產品的新完整資格。版本唯一來源為 `template_ai/review_tool/__init__.py`，首版 `0.1.0-beta.1`、tag `review-v0.1.0-beta.1`、EXE `TemplateAIReview.exe`。舊 `TemplateAI.exe`、beta.1／beta.2 tag、正式證據、模型與舊資料庫不改寫。

## 必要門檻

- 僅精確 `release-request/review-v0.1.0-beta.1` push 或人工dispatch建置；普通開發／main／PR不打包。
- 原生公開Windows標準runner，既有27固定wheel與Inkscape1.4.2全11837檔逐byte再驗。使用既有免費cache預算檢查；跨分支可能miss，不把命中當測試通過。
- 每個目前 `test_review_*.py` 加固定8個來源／PDF字形／分割／語意／引擎核心模組，在獨立程序執行，不空掃描，來源／測試與HEAD精確綁定；失敗、skip、程序錯誤分開記錄。實際模組名保存在報告，此範圍不能升級舊完整軟體或外部資格。
- 真正frozen EXE執行匿名合成AI／原稿／判讀worker／標記／視覺定位／保存重開流程，原稿不變，人工資料和私人內容不混入報告。
- 只有同一來源及同一EXE bytes通過才能打包。ZIP完整inventory、檔案hash、版本／相容性／限制／授權／來源下載資料必齊。
- 既有Inkscape對應來源125物件全驗，重用beta.2既有公開來源ZIP，清楚列URL及SHA，不重複上傳908MB，也不冒稱新下載／新產生原始碼。
- 本版隨包固定官方中／英OCR資料與Apache授權，但**Tesseract執行器選配、未內嵌**。缺OCR時必有白話提示，原文與人工路線可離線使用。不得因有模型檔就宣稱具備OCR引擎。
- 公開前草稿實際下載完整ZIP並逐檔再驗；公開後再實際下載一次。不得用本機loopback或Actions artifact代替GitHub Release下載。
- 元件未知、私人AI還原品質、全部字庫、使用者Windows硬體／效能、新手可用性及後續學習品質保持各自未驗收，不把本版叫做全部AI功能完成。

## 發布控制

正常建置只產證據及artifact。只有精確request分支、提交包含 `[publish-review]`、`REVIEW_RELEASE_PUBLISH_ALLOWED=true`，且本次STATE授權吻合version/tag/scope、`published=false`，才允許 `publish`。

授權可在提交前將 `source_commit` 留為 null，避免把提交SHA寫進自身內容的循環。CI採當下Git HEAD與精確來源manifest綁定真正成品；若授權另有非空來源pin，必須與HEAD相同。Lucide圖標、LICENSE及UPSTREAM一併納入來源身分及PyInstaller資料，從固定提交重建，不下載最新版。

先確定遠端tag與Release不存在，建立新tag與草稿，不覆寫、不強推、不合併main。任何不明認證／查詢失敗都不當成不存在。若草稿／tag建立後驗證失敗，保留失敗證據，修正須明確重試策略或新beta版本，不能默默覆寫既有發行。

`tools/review_release.py`入口：prepare、test、build、exercise、package、verify-download、publish、persist-evidence。每階段記真實耗時。公開合成JSON／log／截圖持久化到獨立 `review-release-evidence/v0.1.0-beta.1` 分支，原稿DB／字型／模型／完整工作區不進Git；二進位ZIP只放Release附件。

本機測試資料放獨立review工具目錄，不自動開啟／遷移唯一舊庫。解壓完整資料夾執行，不需另裝Python或Inkscape；字型留本機。首次交付狀態為「已發布，待使用者本機確認」。
