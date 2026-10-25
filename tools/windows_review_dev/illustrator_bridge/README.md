# 此接口已退役

目前 review-tool 僅使用隔離原生讀取。以下為歷史說明，不適用新版本；舊接口已停止執行。參見 [本機讀取指南](../../../docs/dev/windows_review_environment/adobe-headless-20261025/LOCAL_READER.md)。

# review-tool 的 Windows Illustrator 接口（實驗性）

目的：在已安裝、已啟用且能正常開檔的 Illustrator 電腦，以本機 COM／ExtendScript 開啟 AI，另存獨立 PDF 副本供 review-tool 判讀。這台開發機沒有 Illustrator；合成邊界測試不能當真實 Adobe 轉檔通過。

## 使用

1. 取得 `feature/review-tool-v0.1.0` 的確認提交，依 Windows 開發環境指南安裝依賴，以原始碼啟動 review-tool。仍需要 Inkscape 作既有 PDF 判讀。
2. 「更多」→「使用 Illustrator 匯入 AI（實驗性）」→選本機 `.ai`。請先自行保存並關閉 Illustrator 中同一份原稿；接口拒絕重用已開啟文件，避免動到未保存操作。
3. 切換 Illustrator 處理其警告。接口不關閉字型、連結、色彩或外部指令碼提示，也不修改全域偏好。請確認原檔所需字型和連結可用；不要忽略替代字型或遺失連結。
4. 通過檢查後，副本會成為新的未判讀來源。點「開始判讀」，對照 Illustrator 核對文字、圖片、透明度、顏色與全部畫板。舊來源與人工核對不會被替換。

產物在 review-tool 保存位置的 `illustrator/<隨機工作 ID>/`，包括 `compatible.pdf`、本機指令碼及 `provenance.local.json`。它們可能含私人內容，只留本機；不要將整個保存位置加入 Git。安全問題報告不含這些來源路徑或雜湊。

上限：原檔和 PDF 各 200 MB、100 畫板、路徑 220 字元、10 分鐘等候。使用較短的本機保存位置。UNC／映射網路磁碟不是此入口的支援來源。由 Illustrator 自己處理的嵌入／連結資源與授權連線不受 Python 離線 guard 控制；此接口不包含任何上傳程式或雲端轉檔 API。

「更多」→「停止等候 Illustrator」只停止本次 helper 並拒收遲到結果，不強制結束 Illustrator。若它停在對話框，請自行處理。逾時產物不得當成功副本使用；重新執行會建立新目錄。沒有成功結果時，原來源保持原狀。

使用選配 `pywin32==311`，僅安裝於專案虛擬環境，不執行全域 post-install。呼叫不依賴 PowerShell 指令碼，不更改 Windows 執行原則。安裝一次：

```powershell
.\.venv\Scripts\python.exe -m pip install -r tools/windows_review_dev/illustrator_bridge/requirements.txt
```

多版本 Illustrator 由 Windows 的 `Illustrator.Application` 註冊決定；目前沒有版本選擇器。

## 在有 Illustrator 的電腦做合成驗收

先確認 Illustrator 能正常開啟，使用空白工作階段。以下命令會呼叫 Illustrator 建立兩畫板、矩形與文字的合成 AI，儲存時關閉 PDF 相容，再透過同一接口轉 PDF；不接受私人檔案作輸入。

```powershell
$env:PYTHONUTF8='1'
$env:QT_QPA_PLATFORM='windows'
.\.venv\Scripts\python.exe tools/windows_review_dev/illustrator_bridge/smoke.py --output C:\ReviewSmoke\new-run
```

`--output` 必須是不存在的短路徑。環境仍需依 Windows 指南配置 Inkscape。缺少 Illustrator 回傳 3／NOT_RUN；測試失敗回傳 2；自動檢查通過回傳 0／AUTOMATED_PASS。最後請在 Illustrator 與 review-tool 比對兩頁文字、矩形、顏色和尺寸，再記錄人工結果；自動 PASS 不取代目視保真。

另需實機測：已開啟原稿／未保存文件不被動到、缺字型／連結不被靜默略過、取消與逾時、不同 Illustrator 版本。此批未在開發機執行，不以合成 Adobe 物件模型冒稱通過。

## 無 Illustrator 的回歸

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_review_illustrator_bridge -v
node tools/windows_review_dev/illustrator_bridge/jsx_harness.cjs
```

Python 測試使用真 Windows Qt PDF／QProcess 和假的子程序；Node 使用合成 Adobe 物件模型。兩者不證明 COM 方法、Illustrator 匯入保真或 Adobe 版本相容性。選配 COM 套件只用於此入口；沒有接入原生 Inkscape 擴充、打包或發布。

## 介面依據

- Adobe 官方 [安裝與執行指令碼](https://helpx.adobe.com/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html)：支援 Windows Visual Basic 與 JavaScript／ExtendScript，保留原廠警告設定。
- Adobe 官方 [儲存與匯出 PDF](https://helpx.adobe.com/illustrator/desktop/save-and-export/export-files-to-different-formats/save-and-export-adobe-pdf-files.html)：PDF 與多畫板工作流程。
- Adobe 公開 scripting guide 的社群維護轉錄用於 API 交叉查閱：`Application.DoJavaScript`、`Document.saveAs`／`close`、`PDFSaveOptions`。此機沒有 Adobe runtime，呼叫仍標為待實機驗證。

COM 套件依據：[pywin32 官方文件](https://github.com/mhammond/pywin32)／[固定版本 311](https://pypi.org/project/pywin32/311/)，重用成熟 Windows COM 支援。
