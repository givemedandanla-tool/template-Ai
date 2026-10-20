# 最新接手：全面查證仍在執行，不可提前結案

先讀 pre_download_audit/PROGRESS.json、README、PRE_DOWNLOAD_AUDIT_PLAN_20261020。原11798筆逐筆台帳不可刷新；目前386未審（即時台帳優先）。最新產品3a2ef142，10類根因已實作修正，root10相鄰驗證進行中；未到最終全通過。root8 Type3字型兩實際PDF原先2ERROR、root9重開工作兩真GUI原先2ERROR，修後相關23PASS。SQL列表root4另補重大重審/工作兩讀者：4實際並行SQLite案例原先2ERROR2FAIL，修後37PASS。root10損壞草稿部分替換目前來源/作品：修正測試第三案例前置active選取後，隔離1cef015a舊源4FAIL，新源相關驗證work-load-after-002。保留先前錯誤fixture與未完成結果，不能當根因證據。

full005(92977b77)1886PASS/243健康/0runtime/原1850保留。full006(281b53af)在273案例後因新增SQL實例修正中斷，不算完整PASS。最終catalog預計1901=原1850+本輪51有意義新增案例；尚未跑最終全套。27組原版GUI擷取全部PASS/來源281b53af未變，未包裝程式；最新GUI/root4變更後要按剩餘風險補驗。native00319PASS/11PNG，7獨立數學+原SQL12保留。原真實模型/Windows/私人AI/實體印刷資格不變。

精確AST型別見證001387PASS、0031502PASS（合計原當時1889，兩份清單不重複），皆0runtime/觀察器錯誤/來源未變，移除包裝後業務AST相同；004針對更精確座標91PASS。它們是受限型別證據，不代替原版產品回歸。被拒絕297筆內層座標舊證據與中途改helper的觀察002不可引用。最新三scope標準/runtime-aware/近似查重已跑，但後續修正後仍需更新及審查新增，不能漏掉runtime profile獨有診斷。

零新增費用優先；未用子代理/新API/付費服務，未push/PR/CI。正式治理Gate因歷史證據來源過期而FAIL，且新正式run需要真實遠端來源讀回；不能偽造GitHub JSON或關閉Gate。完成本機查證後可標LOCAL_SCOPE_COMPLETE_WITH_REMOTE_GATE_BLOCKED，不得REMOTE_VERIFIED。最新audit還原ZIP未製作，舊ZIP不含本輪修正。每10分鐘保存本機checkpoint；私人資料/字型/資料庫不入Git。

## 產品GUI交接（保持原資格與證據）

先跑`.venv/bin/python tools/resume_status.py`；分支`dev/v0.1-first-version`／PR2，不合併main。STATE與最新REMOTE_VERIFIED收據為保存依據。

- 本輪CORE-090：10／10 SELF_VERIFIED；[完整報告](GUI_OFFLINE_FINAL_REPORT_20261020.md)、[驗收映射](GUI_OFFLINE_10_CLAUSE_AUDIT_20261020.json)。
- 程式來源`4ebfff6f676b236519c4a1ba2b0cb192acbffea3`；FULL0061850／1850PASS、236健康模組、0runtime、capture0、397附件；原1798保留、新52。後續commit僅證據／交接／收據，不修改此來源。
- native005：桌面12＋原導航3 PASS、11PNG；owned3頁Tab PASS。非Windows／真人／實體印刷資格。
- 三工作區、真核心拖動、更正、確認、版本、固定與學習路徑都接通。普通操作白話，專業細節按需展開；原16家族工具仍可用。
- 完全本地工作，手動匯出安全ZIP；私人作品／字型／資料庫／原文不外傳。不索取私人作品，不自動上傳，不依賴外部AI。
- 額外3skill／5agent角色可由gui_tooling bootstrap重建；使用者本輪允許agent，不成為其他任務永久授權。
- 原AI8／50完整真實資格8部分／0完整。四類使用者暫擱維持；網頁／手機／EXE延後。
- 172登錄：父題69／75已驗證、3部分3延後；CORE90／90、GOV7／7。整體run FAIL僅原有5資格，software execution PASS。
- ALL001中斷、ALL002四FAIL／9Qt例外、ALL003啟動拒絕0測試、ALL004781PASS及ALL005572PASS中斷均保留；WIP1錯base metadata棄用。不要把失敗／部分來源當新驗證。

下一步由使用者下載到本地，依LOCAL_DESKTOP_QUICK_START／DESKTOP_WORKSPACE_USER_GUIDE操作；有問題從「問題與報告」手動匯出ZIP再交Codex。不得自動新增前端、EXE或要求真實資料來阻擋本輪交付。
