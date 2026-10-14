# 持久工作紀錄

每條紀錄應含要求 ID、動作／結果、測試、確切 checkpoint／commit、限制與下一步。最新資料置頂；資料可供 Human 與 GPT 覆核。歷史版本不是即時完成度。

## 2026-10-14：CORE-031 目標啟動，先保存完整候選唯讀契約

- 開工check PASS；確認工作分支82e5bf5d、main仍436ca2d7，無pending。基準111列／30 CORE完成／6 GOV／75父題保持。
- 使用者明確/goal要求候選硬篩、排名、唯讀預覽端到端驗收；新增CORE-031，原父題不降標。FONT_CANDIDATES_DESIGN.md列六項驗收、參考與有界預算。
- 先BEGIN GitHub讀回再改碼；單一checkpoint或部分測試不是停止條件，不重試先前卡住的PR metadata工具。
- BEGIN 8ce4461d0f830578620c2d87ea330b781e5957a1已讀回352檔；引擎、候選GUI與有界PNG已接上。既有18項字型中心及新增20項候選驗收PASS，包含真實worker與失敗重試；此時尚待正式全套證據及永久附件，未標完成。


## 2026-10-14：v0.1.7 字型中心／字形毫米診斷／真實背景交接完成

- 來源 `f347495579a8d43e191ce8e8471e0b90aaaaf3f5`，RUN-FONT-CENTER-002：122 PASS／0 SKIP、22件紀錄與實際匿名附件，包含中心／診斷畫面，已視覺核對。18個focused驗收含真正Qt worker／GUI執行緒、成功／worker錯誤／callback錯誤／重試，非只mock背景。
- CORE-028資產身份／家族款式／健康／模板欄位影響／來源與狀態搜尋及既有匯入修復入口；CORE-029 Unicode集合覆蓋、实际cmap、no-fallback shaping／字面table核對、固定pt毫米寬度與水平可行區間／stale阻擋；不改字級或發布模板。
- CORE-030修正共用Job／Signals生命周期與明確GUIqueued交接；真實worker曾結束卻留busy的故障已重現與修正，前輪未完成run不當PASS。
- 清單108→111，新增CORE-028／029／030三列；刪除0／既有驗收範圍修訂0。功能子項27→30已驗證，治理6不變；75父題完整0／部分42／未實作28／受阻2／延後3，75仍有未完成條件。基準／結束快照與當前Human／Machine統計已生成。
- InDesign／fontTools公開cmap原碼／Qt glyph-run shaping與集合、點mm換算、比例可行區間參考詳見FONT_CENTER_DESIGN.md；自行實作、無新外部依賴、字型只留本機。
- VERIFIED snapshot `73e67f1aff392973af9cbcddc170508876816c7f` 已逐檔核對347檔，22件新版附件、實際before／after日志、要求與前後進度差異全部永久保存。本輪6個已確認checkpoint，總計27個；收據與STATE另保存避免自參照。
- 本輪各確認checkpoint間隔小於10分鐘；歷史超時窗口仍如實保留，不宣稱最後未保存操作零風險。
- 下一步：UI-032只讀替代候選硬篩／排序預覽，未知原稿參考不做視覺等同評分。Windows／TTC／完整字重／嵌入授權／替代高風險審核仍待。

## 2026-10-14：CORE-028／029 字型中心開始

- 開工檢查PASS；讀 UI-032、字型／排版原碼與最新功能清單，108列基準已保存。使用者要求繼續開發與數學／開源／商用參考，不重問例行保存授權。
- InDesign字型一覧／影響、fontTools cmap原碼思路與Qt實際解析／shaping作為參考；加入Unicode集合覆蓋率、固定點數毫米轉換及水平可行區間，不把名義glyph進位當完整shaping。設計參考與限制見FONT_CENTER_DESIGN.md。
- 新增CORE-028共用管理中心與CORE-029字形／字寬診斷，清單108→110；原75父題仍全部保留。先BEGIN，再做有證據的明列子範圍。
- BEGIN `db3039a5ade7716bfda5f905465b3732af7d7ef7` 已讀回304檔。已接中心查詢／影響／背景健康驗證，以及無fallback shaping／字型table核對／Unicode覆蓋／毫米適配診斷；輸入在背景診斷期間變更時，舊結果不套用新輸入。
- GitHub PR說明更新先前兩次被中止；本輪用已成功的程式／文件快照API持久化，不反覆卡住同一PR操作。
- WIP `7e2664adc461a254f34c1c09305775794352185f` 已讀回308檔；14初版具名驗收通過，再加入實際Qt背景執行緒測試與2件真實字型中心／診斷截圖，不只mock背景工作。
- 初版程式 `2db34fad5943aec86821d39ad0d16a9497cedc63` 已讀回311檔；真實背景測試FAIL並在清理時busy未恢復觸發modal，主動中止focus／RUN-FONT-CENTER-001，該run未完成不能當PASS。
- 實際debug activeThreadCount=0但dialog／window仍busy、inventory未收到；before-fix.log保存真實結果。新增CORE-030共用worker／Signals生命週期及GUI queued交接子項（UI-051／003），清單110→111，不把修正故障冒充完整佇列完成。
- 故障snapshot在日志仍寫入時prepare，讀回擋下差異；以原ZIP的凍結字節（當時日志为空）完成不可變snapshot `4986603780e50c8616209bd765d434c9d0d64708` 317檔確認，再於修正checkpoint保存完整before／after日志，不覆寫歷史。
- 修復run_job持有Job／Signals生命週期至GUI queued callback完成，成功／worker錯誤／GUI callback錯誤均恢復busy與釋放；真實字型背景與3種交接故障合計18項focused驗收通過。
- 下一步修正版SOURCE checkpoint、RUN-FONT-CENTER-002 全套122項與22件預期附件；run001未完成及失敗原因保留。

## 2026-10-14：v0.1.6 批次來源恢復與進度回報完成

- 測試來源 `8e8d2bab1789966636b1ac6d7b9a160aaab05cfc`；RUN-BATCH-RELINK-003：104 PASS／0 SKIP、20 件紀錄與實際附件，含新批次來源預覽；實際核對後補列高／完整tooltip／關閉鈕本地化。17產品具名測試＋4進度測試，103／104前輪歷史不沿用新碼。
- CORE-026內容定位：指定單根／受限資源背景讀取、長度預篩、候選各讀一次按hash分組、獨立原登錄／相同副本歧義、預設不選／不勾、取消與部分狀態、接點範圍防護。
- CORE-027交易復原：CAS全批長度／內容／版次核對，末段審核事件失敗亦全批回滾；復原驗舊位置並保存新revision及完整歷史，不重綁客戶或改原檔／舊模板。
- GOV-006本輪定案已實作：render產生機器／人類統計，check偵測登錄漂移，前後stable ID快照與需求／範圍／完成差異。
- 清單105→108（新增CORE-026、CORE-027、GOV-006，刪除0、既有驗收範圍修訂0）。功能子項25→27已驗證，治理5→6；75父題保持完整0／部分42／未實作28／受阻2／延後3，75仍有未完成條件。不能把子項或治理數當父題完成率。
- 對帳：docs/dev/progress/PROGRESS-20261014-BEGIN.json／END.json；當前PROGRESS.md／CURRENT_PROGRESS.json。所有狀態與驗收引用已重新對新版run檢查。
- 最終snapshot `2437a98437087b3cb79b45a6d06b97bbb05adee6` 已讀回300檔；本輪新增7個checkpoint，總計21個已確認。本輪各中途保存間隔低於10分鐘；歷史26／14分鐘超時紀錄保留，未冒稱零風險。收據與STATE另行保存。
- 下一步：UI-032共用字型管理中心子包，完整來源依賴／多根／Windows／客戶映射仍待。

## 2026-10-14：CORE-026／027／GOV-006 開始

- 讀功能清單與 UI-049 全文，基準 105 列：75 父题（0 完整、42 部分、28 未實作、2 受阻、3 延後）、25 CORE／5 GOV 已驗證。
- 使用者定案每次開發回報前後計數與需求變化，已持久化規則與不可變 BEGIN 進度快照。新增兩個功能子包及一個治理子包，總列 108；新增拆分不等於父題完成。
- 第一個 BEGIN 保存設計與規則；登錄更新腳本首次語法錯誤未改資料，已修正並分開 PLAN checkpoint 保留真實過程，不覆寫 BEGIN。
- 使用者本輪再次授予訊息後 24 小時所有 GitHub 文件／分支修改權限，繼續同分支保存，不例行要求再次確認。
- PLAN `e315744d0c67f5c462d8e8cb599d2a7e8b0a8b93` 218 檔已確認。進度工具4項具名驗收通過；背景掃描／CAS 全批交易／新版本復原與 GUI 已實作，尚待產品具名測試及全套證據。
- WIP `7a79ef609f11cc145732179024c6efd104caddce` 226 檔已確認；已加入 16 項批次具名驗收，含最終事件失敗全批回滾及後來版次不被舊批次復原覆蓋。新增真實批次候選預覽截图，勾选維持預設未核准。
- 程式 snapshot `d550d9471da370703b9b31fb7ee820f1498c5fae` 已讀回 229 檔；RUN-BATCH-RELINK-001 103 PASS／0 SKIP、20 件附件。
- 自我檢查補上未標為一般 symlink 的目錄接點實際位置限制，避免進入範圍外目錄；模擬測試不冒稱 Windows 真機驗收。新碼／驗收將重新全套驗證，保留第一輪紀錄。
- HARDENED `95f3d296151b01db6d17de859825f1ed7e0dcaf2` 252 檔已確認，RUN-BATCH-RELINK-002 104 PASS／0 SKIP、20 件附件。實際截圖發現表列高度使第二行來源識別／狀態／bytes 不易閱讀，補自適應列高及完整 tooltip，關閉鈕本地化；不把截圖只生成當作視覺驗收完成。
- 下一步：UI 可讀性來源 checkpoint，RUN-BATCH-RELINK-003 及結束清單統計。

## 2026-10-13：v0.1.5／CORE-025 完成

- 測試来源 `dc76b95fa5ff288d09d4474be2732191b3caa78c`；RUN-FONT-REPAIR-002 83 PASS、0 SKIP、19 件紀錄／實際匿名附件。12 字型修復驗收含實際 PDF 输出、模板 pin 保留、隔離 hash、例外回復、PREPARED 模擬中斷与回復也失敗的鎖釋放。
- 商用 InDesign、開源 Blender／DVC／FontForge 思路與 SHA-256／串流及交易方法已落到產品；來源與授權範圍見兩份設計文檔，未複製第三方代碼、未引入其服務。
- 新源碼後重新驗證，30 子範圍按具名条件 SELF_VERIFIED；75 父题仍非全部完成。Windows、真實 AI、指定硬體、完整字重、批次来源與印刷不冒稱完成。
- 永久證據最終快照 `b11b054a85b626288a99a3a6016cc274f6655e55` 已讀回 211 檔；總計 14 個已確認 checkpoint，本輪新增 7 個。收據／STATE 另提交保存。
- 下一步：UI-049 受控批次定位、候選影響預覽、版本核對／勾選／復原；完整字型版本另包。

## 2026-10-13：CORE-025 開始

- CORE-024 永久證據 snapshot `956e9ecb7078e250682564e1d8cf6954230f5f8e` 161 檔確認；收據／STATE 在 `712448eeb24e373946cc112ba0f41307f7244327` 保存。
- 字型修復只恢復同內容核准複本，隔離損壞副本，保留 pin；加入修復 PREPARED 意圖與啟動核對，避免把跨 SQLite／檔案操作冒稱單一原子交易。
- BEGIN `37d1f2c19ed54215cec1e0258632dd2666e15a7d` 已讀回 164 檔。11 個具名字型修復測試通過，包括新 PDF 實際匯出、模板 pin、隔離 hash、正常例外回滾與 PREPARED 重開核對。
- 檔案／SQLite 不冒稱跨存储原子交易；持久意圖及 SAVEPOINT 保留失敗回滾時的寫入鎖。Windows 鎖檔與斷電仍需真機驗收。
- 第一輪 RUN-FONT-REPAIR-001 在 `b72b44ba945f7cf567b72b1d785cdb162e5fdbd3` 的 82 測試通過。自我檢查补上「回復檔案也失敗」釋放 SQLite 鎖與重開核對；12 項字型驗收通過，新版需重新全套驗證。歷史 82 PASS 不沿用為新碼證據。
- 下一步：修正版來源 checkpoint、83 項來源匹配證據与永久附件，不打包 EXE。

## 2026-10-13：CORE-024 完成

- v0.1.4 測試來源 `285a9e14cf063dc71b04ebc28d4af35efa499bb1`；RUN-SOURCE-RELINK-001 71 PASS／0 SKIP，19 件實際匿名附件／文字紀錄，來源未改變。
- 7 個具名測試涵蓋搬移改名、原稿只讀與 provenance、同名異內容拒絕、過期 revision、事件回滾、狀態與 GUI 背景路徑／重開。
- 原始 sources 登錄、作品與模板不替換；位置及不可變歷史另存。stat 競態防護屬本機正常異動防護，不是惡意檔案系統認證。
- 下一步：永久證據 checkpoint 讀回；再做 UI-032 同內容字型資產修復，批次重連留後續。

## 2026-10-13：CORE-024 開始

- 使用者再次授權 24 小時必要操作，持續功能開發；不宣稱部署常駐執行服務。
- 參考商用 InDesign、Blender／DVC 開源實作與 SHA-256 串流方法，設計見 SOURCE_RELINK_DESIGN.md。
- 單件內容重連先做；原始登錄不可變、另存位置／歷史、CAS 版本防護及同交易審核事件。
- 修改來源前先取消舊當前完成判定；保留歷史證據，重新驗證後恢復具名範圍完成。
- BEGIN 已讀回 135 檔，commit `8dd116abf6db6f65114563d7064a01de8758ca38`。7 個來源重連測試通過；首次 GUI 測試清理重複關閉窗口造成阻塞，已修正測試清理，不列作產品成功證據。
- 下一步：程式可恢復 checkpoint、完整來源匹配測試与永久附件；再進入字型修復。

## 2026-10-13：v0.1.3／CORE-023 完成具名範圍

- 程式來源 commit `6a392639ef7ca8e35ff74ced9e203b7847dff664`。RUN-SOURCE-CACHE-001：64 tests全數PASS、零SKIP，19件紀錄／匿名實際附件。
- 23 CORE加5 GOV按各自的明列範圍SELF_VERIFIED；75原題仍不是全數完成。來源快取完整性不等於完整批次來源重連，metadata checksum不是安全簽章。
- 版本化快取加入圖片／SVG內容hash、metadata checksum、同來源／同頁及固定路徑檢查，損壞時重新轉換；拒絕符號連結，轉換失敗不回退為成功，原檔保持只讀。
- 產品工作包BEGIN到IMPLEMENTED收據約14分鐘，也超過10分鐘目標；已保留實際時刻，不將保存頻率冒稱嚴格達標。下一輪應在長工作包中途先做WIP checkpoint。
- 全部.log及二進位合成附件納入最終checkpoint並逐檔讀回；新增遠端附件完整Gate。最終snapshot commit `19b300cec125149b2adc0e32987d376d2638ab75`確認132檔，入口與收據另提交保存。
- 下一步：UI-049的受控來源重連子包（內容hash驗證、變更拒絕、原登錄保留），其次字型資產修復。EXE／印刷／指定設備與未決產品報告不提前做。

## 2026-10-13：CORE-023 開始（先保存再改碼）

- 五點框架 READY 與收據已永久保存；確認提交 `bc5448f2a4c44c1a503b5ad59d21caf61dad33e8`。
- 下一要求 CORE-023：衍生快取內容、頁碼與 metadata 驗證；異動／損壞時不重用並重建，原始來源保持只讀。
- 故障測試先重現 3 個FAIL與1個ERROR；修正後6個快取測試通過，包括符號連結不改原檔，原始紅／綠紀錄保存於docs/evidence/regressions/CORE-023。
- 發現框架的副檔名白名單漏了.log，初始遠端快照沒有全部文字日誌；本包補.log並增加require-evidence的遠端附件包含檢查，避免只在本機看得到卻宣稱已保存。
- 舊 run 保留可查，但新來源版本開發時先取消當前 completed，重新驗證前不沿用舊 PASS。FRAMEWORK READY 歷史收據仍有效，产品新版本完成另產證據。
- 先做 SOURCE-CACHE-BEGIN checkpoint，完成修改／測試後再做可恢復 checkpoint 與RUN-SOURCE-CACHE-001。

## 2026-10-13：五點框架 READY，遠端快照已確認

- GOV-001～005：框架已實作，源碼 commit `f5da9c41e432e0b7b3927ae9b51c5e94645406b3`；RUN-FRAMEWORK-001 的 58 項具名測試全部 PASS，19 個紀錄／匿名附件。
- 原有 22 CORE 與 5 GOV 以明列範圍 SELF_VERIFIED；75 父主題未被自動標完整完成，CORE-023 尚未實作。所有狀態見機器登錄。
- 已停用 EXE 的 push／PR 觸發；只保留手動日後交付。本輪不等待或重跑 EXE。
- 起始、框架實作、自動狀態共三個 checkpoint 已讀回；prepare 自動加入 pending，acknowledge 自動更新入口指針。
- 首輪建置工具期間起始收據至實作收據約 26 分鐘，未達新訂的 10 分鐘節奏；已記錄此差距，後續以短工作包與自動 pending／入口更新控制保存，不宣稱歷史每次都已達標。
- READY快照 commit `38374fd23b21fedcc7d2df15cf8ae34cd94f3718` 已讀回101檔（含匿名實際附件）；收據與入口指針另行保存。下一步為 CORE-023：來源快取 hash、損壞 metadata、只讀重新轉換及故障驗收。

## 2026-10-13：治理框架建置中

- 來源：使用者的六點指令，原文見 `docs/decisions/2026-10-13-CHECKPOINT-EVIDENCE-POLICY.md`。
- 要求：GOV-001～005。先做框架，再做产品 CORE-023；EXE 改為只保留人工 dispatch，不重新嘗試。
- 已確認起始 checkpoint：`CP-20261013-FRAMEWORK-START`，GitHub commit `02af3a8d556830a0e699dd80e6dbb3535a984c28`，62 檔讀回一致；本機 ZIP 為額外恢復點。
- 已新增 AGENTS／Copilot 入口、STATE、交接、要求登錄、證據研究、快照與一致性工具；保留 75 原題與 23 CORE／5 GOV。
- 尚待：治理測試、框架提交及新版證據 run；此時不把框架或原有 CORE 標完成。
- 修正歷史索引：UI-058 是當次排版候選恢復，已完成的作品標記歷史屬 UI-038 子集，不能混稱。
- 下一步：執行治理自測→checkpoint→GitHub 讀回→以確切 commit 產生證據→READY checkpoint，再開始 CORE-023。
