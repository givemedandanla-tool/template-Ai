# Human／GPT 開發交接

先讀 AGENTS.md → STATE.json → REQUIREMENTS.json／FEATURES.md → WORK_LOG 及 checkpoint 收據 → DEVELOPMENT_PROTOCOL.md。

CORE-025 正在開發，先取消舊當前證據判定；歷史 RUN-SOURCE-RELINK-001 保留。先完成字型修復具名驗收及重新驗證，再恢復完成標記。

上一個已驗證版本 v0.1.4，CORE-024 已實作單件來源重連：背景唯讀 SHA-256、原登錄不變、位置及历史交易保存、過期 revision 與正常檔案異動拒絕、GUI 入口與重開。測試來源 commit `285a9e14cf063dc71b04ebc28d4af35efa499bb1`，RUN-SOURCE-RELINK-001 有 71 PASS／0 SKIP、19 件附件。24 CORE／5 GOV 只按明列範圍自我驗證；75 父题未全部完成。

下一工作包：UI-032 的字型資產修復，從相同內容且已授權字型恢复本機複本，保留已發布模板 pin；完整字重／版本管理另包。UI-049 批次掃描仍待處理，來源修改不得用重連替換舊內容。

只在已確認分支 PR #2 工作，不合併 main；EXE、實體印刷延後，UI-048 最後功能／真實個資使用前完成。真實 AI 視覺與指定設備待資料。沒有 24 小時常駐服務；使用者授權必要操作，不反覆問已決事項。

每 10 分鐘及工作包保存 checkpoint；GitHub commit/tree 逐檔核對後才 REMOTE_VERIFIED，收據與 STATE 另提交避免循環。下一步修改程式先保存 WIP 并使舊當前證據失效；歷史 run 保留。恢復先檢查 pending_remote，補保存後再編碼。
