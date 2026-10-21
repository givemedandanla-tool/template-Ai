# 接手：來源／證據GitHub已核對，待Windows建置與發布

正式CP-20261021-WINDOWS-BETA-SOURCE-002已獨立Git讀回11713條、355附件全涵蓋、隔離還原PASS，require-evidence publication-scope PASS（172要求／166完成範圍／75父題／1958測試）。新source run已完成；不要再重跑Linux或prepare舊CP。現在只推最終closure HEAD到精確release-request/v0.2.0-beta.1，再查Windows171／真實EXE／Release及下載核對。API網路草稿未生效、尚無Windows回執，不得宣稱發布。

# 接手：Linux驗證全通過，Windows EXE仍未發布

使用者已明確授權GitHub發佈Windows x64 beta；不合併main。依STATE.windows_release、releases/v0.2.0-beta.1/STATUS.md與next_tasks繼續，不重問授權，不要求私稿／字型／API key。版本0.2.0-beta.1；發佈維護規則已採用。

- 固定程式／測試來源570ecebe，code manifest 3cd6da4bbe162df29746c17e12e55992a4eabc09042f4492896a0b54b9c9c95f；獨立Git來源讀回.checkpoints/release-beta-source-005/native-readback。
- full004：1958／1958PASS、258健康模組、0runtime、source unchanged；原1942保留、新16。stock004：原27／27PASS，原腳本／斷言／deadline不改，單獨執行。保留.cache/release-beta-stock-004供原圖核對。早期中斷／失敗保持原狀。
- 正式RUN-WINDOWS-BETA-LINUX-001已採錄真正同源full004＋stock004＋獨立Git，355附件；軟體PASS、整體FAIL仍為原5外部未驗證，不能改生產資格。166完成範圍證據已更新，需求／父題／AI8包資格不變，views與快照已產生，普通治理check PASS。
- 已完成增量CP-20261021-WINDOWS-BETA-SOURCE-002，base570ecebe；涵蓋全部新run附件、release文件、.github、requirements-build、README、決策及prepare helper。既有docs/dev/non_code_audit/prepare_scoped_checkpoint.py支援--run-path／--extra-root，缺root負例PASS不改STATE。
- 實際push後，用倉庫內docs/dev/releases/verify_git_readback.py --expected HEAD --checkpoint CP-ID --ack。重用標準ack，原生Git實際commit/tree比對，不冒稱REST。收據與STATE closure再次push／讀回，require-evidence publication-scope須PASS。
- 然後才推最新HEAD到release-request/v0.2.0-beta.1，Windows171適用案例全PASS無skip＋實際EXE兩階段，才tag／Pre-release／上傳／下載逐檔校驗。Linux-only案例不當Windows PASS。

Git正常，GitHub API仍被此雲端HTTP政策擋住；API／uploads／objects主機草稿已保存但未生效，需在平台環境設定套用後再確認既有GitHub權限。目前舊請求ref626ff6b2不代表Actions已啟動，沒有release-evidence回執／可驗證EXE。不得宣稱已發布。未新增付費服務、試用或子代理。

真實作品／指定Windows硬體／實印／新手／網路隔離資格維持未驗證；私人資料留本機，手動安全ZIP回Codex。教學／知識庫草案待核對，網頁手機延後。

CP001僅本機archive完成、/tmp還原ENOSPC，未建立正式record，不可ack或冒稱成功；失敗歷史見checkpoint-attempt-001-failed.json。helper改在workspace .checkpoints做隔離restore，不刪原檔、不需新資源；後續用唯一CP002。
