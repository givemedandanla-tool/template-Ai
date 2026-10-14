# Human／GPT 開發交接

依序讀 AGENTS.md、STATE.json、REQUIREMENTS.json／FEATURES.md、PROGRESS.md／CURRENT_PROGRESS.json、最新 WORK_LOG 與 checkpoint 收據、DEVELOPMENT_PROTOCOL.md。每次開發前保存新要求基準，結束保存差異快照與同數字使用者回報。

## 字型中心開發中

本輪依使用者要求參考數學、開源與商用思路，CORE-028／029設計見FONT_CENTER_DESIGN.md。修改前保存108列基準與BEGIN，旧當前完成判定暫退為待驗證；歷史證據保留。基準27功能子項／6治理已驗證，75父題0完整／42部分／28未實作／2受阻／3延後。最後應重新全套證據，產生結束差異及永久GitHub恢復點。

## 上一個已確認版本

v0.1.6，測試來源 `8e8d2bab1789966636b1ac6d7b9a160aaab05cfc`；RUN-BATCH-RELINK-003：104 PASS／0 SKIP、20 件紀錄／實際匿名附件，含可閱讀的批次候選預覽。歷史 103／104 PASS 的前兩個 run 保留，不當最新版碼的證據。

目前 108 列＝75 原始父題＋27 CORE＋6 GOV。原始父題：完整0、部分42、未實作28、受阻2、延後3，75 項均有未完成條件；已驗證功能子項27（本輪25→27），治理6（5→6）。本輪新增 CORE-026／CORE-027／GOV-006 三列，無刪除、無原驗收範圍修訂；不以拆分數增加冒充原始需求完成率。對帳見 PROGRESS-20261014-BEGIN／END.json。

CORE-026：使用者單根受限背景唯讀掃描、大小預篩及 SHA-256＋bytes、來源身份獨立、多候選預設不選／不勾選、影響預覽、取消／部分／不可讀／同名異內容分開。每來源最多32候選、5000目錄項、深度32、256MiB讀取預算與2000來源上限；根外接點不進入。CORE-027：選取集合再背景驗證、BEGIN IMMEDIATE 全批 revision／stat／長度核對、來源位置與批次歷史／審核同交易；末段事件失敗全批回滾，復原重新驗舊位置／內容且產生新revision。原登錄與作品／發布模板不改，客戶映射未知不猜。

GOV-006 已落實使用者每次開發回報要求：render 自動產生統計，check 擋過期機器報告；immutable 前後快照對 stable ID、狀態、scope／acceptance 及分組計數。部分實作和未實作分桶，GOV 不算產品功能，不能把27 CORE當75父題的完整驗收。

最終快照 `2437a98437087b3cb79b45a6d06b97bbb05adee6` 已逐檔讀回300檔；本輪新增7個 checkpoint，總計21個 REMOTE_VERIFIED。收據與STATE另提交保存，避免自參照SHA。

## 下一工作包

UI-032 共用本機字型管理中心子包：先讀 UI_DECISIONS.md 的474行及 fonts.py。展示 Windows／本程式字型來源、可核對的家族／樣式、hash身份、可用／失聯／異動、實際模板引用與影響；未知原稿字型不假稱已識別。來源輸出字型管理不等於安裝Windows，仍不得自動安裝、接受授權條款或公開字体。完整不同版本同家族／TTC／字重選用需在 per-file 字形／Qt家族解析歧義實際驗收後處理，不能直接取消現有防混用 gate。先拆 CORE-028，保存新的進度基準／BEGIN／具名測試再改码。

UI-049 仍部分：多搜尋根、可恢復掃描狀態、跨設備字型／完整外部依賴、真實客戶映射與Windows真機驗收尚未做。字型中心後回到功能清單按核准優先順序推進；不以父題部分成果結案。

## 保存與限制

每個工作包、10分鐘及中斷前checkpoint。BEGIN、PLAN、WIP、IMPLEMENTED、HARDENED、UI與VERIFIED分包，收據／STATE再保存避免自參照。恢復先檢查pending_remote，補保存後再編碼。修改程式／驗收使當前舊證據失效，歷史保留；新run的全部實際附件需遠端快照核對。

本輪使用者再次授予訊息後24小時GitHub文件／分支修改權限，原文見2026-10-14-GITHUB-AUTHORIZATION.md；不例行要求再次确认。目前PR #2未合併main，沒有24小時常駐服務。EXE及實體印刷延後，UI-048仍最後功能／真實個資使用前完成；測試為Linux／合成資料，Windows、真實AI視覺、指定硬體與獨立覆核仍未完成。
