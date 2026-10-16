# 當前接續（2026-10-16 UTC）

- `/workspace/template-Ai`；`dev/v0.1-first-version`／PR2，不合併main。使用者目標：持續至剩餘28父題原文完整實作＋SELF驗證；**目前僅歷史6/28完成**，不可在7/28停工。原75/固定70/CORE/GOV分開計，不拆題提高完成率。
- 核心：零例行問答／每可恢復包及≤10分鐘checkpoint→GitHub commit/tree/blob讀回→收據也push；一般輸出≤1600token，按需搜尋讀段。無多代理、EXE、paidAPI/新CI；commit `[skip ci]`。UI048最後，UI056D/REV03延後；不宣稱Windows/nativeAI/16GBRTX5050VivoBook/實印/獨立覆核。

## 現在先做

1. 新正式來源checkpoint `CP-20261016-REMAINING28-UI053-QUALITY-SOURCE-003` 正準備；939已知測試，145requirements pending，7parents/71原條已登錄但未完成。先gitstatus/clock/CP與收據，不能虛構SHA。
2. Native讀回新source後將commit/tree複製`.checkpoints/formal-source/RUN-REMAINING28-QUALITY-003/`，執行`tools/run_evidence.py --run-id RUN-REMAINING28-QUALITY-003 --source-commit <actualSHA> --commit-json <baseline>/commit.json --tree-json <baseline>/tree.json`。QT_QPA_PLATFORM=offscreen PYTHONPATH=tests XDG_CACHE_HOME=/workspace/.cache。
3. **Formal期間不改app/tests/tools/acceptance**。新runner每個module獨立owned程序、序列執行/120s；live`.checkpoints/formal-live/<run>/test-progress.json`、JSONL與modulemetadata。等待actualexit，檢查939/939PASS、no missing/skip、Qt0、capture0、sourceunchangedTrue及7parent/145digests。不能只看進度就完成。
4. 僅actual003PASS後執行`docs/dev/wip/UI053_FINALIZE_QUALITY_003.py`（守衛939/145/71/7，移精確binary到localmedia、metadata GitHub）；舊002helper禁止執行。然後render、progress snapshot對BEGIN、fullmetadata CP/push/nativeACK，`dev_governance check --require-evidence --publication-scope`真PASS後才STATE publicationPASS，收據push再Gate。詳完整publicationpolicy `FULL70_PUBLICATION.json`，不套任意9附件例外。
5. 第7/28里程碑保存後繼續UI054原11與其餘21；先145改pending/保留歷史證據再修改source。下一計畫`UI054_EXECUTION_PLAN.json`。新draft需review+真正測試再整合，不能當已實作或盲覆寫activecode。

## 已知證據／失敗

- 最後完整PASS仍Coverage001：source2b054d7d2124268aa49aca918d4bb2bcd218a8d0，798/798、144claims、6parents62原條，38text/117localmedia、GatePASS。已完成UI046/047/049/050/051/052。
- QUALITY001 source233e9ea4edc8d8927e482c3f0d362a78bd2ced5d：935/934PASS/1舊watch等待同步FAIL；sourceunchanged/Qt0，actualexit1，captures未執行(sentinel1)，完整失敗run保留。只修test等待實際candidate/last_result＋受阻FIFO，11watch003PASS。
- QUALITY002 sourcef7fd4536acf1ec3834027384e6951341e1506db4：nativeSIGSEGV exit139，684completed全PASS、685th impact-preview test開始後中斷；無run.json，**不虛構PASS／Qt0**。精確partialjournal/stack/native-interruption.json已保存；sourceunchanged核實。堆疊指向RuntimeSupervisor.eventFilter但根因未確定。
- 新nativeguard：closed/deletedwindow/deletedwatchedWidget不做Qt ancestry；actualdeletedchild/late-shutdown regression。isolatedGUI4PASS，guard+GUI12PASS。新serialmoduleharness獨立真Qt/同catalog而非skip；失敗/nativeabort/deadline/owneddescendant清理3測試，真3module整合15PASS/0runtimeerrors。已知939tests，尚無新全正式PASS。

## UI053／UI054

- UI053完整9原文/SHA與121tests映射已在REQUIREMENTS＋REMAINING28_CLAUSE_AUDIT；actual source-only frozenparser/CharacterModel/approvedrules/Tesseract5.5 eng+chi_tra/Logo全組件/映射；合法immutableGold/相關群組防洩漏/分層counts+Wilson/固定公平A-B/FIFO持久例作/原稿Gold-AI/批准撤回/歷史跨批隔離＋fingerprint防換ID。模組quality_*.py，詳WORK_LOG/工程basis，不再讀整串聊天。
- 七parentaggregate capture smoke002PASS（包括qualitycapture8畫面）；actualhostFIFO4.01s/parent201MiB只是合成安全流程，非實際生產準確率/nativeAI/Windows硬體證明。正式仍待003全capture。
- UI054原11計畫＋實際CPython/sklearn1.7.2/MLflow2.22/NetworkX3.5/AWS公開source/hash依據持久；docs/wip/UI054_QUALITY_REPAIRS_DRAFT.py與UI054_REPAIR_TRAINING_DRAFT.py僅ast語法檢查，**沒import/執行/整合**。選擇復用AUTO_JOB operation/原claim-finish共享lease/子程序，不建新scheduler；root/control/已曝露HLD描述replay/新獨立HLD/isolatedapprovedrules/actualdeployment+rollback/GUI及所有原稿入口仍未完成。不得拿draft閉合UI054。
- .venv Python3.12.14／Qt6.8.3／NetworkX3.5，Tesseract5.5與localpacks已存在，無需重新onboarding或安裝。先前setup/runtime skills已用，當前catalog不可用不重查。
