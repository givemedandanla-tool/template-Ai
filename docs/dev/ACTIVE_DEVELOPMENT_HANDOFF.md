# 交接：Windows相容性修正，完整回歸進行中

2026-10-21。使用者已將倉庫改公開，要求重試Windows EXE發布，並評估雲端文件是否應刪。**尚未建立EXE、tag或Release；本輪刪除0檔。** 不合併main、不覆寫tag、不改帳務或新增付費資源。

目前程式修正來源429bd302已推送dev/v0.1-first-version並獨立Git讀回；新5個安全測試及既有7個證據工具測試PASS。code manifest以STATE.windows_release為準。linux-regression-005已完成1963/1963PASS、259健康模組、0runtime且來源未變；原stock-captures-005已完成27/27PASS，腳本/命令/deadline未變。RUN-WINDOWS-BETA-REPAIR-LINUX-001已採錄同源完整執行與355附件，166完成範圍證據引用已更新但完成/驗收不變。下一步完整新run遠端checkpoint與嚴格publication gate，再送Windows176/EXE。測試中不改產品/tools/tests；文件checkpoint不改code manifest。完成後單獨執行原27個stock captures，指令：QT_QPA_PLATFORM=offscreen .venv/bin/python docs/dev/pre_download_audit/run_stock_capture_audit.py --output docs/dev/releases/v0.2.0-beta.1/stock-captures-005 --workspace /workspace/template-Ai/.cache/release-beta-stock-005。不能與完整回歸並行。

公開重試3次實際結果保留：前2次建置依賴失敗；第三source35d133cd/run39592388094治理PASS、Windows171預定131完成129PASS2ERROR、40未完成，報告在releases/v0.2.0-beta.1/windows-native-001-failed。真實原因包含Inkscape附帶Python遮蔽setup-python（workflow已修正）；Windows的os.kill(pid,0)會殺程序（改既有psutil）；進度檔rename分享衝突（重用atomic helper，限定錯誤有限重試）；合成測試的Noto字型與短路徑假設（使用實際字型及resolve，不放寬原斷言）。input-integration deadline未解釋，未提高期限；加入Windows近原截止時間的一次stack dump及有界失敗log，若再現讀實際stack。

Linux1963及原GUI27全PASS後，用docs/dev/non_code_audit/adopt_verified_execution.py採錄新正式run；readback用.checkpoints/WINDOWS-NATIVE-REPAIRS-SOURCE-001/native-readback。dev_governance render、dev_progress快照、嚴格require-evidence/publication-scope、包含全部新附件的增量checkpoint和獨立Git讀回後，才推精確候選到release-request/v0.2.0-beta.1。Windows矩陣現在16模組176項，新增5項、不刪舊171；全部PASS無skip、真正frozenEXE兩階段、tag/Pre-release、公開後實際下載逐檔核對，才稱發布。

此雲端api.github.com仍Forbidden；公開GitHub HTML與原生Git讀寫可用，release-evidence/v0.2.0-beta.1回執可fetch。不要索取API key、繞proxy或將API限制當完全不能運作。舊run39587259422是啟動前帳務/支出限制；公開後標準windows-latest已真正執行。具體帳務原因未核實。

空間評估已完成並REMOTE_VERIFIED：docs/dev/maintenance/STORAGE_ASSESSMENT_20261021.md、JSON、226列CSV。81失效ZIP連結的歷史commit/tree可追溯；55舊實體ZIP共19.42GiB只是待hash/獨有內容/還原核對的候選。兩個保留包hash/CRC/base核對2/2PASS，非全部歷史包驗收。不清空tmp/checkpoints、正式證據、Git或私人資料。啟動指引草稿已保存修正過期EXE延後/LOCAL_ONLY，尚未套用或發布環境。

原要求172、父題75、166完成範圍及AI8包真實資格不變；舊來源1958+27 PASS僅對舊3cd6da4b，不能當修正程式新來源通過。真實作品、使用者Windows硬體、實印、新手及隔離資格待本機回饋，私人資料留本機。教學/知識庫草案未採用，網頁手機延後。新對話讀STATE與本交接，保留正在執行的程序和原始失敗結果。
