# 持久工作紀錄

每條紀錄應含要求 ID、動作／結果、測試、確切 checkpoint／commit、限制與下一步。最新資料置頂；資料可供 Human 與 GPT 覆核。歷史版本不是即時完成度。

## 2026-10-13：v0.1.3／CORE-023 完成具名範圍

- 程式來源 commit `6a392639ef7ca8e35ff74ced9e203b7847dff664`。RUN-SOURCE-CACHE-001：64 tests全數PASS、零SKIP，19件紀錄／匿名實際附件。
- 23 CORE加5 GOV按各自的明列範圍SELF_VERIFIED；75原題仍不是全數完成。來源快取完整性不等於完整批次來源重連，metadata checksum不是安全簽章。
- 版本化快取加入圖片／SVG內容hash、metadata checksum、同來源／同頁及固定路徑檢查，損壞時重新轉換；拒絕符號連結，轉換失敗不回退為成功，原檔保持只讀。
- 產品工作包BEGIN到IMPLEMENTED收據約14分鐘，也超過10分鐘目標；已保留實際時刻，不將保存頻率冒稱嚴格達標。下一輪應在長工作包中途先做WIP checkpoint。
- 全部.log及二進位合成附件納入最終checkpoint並逐檔讀回；新增遠端附件完整Gate。最終snapshot commit `19b300cec125149b2adc0e32987d376d2638ab75`確認132檔，入口與收據另提交保存。
- 下一步：UI-049的受控來源重連子包（內容hash驗證、變更拒絕、原登錄保留），其次字型資產修復。EXE／印刷／指定設備與未決產品報告不提前做。

## 2026-10-13：CORE-023 開始（先保存再改碼）

- 五點框架 READY 與收據已永久保存；確認提交 `bc5448f2a4c44c1a503b5ad59d21caf61dad33e8`。
- 下一要求 CORE-023：衍生快取內容、頁碼與 metadata 驗證；異動／損壞時不重用並重建，原始來源保持只讀。
- 故障測試先重現 3 個FAIL與1個ERROR；修正後6個快取測試通過，包括符號連結不改原檔，原始紅／綠紀錄保存於docs/evidence/regressions/CORE-023。
- 發現框架的副檔名白名單漏了.log，初始遠端快照沒有全部文字日誌；本包補.log並增加require-evidence的遠端附件包含檢查，避免只在本機看得到卻宣稱已保存。
- 舊 run 保留可查，但新來源版本開發時先取消當前 completed，重新驗證前不沿用舊 PASS。FRAMEWORK READY 歷史收據仍有效，产品新版本完成另產證據。
- 先做 SOURCE-CACHE-BEGIN checkpoint，完成修改／測試後再做可恢復 checkpoint 與RUN-SOURCE-CACHE-001。

## 2026-10-13：五點框架 READY，遠端快照已確認

- GOV-001～005：框架已實作，源碼 commit `f5da9c41e432e0b7b3927ae9b51c5e94645406b3`；RUN-FRAMEWORK-001 的 58 項具名測試全部 PASS，19 個紀錄／匿名附件。
- 原有 22 CORE 與 5 GOV 以明列範圍 SELF_VERIFIED；75 父主題未被自動標完整完成，CORE-023 尚未實作。所有狀態見機器登錄。
- 已停用 EXE 的 push／PR 觸發；只保留手動日後交付。本輪不等待或重跑 EXE。
- 起始、框架實作、自動狀態共三個 checkpoint 已讀回；prepare 自動加入 pending，acknowledge 自動更新入口指針。
- 首輪建置工具期間起始收據至實作收據約 26 分鐘，未達新訂的 10 分鐘節奏；已記錄此差距，後續以短工作包與自動 pending／入口更新控制保存，不宣稱歷史每次都已達標。
- READY快照 commit `38374fd23b21fedcc7d2df15cf8ae34cd94f3718` 已讀回101檔（含匿名實際附件）；收據與入口指針另行保存。下一步為 CORE-023：來源快取 hash、損壞 metadata、只讀重新轉換及故障驗收。

## 2026-10-13：治理框架建置中

- 來源：使用者的六點指令，原文見 `docs/decisions/2026-10-13-CHECKPOINT-EVIDENCE-POLICY.md`。
- 要求：GOV-001～005。先做框架，再做产品 CORE-023；EXE 改為只保留人工 dispatch，不重新嘗試。
- 已確認起始 checkpoint：`CP-20261013-FRAMEWORK-START`，GitHub commit `02af3a8d556830a0e699dd80e6dbb3535a984c28`，62 檔讀回一致；本機 ZIP 為額外恢復點。
- 已新增 AGENTS／Copilot 入口、STATE、交接、要求登錄、證據研究、快照與一致性工具；保留 75 原題與 23 CORE／5 GOV。
- 尚待：治理測試、框架提交及新版證據 run；此時不把框架或原有 CORE 標完成。
- 修正歷史索引：UI-058 是當次排版候選恢復，已完成的作品標記歷史屬 UI-038 子集，不能混稱。
- 下一步：執行治理自測→checkpoint→GitHub 讀回→以確切 commit 產生證據→READY checkpoint，再開始 CORE-023。
