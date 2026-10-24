# 當前：原始碼直接啟動與三項回饋修正，待 Windows 本機驗證

先讀 STATE.review_source_maintenance、[修正報告](bugfixes/review-source-maintenance-20261024/REPORT.md)與[原始碼啟動／更新](analysis_review_ui/SOURCE_RUN_AND_UPDATE.md)。分支feature/review-tool-v0.1.0，source開發版0.1.0-beta.3.dev1；本輪不打包、不發布、不改舊tag。

修正：已知AI PDF相容提示頁不當作品、混合頁保留正常部分與固定安全錯誤指示；暗系統下選單明確淺色；GUI subsystem＋只恢復父重導worker管道、介面字型選擇。新版判讀口徑3，不靜默接舊分析，原稿及人工修訂保留。

本輪9模組隔離：141PASS/1Windows pythonw skip/0failure/0error；真正source Qt35checks PASS、實際QProcess與兩語OCR通過。Linux source不當Windows/EXE驗收。新START_REVIEW_WINDOWS.bat是判讀入口，PREPARE_WINDOWS只準備固定依賴；舊START_WINDOWS是完整產品。Git更新指定提交，避免手工混換檔案；引擎與模型沿用本機明確路徑，不必每次下載。

下一步在Windows準備原始碼環境，驗pythonw/字型/背景IPC再使用本機作品副本；雲端無法存取C槽。發布EXE相關修正仍需未來真正Windows frozen驗收。PRIVATE作品/字庫/硬體/AI訓練/印前及舊完整產品資格不升；原未提交timeout/adopt成果保留，不讀私人作品、不新付費。

已發布review-v0.1.0-beta.2仍是source6fd0b1435a8ebd1f384b2f76ceaa85dcbc2fba60／run40057767083：Windows270與真EXE40、兩次下載校驗PASS，僅屬該舊成品。STATE.review_tool_release_request及[原交付報告](releases/review-v0.1.0-beta.2/DELIVERY_REPORT.md)保留，不以舊資格覆蓋本輪新source。
