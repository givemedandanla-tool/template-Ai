# review-tool 離線原生讀取交付

來源開發版 **0.1.0-beta.3.dev2**。一般「加入檔案 → 開始判讀」已使用隔離 Adobe 引擎，可在本機讀取已驗證的 AI、PDF 與 SVG。新的本機工作階段已開啟，載入指定私人 AI 的已驗證結果；舊工作及原稿保留。沒有打包或發布。

## 禁止連線的實作

Adobe DLL 只在每文件獨立的 Windows AppContainer 中載入，啟動前檢查實際 token：零網路能力、禁止子程序，並先綁定關閉即終止且最多一程序的 Job。隔離失敗、逾時或取消皆停止，沒有未隔離、COM 或 Inkscape 退路。

本機 TCP4／TCP6／HTTP／UDP／DNS 正向對照確實接收，隔離對照全為零；DNS 呼叫明確存取拒絕。測試包含原生 WinHTTP／DNS API，不依賴 Python 攔截。這是 OS 強制隔離，不是只靠網域黑名單或「沒有觀察到流量」。對其他已安裝軟體不作斷網宣稱；未來 Template AI 必須重用此受限入口。

新副本排除 AIRobin、AISafeModeLauncher、AISniffer、CRLogTransport、CRWindowsClientService、LogTransport2、研究 helper、CEPHtmlEngine 與 libcef 共九個執行／瀏覽器元件。保留 Illustrator.exe 作資源識別，從不執行它。必要 DLL 可能仍包含網路程式碼，因此限制必須一直存在。原 Adobe 磁碟檔不變；只對精確版本的已載入語言模組提供程序內空通知信箱，避免 mailslot 初始化失敗，沒有增加網路權限。

## 實際驗證

- 89 項 Windows 元件回歸：89 PASS、0 FAIL、0 SKIP，來源雜湊與測試清單見 DELIVERY_EVIDENCE.json。
- 合成 AI、指定私人 AI、雙頁 PDF、文字 SVG 完整讀取、保存與重新開啟通過；原稿不變。缺字型與錯誤檔案拒絕測試通過。
- 三份輸出共五頁，72／300 dpi 逐像素與既有同引擎本機基準一致，原生幾何及畫板亦相同。這不是獨立 Illustrator UI 黃金標準或所有 AI 版本資格。
- 取消、逾時、隔離驗證失敗、父程序結束四項控制通過，無殘留讀取程序。
- 真實 Qt 視窗／QProcess 的讀取、畫布定位、修改、保存、重新開啟、安全報告及移除 COM 選單七項通過。已核對合成截圖。畫布標記改用介面選定字型；本輪修正後實際流程 DirectWrite／字型警告為零，不宣稱所有電腦與操作都不會警告。
- 「更多」選單及核對表單明確使用淺底深字，深色系統配色回歸通過。Windows pythonw 啟動不依賴黑色主控台。

缺字型 SVG 曾被匯入器先行替代，已補原宣告與原生字型名冊對照；原失敗保留。字型簡寫／變數等未能核對的 SVG 宣告會明確停止，外部資源要求先內嵌。作品分區與文字框仍是待人工核對的候選，衍生 PDF 宣告不冒充原始 AI 可編輯結構。

## 使用與保存

使用本機 `.local/START_OFFLINE_REVIEW.cmd` 返回新的工作階段；一般來源入口為 START_REVIEW_WINDOWS.bat。引擎設定在 Git 忽略的 `.local/review-native.json`。詳細環境與換機方式見 LOCAL_READER.md。每文件實測約 97–128 秒，GUI 全流程約 143 秒；不以未量測的速度保證代替實測。

作品、字型、引擎、原始診斷、已啟動工作階段與私人輸出只留本機，診斷封存至使用者指定分析目錄。GitHub 只保存程式、合成驗證與匿名交接；feature 分支須有精確提交／完整樹／逐檔讀回與收據。不合併 main，不建立安裝包、tag 或 Release。已發布 beta.2 保持不變。

本輪資格限定指定 CC 2020 引擎與本機 Windows。既有離線 Windows Sandbox 的引擎基準仍保留；此新版完整 UI 尚未在另一台實體電腦重驗。全專案 governance check 在本輪開始前即因歷史證據過期失敗，最後仍相同；沒有把這次部件資格升為整個 Template AI、完整 OCR 或已發布 EXE 資格。

## 設計依據

- https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation
- https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-process_mitigation_policy
- https://learn.microsoft.com/en-us/windows/win32/api/errhandlingapi/nf-errhandlingapi-seterrormode
- https://ai-sdk-2020.84.nz/html/struct_a_i_font_suite
