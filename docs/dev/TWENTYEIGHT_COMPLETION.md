# 28原父功能軟體驗收完成

本輪新增父題0、刪除0、修訂完整驗收28、完成28。原20工作保留並擴為28；沒有用測試數或拆子項取代父題。

正式來源 `81f73e03449bbe2abb79251d2ec8919662b5ab2c`；[RUN-TWENTYEIGHT-FULL-002](../evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json)：601/601 PASS、0跳過、0未處理Qt回呼錯誤、239條具名驗收全部PASS、實際Qt／數位檔擷取0、來源未改。

累計原75：44 SELF_VERIFIED／28 PARTIAL／3 DEFERRED；固定70：42完成／28剩餘。CORE87、GOV7另計。

本批完成來源多頁預檢與可恢復自動管線、例外隔離／排序／標記校正／規則治理、三向安全編輯與版本、固定字級字距及墨跡量測、即時輸入風險、合格候選分區、有界Cassowary特製草稿、預覽格式與逐檔安全輸出／恢復／精確重試。

工程重用：Qt／Inkscape／SQLite／libphonenumber／既有TrainingStore與渲染／Kiwi Cassowary；數學、開源版本及Figma／Adobe公開介面參照與hash見[TWENTYEIGHT_ENGINEERING_BASIS.json](TWENTYEIGHT_ENGINEERING_BASIS.json)。未啟用付費模型API或自動EXE工作流程。

第一輪598單測PASS仍因Qt回呼讀表時schema未初始化而整體FAIL；紀錄完整保留。修復並新增回歸後才採用第二輪；未刪除或跳過失敗驗收。

本批為Linux合成／實際Qt與數位檔自我驗證；不宣稱Windows、私人AI全面、原生未知細節、外部磁碟崩潰耐久、實體印刷或獨立覆核完成。95件媒體依既定metadata-first例外留本機，27件文字metadata與全部程式／測試／交接保存GitHub；最終遠端確認以STATE及checkpoint讀回收據為準。

|原父題|名稱|完整原條款數|結果|
|---|---|---|---|
|UI-003|訓練區批次匯入與啟動|7|SELF_VERIFIED|
|UI-004|訓練例外處理|7|SELF_VERIFIED|
|UI-005|例外中心智慧待辦排序|6|SELF_VERIFIED|
|UI-007|修正套用與 AI 學習確認|8|SELF_VERIFIED|
|UI-008|待審核規則中心|7|SELF_VERIFIED|
|UI-038|多作品總覽、智慧辨識框與作品上直接標記／修正|12|SELF_VERIFIED|
|UI-039|AI 智慧資料辨識框的畫布快捷標記與人工校正|10|SELF_VERIFIED|
|UI-040|智慧標記完整性衝突檢查與可重用雜訊剔除規則|13|SELF_VERIFIED|
|UI-041|雜訊規則庫、命中追溯、例外白名單與安全回滾|10|SELF_VERIFIED|
|UI-042|訓練可恢復進度、精確去重與客戶資料庫重訂關聯|11|SELF_VERIFIED|
|UI-001|三模式主視窗|5|SELF_VERIFIED|
|UI-002|模式切換狀態|6|SELF_VERIFIED|
|UI-006|例外修正工作台|7|SELF_VERIFIED|
|UI-010|模板版本編輯機制|8|SELF_VERIFIED|
|UI-011|模板編輯器物件操作|7|SELF_VERIFIED|
|UI-012|物件移動縮放與智慧對齊|8|SELF_VERIFIED|
|UI-033|字型替代影響範圍與風險分級批次審核|10|SELF_VERIFIED|
|UI-034|畫布、物件清單與屬性面板同步安全編輯|10|SELF_VERIFIED|
|UI-035|語意樹、Illustrator 圖層與搜尋／鎖定管理介面|9|SELF_VERIFIED|
|UI-036|多物件精確對齊、等距分布與群組位移|10|SELF_VERIFIED|
|UI-013|文字框智慧編輯介面|9|SELF_VERIFIED|
|UI-014|文字框無解診斷與輸入密度分級提醒|7|SELF_VERIFIED|
|UI-015|使用者資料輸入警告介面|8|SELF_VERIFIED|
|UI-018|自動排版結果與候選模板呈現|9|SELF_VERIFIED|
|UI-028|黑底白字占位預覽檔格式與非正式標示|9|SELF_VERIFIED|
|UI-029|批次輸出清單、智慧命名與安全儲存|9|SELF_VERIFIED|
|UI-030|批次輸出失敗診斷與安全重試|8|SELF_VERIFIED|
|UI-037|畫布縮放、平移、快速定位與同步對照檢視|9|SELF_VERIFIED|

下一包：UI-031原條款／缺口對帳並凍結新驗收後開發。核心入口與精簡交接見[ACTIVE_DEVELOPMENT_HANDOFF](ACTIVE_DEVELOPMENT_HANDOFF.md)；不需要原聊天。
