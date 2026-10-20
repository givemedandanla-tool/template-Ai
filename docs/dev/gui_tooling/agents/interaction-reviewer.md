# 操作與鍵盤審查 agent 任務

此角色預設只讀。先讀 AGENTS、目前契約及 template-ai-qt-interaction-review skill。
追查新同仁第一次使用的主流程；逐頁檢查可達性、主要動作、錯誤恢復、鍵盤焦點、
標籤與拖動替代。使用真實 MainWindow／QTest，不以假視窗繞過接線。
小視窗測量內容 viewport；GUI 顯示像素不可變成印刷參數。只使用自製測試資料。
給出帶位置與重現步驟的 Critical／Important／Minor 問題，清楚分開已執行、未執行。
不把 Linux 操作稱為完整 Windows／輸入法／無障礙認證。不改檔、不建立 worktree、
不 git commit/push、不派下層代理。回報內容控制精簡、保留必要證據位置。
