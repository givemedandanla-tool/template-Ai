# 當前接手：Windows beta驗證持續，尚未發布

依STATE.windows_release來源與next接續。full003完整1958為1956PASS／2未通過，原因是兩測試子程序攔截器固定索引，已只修測試參數定位，21相關測試PASS。原斷言與逾時未改。下一步先單獨stock004（不要與全回歸同跑），再linux004完整1958；新來源全通過並完成同源正式run及遠端checkpoint後才推最新release-request。已存在舊請求不代表Windows已啟動，API政策仍擋住查詢；待套用環境網路草稿，不能索取私人資料或API key。

# 當前接手：Windows測試版發佈已授權

當前固定來源094f8f9a；完整1958在linux-regression-003執行，見STATE.windows_release與checkpoint-progress-001.json。原1942全部保留、新16。source-flow011兩階段PASS但僅Linux/Python來源，不是frozen Windows。stock003在與全回歸同跑時首項工作未完成斷言失敗；保留結果，完整回歸後再單獨跑原版stock004，不改原斷言／時限。API主機網路草稿未生效，Windows執行回執未讀到，不能宣稱已打包／發布。新正式Gate／全部附件遠端checkpoint完成後才更新release-request候選分支。


使用者明確要求發佈EXE供本機實測。依STATE.windows_release及releases/v0.2.0-beta.1-plan.md接續，不再沿用舊EXE延後阻擋本次交付。一般push仍不打包；教學／知識庫草案仍待核對。未完成實際Windows包與下載校驗前，不宣稱已發佈。

# 當前接手：教學與獨立可搜尋知識庫方案供核對

使用者追加本體之外、可關鍵字搜尋的教學與功能資料庫：[知識庫草案](EXTERNAL_KNOWLEDGE_BASE_PROPOSAL.md)與研究紀錄。與下列教學草案共用內容／版本依據，兩者均待核對，不取代原任務；未建站、建索引或驗證離線搜尋。不要把研究設計當已實作或已採用。

最新草案：[教學與面板簡化](TUTORIAL_AND_PANEL_SIMPLIFICATION_PROPOSAL.md)，7份固定來源（含心理學原論文選段）、現況與同碼原生畫面走查。DRAFT_FOR_DISCUSSION_NOT_ADOPTED；本輪沒有GUI／教學實作、新手實驗或EXE。後續按使用者指令討論／採用，不改已採用發佈規則及下列軟體／外部資格。

正式規則見[RELEASE_MAINTENANCE_POLICY.md](RELEASE_MAINTENANCE_POLICY.md)及STATE.release_maintenance_policy；使用者已確認採用，不再詢問規則是否接受。版本與發佈工具尚未實作或執行，本輪未打包／發佈EXE；按後續指派落地，EXE延後政策維持。下列既有軟體交付及外部限制繼續有效。

先跑 `python tools/resume_status.py`，核對STATE、分支 `dev/v0.1-first-version`／既有PR2與最新不可變遠端收據。不得合併main或部署。

- [完整完成報告](non_code_audit/FINAL_REPORT.md)、[32項處置](non_code_audit/execution-001/case-results.jsonl)、[問題清單](non_code_audit/execution-001/issues.jsonl)。32主題已處置：28 PASS、4 UNKNOWN；外部資格不是通過。
- 最後產品／測試來源 `4f763f87458f0f65914d7e7c9a04b0a46f8dd912`；1942／1942 PASS、254健康模組、0runtime；原1921保留，新21。27原版GUI、19原生桌面、4核心後置條件與7證據負例通過；部分重複執行，不加總為新增測試。
- 修正2個容量建議語意缺陷：負例污染適合區間、跨條件借用最大欄位數。容量版本v2；舊模型不改寫，明確要求重校準；舊已確認稿保護／重播及正式Gate不放寬。另修正過期進度視圖與正式證據登錄。
- 正式 `docs/evidence/runs/RUN-NONCODE-ALL-001/` 採錄實際結果，來源e558311c與4f程式manifest一致；`software_execution_status=PASS`、整體FAIL僅原5外部條款。原治理檢查含publication scope PASS；原AI8包50條真實資格仍8部分／0完整。
- 172登錄／825條、75父題69已驗證3部分3延後、CORE90／90、治理7／7不變。825條映射不是新增獨立驗收；另核對64個實際函式斷言。
- CP001與正式CP003已獨立原生Git讀回；CP003快照b337dac5、368條。最終CP004與精確提交／phase以STATE與收據為準。原生Git投影不是REST API回應。
- 未解決資格：真實作品學習品質／完整.ai、Windows與指定硬體／效能、實體印刷、獨立新手、Windows與完整網路隔離。使用者已允許本地操作後回饋，不要求上傳私人作品。
- 新54個測試型別診斷為P3待辦，保留全部警告／原查重基準；1項產稿後通用提示文案候選待新手回饋。沒有已重現未解決P0/P1；不保證所有未測條件無錯。
- 中斷full001／初始fixture錯誤／無效本機checkpoint002均保留歷史，不冒稱通過；後者在推送前棄用，新增基底驗證及反例控制，正式CP003使用真實Git物件。

下一步：使用者本地試用後，從「問題與報告」手動匯出安全ZIP交Codex；依具體資訊處理。不要自動擴張成EXE／網頁／手機／全庫型別整改。啟動說明見 `LOCAL_DESKTOP_QUICK_START.md` 與 `DESKTOP_WORKSPACE_USER_GUIDE.md`。私人作品、字型、資料庫及模型留本地，不自動上傳。

本輪沿用免費本機工具與既有正常GitHub保存，沒有新付費API、試用、雲端資源或子代理；不要求帳單證明。前次GUI、全面代碼掃描與設計歷史見WORK_LOG及各自FINAL_REPORT，不依賴完整聊天。
