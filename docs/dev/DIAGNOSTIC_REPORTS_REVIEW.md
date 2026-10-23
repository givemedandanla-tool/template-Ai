# 診斷報告工作包設計與驗收覆核

日期：2026-10-15（Asia/Taipei）。本輪只SELF／Linux／匿名合成；完整結果與GitHub保存收據以FINAL_VERIFICATION／STATE為準。

## 方法與參照

- 參考商用設計工具／Acrobat Preflight的問題清單、可定位原因與離線報告思路；這是交互設計參照，未使用其商用原始碼、沒有宣稱與其相容或具同等印刷驗證。
- 參考開源與標準化問題紀錄的結構化結果／位置／規則碼方式，例如[SARIF概念](https://github.com/oasis-tcs/sarif-spec)。本工具使用自己的封閉schema v1，**不是SARIF實作或相容宣告**；沒有複製第三方專案程式碼或新增依賴。
- 重用原排版量測：固定pt下量得字寬tw、可用寬w，水平比例min(1,w/tw)須不低於模板min_scale，字高不得超框。報告直接保存原驗證器的code與數值，不從中文訊息重新猜測判定。字型不明時量測null，非0；此局部條件不是全域排版可解／無解證明。
- 使用Python標準庫ZIP／JSON／HTML escaping／SHA-256、Qt原有worker與訊號；HTML和JSON由同一安全模型產出，存檔再讀後仍須一致。hash是完整性檢查，不是可信作者簽章。共用safe_publish與作品輸出的同目錄暫存、fsync、硬連結排他發布，無不安全覆寫fallback。

## 最終能力

- 原輸入、候選、模板、訓練品質、已存分類評估與當次背景進度可開相同報告reader。資料處理／模板生成／輸入產出共用格式，每個問題保留發生與影響環節；未檢查明示。
- 人類頁用中文問題、量測、分母、範圍與三環節表，不把JSON當使用者必讀內容；另有同份JSON頁給GPT。ZIP只有report.html／report.json／manifest.json。
- 共享白名單只允許固定code、必要數字、報告內匿名代號。私有定位ID／指紋不進ZIP；來源原稿、字型、自由文案、實際個資、路徑不進ZIP。未知訊息用明示省略的UNCLASSIFIED，不解析文字猜出身份或嚴重度。
- 每次保存前後核對快照依賴，磁碟／取消／撞名失敗不報成功。私有索引7天、可清除，過期／變更／異庫不能誤定位；報告仍可唯讀歷史閱讀，不回填舊PASS。
- 不解壓外部ZIP、不執行供應的HTML；拒絕額外條目、路徑穿越、symlink、非canonical封裝／尾隨資料／ZIP comment／extra、高壓縮與超額。JSON嚴格欄位、固定列舉、有限數字且不可重複鍵；驗證HTML與JSON一致後從可信schema重建畫面。

## 驗收及保留的失敗

原348測試＋29報告測試＋1發布邊界測試＝378。target001保留Qt參數錯誤；target004保留表格迭代順序在JSONroundtrip改變的錯誤。已修而非刪測試或降低校驗標準。target005的29項全PASS。

RUN-DIAGNOSTIC-REPORTS-001全378PASS後，實際畫面審閱發現數值在JSON中不便人閱讀；改善中文表格並重凍來源。002再次378PASS／0SKIP、capture0、source unchanged、78本機附件。001保留歷史，不當新版current證據；002是最終來源證據。每條契約驗收都有具名測試，另有actual Qt保存重開／過期拒絕／來源問題與原Gate不改audit。

## 實際邊界

- 第一版支援本工具固定schema與封裝；未來格式改動須保持舊解碼器或升schema並做遷移測試，不承諾任意第三方ZIP／PDF。
- 無PDF診斷報告、原圖附件、完整個資除錯包或自動雲端／郵件傳送；報告不代替資料備份或正式輸出。
- 缺可靠ID的模板／未分類診斷不任意定位；無來源／無字型仍可保存已取得的缺證據文字報告，但不假裝取得原生語意或量測。
- 2MiB、2000問題等為有界工程預算，不是VivoBook已測效能承諾。完整權限UI048、真AI全面視覺、Windows指定機與實體印刷未藉本包宣稱完成。
- 本輪沒有新增需發布的真實客戶素材／字型或第三方版權素材。新證明PNG/JPG/PDF依既有使用者指令只保留本機及exact source/hash清單，code/tests/文字metadata保存GitHub；不宣稱所有媒體附件Gate通過。
