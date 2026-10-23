最新：本機範圍完成，先讀[FINAL_REPORT](FINAL_REPORT.md)、PROGRESS與還原receipt；正式遠端治理仍阻擋，沒有推送。本目錄也保留歷史失敗/中斷/拒絕證據，不能把任意歷史目錄當最後版本。

# 第一次下載前全面查證：執行入口

使用者已授權執行完整計畫及可驗證的最小根因修正。本目錄保存本輪進度、原始診斷逐筆台帳、來源／資源證明與新驗證；舊基準及失敗紀錄不覆寫。

- `PROGRESS.json`：當前階段及下一步，並非完成宣告。
- `diagnostic-ledger.jsonl`：11798筆原始Pyright診斷，以原始指紋加出現次數保留每筆；未審項目明列UNREVIEWED。完整欄位保留未取得的證據為null，不能推測填入。
- `qt-enum-members.json`：實際PySide6 6.8.3中首批87組Qt enum舊別名；complete-002另補完整名字空間，精確1728筆Qt別名診斷有對照。
- `qt-shadow-before.json`：真實MainWindow及InputGraphDialog的QWidget.window()被同名資料覆蓋，呼叫可重現TypeError；已在045517e修正；後續QObject.event及收尾回呼見PROGRESS。
- `requirements-test-matrix.json`：172需求／條款與原1850測試目錄的對照，缺失ID為0；這是盤點，並非本輪已執行結果。
- `resource-cache-release.json`：8份既有REMOTE_VERIFIED快取經來源／manifest／Git blob／收據／ZIP hash核對後釋放的證明；私人資料、本機未遠端保存快照及失敗證據保留。

費用規則已更新：既有ChatGPT Pro權益及合理使用內可分工，訂閱以外額外費用禁止。無法核對額外代理權益時不用，不以此停止本機工作。GitHub觸發費用仍無法核實，保存本機提交與可恢復差異包，不標REMOTE_VERIFIED。

Qt根因修正對應既有CORE-090與UI-062操作契約：保留Qt原生視窗API、擁有者關係、既有功能、人物／公司歸屬與版本保護；以真實視窗重現→最小修正→原測試／新增行為測試驗證，不改既有需求完成計數。
