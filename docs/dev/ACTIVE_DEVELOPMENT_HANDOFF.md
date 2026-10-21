# 交接：修正版本正在原生 Windows 建置

2026-10-21。使用者已將倉庫公開，要求重試EXE發佈，並評估雲端文件是否應刪。**目前未建立EXE/tag/Release；沒有清理既有資料。** 不合併main、不覆寫tag、不調帳務或啟用新付費資源。

目前原生請求精確來源fac43f21072113abc95355c531e104921aca040a，已push/readback；run39601136869實際RUNNING，https://github.com/givemedandanla-tool/template-Ai/actions/runs/39601136869 。branch release-request/v0.2.0-beta.1；dev後續只存交接。原生結果在release-evidence/v0.2.0-beta.1/latest.json與來源子目錄，可git fetch讀回。api.github.com仍被此雲端policy擋，但公開HTML及Git可用，無需API key或繞proxy。觀察腳本.cache/release-public-retry/watch_receipt.py及owned session75929仍可能運作，先查現況，不重複觸發runner。

實際code來源429bd302，manifest435dc0d88501c6de7394378ab26c535a0da9e6e5a7228747cd67cd0d2f08b70f。linux-regression-005已1963/1963PASS、259健康、0runtime、sourceunchanged；stock-captures-005原27/27PASS，沒有和完整回歸並行。原1958測試ID全保留，原27個capture腳本/命令/deadline不變；新增5安全案例。source-compatibility-005.json可核對。

正式RUN-WINDOWS-BETA-REPAIR-LINUX-001採錄真實同源執行+355附件；softwarePASS，原5外部未驗證保留整體FAIL。166完成範圍重新引用新run，原條款/完成旗標不變，進度delta全0。CP-20261021-WINDOWS-BETA-REPAIR-SOURCE-001快照ded89cf6，REMOTE_VERIFIED412項，增量基底308491fc；完整Linux4946項另有CP-WINDOWS-REPAIR-FULL005-001。嚴格require-evidence/publication-scope已PASS1963。不重跑已通過Linux/GUI，除非有新source/失敗或具體風險。

下一步等待本次Windows16模組176項全部PASS無skip，真正frozenEXE兩階段也PASS，才建立不可變v0.2.0-beta.1tag/Pre-release、上傳ZIP/manifest/SHA256、公開後實際逐檔下載校驗。確認原生回執與tag解參照來源、實際公開附件，才給下載連結。若失敗讀有界unittest/progress/stack/packaginglog，按根因修正，不停用測試、換假視窗或放寬期限。

三次舊public run失敗保留：5fc96/b0e依賴安裝錯；35d133/run39592388094為Windows171中129PASS2ERROR40未完成，報告windows-native-001-failed。已確認Inkscape附帶Python遮蔽setup-python，workflow明確選3.11。真實Windows os.kill(pid,0)會殺程序，程式改既有psutil；progress重用atomicJSON並有限分享衝突重試；合成測試用實際可用字型及canonical路徑，原缺字型/版本/hash斷言不放寬。input-integration舊deadline未解釋，若重現讀新增Windows近原截止時間的一次stack，不提高deadline。

空間評估已完成並REMOTE_VERIFIED：docs/dev/maintenance/STORAGE_ASSESSMENT_20261021.md、JSON及盤點時226列CSV。81失效ZIP連結的歷史commit/tree可追溯；55舊實體ZIP19.42GiB只是需hash/獨有內容/還原核對的候選；兩個保留包hash/CRC/base2/2PASS。不清空tmp/checkpoints、正式證據/Git/私人資料。啟動指引草稿已保存改正過期EXE延後/LOCAL_ONLY，尚未套用或發布環境。

原172需求/75父題/166完成範圍與AI8包真實資格不變。真實作品、使用者Windows硬體、實印、新手/隔離資格待本機回饋；私人資料留本機。教學/知識庫草案未採用，網頁手機延後。沒有子代理、外部模型或新增收費服務。
