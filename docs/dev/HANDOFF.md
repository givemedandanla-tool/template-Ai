# Human／GPT 開發交接

先讀根AGENTS.md與STATE.json，再讀REQUIREMENTS.json／FEATURES.md、最新WORK_LOG及checkpoint收據。這些是即時入口；舊訪談、CSV與FIRST_VERSION_STATUS是歷史來源，不能當完整產品完成度。

## 已確認現況

五點框架完成後，已繼續CORE-023。產品目前v0.1.3，確切測試來源commit為`6a392639ef7ca8e35ff74ced9e203b7847dff664`；RUN-SOURCE-CACHE-001有64項單獨測試全數PASS、零SKIP及19件紀錄／匿名實際附件。23個CORE子範圍與5個GOV為SELF_VERIFIED，75筆父題並未因此全數完成。所有依據在要求登錄，沒有獨立覆核。

最終快照`CP-20261013-SOURCE-CACHE-VERIFIED`已讀回132檔，snapshot commit `19b300cec125149b2adc0e32987d376d2638ab75`。收據及入口指針另行保存，避免自參照commit循環。來源checksum是完整性檢查而非安全簽章。全部文字日誌與匿名二進位附件已納入快照，不只存在本機。

## 下一個工作包

UI-049的受控來源重連子包：核對內容hash，不憑檔名接受；保留原來源登錄、作品及模板版次。原稿變更需記新內容版本並重新審核，不能把舊模板來源偷偷替換。先寫明列驗收／具名測試，建立WIP checkpoint再改碼。其次為字型資產修復；完整批次重連及字重版本仍分包處理。

## 工作規則與限制

零例行問答，使用已有授權自主推進；真缺資料記BLOCKED並轉做其他已核准要求。每個工作包及10分鐘目標保存checkpoint，長包中途先做WIP；本轮26分鐘／14分鐘兩個超時窗口如實記錄，不能宣稱嚴格全程達標或最後未保存操作零風險。

EXE不再自動觸發、不重試，也不是目前完成Gate。印刷分析延後；UI-048仍最後功能，正式真實個資使用前必須完成。UI-058的當次排版候選恢復仍未完成，不能拿作品標記歷史替代。真實AI全面視覺驗收、VivoBook／RTX5050仍待資料與設備。沒有部署24小時常駐編碼服務。

## 中斷恢復與重新驗證

讀STATE.last_confirmed_checkpoint的不可變snapshot commit，檢查pending_remote；本機ZIP可以restore-copy到新目錄，工作區丟失從GitHub確認commit取回。先補未保存的紀錄／證據，再做下一條要求。新源碼或驗收條件改動會讓舊證據失效，不沿用舊PASS。

重現目前測試：在同一來源版本、同一文件字節（Git checkout避免自動換行轉換）執行：

```bash
python tools/run_evidence.py --run-id RUN-NEW-UNIQUE --source-commit 6a392639ef7ca8e35ff74ced9e203b7847dff664 --commit-json docs/evidence/runs/RUN-SOURCE-CACHE-001/commit.json --tree-json docs/evidence/runs/RUN-SOURCE-CACHE-001/tree.json
python tools/dev_governance.py check --require-evidence
```

新的run仍需保存全部附件並做GitHub讀回後才能當永久證據，run ID不可重用。根AGENTS提供完整命令與流程。
