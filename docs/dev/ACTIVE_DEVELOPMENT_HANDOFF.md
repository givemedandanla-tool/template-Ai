# 當前精簡接手

- 核心：零例行問答、按需rg/小段讀、一般總輸出≤1600tokens，每可恢復階段與10分鐘checkpoint。無多代理/EXE/main merge，提交[skip ci]。
- /workspace/template-Ai；dev/v0.1-first-version／PR2。先resume_status、STATE/receipt、governance check。active_contract FIXED70_REMAINING28_CONTRACT；原前輪28完成與本輪剩餘28不可混淆。
- 剩餘28本輪已完成UI046/UI047/UI049三題，共32原條款；正式662/662 PASS、Qt錯誤0、capture成功、來源未變。全75：47 VERIFIED／25 PARTIAL／3 DEFERRED；固定70：45閉合／25仍部分。CORE87／GOV7另計。
- 最新run docs/evidence/runs/RUN-REMAINING28-RELINK-001/run.json；正式source 8193dc2257a31ec6092d1e6bafb941ddc46329c8；0skip/0runtime/capture0/sourceunchanged，141 completed要求/claims匹配。
- UI049：沿用SHA256+length/source_links/SQLite；16明列根重疊不重掃、全局5000項/256MiB，32候選/異內容位置顯示並保留實數；完整customer/style/person-scope/training/font/Logo資產關聯背景快照與詳情，來源版次/context CAS；單件也先共用未勾選GUI，單件/批次映射稽核與可核驗撤銷；原檔/客戶不改。
- context每件1MiB/2000筆、整批預覽/稽核8MiB、只讀查詢30秒，超額整批停止。共用asset_references排除file_hashes值；資產存在不等於品質/權利Gate已過。
- UI047全關聯加密/隔離副本/實際測試還原/現有差異/app-open排程已全10原條驗證，移轉source facts/Logo/BG正式Gate仍需重驗；UI046全11條身份合併/保後續合法新值拆分已驗。
- 32文字metadata GitHub，103媒體.checkpoints/formal-media/RUN-REMAINING28-RELINK-001，FULL70_PUBLICATION精確source/sha/bytes；strict全附件未宣稱。
- 下一UI050：現source_scan只手動雙hash；source_scan_dialog明示無watch。重用Qt QFileSystemWatcher(提示)+debounce/週期/重啟補掃，明列根/排除/暫停、低量有界掃描、舊索引不因離線刪除；沿用import_batches候選，不另建影子庫。檢查BatchStore目前異名同hash會重用同source ID風險，需保存獨立來源/客戶審核；同名內容變更保舊ID版型進人工例外。
- UI031/032/REV02仍需合法真AI、Windows字型受控安裝/host output rights/版本映射；REV04真16GB/RTX5050/VivoBook未實測。UI048 LAST；UI056D/REV03延後。
- 下一來源修改先把141完成標pending、保存previous_evidence/清latest、render；正式凍結後全回歸再恢復。

- 現開始UI050來源擴充；141歷史完成已標pending、latest=None。下一watch/scan/queue/alias原12條，非正式通過前不可宣稱目前source全驗。

- UI050 core WIP：source_scan重用source_discovery有界scandir visitor，不另造walker。根/格式/排除/暫停/移除CAS，雙hash按size配額，失聯/等穩定/部分不稱成功；同TrainingStore SCAN_CANDIDATE穩定ID，異名獨立、同名新bytes舊候選stale、manual後auto才入隊，未建立AUTO_JOB。7新+55相關=62PASS。
- 下一SourceWatchService(Qt事件僅hint/debounce/開啟與週期補掃/共享worker/stop)及新版SourceScanDialog；候選交既有AutomaticTrainingDialog，該管線已保異名source獨立，無需改一般BatchStore重用行為。尚未真watch/GUI/原12完整註冊/全formal；UI050仍PARTIAL，141歷史要求待重驗。

- UI050 service WIP：source_watch SourceWatchService已接MainWindow，Qt QFileSystemWatcher根/最多128提示點、600ms去抖、30秒補掃/啟動補掃、FIFO共享run_job、實際worker獨立SQLite、root與來源索引digest CAS、途中取消/延後安全pause及close守衛。6新真Qt事件測試+7index+9操作=22PASS；前62相關也PASS。
- source_scan known_sources局部SQL最多2000登錄（同路徑多版本hash保留），內容全庫查索引判alias只當線索；候選不自動訓練，已實際登錄仍標需歸屬審核。下一重寫SourceScanDialog接共用service及根控制/候選分頁/UI003交接，現舊GUI仍手動，勿結案UI050。
