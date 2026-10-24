# Illustrator 本機接口：實作與 Windows 邊界回歸完成，Adobe 實機驗收待辦

使用者已改為要求在有 Illustrator 的環境建立接口。本輪只處理 review-tool，指定 feature/review-tool-v0.1.0；原生 Inkscape 擴充的文字遺失問題仍未通過，沒有接入。

「更多」新增「使用 Illustrator 匯入 AI（實驗性）」及「停止等候 Illustrator」。選本機 AI 後，以獨立 Python STA COM helper 呼叫 Illustrator 的 JSX，產生全畫板 PDF 副本。只有原稿 SHA256 未變、頁數與畫板數一致、頁面尺寸有效且未檢出 PDF 相容提示頁，才新增為待判讀來源。原來源／人工核對不替換，使用者自行點開始判讀並目視核對。

拒絕重用已開啟原稿或 app.open 返回的既有文件；只關閉此次開啟的文件，使用 DONOTSAVECHANGES，不呼叫 Quit、不強制結束 Illustrator、不修改偏好或靜默隱藏警告。取消／10 分鐘逾時只終止自身 helper；遲到副本不採用。每次獨立目錄，不覆寫現有輸出。來源／副本各 200 MB、100 頁、Windows 路徑 220 字元上限。

最終 Windows 回歸 56 PASS／0 FAIL／0 skip：新接口 26、PDF 17、Jobs 與失敗 UI 13。新接口套件內另含 14 個合成 Adobe DOM 控制情境；不是額外 14 個 Python 測試。真 Qt PDF／QProcess、安全報告遮蔽、保存重載與原資料保留通過。真 pywin32 host 在此機回報 NOT_INSTALLED。工具 [指南](../../../../tools/windows_review_dev/illustrator_bridge/README.md) 附有兩畫板／矩形／文字的實機合成 smoke，可在異地重跑。

此機沒有 Illustrator，真 COM→Illustrator→原生 AI→PDF、字型／連結提示及多版本行為全部 NOT_VERIFIED。合成 DOM 或合法 PDF 不證明 Adobe 匯入、文字與外觀保真。沒有為私人作品、特殊效果、色彩／印刷或新 EXE 宣告通過。原 DirectWrite 情境此前未重現，完整 OCR 未配置。

依據 Adobe 官方桌面指令碼與 PDF 工作流程，重用 pywin32 311（選配、固定版本、專案 venv），不更動系統執行原則。測試期間發現的初版 PowerShell 執行原則阻擋及 mock 未涵蓋 API 差異已修正；記錄見 windows-regression.json。既有 30 項回歸合併執行耗時 913.777 秒，最終完整 PASS；期間啟動的重複分組在原回歸通過後停止，不將其部分輸出重複計數。

只同步程式、合成工具、匿名結果及精簡交接。工作副本、來源路徑／雜湊、原始記錄、字型與客戶資料只留本機。共享歷史 AGENTS／STATE／WORK_LOG 不重傳；本部件 STATE 和 checkpoint 為接續入口。不合併 main、不打包、不發布，beta.2 與 source 版本號不變。
