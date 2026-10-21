# 當前精簡交接

2026-10-21：da809cf5／run39612727807正式Windows建置在來源測試失敗，未產EXE、未tag、未發布。176預定、169PASS，input模組12/19後180秒程序watchdog。原始證據見releases/v0.2.0-beta.1/windows-native-003-failed。新CI設定將全部原ID按每程序至多4例分組，同桌面serial1、原180秒不變，原工具/產品/測試不變；原5安全案例新入口5/5PASS跨2程序，刻意失敗負例正確拒絕。見grouped-qt-config-001。下一個正常release-request分支提交不能帶[native-tests-only]標記；仍須176完整通過、實際凍結EXE及兩次下載驗證才可發布。精確來源77e215440d7e4fe1aaa9fd49b143acbb8dc17c14，run39619925888已有RUNNING原生回執，CP-WINDOWS-QT-GROUPS-001已獨立讀回38項REMOTE_VERIFIED。候選後的dev僅交接收據變更，不觸發額外Windows建置。

已完成當前來源資格：RUN-WINDOWS-BETA-FINAL-LINUX-001，softwarePASS1963與原GUI27；原5外部未知保留overallFAIL。CP-20261021-WINDOWS-BETA-FINAL-SOURCE-001快照a697fb7a，REMOTE_VERIFIED5388條、369正式附件及原始執行資料，增量基底bea79a10；嚴格require-evidence/publication-scope實際PASS172/166/75/1963，進度delta全0。原1958ID與27capture script/command/deadline均保留。Windowsbea79/run39607635193診斷176/176PASS、16健康、0runtime；單獨3格式輸出PASS7.575s；這是diagnostic不是EXE。

Linux資格是明確逐模組重驗，**不是一次全綠批次**：raw linux-regression-006四並行1961PASS，SourceWatch清理時真實MainWindow關閉通知等待180秒，2未完成，保留FAIL。相同code/fixture全部byte一致的linux-source-watch-isolated-006整個11案例在原180秒內33.855sPASS。linux-regression-006-requalified選取259個實際健康模組、1963唯一PASS；module-revalidation.json逐case來源、原錯誤及兩份inputhash保留。新qualify_module_revalidation.py拒絕混入舊source（負例PASS），adopter增加來源hash/真實原record比對並將12份inputJSON納入369附件。不改任何案例/時限或baseline；四並行的該GUI清理模組不算已資格化，選用其獨占成功結果。stock-captures-006原27全PASS，單獨執行，與原始full及重驗都未並行。

原Windows失敗保留windows-native-001/002-failed：PID0在Windows會殺程序（改既有psutil）；progress rename sharing conflict（重用atomicJSON有限重試）；合成字型/短路徑前置；SQLite fixture先刪temp後addCleanup才關other（doCleanups前置）。Inkscape/bin曾遮蔽Python，workflow明確選setup-python3.11。native-diagnostic-001/002有入口錯誤，Root sys.path已修正，sourcebea79診斷真實通過。Windows模組現在serial1（同桌面/剪貼簿/字型資源），maththread1、原180秒不變。

新正式run已在REQUIREMENTS166完成範圍引用，條款/旗標/父題不變。真實作品、用戶Windows硬體/效能、實印、新手/隔離等原資格仍待本機回饋，不因HostedWindows或合成升級。教學/知識庫草案未採用，網頁手機延後。

空間評估完成並GitHub讀回：docs/dev/maintenance/STORAGE_ASSESSMENT_20261021.md、JSON與盤點時226列CSV。81失效開發ZIP連結但Git歷史可追溯，55舊實體ZIP19.42GiB只是待hash/獨有內容/還原核對候選；兩保留包hash/CRC/base2/2PASS。本輪不清空.checkpoints/tmp/正式證據/.git/私人資料。Codex環境啟動指引草稿已保存待設定review/save/publish，與程式Release不同，不阻塞當前runner。按STATE/本交接及實際run接續，不重讀整串聊天。
