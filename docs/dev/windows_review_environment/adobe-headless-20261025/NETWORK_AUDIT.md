# Adobe 部件網路稽核：階段結果

2026-10-25。此結果尚不足以宣稱 review-tool 已完全斷絕 Adobe 伺服器連線。產品整合、原生字型檢查與 AI／PDF／SVG 統一路徑仍未完成；本次沒有改動產品程式或 Adobe 原始 DLL。

## 靜態盤點

本次掃描 1,083 個 Windows PE 檔案：本機 Adobe 測試配套 362、Python 32、review 開發環境相依套件 686、Microsoft CRT 3。38 個模組匯入網路相關系統函式庫；找出 802 種網址網域字串。這代表能力或參照，不能當作已執行請求或已傳送使用資料的證據。

本機配套包含登入、雲端資產、更新、當機記錄相關模組／字串。先前讀取測試載入的 Adobe 模組中，AdobePIE.dll 與 usd_win.dll 有直接網路相關匯入；不能只移除獨立回報 EXE 就宣稱所有原生模組不會連線。

載入模組中有 3 個沒有簽章：libmmd.dll、WRServices.dll、WRLiloPlugin.dll。沒有簽章不等於惡意，但來源保證有限。原提供套件的 Illustrator.exe 曾有簽章雜湊不符；既有隔離實驗採用有效簽章的備份版本，原件保留。不得把原套件全部視為已認證。

24 個 Python 套件的 11,118 個 RECORD 雜湊項目中，發現 1 個 numpy 位元碼快取不符；其程式碼物件、指令、常數及名稱與重新編譯已核對的原始碼一致。保留初始差異與後續比較紀錄，不把快取差異誤報為原始碼遭修改。另有 5,332 個項目無記錄雜湊，不能宣稱所有檔案都有上游完整性證明。

這不是已發布 EXE 的完整稽核；舊 Inkscape 安裝、未設定的 OCR 執行器，以及所有未來部署組合不在本次 PE 掃描資格內。

## 動態觀察與控制

第一輪 Windows 隔離環境在完成控制及讀取前結束，列為 INCOMPLETE；原因未確認，不能算通過。

第二輪沒有網路介面，合成／指定私人樣本／合成各使用新程序完成讀取與 PDF 輸出。加入約 20 秒閒置觀察。ETW 共 1,164 個事件；人工發起的無資料 DNS、TCP 與 WinHTTP 控制可觀察到相關事件。未發現直接歸屬三個讀取程序的相同類型事件。

這僅表示此離線情境下沒有觀察到指定事件，不能推出所有模組在有網路、登入、更新、錯誤或長時間閒置時均不會連線。未完整排除服務代送、延遲行為與未涵蓋事件來源。沒有把私人作品、字型或原始記錄傳到外部服務。

## 原生程序強制隔離試驗

Windows AppContainer 測試程序使用零網路能力並禁止建立子程序；實際 token 證實在 AppContainer 中。對保留測試位址的 TCP 請求遭 WinError 10013 拒絕，子程序建立遭 WinError 367 拒絕。兩個 loopback 測試只有逾時，尚無監聽器正向對照，不能獨立當作 loopback 封鎖證明。

相同隔離政策下，Adobe 引擎的合成／指定私人樣本／合成三次都在 AILInitializeWithHostApplicationData 階段終止，退出碼 0xC0000409。各次已確認隔離 token，但未進入文件讀取、沒有 PDF 輸出。原因待追查，不能直接認定由網路封鎖造成。此 AppContainer 路徑判定 NOT_QUALIFIED，不整合到正式讀取流程，也不悄悄改用未隔離執行。

先前整個 Windows 測試環境關閉網路的成功結果仍有效；它與本輪原生程序隔離不是同一種驗證。當前 Python offline guard 不能涵蓋 DLL 的原生連線。

## 修改 DLL 與獨立實作

DLL 的機器碼可以分析與修改。應先在副本定位實際回報／登入／更新呼叫，區分不必要模組與必要解析依賴，再逐項測試修改。改連線入口、網址字串或移除一個 EXE，不能證明動態載入、IPC、其他網路 API 或服務代送皆不存在；修改後也必須重新檢查初始化、字型與作品保真。尚未修改 Adobe DLL，尚未證明停用模組後所有需求均成立。

獨立實作唯讀 AI 解析器且不載入 Adobe DLL／EXE／服務，可移除 Adobe 二進位依賴所帶來的直接連線風險。直接移植反編譯程式碼仍可能保留原有行為；自行開發也不代表沒有解析漏洞或相依套件風險。既有獨立提取器只證明兩份樣本原生資料可解出，完整文件模型與呈現仍未完成；先前 Inkscape 原生 AI 擴充測試的文字案例曾遺失文字。使用者目前在詢問替代方案，不把問題當作已授權整套 Illustrator 重寫。

## 後續與資格

先解決可強制斷網且仍能正確讀取的執行邊界，再做配套最小化、native 字型替換檢查與 AI／PDF／SVG 統一解析。每個變更以合成資料及指定私人樣本在本機回歸。若調查 DLL，保留原件及逐次副本，不能以略過檢查或漏讀物件當成功。

原始診斷、私人作品、字型與 Adobe 引擎只留本機。GitHub 僅保存此匿名報告、需求及交接。沒有主分支合併、打包、發布或已完成產品整合的聲明。

參考：[Microsoft AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)、[process attribute controls](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)、[WinHTTP tracing](https://learn.microsoft.com/en-us/windows/win32/winhttp/collect-traces)。
