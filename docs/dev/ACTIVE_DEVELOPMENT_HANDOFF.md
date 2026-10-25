# 當前：review-tool 統一 Adobe 解析，先稽核網路行為

使用者已授權整合已驗證的無視窗 Adobe 讀取方案，後續明確要求 AI／PDF／SVG 優先統一由 Adobe 原生部件解析，通過回歸後移除 review-tool 的 COM／Inkscape 重複路徑。仍保留其他部件需要的共用程式。

先讀 [本輪 STATE](windows_review_environment/adobe-headless-20261025/STATE.json) 與 [契約](windows_review_environment/adobe-headless-20261025/CONTRACT.json)。分支 feature/review-tool-v0.1.0，開工基底 7df7a26f3b1995a73e58626edd20bf9c8d77314a。目前僅登錄要求，產品尚未改動，網路行為稽核正在進行。

前輪本機隔離實驗證實指定 CC 2020 引擎可逐文件背景讀取與 PDF 輸出，合成與指定私人樣本在補齊本機字型後與同引擎主機參照一致；不等於所有 AI／PDF／SVG、字型或無網路嘗試已驗證。本輪需 native 字型替換檢查、獨立程序、取消／逾時、原檔不變與新 PDF 驗證，並做 Windows 產品回歸。

最新指令要求極嚴格稽核所有採用部件的自動連線／遙測。先做來源／簽章與靜態連線能力盤點，再於無網路隔離環境觀察原生連線嘗試並設正向控制。現有 Python offline guard 不約束原生 DLL／外部程序，不能當作原生斷網證明。使用者提供的作品、字型、Adobe 引擎、原始診斷都只留本機。

依 SYNC_POLICY 僅同步部件程式、合成測試與匿名交接；共享歷史 AGENTS／STATE／WORK_LOG 不重傳。全專案歷史 governance check 在開工前已因舊證據過期失敗，不升其資格。本輪尚未完成整合或回歸。不合併 main、不打包發布。舊 COM／USB 交付保留於歷史 checkpoint，不能當新 Adobe 無視窗方案的驗收。
