# 持久工作紀錄

每條紀錄應含要求 ID、動作／結果、測試、確切 checkpoint／commit、限制與下一步。最新資料置頂；資料可供 Human 與 GPT 覆核。歷史版本不是即時完成度。

## 2026-10-13：治理框架建置中

- 來源：使用者的六點指令，原文見 `docs/decisions/2026-10-13-CHECKPOINT-EVIDENCE-POLICY.md`。
- 要求：GOV-001～005。先做框架，再做产品 CORE-023；EXE 改為只保留人工 dispatch，不重新嘗試。
- 已確認起始 checkpoint：`CP-20261013-FRAMEWORK-START`，GitHub commit `02af3a8d556830a0e699dd80e6dbb3535a984c28`，62 檔讀回一致；本機 ZIP 為額外恢復點。
- 已新增 AGENTS／Copilot 入口、STATE、交接、要求登錄、證據研究、快照與一致性工具；保留 75 原題與 23 CORE／5 GOV。
- 尚待：治理測試、框架提交及新版證據 run；此時不把框架或原有 CORE 標完成。
- 修正歷史索引：UI-058 是當次排版候選恢復，已完成的作品標記歷史屬 UI-038 子集，不能混稱。
- 下一步：執行治理自測→checkpoint→GitHub 讀回→以確切 commit 產生證據→READY checkpoint，再開始 CORE-023。
