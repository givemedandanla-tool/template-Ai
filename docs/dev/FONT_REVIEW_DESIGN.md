# 受控字型替代：CORE-032／033／034 完整工作包

2026-10-14（Asia/Taipei）。CORE-031唯讀候選已完成，使用者本輪新增指令：報告下一步後繼續實作一個大功能才停止。接續已核准UI-033，而不是重做候選或停止在影響列表。

## 參考與選擇

商用 [InDesign Find/Replace Font](https://helpx.adobe.com/indesign/desktop/fonts/find-and-replace-fonts.html) 的家族與款式、定位使用欄位及明確替代範圍。開源 [Qt Undo Framework／Command pattern](https://doc.qt.io/qt-6.8/qundo.html)、[QUndoStack原碼](https://github.com/qt/qtbase/blob/6.8/src/gui/util/qundostack.cpp) 的前後狀態、撤銷／重做；自行建立可重開的SQLite歷史，而非只依賴記憶體stack。[SQLite BEGIN IMMEDIATE](https://www.sqlite.org/lang_transaction.html) 保護全批與版次分配，不在巢狀save_template中提前commit。

數學沿用Unicode集合全覆蓋、no-fallback shaping、固定pt毫米與r=min(1,B/W)；增加單行高度≤欄位高度、既有矩形／語意／重疊驗證。CAS同時比較canonical模板摘要與單調edit_revision，避免變更後還原內容的ABA。每模板產生一份新草稿，選中slot集合之外完全不改；批次資料與核准／歷史同一交易。失敗全批回滾。

## CORE-032 影響比較與逐欄人工審核

入口從所選核准ASSET候選進入；Qt未知來源候選仍只讀。列最多200個文字欄位（Logo排除），模板／版本／狀態、物理尺寸、來源作品與版次、owner／kind／slot、框位、原／候選家族款式、原稿身份未知。使用者逐欄輸入臨時驗證文字（不自動將同一姓名填全庫），最多20欄執行背景量測、單輪64 MiB不同資產大小預算，超額明示部分。

逐欄顯示真實前後字寬、高度、水平比例、缺字／健康與原因；原字型不可量測即未知，不能編造差異。目標必須核准本機身份、完全覆蓋且尺寸及幾何合格；目標未知／缺字／越界／無文字等BLOCKED。原字面可驗證且前後同字面身份的複本綁定修正可列LOW，其他替代或原稿未知列HIGH，不因欄位名稱推測已核實。HIGH須逐欄查看差異／實際預覽後明確核准；未核准／未勾選不套用。

## CORE-033 新版本草稿、全批交易及持久Undo／Redo

確認僅限明列選中模板／文字框，顯示新草稿版次、原／目標字型與核驗結果。先背景重新量測，再以短生命週期內部票據交GUI交易；票據不能由回傳可修改report冒造，SQLite只在GUI執行緒。提交核對目標字型登錄／內容、每個基底模板payload及單調clock，鎖內重新分配family版次，保留所有原模板（發布與草稿），不安裝字型、不改AI、不學全域規則。

持久歷史記錄前後草稿完整快照、選中欄位、原／目標pin與style、量測與臨時文字SHA-256（不存原文字），核准範圍與phase。Undo／Redo只作用於本次建立且仍未被後續編輯／發布的草稿；全批CAS＋交易，晚期核准事件失敗也回滾。Undo還原原綁定即使原字型失聯仍標待驗證草稿；Redo重新核對目標bytes／字面及原核驗度量身份，明示沿用歷史樣本驗證，不虛構重新量測已丟棄文字。重開可查歷史及Undo／Redo，任何後續改動包括ABA／發布均拒絕覆蓋。

## CORE-034 款式持久與實際渲染一致

Slot增加可選font_style，舊模板預設空字串相容。受控替代保存實際解析款式，固定pt／框位／color／align／owner／index不改。排版量測與數位渲染使用此style及相同無fallback字面核對，不能候選Oblique、存檔卻默默Book。未核驗的不同檔同家族仍沿用原拒絕Gate，沒有藉此宣告全TTC／variable font支持。

## 完成與證據

端到端GUI入口→文字／影響→背景核驗→逐欄審核→勾選與最終确认→新草稿→歷史→Undo／Redo／重開；具名健康／字形／高度／CAS／ABA／多模板原子性／晚期失敗回滾／款式实际渲染測試及必要回歸全PASS。匿名差異、實際草稿与歷史截圖、JSON／JUnit、精確來源commit/tree永久GitHub保存並逐檔讀回；每包與10分鐘checkpoint。

這是完整受控草稿替代工作包；UI-033父題仍PARTIAL，原生AI定位／效果、全庫完整來源依賴、真人原稿視覺與列印品質、永久映射治理、正式發布／輸出仍需各自Gate。草稿核准不等於原稿一致、嵌入／印刷／正式輸出許可。UI-048最後、EXE與印刷延後。
