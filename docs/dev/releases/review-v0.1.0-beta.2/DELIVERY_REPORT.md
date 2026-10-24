# 作品判讀與核對工具 beta.2：OCR隨包版交付

已公開發布 **0.1.0-beta.2**。Inkscape、Tesseract執行器及固定英文／繁體中文模型皆隨包附帶，不必另裝OCR，正常使用離線，私人作品與修正記錄留本機。

[下載Windows程式ZIP](https://github.com/givemedandanla-tool/template-Ai/releases/download/review-v0.1.0-beta.2/TemplateAIReview-v0.1.0-beta.2-windows-x64.zip) · [Release與全部附件](https://github.com/givemedandanla-tool/template-Ai/releases/tag/review-v0.1.0-beta.2) · [第一次操作](QUICK_START.md)

## 使用方式

完整解壓到新的本機資料夾，進入TemplateAIReview執行TemplateAIReview.exe，保留旁邊的_internal與engines。日常只需程式ZIP，OCR原始碼附件供授權／開發用途。

先加入一份作品副本→開始判讀→點原稿標記核對文字／種類／歸屬→選「已核對」或「暫時無法確定」→套用這項修正→保存進度；核對完按「完成這份核對」。舊記錄仍可讀，原人工修正保留，新版判讀另存口徑。

遇到問題使用「更多→匯出問題報告」，查看後手動提供版本與操作步驟；不需上傳私人作品、字型或完整資料庫。報告包含受控OCR狀態／錯碼／公開版本與hash，以及白話摘要。

## 已實際驗證

- Windows 22個隔離模組 **270／270 PASS**，0失敗、錯誤、跳過或逾時。不是只查版本或空掃描。
- 真正frozen Windows EXE **40項PASS**：英／繁中外框SVG及純點陣PDF正確文字、座標與語意候選；人工歸屬、保存重開；缺執行器／壞manifest明確退路及人工補標。
- 凍結版固定包內引擎，抵抗外部PATH／環境選擇；精確runtime pin、2語言模型及原始資料不改寫。
- Windows深中文圖片／模型路徑、原圖bytes／geometry、受驗短模型暫存與清理通過；原PNG以binary stdin輸入，固定模型內容不變。
- 草稿與公開Release兩次實際下載，各逐檔校驗 **13,203個程式檔案**；OCR來源ZIP各 **25個來源壓縮物件＋75份notices** 逐內檔再驗。
- 正常入口於該Windows runner顯示視窗1.291258秒。此為本次CI測量，不保證使用者硬體相同。
- 維護端另實際下載公開SHA256SUMS、讀回12份安全證據逐byte/hash及原生Git精確來源／tag；相符。

## 精確版本與附件

- Tag：review-v0.1.0-beta.2；建置來源：6fd0b1435a8ebd1f384b2f76ceaa85dcbc2fba60。
- [Windows run40057767083](https://github.com/givemedandanla-tool/template-Ai/actions/runs/40057767083)：completed／success。
- 程式ZIP356,929,481bytes；SHA256 `0095bb4491807e81f9c352174d543b3244d3b006522a17d6db23343a29017e66`。
- OCR來源ZIP261,642,776bytes；SHA256 `b6a41ee381f1765893fa5264e0ae9a5430ec0ef72f270ce2d9b40e8d62e6a6b2`。本機試組裝ZIP的c2c6…屬本機證據；正式下載以上述Windows附件hash為準，沒有宣稱跨OS ZIP容器bitwise一致。
- 其餘附件：release-manifest.json、SHA256SUMS.txt、validation-summary.json、SOURCE_DOWNLOADS.json。程式內已保留各開源元件授權，來源附件另附，既有Inkscape對應來源保持固定且驗證後重用。
- 可信Tesseract 5.4.0.20240606／Leptonica1.84.1；runtime107個清單項加manifest共108檔，包含所需27個PE執行器／DLL與完整通知，不以Apache概括所有依賴。
- [維護端讀回](windows-published-40057767083/ROOT_READBACK.json)、完整每檔hash／模型pin／耗時／下載證據均在同版本windows-published-40057767083目錄。
- 原始CI安全證據分支review-release-evidence/v0.1.0-beta.2，目錄runs/40057767083-1-6fd0b1435a8e/。來源／交接在feature/review-tool-v0.1.0；未合併main、未覆寫beta.1。GitHub API預設targetCommitish=main不作來源證據，實際tag已精確核對。

## 修正與範圍

首五輪失敗保留於LOCAL_VALIDATION與各Windows目錄：漏入Git的合法空license、PDF測例資源釋放、Windows圖片／模型路徑互通、來源故障測試隔離及測試短／長路徑別名比較。沒有略過中文字要求、改模型或放寬原private payload gate；最終來源與真正EXE全部通過。

主圖形介面維持原稿中心＋步驟引導；日常處理可見內容及歸屬，底層數據從「查看全部判讀資料」開啟。OCR結果仍是待核對候選，字型／字級／間距／人物身分不確定時保持未知。這是判讀與核對部件，沒有自動訓練模型或產出模板。

所有測例均為合成資料，私人.ai還原品質、使用者字庫／硬體／新手體驗、實印與後續AI學習仍待本地回饋；real_corpus_qualified=false、user_local_confirmation=false。舊完整產品的過期來源／外部資格沒有被本元件結果提升。程式未簽章，遇系統阻擋請核對來源／SHA並回報，勿關閉防護。

使用既有Pro/Codex能力、免費本機工具與公開GitHub標準runner，未購買、啟用試用、付費API／模型服務或新付費資源；未查核帳戶帳單，不捏造扣款。私人作品、字型、客戶DB與私有模型未上傳。原未提交timeout/adopt工作仍保留。

交付後等待使用者一份本地作品實測／安全報告，再按review版本維護，不自動展開下一部件。
