# 當前精簡接手

- 核心零例行問答、按需rg小段讀、一般輸出≤1600tokens；每可恢復階段/10分鐘GitHub checkpoint＋receipt逐檔readback。無多代理/EXE/main merge，提交[skip ci]。/workspace/template-Ai，dev/v0.1-first-version／PR2。
- active_contract FIXED70_REMAINING28_CONTRACT。原前輪28與本輪剩餘28分開；本輪歷史完成4/28（UI046/UI047/UI049/UI050），原75為48 VERIFIED/24 PARTIAL/3 DEFERRED，固定70為46閉合/24剩；新code全部142歷史要求待重驗，UI051原8已完整綁但未VERIFIED，不得報5/28。
- 最新完整正式PASS仍RUN-REMAINING28-WATCH-002：692/692、0runtime/capture0/source unchanged。新UI051從資源/低負載/FIFO/逐source-work人審/子程序隔離/重試/續跑到GUI已實作，未全正式PASS。UI051_EXECUTION_PLAN/UI051_TIMEOUT_RECOVERY及REMAINING28_CLAUSE_AUDIT可查原8。
- Runtime001 source6a7ded4，約12min未終報，SIGINT無效後SIGTERM；沒有收集單項結果/沒有capture，不是PASS。原attempt metadata/log及partial source proof保留，不能覆寫或補造run.json。
- Runner已新增ignored .checkpoints/formal-live/RUN-.../test-progress.json＋jsonl結果，60秒faulthandler全thread stack；完整run結束才複製diagnostics進evidence。臨時py-spy attach被OS拒絕，改builtin，無申請提權/無app dependency變更。
- Runtime002 source da132107ddfbd64e65432a14f953070c7e2f1598，前408實際PASS，409 test_logo_workflow_gui generic_worker_start_failure卡QMessageBox。stack gui.error→failed→launch→run_job→test121確認同步pool.start失敗被改成modal；22:16:49 TERM。docs/evidence/runs/RUN-REMAINING28-RUNTIME-002/interrupted.json/partial-tests.jsonl/stack保存；整run未PASS，勿close milestone。
- 已恢復legacy無explicit on_error的同步pool.start raise/cleanup；資源延後錯誤交JobCallbacks(done,error,cancel_event)，callable仍3arg兼容舊mock。全部guarded dialog接error，batch原interrupt_owned處理deferred失敗/取消，未提交不假成功；batch preflight用worker own Library定點hash/page lookup不全載來源。
- Legacy import SKIPPED同bytes但source_id尚無的範圍也在只讀ledger另列，AUTO/SCAN/IMPORT各自scope分母，不冒已登錄/已審；summary明示未登錄與indexed候選。原749測試已知，不把新增tests當父題完成。
- 24 launch/Qt target PASS；106 callback broad初1FAIL是新resource-wait測試早於QTimer真正step的assert，保留原log，改等busy實際入口後9/9 PASS；不改產品邏輯/不降低源碼/控制/持久狀態斷言。
- 当前all-callbacks002 target在跑（/tmp/remaining28-runtime002-all-callbacks-002.log），命令有兩個錯module test_source_links/test_exception_center，應用test_source_relink/test_source_relink_scope/test_batch_source_relink/test_import_exceptions，另test_output_batch_gui。看完再補正broad；新source checkpoint/receipt/readback後才正式RUN-REMAINING28-RUNTIME-003，全749＋全部capture，讀live進度每60s更新，不改code/acceptance。
- /tmp/close_runtime_milestone.py是未執行template，目前仍指002/746，不能直接跑；只有新正式全PASS、5parent52原條/143claims合約hash/0skip/0Qt/capture0/source unchanged後才調整並結案UI051、更新5/28/49父題Verified/47固定70closed、archive媒體metadata-first exact policy、進度baseline BEGIN差異。
- UI051真Qt capture smoke成功：runtime pause/FIFO/source ledger/human review4PNG，已視覺檢查改中文label/欄寬/詳情；metrics真目前32GiB/4CPU host，非參考機。所有媒體仍metadata-first本機，無strict全附件上傳宣稱。
- 完成UI051後下一UI052原10條：exact批次來源快照/分層分母/未切分不減分母/正式規則低risk驗證與高risk人工/缺證結案阻擋/版本失效重開/500+低負載。現有quality_coverage僅paged inventory，不能把UI051逐筆ledger或100%畫面當結案。
- UI031/032/REV02合法真AI/Windows字型與版本、REV04實機尚未完整驗；UI048 LAST、UI056D/REV03延後。每個新source先維持已完成pending，未通過整題不要加完成率。
