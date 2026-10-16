# REPAIR002 正在正式執行：source/tests/tools/acceptance凍結

- 活躍parent session63633，run RUN-REMAINING28-REPAIR-002，實際source eee91b160e11685f05543e4f05843dbfd345bc77/tree51396ab5e12ec8a4e41fe7ddb2ab6a8f1573b282；源碼逐檔nativeACK。預期999 tests/146requirements/82原條/8parent-audit，尚無最終結論。讀 `.checkpoints/formal-live/.../test-progress.json`，不是runfolder的progress.json。實際shell exit在 docs/qa/targeted/remaining28-repair-002-parent-exit.txt。run.json未出現前不要finalize。
- 只准docs-only checkpoint／nextplan，勿修改程式／測試／工具／REQUIREMENTS。UI055_EXECUTION_PLAN.json是原11全文/SHA與已實際讀LabelStudio1.21.0(57531B/SHA10e2...)等設計，**尚未實作**；等UI054 fullPASS/Gate才改source。
- 確認REPAIR002實際999全PASS/sourceunchanged/parentexit0/captures與146claimdigests、82原條後才finalizeUI054；要建立新的UI054/REPAIR002 finalizer，絕不跑舊UI053 finalizer。7/28歷史，未計8。其後立即UI055+rest20，勿停milestone。

# REPAIR001 已受控停止；下一凍結999測試跑 REPAIR002

- **REPAIR001不是PASS**：source3fb28a69d3a23df944105f98718cf839da022f08，實際parent exit130（僅SIGINT exactownedparent，ownedchild已停），437completed/436PASS/1FAIL，沒有run.json／capture。失敗是AutomaticTrainingGuiTests確認取消案例在preflight等10秒未完成，未到取消assert；原始延遲具體sensor原因未捕獲，勿斷言生產bug。275個rawfiles533397B逐檔hash保留在該run/interrupted-live、module-raw-evidence.jsonl與controlled-stop.json，不覆寫／不finalize此run。
- 只改該GUI workflowfixture用既有controlled_resources（不是產品程式），新增真startup barrier60s→證明仍在等且無jobs/sources→解除後預檢完成→No取消仍無job。與actual runtime sampling/pressure/fairqueue一起32/32PASS；999known，146claims仍pending。下一 RUN-REMAINING28-REPAIR-002 source必須重新push/native後實際full；不可用001或target32結案。
- 仍歷史7/28；UI054原11/SHA/80supportingtests已pending註冊；新full應999tests／146claimrequirements／82原條／8parent audit。實際fullPASS＋exit0/sourceunchanged/captures/Gate後才8，立即繼續UI055/rest20。

# 正在正式驗證：不可修改source/tests/tools/REQUIREMENTS

- 下一步啟動／追蹤 `RUN-REMAINING28-REPAIR-001`，預期998tests／126左右serialownedmodules／146claim requirements／8of28 fullparent-audit／82原條。只有實際parent shell exit0、source_unchanged、allcatalog PASS、所有capture exit0與publication Gate才可結案UI054；其後立即繼續20父題，不停milestone。
- Full11 source checkpoint已由native精確ACK：f3609dfc572a97a673f907b7a86075a43f9b3949/treefa44d0ff72c09ca52819409f89eea0d8333b8be4（2885files）。前一dafdcd漏generated CURRENT_PROGRESS/PROGRESS，讀回正確拒絕；已補兩檔，未改原prepared manifest，延遲超10min已記STATE，不能說strictcadencePASS。正式實際tested commit以run.json為準（receipt/state followup可能再有docs-only commit）。
- pending_revalidation_ids已補UI054共146；原11逐字/SHA已註冊，80unique supporting tests。7of28是歷史，UI054仍pending。003七頁實際截圖都已視覺檢查，parent180183040B/GUImaxgap65.0569ms是controlledworkflow，非硬體benchmark或生產準確率。
- Sourcefreeze後只可docs-only保存CP／run進度／finalizer設計；不得編輯source/tests/tools/acceptance。full formal結果/claimdigests確認前不能重跑任何舊finalizer。

# 當前交接：持續完成原28父題，不例行詢問

- 倉庫 `/workspace/template-Ai`；分支 `dev/v0.1-first-version`／PR2，禁止自行merge main／EXE／subagents／新增付費服務。Python `.venv/bin/python`；Qt offscreen；`PYTHONPATH=tests XDG_CACHE_HOME=/workspace/.cache`。
- 先讀 STATE 的 current_work／next_tasks／last_confirmed_checkpoint，並跑 dev_governance check。按需 rg、通常輸出≤1600；每可恢復包與10分鐘 GitHub checkpoint＋原生逐檔讀回；歷史不得覆寫。
- 原28契約 `FIXED70_REMAINING28_CONTRACT.json`；歷史完成7：UI046/047/049/050/051/052/053（71原條）。UI054原11正在實作，**不能計8/28**；當前145 claims因source更動全部pending，998known tests。CORE/GOV不冒充父題。

## 當前優先：正式來源凍結／全回歸

- 07:17 原UI054 **11條逐字與原sectionSHA13e2...完全核對**，已在REQUIREMENTS註冊pending（共146claims、998known），覆蓋矩陣 UI054_FULL_ACCEPTANCE_COVERAGE.json。歷史7/28，未計8；下一 RUN-REMAINING28-REPAIR-001 實際full sourcefreeze/push/native/fullrun/sourceunchanged/parentexit0/allcapture/Gate。不要再只跑target當結案。
- 畫面003全部7張已視覺檢查並持久化：docs/qa/ui054-native-capture-003；tableheight/columns及具名source/progress已改善；preparation57.5056s，controlledworkflowGUImaxgap65.0569ms、parent180183040B。不是硬體benchmark／生產品質。003 actualownedSTATUS pin替代capturer同步duplicatebackendassert，002原2456ms保留不改。正式runner新增獨立repair capture子程序，同120s上限，避免與既有Qt capture共用存活widget。

## 前期畫面檢查與歷史下一步

- 07:07 actual `docs/qa/ui054-native-capture-002` 七張真Qt截圖＋metadata，全部視覺檢查；actual fullchain59.94s preparatory，另有真語意FIFOchild，withdrawalblocksrollback。**有待修**：source/impact table欄太窄且高度只顯示2列，進度rawid/English需具名；maxGUIgap2456ms包含capturer直接呼叫重backend `release.pin()` assertion，非正常UI讀取，先改用已由ownedSTATUS回傳的pin並重測，不能把這份冒稱低負載PASS。capture001 namespaceImportError保留。
- tests/quality_repair_acceptance_fixture.actual_chain已抽共用給fullchain測試與capture，無複製模型結果；fullchain test仍withdrawpriorRootGold阻擋，目前新helper由actualcapture完整執行。

1. **實際七頁截圖／視覺檢查／加入aggregate**。`quality_repair_dialog.py` 七個原生scrollpages已做；`capture_quality.py` 舊8張、`capture_remaining28.py` aggregate尚未含repair。新capture沿用真實合法合成資料／現有Qt／同SQLite／FIFO，實際state，不能以空白tab或字符串冒充。整個現有aggregate有外部timeout，先查run_evidence呼叫界線；不要為了截圖又重建引擎或長期卡住GUI。
2. 原UI054全文11／SHA在 `UI054_EXECUTION_PLAN.json`（13e2c0f1dee610fa6485a53f806bef1dadacd9f0c920a32953851121af942498）。按全條核對後才註冊完整pending驗收／sourcefreeze／push＋native readback／正式fullrun。不得只拿target PASS結案。
3. PASS需實際full parent shell exit0、source_unchanged、全catalog無skip／missing／native異常、真capture，再做完整publication-scope Gate及GitHub receipt。其後才8/28，繼續其餘20，不能停在milestone。

## 已實作／最新證據

- quality_repairs：actual canonical failure、SOURCE_FACTS／實際AUTO_UNIT例外／持久Q_WORK跨批重審／匯入batch item無作品manual恢復；原稿FACTS/Gold人工核對、11層根因候選，不把假設說成已證實。QualityRechecks共用resolver含歷史RULE exactrev→SAMPLE→DATASET→geometrytemplate、模型inputs→actualAUTO→alltemplate/customer；未知／缺rev保留POTENTIAL。
- quality_repair_training：既有AUTO_JOB operation、sharedFIFO/lease/ownedchild/selectedTRAIN-VALIDATION、model+candidate+job+lease同Tx；真timeout訓練未提交rollback／pause/cancel/resume／加密restore7PASS+legacy43PASS。
- quality_repair_rules／quality_rule_selector：共用風險review、isolatedimmutable候選及origin exactid鎖；永續TRAIN曝露、一般approve/version旁路阻擋；明列frozen選擇執行、不在預設ACTIVE；現有QualitySetup在GUI可選真已核准ISO規則，不輸入UUID；cloneid不能冒充核准link。
- exposed-HLD descriptive protocol重播、current human Gold rebind：新人工事實後明確新Gold／新rootreview；舊failure／HOLDOUT／曝露／consumption永不重置；quality false、CI suppressed，實際FIFO驗證13+15等target PASS。
- quality_repair_gates：predeclared ROOT→unaffectedcritical-controls→fresh-HLD不可跳階；required baseline+candidate positiveTP（人物/電話/Logo/mm/customer/realmultiwork）。真frozen故障parser→正常parser→controls→freshHLD→impact→repairDEPLOY整鏈PASS。duplicate recursive validation移除但QualityReports/protocol.check_metadata仍fresh驗完整前鏈；test_quality_repair_full_chain自己的module，priorRootGold.withdraw後finalGate及activepin阻斷，11combined PASS75.507s。
- quality_repair_releases：不可變deployment+CASpointer，AUTO預檢／job／scope／推論pin；pointer換版不偷換佇列version；actualwithdrawn/criticalsame-parser quarantine舊版不自動fallback；實際encryptedrestore標記revalidation。32combined PASS。只有無repairissues才可initialbootstrap，repairDEPLOY需lastGate+impact/no pendinghighrisk。原稿/客戶/模板/active-model record不暗改。
- GUI sevenpages／原稿facts/actualexception/quality/recheck/importfailed/canvas全入口。新quality_repair_commands只是existing quality_command/QualityPanel.request內routing，無新transport/DB/worker。50pagedHLDdisabled來源、defaultunchecked、changedinputs清舊預覽、error返child、unsavedfacts/close guard。busyprogress只SQLmetadata50，不搶worker。明確品質決策有insideTx expectedreportdigest，仍不activation。
- 最新：`ui054-seven-page-gui-002.log`4PASS、`ui054-native-critical-actions-003.log`4PASS、`ui054-exact-rule-native-001.log`11PASS、`ui054-import-canvas-exact-rule-001.log`9PASS（互有重疊，不相加）。原失敗logs都保留。

## 正式歷史與限制

- 最新完成正式 `RUN-REMAINING28-QUALITY-005`：source6cd038cb6aca4544a0a9458eac859289496dc613/tree5f8fe4457cc1aec6e2521b9233428c0d95c4d251，943/943、111serialownedmodules exit0、parentexit0、sourceunchanged，GatePASS；**只證7父題的當時來源**。166附件=41text+run.json在GitHub、125PNG/PDF local例外有exactmanifest；不是所有media已上傳。
- UI053 finalizer005已執行，**絕不可重跑**；QUALITY001–004失敗／native／受控中斷保留，不能拿其finalizer結案。早期細節在archive與各run。
- run_evidence使用serialfreshownedmodule harness、強QApplication/精確catalog/120s每module/ownedprocess終止；不能編輯受測source/tests/tools/acceptance於正式run期間，docs-only CP可。
- 全部品質fixture是明確寬鬆policy的合法作者合成安全流程；不是生產準確率校準／nativeIllustrator／Windows16GBRTX5050VivoBook／實印／獨立覆核。先完成其他未阻擋軟體，不虛報這些證明。
- 實際數學／sklearn1.7.2、NetworkX3.5、MLflow2.22、AWS公開設計/Tesseract5.5依據與hash在 REMAINING28_ENGINEERING_BASIS.json／UI054 plan；沒有新增SDK/雲服務/神經架構。Semantic用本機字元NaiveBayes及成熟語意/電話套件。
- 詳細本段歷史：handoff-history/ACTIVE-20261016-UI054-DESIGN-TO-NATIVE-GUI.md；只按需讀，別再整份展開。
