# 交接：Windows診斷與Linux重新驗證同時執行

使用者要求公開template-Ai後重試Windows EXE發布，另評估工作區用途/刪除建議。**尚無已驗證EXE、tag或Release；未清理既有備份/私人資料。** 不合併main、不強推、不新增付費資源/模型/子代理。

當前產品原始碼的Windows存活探測與atomic progress修正已完成；舊source435dc0d8的Linux1963/1963、259健康、0runtime及原GUI27/27全部PASS，正式RUN-WINDOWS-BETA-REPAIR-LINUX-001與412項CP/ded89cf6已REMOTE_VERIFIED、嚴格gate曾PASS。這些是舊manifest，不能當成當前fixture/build-helper新來源已合格。

目前並行兩項（不要重複啟動）：
1. Linux完整linux-regression-006，owned session11563，source a322683a，4個獨立Qt程序，每程序OMP/OPENBLAS/MKL1thread，TMPDIR=.cache/test-tmp-006，既有4CPU/32GiB。原CLI只允許1/2，已在.cache隔離校準4程序同時運作4/4PASS後，僅擴充docs/dev/pre_download_audit/run_local_audit.py的CLIchoice到4；原案例/180秒限制不變。配置與校準報告已存releases/v0.2.0-beta.1。最近744/1963PASS，未完成；查live/test-progress.json與實際程序。跑完才能單獨stock-captures-006，不和完整回歸並行。
2. Windows診斷來源a4799a309cbd6587c0f39ff2b8a7b6f751e0f9b6，run39606517382，實際RUNNING；owned watcher84201，.cache/release-public-retry/watch_receipt.py。Git fetch release-evidence/v0.2.0-beta.1/latest.json與來源目錄；公共Actions HTML也可讀，api.github.com仍被雲端policy擋。此為[native-tests-only]模式，不建EXE/tag/Release。先執行原input三種格式輸出案例單獨probe，再原176全部Windows模組逐一執行，原180秒不變。失敗讀package-check/native-export-probe-error.log、export-probe-*、pyinstaller.log尾端完整啟動trace。前次255e5635診斷入口只有概括錯誤，報告native-diagnostic-001-startup-failed；新入口增加excepthook與workflowTee，未改產品/測試核心。

最新正式Windows失敗fac43f21/run39601136869：176中175完成174PASS1ERROR，1未完成。windows-native-002-failed完整保留。SQLite ERROR是fixture先刪temp，addCleanup(other.close)在tearDown後才跑；tests/test_automatic_training.py現在刪資料夾前doCleanups，targeted RuntimeQueue9/9PASS。Input18項共124.75秒，最後3格式案例到模組180秒仍未完；不能先認定產品bug或任意延長時間。單例+序列Windows測試及每程序1maththread用來區分原因。源PS1與fixture已改，所以重新建立當前同源證據。原WindowsPID0殺程序/rename衝突/字型與短路徑fixture問題已在上輪改善，剩餘不能略過。

下一步：處理診斷實際root cause；若改產品/tools/tests再重建同源證據，docs/CI入口修正不改code-only manifest但須記錄實際driver。Linux006全PASS後原stock27單獨執行，確認原1958測試ID與27script/command/deadline全部保留；採錄新正式run，166完成範圍證據引用更新但資格不變，render/snapshot與全部新附件checkpoint/remote讀回後嚴格gate。最後普通提交（不含[native-tests-only]）才推release-request/v0.2.0-beta.1，正常模式仍強制完整gate→Windows176→真正EXE→tag/Pre-release→公開下載逐檔校驗。診斷PASS不是發布資格，built/published保持false直到真實完成。

空間評估已完成並GitHub讀回：docs/dev/maintenance/STORAGE_ASSESSMENT_20261021.md、JSON、盤點時226列CSV；81失效開發ZIP連結但歷史commit/tree可追溯，55舊實體ZIP19.42GiB為條件候選，未逐份hash/獨有內容/還原核對；兩保留包hash/CRC/base2/2PASS。不清空.checkpoints、/tmp、正式證據、Git或私人資料。工作區現約1.3GiB可用，tmp約102MiB，新增測試tmp已放workspace自有cache。

原172需求/75父題/166完成範圍與AI8包真實資格不變；真實作品/用戶Windows硬體/實印/新手/隔離等原5外部資格仍未知，不靠合成或HostedWindows升級。教學/知識庫未採用草案，網頁手機延後。啟動指引草稿已保存待環境設定review/save/publish，不阻塞當前GitHub runner。零例行確認，新對話從STATE/本交接/真實run接續，保留執行中程序。
