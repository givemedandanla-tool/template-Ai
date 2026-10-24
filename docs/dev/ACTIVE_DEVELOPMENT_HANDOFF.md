# 當前：review-tool Windows PDF 回歸通過；DirectWrite 未能重現

分支 `feature/review-tool-v0.1.0`，source `0.1.0-beta.3.dev1`。先讀 [部件狀態](windows_review_environment/pdf-dwrite-20261024/STATE.json) 與 [本輪報告](windows_review_environment/pdf-dwrite-20261024/REPORT.md)。checkpoint `CP-20261024-REVIEW-PDF-DWRITE-002`，精確 snapshot／收據以 STATE 為準。

舊 beta.2 判讀模組隔離對照會把合成提示頁當 1 件作品；目前來源正確排除，中斷點確認可見文字分類。Windows 原生回歸 31 PASS／0 skip（PDF14、診斷7、stdio9、暗選單1）。修正測試啟動器的 offscreen 空白 fixture 與過短模組時限，沒有放寬產品判讀規則。

新增本機 Qt 診斷選項，真正 GUI、worker、獨立 pythonw 均已驗。加入診斷前後 DirectWrite 皆 0，canary 成功；worker 仍有 1 筆非 DirectWrite 字型記錄。只能稱 NOT_REPRODUCED，不能稱原使用者情境已完全修復。原始記錄含潛在字型名稱／路徑，只留本機；GitHub 僅存匿名計數與合成證據。

下一步回到 review-tool 開發；如原 DirectWrite 情境再現，開啟 --diagnostics-dir 在本機取得證據後修正。OCR／英繁中模型未配置，raster 測試用合成 OCR observations，不升真正 OCR 資格。已發布 beta.2、舊完整產品資格與外部驗證不變。

使用者已授權此部件開發與 GitHub 同步。依[部件規則](windows_review_environment/SYNC_POLICY.md)保存、讀回、對齊本機；不合併 main、不打包發布，不上傳私人作品、字型、客戶資料，不自動擴大成完整 template-Ai 工作。環境初始失敗保留於上層歷史報告，不覆寫成 PASS。
