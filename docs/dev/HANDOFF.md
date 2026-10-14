# Human／GPT 開發交接

先讀 AGENTS.md → STATE.json → REQUIREMENTS.json／FEATURES.md → PROGRESS.md／CURRENT_PROGRESS.json → WORK_LOG最新紀錄／checkpoint收據 → DEVELOPMENT_PROTOCOL.md。每輪保存基準、要求差異、完成與未完成數量；零例行問答、checkpoint優先，不重試EXE打包。

## 最新版本與完整里程碑

v0.1.8；來源 `17ce93d86c68df281c1d4868e6a65ba389215704`，正式 RUN-FONT-CANDIDATES-001：145 PASS／0 SKIP、26件實際匿名附件。23項候選focused驗收，含真實Qt worker、背景失敗重試、輸入過期、字面／檔案異動、有效比較寬度與有界PNG。4個CORE-031 acceptance逐項PASS；另36個已有CORE／GOV要求以同一精確來源重新驗證。自我驗證Linux／環境字型，不是獨立審查、Windows或真實AI全驗收。

本輪使用者 /goal 的「候選篩選、排名、唯讀預覽」契約已實作並通過測試；宣告最終完成前需將26件附件完整checkpoint逐檔讀回。最終保存狀態以STATE.goal_milestone、last_confirmed_checkpoint及REMOTE_VERIFIED收據為準，不以本段測試PASS代替遠端保存。

112列＝75原父题＋31 CORE＋6 GOV。功能子項30→31（新增CORE-031完成1），治理6不變。父題完整0／部分42／未實作28／受阻2／延後3，75仍有未完成條件。新增1／刪除0／既有驗收範圍修訂0；部分題與子項不混算產品完成率。基準／結束見PROGRESS-20261014-FONT-CANDIDATES-BEGIN／END.json。

## CORE-031實作及限制

FontCenterDialog所有模式共用中心提供入口，候選對話框沿用文字、固定pt、框寬、最低水平比例。比較中心所選字面需明確勾選，預設不勾、不選候選。字形／健康／檔案身份／no-fallback shaping及水平適配硬篩；不通過項目列原因。來源核實級別、已知比較字寬相對差、壓縮程度、穩定id／style依序排序；未知原稿與外觀一致不造分數。參考寬度measurement_verified只有hash與字面核對後成立；框寬不足可以顯示有效自然字寬，內容異動／缺字則未知。

每輪最多64字面、64 MiB資產大小、10展示候選，超額及來源快照部分明示PARTIAL；觀看預覽後仍保留未量測／未展示數量。單輪相同identity／style去重及量測快取，不跨輪沿用。此預算是檔案大小，不是全部hash I/O、牆鐘或完整記憶體硬上限；Qt資料庫來源無法核實者標未知。

明確選取後重新核對字型／输入／width／face fingerprint；glyph-run一致才生成PNG，Qt物件留worker、只回bytes/dict；GUI stale結果不發布，失敗恢復控制可重試。圖片最大1724×424px，整框觀看倍率不改物理pt、文字或水平比例。不改模板、發布font pin、原稿、字型登錄或系統安裝，沒有套用／正式輸出動作。預覽僅單行排字寬度，非完整ink bounds／模板品質／原稿視覺一致或嵌入授權。

正式附件包含候選排名／預覽真實GUI截圖、font-candidate-line.png及可讀font-candidates-report.json；原字型bytes／私有來源／本機DB不進GitHub。數學、InDesign、Fontconfig歷史原碼FcSortCompare／FcSortWalk与Qt參考見FONT_CANDIDATES_DESIGN.md。沒複製第三方代碼或新增依賴。

## 下一個工作包

先讀UI-033原決策、候選契約、既有模板版次／Undo與發布保護；拆明確下一CORE驗收，保存新基準與BEGIN。建議先完成單欄影響／差異與人工審核，再設計受控草稿套用、CAS、防過期及可驗證Undo，不直接全庫批次替換。候選預覽完成不授權自動套用、Windows安裝、原稿修改、學習全域映射或改Logo。

完整UI-032的Windows來源、TTC多字面、不同文件同名字型版本共存、字重、嵌入權利仍待；不能只刪現有same-family拒絕判斷。UI-049多根／完整外部依賴，真實AI／指定硬體／獨立覆核仍未全做。印刷与EXE延後，UI-048維持最後功能、真實個資使用前須完成。

## 恢復與GitHub

工作分支dev/v0.1-first-version／PR #2，main未合併。本輪BEGIN 8ce4461d、WIP a60a6c89、IMPLEMENTED 17ce93d8均已REMOTE_VERIFIED；最終完整證據收據見STATE指向。每包／10分鐘保存，pending_remote先補確認，不累積未保存碼；程式或驗收更改使當前證據失效，歷史保留。最終收據与STATE再小提交以免SHA自參照。

先前PR metadata工具多次長時間未返回並被中止；本輪不重試，同步說明在PR_REVIEW.md，PR頁面標題仍待同步，不宣稱已更新。資料持久化用已可用git tree／commit／ref lease API；GitHub讀回逐檔match後才確認，不能拿本機ZIP或hash冒充遠端成功。前版本完整工作紀錄、CORE-030真實背景交接故障及歷史checkpoint超時窗口繼續保留，不宣稱斷電零損失。
