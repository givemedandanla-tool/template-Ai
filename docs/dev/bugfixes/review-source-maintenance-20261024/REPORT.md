# 判讀工具：來源模式維護與三項問題修正

2026-10-24（Asia/Taipei）。本輪使用 GitHub 工作分支維護，不打包、不發布；已發布 beta.2 仍是原來位元組。
原始碼開發版為 `0.1.0-beta.3.dev1`，來源分支 `feature/review-tool-v0.1.0`。

## 使用者可理解的結果

可以準備一次 Python／Qt／固定依賴及本機引擎，日常直接啟動原始碼版，減少每次修正都打包下載的時間。
新增 `START_REVIEW_WINDOWS.bat`，對應目前判讀小工具；舊 `START_WINDOWS.bat` 是完整產品，不能混用。
完整步驟及沿用已下載 Inkscape／OCR 的方法見[原始碼指南](../../analysis_review_ui/SOURCE_RUN_AND_UPDATE.md)。
建議由 Git 更新完整已驗證提交：Git 會傳輸差異，並保留版本與回退資訊。手動只換幾個檔案可能漏掉相依檔、資源、刪除／改名、依賴及資料契約。

## 修正與邊界

1. Illustrator PDF 相容提示頁：只對 PDF-backed AI/PDF 可見文字採完整、多訊號中英特徵；不掃 raw payload／metadata 或只看到 Illustrator 字樣就擋。直接頁面文字及後段物件／OCR 都受檢；全部都是提示頁時不產作品，回傳固定安全指示。混合頁保留正常作品，提示頁不產候選，來源維持 PARTIAL，且不授予訓練資格。
2. 更多及新增標記選單：明確設定淺色底、正常／選取／停用文字與分隔線。真實暗 palette 選單像素測試覆蓋兩個 popup；沒有藉此變更 action 的 enabled 狀態或 callback。
3. 黑色主控台：打包規格改 GUI subsystem，新增僅針對 worker／驗收模式的標準管道恢復，避免切換 GUI 模式後背景 JSON 通訊被 `stdout=None` 中斷。只接受父程序已重導的 PIPE／DISK，duplicate handle 有明確所有權，不建立或連接新 console，也不隱藏使用者原有命令列。無 stdout 的 worker 立刻 exit74，不等待逾時。主介面及 worker 選本機已安裝介面字型，不修改作品的原始字型證據，也不把 DirectWrite 警告當成作品字型損壞。

另修正 error IPC：父程序原先會丟棄具體錯誤原因；現在只接受已知錯誤 code 並映射固定白話提示，仍不轉送子程序的任意文字或私有路徑。PARTIAL 保存資訊也會顯示提示頁處理方向。
判讀口徑升為 `review-observations-3-source-compatibility`，舊人工修訂、舊版本及原稿保護沿用，不靜默把新舊結果接在一起。
偵測刻意限定已知強特徵，不能宣稱支援所有語言、轉外框或 OCR 誤字。

## 本輪實際驗證

依既有 `tools/review_release.py test-one` 與程序隔離器執行 9 個相關模組，每模組獨立程序、90 秒上限。
`validation/summary.json`：142 項執行，**141 PASS／0 failure／0 error／1 skip**；跳過的僅 Windows 原生 pythonw 測例，Linux 無法執行。
包括真實合成英繁 PDF、混合頁兩順序、PDF metadata 與 SVG 負例、明標合成 OCR 晚段、實際 QProcess 錯誤傳遞、私有文字不外傳、保存重開、Qt 介面、stdio 管道所有權與發布 guard。

另以真正 `review_app.py --release-check` 啟動來源介面：**35 項操作檢查 PASS**，ACTUAL_QPROCESS，原稿不變，實際英／繁中 OCR、預覽、標記、保存與重開通過。
`actual_frozen_executable=false`；OCR 證據是 `SOURCE_LOCAL_POSITIVE_NOT_BUNDLE_QUALIFICATION`，不冒充 Windows frozen 包內驗收。
六份真實 Qt 截圖及 proof／log 保存於 validation；其餘生成的合成工作區、模型暫存及測試資料庫留本地，以 generated-synthetic-manifest.json 留存 hash。
選單另經 150% 縮放單項 PASS；最初驗收程式未換算 DPR，修正截圖座標換算後通過，未放寬產品對比標準。

全域舊 `dev_governance.py check` 因舊證據來源資格已過期退出1；未刷新原證據或降低斷言。本輪建立精確範圍的新來源證據與 checkpoint，不冒稱舊完整產品全庫資格已恢復。
進度工具第一次收到絕對 baseline 路徑而被拒絕，改為倉庫內相對基準後成功；需求登錄新增、刪除、範圍及完成數差異均為0。

## 尚待本機驗證

目前仍是 Linux 雲端，沒有存取使用者 C 槽。Windows 原始碼啟動批次檔／pythonw、真實 DirectWrite 與 GUI subsystem 包的 IPC 尚未實機驗證。
GUI subsystem 的 PE header 與 spec guard 已加入下一次發布驗收；本輪沒有執行打包、Windows runner、Release 或下載驗收。
已發布 beta.2 的270項來源／40項EXE資格僅屬其精確舊來源，不能套用到本輪新位元組。
私人作品、使用者字庫與硬體、AI 訓練及印前品質資格不變。原本未提交 timeout/adopt 工作保留；不提交私人資料。
未啟用新付費服務、試用、API key 或額外額度；正常功能不連網下載。GitHub僅推送維護分支，不觸發已核對的發布分支工作流程。

下一步是在 Windows 準備原始碼環境，以合成資料驗證這三項，再使用本機作品副本；需要 EXE 時另開新版本，不能覆寫 beta.2。
