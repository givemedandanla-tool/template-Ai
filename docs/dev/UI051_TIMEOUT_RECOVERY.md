# UI051 單位邊界、超時與收據恢復

- 保留既有 JOB/AUTO_JOB/WORKER 與 SQLite；runtime_requests 僅同庫排程收據，無平行模型或客戶真相。
- 每來源／樣本先提交 RUNNING（尚未完成），轉換、事實／draft／USE 與結果仍依原安全單位原子交易。正常暫停／失敗將未提交項留 READY，已提交成功不重做。
- 標準庫子程序執行既有引擎；父介面不載原稿。120秒沒有單位邊界、取消10秒無回應才停止本worker與子樹；均屬保守預設，未宣稱參考硬體性能。協定行16KiB，event queue32／command queue1，寫pipe daemon不阻塞watchdog；stdin用os.read避免Python buffered daemon shutdown fatal。
- 僅在證明子程序已停止、原owner/scope/CAS仍相同、恰一持久RUNNING項時隔離該項FAILED，SQLite未提交寫入回滾，餘下READY保持原確認範圍續跑。無唯一活動項則BLOCKED，不猜測。
- retry_failed確認在一次claim消耗；同批自動續跑不再次重試剛失敗檔。例外自動重試為0，需操作者明確重新勾選；新retry請求在尾端，資源暫停不重複詢問同scope。
- 原工作已提交但queue receipt失敗時，排程Fail-Closed。明確恢復核對DB可寫入與保存憑證，按原job/owner/scope讀回終態補收據，分析不重做。真正寫入失敗不清故障。
- 逐來源作品清單獨立只讀process核實SHA、facts pins、unit signature與cache；每頁50、結果4MiB、30s timeout。作品紀錄含未人工核對候選；全庫有效已審數與來源完整覆蓋未逐項核實時明示未知，不以排除、快取或同bytes減分母。
