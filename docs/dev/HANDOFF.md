# Human／GPT 開發交接

先讀 AGENTS.md → STATE.json → REQUIREMENTS.json／FEATURES.md → WORK_LOG 及 checkpoint 收據 → DEVELOPMENT_PROTOCOL.md。

## 已確認現況

目前 v0.1.5，測試來源 commit `dc76b95fa5ff288d09d4474be2732191b3caa78c`；RUN-FONT-REPAIR-002 有 83 PASS／0 SKIP、19 件實際附件及紀錄。105 筆要求含 75 父题、25 CORE、5 GOV。30 子範圍 SELF_VERIFIED，父题未全部完成，沒有獨立覆核。第一輪 82 PASS run 及重連 71 PASS run 保留歷史，不當最新版證據。

CORE-024 單件來源重連：背景唯讀 SHA-256、原登錄不變、位置及历史交易、過期 revision 與正常檔案異動拒絕、GUI 入口與重開。CORE-025 字型同內容修復：核准 hash、Qt 解析、損壞隔離、模板 pin 不變、正常例外檔案回滾、PREPARED 意圖及啟動核對。回復檔案亦失敗時釋放 SQLite 鎖，重開驗實際內容，不能冒稱跨儲存原子交易或 Windows 鎖檔已驗證。字型及 SQLite 只留本機。

## 下一個工作包

UI-049 受控批次定位子包，先讀 UI_DECISIONS.md 的 UI-049 全文（780 行開始），拆 CORE-026 验收：使用者指定範圍與有限資源掃描；依內容長度預篩、候選 SHA-256 分組，時間 O(候選總 bytes)、每個內容只算一次；同名不同內容、候選歧義、無權讀取、掃描未完成分別報告，不能稱全盤找齊。建立「原來源→候選→影響作品／模板」預覽，使用者明列勾選；CAS 批次交易及可復原新位置歷史，原登錄與舊模板不替換。未知客戶編號顯示未知，不猜測。先寫具名測試、保存 BEGIN 再改碼。批次掃描不能阻塞 GUI，不自動遍歷整部磁碟。

其次處理完整字型字重／版本：目前不同檔同家族會拒絕，不能簡單取消此防護。需要 style 身份、同家族載入歧義及模板 pin 的明確驗收。未完成來源内容替換／跨設備字型搬移不要冒稱 UI-049／UI-032 全滿足。

## 工作規則

使用已授權必要操作，零例行問答；沒有 24 小時常駐服務。只在 PR #2 工作，不合併 main；EXE、實體印刷延後。UI-048 為最後軟體功能，真實個資使用前完成。真實 AI 視覺／指定硬體仍 BLOCKED，先做不依賴樣本的核心。

每個包及每 10 分鐘保存 checkpoint；本輪 BEGIN→IMPLEMENTED 約 4／7 分鐘，另保存故障防護 checkpoint；歷史超時窗口仍保留原紀錄。GitHub commit/tree 逐檔讀回才 REMOTE_VERIFIED，收據及 STATE 再提交避免循環。恢復先檢查 pending_remote，補保存後再編碼；修改程式或驗收使舊當前證據失效，不沿用舊 PASS。

重現目前證據，以同一來源檔案執行 tools/run_evidence.py，指定 source-commit dc76b95fa5ff288d09d4474be2732191b3caa78c 及本 run 的 commit.json／tree.json，使用新的 run ID；執行 dev_governance.py check --require-evidence。新附件也需 checkpoint 永久保存。
