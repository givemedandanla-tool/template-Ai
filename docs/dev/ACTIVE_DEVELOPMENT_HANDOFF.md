# 持久化接續入口

使用者本輪明確要求：按計畫自主開發，完成十個完整父功能；參考數學演算法、成熟開源與商用方案的思路；零例行問答、持久化優先，即使換對話也能直接接續。

1. 使用既有 checkout；先讀 AGENTS.md、STATE.json、STATE.active_contract、本檔、HANDOFF 最新段與 WORK_LOG 最新記錄。不要把main的歷史文件狀態當開發現況；工作在dev/v0.1-first-version／PR2，尚未合併。
2. 固定來源為使用者指定4238ebc24ae62a2ef90051a86685a4c13bfca94b的PARTIAL_70_GAP_REPORT；目標UI043、045、020～027，共10原父題。新契約覆蓋初始GUI-first選擇，但保留原契約與checkpoint；不重算舊十工作包或既有4個固定70完整父題。
3. UI045圖差異引擎／Qt入口9項目標PASS；UI043來源客戶候選／審核／交易入庫8項目標PASS。原基準428PASS。兩父題尚待完整source-bound回歸／逐條對帳，仍PARTIAL；接著做Logo閉環與多尺寸輸出。
4. 不重問是否繼續、是否保存或已核准選型。真正缺少的外部資源記明相依條件，只阻塞相依驗證，先做其他工作。不得宣稱讀到無法取得的/local完整對話；已找回的GitHub決策是現有依據。
5. 每個可恢復階段及每10分鐘建立唯一checkpoint並推送；原生Git重新fetch確認commit/tree/blob才寫REMOTE_VERIFIED，收據下一個提交保存。記錄真實間隔；不能以本機ZIP冒稱GitHub保存。
6. 不啟動多代理、不合併main、不建EXE；[skip ci]保存以免自動觸發Actions。合成資料本機測試，新媒體依原政策留本機、code/tests/text保存。
7. 環境：.venv/bin/python；XDG_CACHE_HOME=/workspace/.cache、QT_QPA_PLATFORM=offscreen。依requirements-lock.txt重建；SQLite、Qt與Inkscape已有真實基準。

每輪離開前更新STATE下一步、完整父題完成／剩餘、具名驗收與未驗證條款。持續目標不因checkpoint或聊天換頁而取消；未完成不得報10/10。
