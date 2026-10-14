# Human／GPT 開發交接

開始先讀AGENTS.md、STATE.json、REQUIREMENTS.json／FEATURES.md、PROGRESS.md／CURRENT_PROGRESS.json、WORK_LOG最新紀錄與checkpoint收據，再讀DEVELOPMENT_PROTOCOL.md。每輪基準／結束差異與完成／未完成數量必須持久化並回報；零例行問答，checkpoint後繼續工作，不重試EXE。

## 最新完整工作包

v0.1.9，精確來源`ecb863bf3ee62277318e31792517945ed6674ccd`；RUN-FONT-REVIEW-001：168 PASS／0 SKIP、31件匿名附件、43個acceptance全PASS。使用者要求接續下一步並實作一個大功能後才停止；本輪將CORE-032影響／逐欄審核、CORE-033新草稿交易與持久Undo／Redo、CORE-034款式渲染一致整合為完整端到端工作包，沒有重做已完成CORE-031或停在小列表。

功能鏈：核准ASSET候選→影響範圍→逐欄臨時文字→背景字形／固定pt寬高→HIGH詳審實際字形→主動勾選→範圍確認→新版本草稿→歷史→Undo／Redo／重開。原模板（草稿及發布）保留，Logo及未選slot、字级／框位／owner／index／color／align不改；Qt來源未知只讀，沒有系統安裝、AI修改或永久全域映射。本工作包完成不代表全UI-033／原稿外觀／正式輸出或嵌入權利合格。

最終31件附件與完成統計需要完整REMOTE_VERIFIED checkpoint；完成保存狀態及快照SHA以STATE.goal_milestone／last_confirmed_checkpoint與不可變收據為準。程式測試PASS不冒稱遠端持久化已完成。

## 功能統計

115列＝75父題＋34 CORE＋6 GOV。CORE31→34完成3，治理6不變；父題完整0／部分43／未實作27／受阻2／延後3，75仍有未滿足条件。UI-033從未實作到部分，新增3／刪除0／既有驗收scope改動0。進度基準／結束見PROGRESS-20261014-FONT-REVIEW-BEGIN／END.json；不混算父題、子項或治理成產品百分比。

## 實作與邊界

FontReviewEngine普通資料／內部核驗cache與120秒one-use票據；回傳report不能偽造after或eligible，HIGH必須逐欄明確核准。原字寬未知保留未知；LOW只有已核驗同字面複本綁定修正，完全同綁定不建無效草稿。單轮最多200展示文字框、20量測欄、64 MiB不同資產大小，PARTIAL明示；不是全庫／全磁碟／硬性牆鐘或實測記憶體保證。

Library新增template_edit_clocks／font_changes；舊資料初始化clock0。每次實際save／publish增加clock，完全相同save為noop；canonical payload hash＋單調clock CAS擋ABA。SQLite BEGIN IMMEDIATE鎖內按family分配版次，全批新草稿／歷史／核准event同交易；晚期event失敗全rollback。新草稿font binding變更外所有fields維持。GUI拒絕未保存主編輯，交易後重載新草稿，不能讓舊memory autosave覆蓋Undo。

持久歷史保存前後草稿與本批slot、來源／目標pin、核驗度量、文字SHA-256及缺字數，不存臨時文字或缺字字元集合。Undo／Redo只作用仍未改／未發布的本批草稿，任何後續變更（含ABA）全批拒絕。Undo可回到原缺失pin，仍是待驗證草稿；Redo重新檢查目標bytes與字面，明示沿用歷史樣本核驗而非重測已捨棄文字；正式人物排版／輸出需再驗證。歷史序列／review events在本機DB，合成audit證據可讀，真實DB不進GitHub。

Slot.font_style預設空字串相容舊模板，受控替代保存實際款式。真實NimbusSans-Italic揭露Qt setStyleName不會保證italic／weight完整，改QFontDatabase.font取得完整style屬性，保留raw table／no-fallback Gate。主編輯combo foundry別名需維持已選slot原pin／family／style，不以顯示別名重建資產；幾何／色彩變更不重設款式。CORE-034已驗真實Italic排版／PNG／PDF，非完整TTC／同名多檔版本／variable font治理。

所有背景完成／失敗均回GUI，stale輸入清除勾選、核准、圖像、詳細數值及風險字樣，可重試。程式化GUI核准是合成驗收，不替代真實原稿的人類核對。Linux自我驗證，不是獨立審查或Windows／指定硬體實測。

## 故障與證據

保留CORE-034 missing-test-fixture、available-style-fixture（實際字面不符）、after-style-resolution-fix，以及before／after-editor-pin-fix日志。不刪失敗測試、不改原樣本避開問題、不放寬fingerprint。正式驗證首度metadata指向收據而來源SHA指向程式，guard於測試前拒絕；凍結獨立source commit/tree後正式run成功，原拒絕日志保留CORE-033。31件附件包括差異、逐欄預覽、草稿歷史、Undo GUI及匿名audit，來源原字型／私有AI／DB／密鑰不公開。

## 下一個工作包

UI-033來源／模板畫布与逐欄before-after定位對照：先讀原決策與FONT_REVIEW_DESIGN.md、source artwork／background資產及現有preview。用合成合法樣本設計具名验收、基準与BEGIN；已知來源位置才定位，原生可編輯性／特殊效果／原稿字面缺失則未知，不能只因字寬合格宣告視覺一致。先可核對的來源＋模板圖像／框位與人工審核，不建立未核准全域映射。

完整Windows來源／全TTC／不同檔同家族版本、來源外部依賴、真實AI視覺、獨立品質及指定硬體仍未全面完成。印刷／EXE延後，UI-048維持最後功能且在真實個資使用前完成。

## Checkpoint與遠端

工作分支dev/v0.1-first-version／PR #2，main未合併。BEGIN7870a47c、ENGINE021968bd、GUI0237e3ef、STYLE-FIXED448d428b、IMPLEMENTEDecb863bf均REMOTE_VERIFIED；最終證據收據見STATE。每包与10分鐘保存，pending_remote先恢復，receipt／STATE另小提交避免SHA自參照。來源／驗收改動使當前證據失效，歷史保留；不承諾最后未保存操作零損失。

PR metadata工具先前長時間不回並被中止；不反覆重試，審查說明存PR_REVIEW.md，不宣稱頁面標題已同步。使用已可用git tree／commit／ref lease API與逐檔讀回。source metadata固定獨立檔，不將收據提交覆寫同一tmp路徑後再當程式來源讀。
