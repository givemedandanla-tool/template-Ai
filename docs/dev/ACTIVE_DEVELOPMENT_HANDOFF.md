# 接手：Windows beta尚未發布，最後來源回歸中

使用者明確授權發佈Windows x64 EXE供本機實測；不合併main、不開發網頁／手機／待核對教學草案。分支dev/v0.1-first-version／PR2，規則RELEASE_MAINTENANCE_POLICY.md，版本0.2.0-beta.1；依STATE.windows_release及next_tasks繼續，不讀整串聊天。

固定來源570ecebe（程式／工具最後變更094f8f9a，兩測試factory參數定位修正7d43d956）；code manifest為3cd6da4bbe162df29746c17e12e55992a4eabc09042f4492896a0b54b9c9c95f。獨立Git完整讀回在.checkpoints/release-beta-source-005/native-readback。

- stock-captures-004：原版27／27 PASS、0runtime、source unchanged，單獨執行；.cache/release-beta-stock-004影像尚須保留供正式採錄。前3次中斷／失敗保留歷史，不改成PASS。
- linux-regression-004：完整1958目前執行中，tool session52479；讀summary與live progress確認，不能把進行中當通過。source003已完成1956PASS／2未通過，兩測試注入factory固定command[3:]導致取錯module參數；只改定位--root，原逾時／取消／回滾／接續斷言不變，9＋12相關測試PASS。
- 原1942測試名稱全保留、新16；172要求／75父題與AI8包50條資格不變。正式舊RUN-NONCODE-ALL-001對新來源已過期；需用既有adopt_verified_execution.py採錄全通過的full004＋stock004，建立RUN-WINDOWS-BETA-LINUX-001。原5外部NOT_VERIFIED及總體FAIL須保留。
- 更新完成要求證據指標及views後，用已擴充run-path／extra-root的prepare_scoped_checkpoint.py做增量保存，涵蓋全部新run附件／release文件／.github／requirements-build；base用實際570ecebe。隔離還原核對、push、原生Git逐檔讀回、標準ack及收據closure，最後require-evidence publication-scope須PASS。
- Windows流程15適用模組共171案例全部必須PASS無skip，再從實際EXE驗證。Linux-only字型／symlink案例不當Windows PASS。包不含私稿／客戶庫／字型／訓練資料／開發查重工具；Inkscape及OCR外部依賴需本機就緒。

Git讀寫正常；api.github.com仍被此雲端環境網路政策擋住。加入API／uploads／objects主機的草稿已保存但未生效，需要在平台環境設定套用；不要要求私人作品或API key。舊release-request分支626ff6b2僅請求，不代表Actions已啟動；沒有release-evidence回執／tag／可驗證EXE。正式Gate完成後才推最新候選，再查Windows與Release真實結果；無法取得時保留具體阻擋，不能捏造已發布。

真實作品、指定Windows硬體／效能、實印、新手與完整網路隔離資格仍未驗證。私人資料留本機，使用者手動匯出安全ZIP回Codex；原CURRENT_PROGRESS計數按registry，不把新測試當新父題。
