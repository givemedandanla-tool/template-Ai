# 當前：原生 AI 擴充可行性未通過，尚未接入產品

指定分支 `feature/review-tool-v0.1.0`，基底 `33e2152dde48970f99875fff34497bbb7dd66b70`。使用者只有 Inkscape；要求合成隔離驗證可行後才整合，不要求安裝 Illustrator。先讀 [部件狀態](windows_review_environment/native-ai-20261025/STATE.json) 與 [報告](windows_review_environment/native-ai-20261025/REPORT.md)。checkpoint `CP-20261025-REVIEW-NATIVE-AI-001`，精確提交／收據以部件 STATE 為準。

官方 inkai 1.2.0 固定 `1a5f42a0b0407fc869e032420570682048810108`。新目錄重建及合成 Windows 驗收完成：7 項中 5 PASS／2 FAIL。純原生與 PDF 包裝的矩形／顏色／尺寸可讀，zlib／zstd 可解；矩形加文字兩案只剩矩形，文字未轉為 SVG text 或輪廓。成功返回 SVG 不代表完整作品。正式 probe exit 2，整合條件未過，因此產品源碼與既有入口保持原樣。

現有 Windows 回歸另跑 30 PASS／0 skip（PDF17、Jobs10、失敗介面3），不抵銷上游 2 項 FAIL。工具與重跑說明位於 tools/windows_review_dev/native_ai_feasibility/；只產生合成檔案、固定公開下載、驗證 hashes、每案獨立程序，沒有私人檔案輸入參數。

下一步先解決原生文字轉換，再驗現代文字／字型缺失／圖片／透明度／多畫板等必要保真條件，之後才接 review-tool。原始碼 source 仍 0.1.0-beta.3.dev1；已發布 beta.2 不變。原 PDF 提示頁攔截、短路徑設定及失敗介面修正保留。DirectWrite 未重現，OCR 未配置。

本輪未用私人作品／字型，下載源碼、wheel、生成 AI／SVG 及原始記錄只留本機。只同步工具／匿名證據／部件交接。依 [部件規則](windows_review_environment/SYNC_POLICY.md) 讀回對齊；共享歷史 AGENTS／STATE／WORK_LOG 不更新。不合併 main、不打包發布。
