# 本機離線原生讀取開發版

目前來源版為 0.1.0-beta.3.dev2。AI／PDF／SVG／EPS 經本機 Adobe 引擎讀取，每份文件使用獨立 Windows AppContainer，網路能力為零，禁止建立子程序；驗證失敗便停止，沒有 COM 或 Inkscape 退路。一般「加入檔案 → 開始判讀」即可使用，不會開啟 Illustrator 視窗。

引擎、Python 執行副本、字型及診斷都在 Git 倉庫外。本機 `.local/review-native.json` 只記錄執行環境與清單雜湊，已忽略，不上傳 GitHub。換電腦需以本機／隨身碟提供引擎和字型，再重建環境；GitHub 僅有程式與匿名驗證資料，不含 Adobe 軟體。

新環境準備工具是 `tools/windows_review_dev/prepare_native_reader.py`。指定 `--engine`、Python 3.11 的 `--python`、`--fonts`、`--crt`、新的 `--target` 及新的 `--config`。所有位置必須為本機正常資料夾；已有目標或設定時停止，不覆寫。只支援已驗證的 CC 2020 引擎雜湊，其他版本拒絕執行。啟動時可用 `TEMPLATE_AI_NATIVE_CONFIG` 指向設定，預設為倉庫 `.local/review-native.json`。

完成準備後使用 `START_REVIEW_WINDOWS.bat`。診斷可傳入 `--diagnostics-dir` 本機目錄；原生診斷另保留在引擎環境的 `jobs`。本輪實測每文件約兩分鐘，初始化、檢查與退出均在處理時限內；尚未作效能優化。取消或關閉判讀程序會終止所屬原生工作。

畫面使用 Adobe 輸出的 PDF。作品分區與文字框仍是待核對候選；衍生 PDF／SVG 的字型宣告不冒充原始 AI 可編輯結構。遇到原生替代字型則停止並列出缺字型，不默默換字。無文字文件的未使用預設字型參照僅留診斷。

本輪已驗證指定私人樣本與合成雙畫板 AI 的讀取、保存與重新開啟；其他格式、錯誤情境及 GUI 回歸狀態以部件 STATE 與最後報告為準。沒有新安裝包、標籤或 Release。歷史 COM／USB 方案不代表這個版本的環境資格。
