# GUI 最後驗證與結案接續

本輪結案已完成；以下為當時的恢復步驟，最新採用來源／驗收與checkpoint以STATE及GUI_OFFLINE_FINAL_REPORT_20261020.md為準。

這是結案流程指引，不是完成聲明。STATE／實際 run.json／REMOTE_VERIFIED 收據優先。

- 最終程式來源：`4ebfff6f676b236519c4a1ba2b0cb192acbffea3`；code manifest `30ac2af0c791906198687628b70df2e6ed0ebed459ffdbb1409820dc94eb1f35`。後續只有證據／文件／收據 commit。
- 正式 `RUN-GUI-OFFLINE-ALL-006` 已保存1850／1850逐項PASS、236健康模組、runtime-errors空；仍須等待capture鏈與run.json。此環境owner exec session14689；先查是否還在跑，不重複開整套。
- `RUN-GUI-OFFLINE-NATIVE-005`：desktop12＋原parent3 PASS，11張圖；`RUN-GUI-OWNED-NATIVE-005`另3頁／Tab PASS。來源圍欄一致，永久Git保存，不再重跑。
- 此環境`/tmp/template-ai-finalize-gui.py`是metadata helper，只有完整1850／0runtime／capture0／來源不變才會採用；fresh環境沒有此檔時，依下列步驟用既有治理工具操作，不能以hash或舊PASS代替新證據。

1. 核對完整006的software_execution_status PASS、1850計數、236模組健康、0runtime、capture_exit_code0、來源不變，以及所有附件bytes／SHA；capture.log不得有未處理Traceback。核對原1798IDs保留、新52，所有新CORE-090十條claims PASS。原外部未驗條款應與INPUT-INTEGRATION-ALL-007相同。
2. 額外114件GUI tooling／skill與凍結Git樹的對帳在006 supplemental-source-before；逐檔驗後寫after。2個Windows launcher已在正式code manifest內。不要修改凍結tooling檔。
3. REQUIREMENTS只將本輪前baseline已完成165筆及CORE-090改VERIFIED/completed true/SELF_VERIFIED，evidence_run指006；逐條verify_acceptance。原3PARTIAL/3DEFERRED及AI8包50條完整真實資格8部分/0完整不改。
4. 產生CORE090十條audit、GUI_OFFLINE_FINAL_REPORT、精簡ACTIVE_DEVELOPMENT_HANDOFF；更新AGENTS/README/STATE及計畫狀態。用dev_progress snapshot對GUI-OFFLINE-BEGIN，render後dev_governance check --require-evidence --publication-scope。172登錄：topic69/75、core90/90、gov7/7；其他6保留部分/延後。完整run整體FAIL若僅舊外部資格，必須與software PASS分述。
5. 最終checkpoint prepare的base直接讀git rev-parse HEAD，不手填猜測。先等capture全部完成，避免snapshot包含仍在追加的log。commit/push既有dev分支，git_readback --checkpoint精確讀回，持久化收據及STATE，再讀回metadata commit。不merge main，不做EXE。
6. 磁碟不足時僅可釋放已REMOTE_VERIFIED且SHA吻合的本機ZIP cache，或完整006完成且公開附件逐hash已驗後的本次owned synthetic evidence-workspaces cache；寫釋放稽核，不能碰私人資料／來源／公開附件。不得為空間刪測試或證據。
7. 雲端設定草稿先重新讀取，完整掃/workspace含隱藏/linked git，明確區分template-Ai專案與UIUX工具依賴／cache。以實際最新HEAD保存專案ref及GUI start_skill，保留網路／秘密／runtime requirements。只存草稿不等於平台已發布；本次環境已有native驗證。回存不含秘密的草稿收據，Git讀回。

既有失敗全部保留：ALL001中斷、ALL002四FAIL/9Qt例外、ALL003目錄防覆寫拒絕0執行、ALL004781PASS人工收斂中斷、ALL005572PASS因事件observer例外中斷。typed Qt guards的target41PASS。混合程序候選計數問題已查明GUI與fresh-thread字面不同且fresh stamp吻合stored；Gate正確阻擋，原worker字面未直接插樁；公開診斷在qa/targeted/GUI-FONT-CONTEXT-DIAGNOSTIC，不改Gate或宣稱Windows資格。

交付用DESKTOP_WORKSPACE_USER_GUIDE、LOCAL_DESKTOP_QUICK_START、OFFLINE_SUPPORT_USER_GUIDE。本體離線，使用者手動匯出安全ZIP；私人作品／字型／客戶原文／資料庫留本地。四類暫擱不索取私稿；網頁／手機／EXE維持延後。
