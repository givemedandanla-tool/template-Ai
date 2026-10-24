# 官方原生 AI 擴充：Windows 隔離驗證未達整合條件

使用者要求先以合成資料驗證 Inkscape 官方原生 AI 擴充，可行後才接入 review-tool；環境只有 Inkscape，不要求安裝 Illustrator。本輪已完成隔離可行性測試、全新目錄重建驗證及 Windows 回歸；因文字遺失，產品整合尚未執行。不能宣稱 review-tool 現在已能直接讀取這類 AI 的完整作品。

## 固定來源與隔離環境

官方 extension-ai／inkai 1.2.0，固定提交 `1a5f42a0b0407fc869e032420570682048810108`，上游標示 Pre-Alpha。來源封存及兩個 wheel 逐 SHA256 驗證，執行前將全部 inkai Python 檔逐 byte 對照封存；實際數量見 feasibility.json。未改寫第三方來源。

重用 Inkscape 1.4.4 內附 Python 3.12.12、inkex 1.4.0、zstandard 0.25.0、Pillow 12.0.0、lxml 6.0.2。缺少的 pypdf 3.17.4、pyparsing 3.2.5 只下載固定 wheel，在獨立程序讀取；不修改 Inkscape、既有 venv 或私人會話。分析子程序以 -I 執行、45 秒上限並拒絕 Python socket 操作；此為程序隔離，不宣稱完整 OS 沙箱。準備階段只下載公開來源。

## 合成驗收結果：5 PASS／2 FAIL

| 情境 | 結果 | 核對 |
| --- | --- | --- |
| 純原生矩形 | PASS | 路徑、紅色填色、180×90pt 尺寸一致 |
| PDF 提示頁＋zlib 原生矩形 | PASS | 讀到內部矩形，未把提示文字當作品 |
| PDF 提示頁＋zstd 原生矩形 | PASS | 讀到內部矩形，未把提示文字當作品 |
| 純原生矩形＋文字 | FAIL | 只剩矩形，文字遺失 |
| PDF 提示頁＋zlib 原生矩形＋文字 | FAIL | 只剩矩形，文字遺失 |
| 損壞原生來源 | PASS | 拒絕、未產生成功 SVG |
| 只有提示頁、沒有原生資料 | PASS | 拒絕、未產生成功 SVG |

所有檔案由工具現場生成；未使用私人作品、客戶資料或私人字型。文字為明確合成標記，沒有嵌入任何字型檔。兩個文字情境轉換函式正常返回，但 SVG 沒有 text 元素、沒有文字內容，也沒有新文字輪廓，唯一 path 仍精確等於原矩形。上游對 To／Tp／Tf／Tr／Tx／TO 回報未實作；不能把這種部分輸出算成功。原始輸入全部 byte/hash 不變。

初始隔離環境與全新重建環境均重現上述 5／2。正式 probe 退出碼 2 表示驗收不通過，不是已整合成功。完整匿名結果見 feasibility.json；原始 stdout／stderr、生成 AI／SVG、下載源碼、wheel 和第三方測試檔僅留本機，未同步。

## Windows 回歸與決策

現有 review-tool 回歸重新執行：30 PASS／0 skip／0 failure／0 error（PDF17、Jobs10、失敗介面3）。產品原始碼、測試原斷言及既有 requirements 未變；不將這 30 項 PASS 掩蓋原生匯入的 2 項 FAIL。原先 PDF 提示頁攔截仍保留。

依「可行後整合」條件，本輪不接入會遺失文字的匯入器。下一步需先補齊／採用有實測文字支援的原生轉換，並驗證現代 AI 文字、字型缺失、圖片、透明度、多畫板與幾何／尺寸保真；這些目前不能稱已支援。沒有要求使用者購買或安裝 Illustrator，也未自動安裝任何系統擴充。

可重跑工具見 tools/windows_review_dev/native_ai_feasibility/README.md。其用途是有明確通過／失敗的整合門檻，不是產品入口；另一台 Windows 電腦可由指定分支按固定版本重建。原生資料解碼成功不等於完整作品、OCR、印刷或訓練資格。

同步僅包含工具、固定來源資訊、匿名證據、精簡交接、部件狀態與 checkpoint。不合併 main、不打包發布，舊 beta.2 與共享歷史 AGENTS／STATE／WORK_LOG 保持不變。
