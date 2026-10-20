# DEV-QUALITY-001 工作紀錄

使用者本輪明確授權開發工具設定、隔離依賴、必要入口與驗證；不修改產品。這項授權優先於 onboarding 技能對單純環境設定的檔案保護預設。原產品 75 父題、CORE/GOV 與資格狀態維持不變。

- 開始：本機及遠端均為 `0e7b8aee82331ff6efa02a1a8233ff85689b660a`，工作目錄乾淨。既有治理 PASS（172 登錄、166 明列範圍、1850 已知測試）。
- Git hooks：未設定自訂 hooksPath，預設目錄沒有啟用 hook。
- CI：開發工作流程的 push/PR 路徑含 tools/tests/產品程式；Windows 打包只允許人工 dispatch。沒有查到可證明不加費的帳戶額度；本輪不推送、不開 PR、不啟動工作流程、不改 CI 或帳務。
- 起始恢復點沿用已驗證 GUI FINAL checkpoint 與上述 Git 基底。工具里程碑以本機提交與差異快照保存；完成後建立本機 checkpoint、patch 與 bundle，均不得稱 REMOTE_VERIFIED。
- 計畫：先建立固定版本工具與技能，再完成隔離示範／真實掃描／基準分類及既有相關測試。只對明確剩餘風險增加測試，不跑全產品回歸以增加數字。

- 里程碑 e08f4f3 / cb3ce61：固定來源與隔離工具、掃描及示範入口已本機提交，沒有推送。
- 已明確讀取兩個專案 wrapper 與全部上游技能，按根因流程修正空掃描設定；按 dry-refactoring 原則先判讀、不自動改產品。平台 executor skills catalog 回傳 0 筆，本輪不能證明原生自動載入；兩個 project skill 入口已驗證且可顯式讀取。
- demo-001 / 002 的設定問題已記錄 attempts.json；demo-003 的 8 個功能斷言通過（示範，不是真實產品修正）。版本：Ruff 0.17.1、Pyright 1.1.414、jscpd 5.4.1。

- 最終來源5bdff7d：三範圍576檔完整靜態掃描；新工具／測試0診斷。18項針對性PASS，0runtime。原產品manifest與FULL006一致，未重跑1850項。
- Ruff三版本同一soft-keyword誤判已保留為限制；不改產品／不隱藏，另以實際Python3.12.14編譯與3.11語法模式及Pyright核對。初次把文件目標3.11當執行版本的紀錄已明確更正。
- 7組exact已讀兩端與呼叫者：6保留、1候選；沒有重構。三個immutable初始基準已建；application正式check新增0，其餘用既有精確完整掃描結果分類。
- 僅保存雲端metadata草稿rev7，追加段落實測、讀回一致；不執行／發布新環境、不改ref或網路密鑰。原碼遠端未推送。最後封裝收據位於忽略目錄及ZIP內，避免自身SHA循環；須實際隔離套用後才記PASS。
