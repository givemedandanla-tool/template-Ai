# Human／GPT 開發交接

## 最新整包：v0.1.11 CORE-037／038／039

先依AGENTS／STATE／要求／最新證據／PROGRESS／WORK_LOG／協議恢復，長期全清單目標仍存PROJECT_GOAL／ROADMAP；不重試EXE，不啟用agent，不要求例行重說繼續。

source `2f2d32bf313616414b86bf866faef73dac884a3f`；RUN-OBJECT-TOOLS-001：194PASS／0SKIP、44附件、48acceptance全PASS，source前後不變。整個OBJECT_TOOLS_DESIGN具體契約已驗；最後snapshot／收據待GitHub讀回前不先宣稱REMOTE_VERIFIED。

完成功能鏈：來源／模板入口→same advanced editor→真click/Ctrl／RubberBand／list／properties stable-ID集合→mixed dirty patch／lock→明確reference六方向／兩軸gap／group mm delta或drag→old/new與green候選→cancel或明確scope確認→鎖內重算／原子保存→persistent history／重開UndoRedo。Property schema／lock root沿用Slot boolean defaultFalse兼容舊data；普通原編輯、save／source、publish及font新草稿亦守lock。原稿／发布不可覆寫，Logo不轉一般文字或不等比，geometry只改selected x/y，font／pt／未選不變。

object_tools.py純mm／stable排序／dirty request，負gap／bounds／font與語意問題保持warning；未提供人物資料的字形/readability仍另排版。最多200工具物件／50歷史展示，不以隱藏減少Gate。ObjectToolsDialog候選不改DB，樹／原生文字字距未知如實標，所有變動明列及trueQTest。Source幾何取消visual確認；historical explicitUndo能還原舊flag但仍不是機器證實原稿一致。

Library.object_edits保留before/after、request／scope／warnings／clock及phase；BEGIN IMMEDIATE內用實際DB重算，不信任caller after，source newrevision／template clock／audit同交易，late event失敗整包rollback。UndoRedo先exacthash＋monotonicclock CAS，後續更改／發布／ABA拒絕；lock历史是獨立明確範圍，非自動解鎖。Source revision也提供保護。MainWindow loaded revision/hash／payload守傳統save/undo/newVersion/publish；保存失敗保留手工內容。Child返回確認期間主手工或properties變化也拒絕覆蓋，重新載入可針對外部新saved base再preview/retry。

故障：第一legacy ABA fixture先Save清空UndoStack，不能表示真正風險；原FAIL保留，補保存後再手工改x10的fixture，REAL-ABA-RED真正顯示Undo誤退x9。修正版本防護後PASS，沒有刪failure測試／降低期望。首次UI長文字擠壓，scroll panel／readOnly可捲summary與show-fit修正，永久screens是真生成。元件clock與回歸194PASS不代表Windows／原生AI／hardware或獨立覆核。

功能120列＝75父題＋39CORE＋6GOV；CORE36→39新增并完成3，父題0完整／44部分／26未實作／2受阻／3延後，75仍未完整完成；UI036僅从NOT_IMPLEMENTED→PARTIAL。不以已登记CORE39全verified當產品清單已完整拆分或產品100%。本輪BEGIN117列／END120列不可變差異，GOV6。

下一大包UI035 semantic索引／共用實體搜尋／檢視隔離：先讀原條款與source可驗性，baseline／具體契約／BEGIN再code，native層未知不猜或用衍生SVG冒稱原生AI。共享公司和Logo以同一stable底層實體引用，hide不減少驗證；完整父題未滿前仍partial。UI048最後，print／EXE／future UI056D不提前；外部真實AI與可信參考、指定hardware、Windows、獨立品質及UI066兩未決項依原狀態，先做不依賴它的工作。


先依AGENTS→STATE→本文件→PROJECT_GOAL／PROJECT_ROADMAP→REQUIREMENTS／FEATURES／PROGRESS→最新WORK_LOG／證據／收據→DEVELOPMENT_PROTOCOL恢復。全75父题長期目標持續，不要求重說繼續，不使用代理或重打EXE。

## 歷史v0.1.10完整大功能 CORE-035／036

精確來源`36307d58ed8f10e6549ba3580a20541244b036db`／tree`305cbd40fe75d940f46274ca8190ddda5fe52cd5`，RUN-CANVAS-COMPARE-002：177 PASS／0 SKIP、37附件、45acceptance全部PASS，source前後不變。正式來源metadata凍結獨立檔，收據提交不覆寫。最後完整snapshot `fb3f6c31d14c88018cd83ca059e69a6fb961ccaf`／tree`98d364b9fb2785acdccbcda7faee18128e163d0c`，550檔包含37附件逐一Git blob SHA讀回；require-evidence PASS。新增6個REMOTE_VERIFIED checkpoint、累計43；本完整大工作包已完成，收據／入口指針另小提交保存。

功能鏈：核准候選→模板逐欄差異→所選欄臨時文字→背景產生原稿衍生參考／原模板／替代矩形→共用zoom／pan／fit／stable slot_id列表與框選定位→返回後背景再驗→明確人工核准後再驗→主動勾選→套用前驗來源／檔案／clock→新草稿與歷史。模板、原始檔、font pin及DB在只讀對照前後不改。三視圖另一欄文字未提供就只畫空框，Logo未提供不借別資產；原字型未知不fallback。

Library.comparison_source只在GUI取source_work_id／revision精確歷史crop／physical dimensions；普通資料傳worker。源原始文件SHA／導出image與SVG／metadata_checksum核對，missing UNKNOWN；修改／損壞BLOCKED。三視圖共用模板mm domain，source pixmap仿射回此domain，可逆crop→page→pixel；未物理標定明示參考單位。來源點陣只證衍生身份，不證原生字型／視覺一致。QFont glyph／face Gate與款式固定pt／align／color沿用既有可信渲染。

每template圖6MP／源12MP解碼、单file50MiB／總64MiB／最多200框；不是硬性牆鐘或硬體實測保證。比較只渲染所選欄提供文字，其他全空框；不自稱完整正式人物排版。high-review資料與模板fingerprint／clock、来源context保存私有暫時proof；顯示返回／核准提示後／套用前都重驗，最新模板和來源登錄在GUI重查。start可串接真實背景階段但只在無下一階段時恢復controls；modal閉合deleteLater釋放圖像。

## 故障與覆核界限

001原176PASS／37附件完整保留，但後續發現NoAnchor在resize後實際中心漂移（要求43,11.5→約29.6,35.94），因此取消当前完成、保存RED。ResizeEvent重套共享center／zoom，177th具名測試對多種視窗大小核對實際mapToScene中心，而不是只比內部state；新002全部PASS。首個SyntaxError及非法IMPLEMENTED狀態拒絕、baseline ID路徑拒絕均如實記WORK_LOG，沒有改治理工具降低標準。

RED上傳完後GitHub create_tree catalog change拒絕；保持pending，一次重新載入後重試成功adc28fd4／506檔讀回，沒有force。IMPLEMENTED05:46:18→RED06:55:45確認約69分27秒，遠超10分鐘目標，如實保留；原碼原有遠端commit與本機PREPARED尚在。FIXED→VERIFIED也相隔664.35秒（11分4.35秒，超目標64.35秒），其餘本輪間隔低於10分鐘；不能宣稱本輪頻率嚴格達標。後续每GitHub操作60秒有界等待；超時先讀ref核對存下created commit，不能無限重試／假造確認。blob上傳最多4件一批／60k字元片段；tree／commit／lease ref／逐檔readback順序。SELF_VERIFIED Linux／匿名合成不等於獨立品質、真實AI／Windows／指定硬體。

## 計數與下一個大工作包

117列＝75父題＋36CORE＋6GOV；CORE34→36完成2，新增2／刪除0／既有scope改動0。父題完整0／部分43／未實作27／受阻2／延後3，75仍有缺口；GOV6。baseline BEGIN／正式001當刻END／最後FINAL均immutable，不混算父題與子項成產品百分比。

全清單範圍／順序已保存PROJECT_GOAL／PROJECT_ROADMAP。已讀原UI034／035／036條款並開始下一包分析，具體scope／算式／驗收方向保存OBJECT_TOOLS_NEXT_PLAN.md；這是PLANNED，不冒充下一包已實作。下一包UI034／036：先讀original UI_DECISIONS（三向同一集合與混合值、明確基準及差異預覽／對齊不改字級Logo比例），寫具体完整大包契約、進度基準與BEGIN，再實作 stable-ID 多選／鎖定與安全共同／混合屬性、精確對齊等距與同owner或explicit範圍、原子可撤回差異預覽，背景結果不得覆蓋手工編輯。原題全部條款完成之前仍PARTIAL。

外部真實合法AI／可靠參考、Windows／全TTC同名多檔字重、指定hardware／獨立覆核仍有缺口。UI066報告兩未決項BLOCKED；先做其他已授權功能。UI048完整權限維持最後且真實個資前完成；印刷與UI056-D按既有延後，EXE不重試。工作branch dev/v0.1-first-version／PR2，main不合併；PR頁面metadata未同步，PR_REVIEW保存可複用說明。

## 歷史v0.1.9完整工作包

v0.1.9，精確來源`ecb863bf3ee62277318e31792517945ed6674ccd`；RUN-FONT-REVIEW-001：168 PASS／0 SKIP、31件匿名附件、43個acceptance全PASS。使用者要求接續下一步並實作一個大功能後才停止；本輪將CORE-032影響／逐欄審核、CORE-033新草稿交易與持久Undo／Redo、CORE-034款式渲染一致整合為完整端到端工作包，沒有重做已完成CORE-031或停在小列表。

功能鏈：核准ASSET候選→影響範圍→逐欄臨時文字→背景字形／固定pt寬高→HIGH詳審實際字形→主動勾選→範圍確認→新版本草稿→歷史→Undo／Redo／重開。原模板（草稿及發布）保留，Logo及未選slot、字级／框位／owner／index／color／align不改；Qt來源未知只讀，沒有系統安裝、AI修改或永久全域映射。本工作包完成不代表全UI-033／原稿外觀／正式輸出或嵌入權利合格。

最終完整snapshot `bcef39a942912272ab32aae2348efa6b976577dc`／tree `84f56e0ae354d5d6d5ee3e43157875a644ba8854`已逐檔讀回446檔，包含31件附件、功能基準／差異及Human／GPT交接。最終收據／STATE另小提交讀回；本輪新增6個REMOTE_VERIFIED checkpoint，累計37個。本輪目標已完整完成。最後兩次遠端確認相隔652.7秒（約10分53秒），超過10分鐘目標約53秒；完整本機PREPARED快照先完成於2026-10-14T04:58:22.514134+00:00，程式已在IMPLEMENTED遠端保存。附件上傳／tree讀回延遲如實保留，不宣稱所有確認間隔達標；後續以較早凍結附件及有界批次上傳縮短窗口。

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
