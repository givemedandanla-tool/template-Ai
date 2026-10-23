---
name: template-ai-gui-code-review
description: Review desktop refactoring against approved behavior, privacy, evidence and preserved version contracts, with bounded read-only specialist context.
---

# Template AI GUI 程式審查

沿用 AGENTS 與使用者授權；專項 agent 協作必須由目前使用者指令支持。
本輪使用者已明確授權以 skill／agent 協助 GUI 重構；不轉成未來所有任務的永久授權。

1. 按需讀 ../../vendor/superpowers-code-review/SKILL.md 及 code-reviewer.md。
   採用精簡目標／驗收、來源 SHA、範圍明確的只讀審查、嚴重度與證據格式。
   本專案與高優先指令優先；不自動加入其整套開發工作流，不建立 worktree、不自動 merge，
   不要求讀完整聊天，不因上游說 mandatory 就無條件派出代理。
2. 由主代理取得 base/head，執行
   `python docs/dev/gui_tooling/agent_task.py --role gui-code-reviewer --base BASE_SHA --head HEAD_SHA`，
   把實際輸出交給 collaboration 工具；腳本只產生任務，不虛稱平台已增加模型或代理種類。
3. 審查使用者工作能否完成、既有功能是否可達、資料／畫面／輸出是否同版本、
   對話框與背景工作的生命週期、離線邊界及報告隱私；不只評估配色與程式碼風格。
4. 報告列出可重現位置、影響、修正建議、實際執行檢查與未驗證範圍。
   未提供私人作品／Windows 測試屬已延後資格；不能要求上傳或阻擋其他 GUI 工作。
5. 把本代理稱為同一團隊的專項審查，不宣稱外部獨立認證；原正式 Gate 不因此放寬。

來源固定 commit、MIT LICENSE 與 hash：../../EXTENSIONS.json。
