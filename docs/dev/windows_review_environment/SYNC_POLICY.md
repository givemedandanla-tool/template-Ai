# review-tool 部件同步與交接規則

2026-10-24（Asia/Taipei），使用者明確收斂範圍：先完成本機 review-tool 與 GitHub 的一致性及交接基礎，盡快回到部件開發。此指令優先於歷史完整 template-Ai 的工作範圍。

## 範圍

工作分支固定為 `feature/review-tool-v0.1.0`。日常只保存 review 入口、review 部件、直接相關測試／合成 fixture、此部件的環境設定和交接。共用 AGENTS、STATE、精簡交接、WORK_LOG 只更新相關區段。必要的共用依賴變更必須有具體 review 問題與影響說明，不能因同步而開發整個 template-Ai。

使用 `tools/windows_review_dev/checkpoint_scope.json` 作為明確範圍索引。Git 提交沿用完整既有 base tree，只加入審查過的變更；其餘遠端內容保留，不刪除未 checkout 的歷史檔案。不得自動合併 main、force push、打包、觸發發布或覆寫舊 tag。

## 每次接續

1. 核對本機未提交內容與遠端 feature HEAD；保留私人資料及未提交成果。以 UTF-8 執行 `tools/resume_status.py`，讀 STATE.review_tool_sync、STATE.review_windows_environment、精簡交接及本部件待辦。
2. 原始碼變更先記錄相關需求與驗收，再使用空白／合成資料測試。保存失敗與 skip；不得把啟動成功等同 PDF／OCR／EXE 完整通過。
3. 已授權的開發任務中，每個可恢復階段及約 10 分鐘保存本部件 checkpoint。沿用 `tools/dev_checkpoint.py` 的 prepare／acknowledge 與唯一 ID；準備 view 必須列出本部件實際檔案清單、固定 base commit 及範圍，不能掃入機器專屬檔案。
4. 以 Git 或已連接的 GitHub 介面保存；連接器使用 base tree、parent commit 及 `expected_sha`／`force=false` 更新分支。遠端若有新進度，先整合，不覆蓋。提交前檢查實際變更清單。
5. 讀回確切 commit/tree 與全部範圍內檔案，驗證逐檔 blob／SHA256，才可標記 REMOTE_VERIFIED；下一筆小提交保存收據與 STATE。`github_readback.py` 可保存原始 API 回應並重算完整樹雜湊；以 SHA 快取既有不變子樹，避免重複下載歷史資料。API 限流或缺檔時保持待驗證，不能忽略錯誤。
6. 保存後核對本機 branch HEAD 與遠端相同，且已同步檔案的 bytes／index 一致；另有使用者未提交成果則原樣保留並明示。交接只列部件狀態、精確提交、checkpoint、真實測試、限制及下一步。

這是工作期間的保存流程，沒有建立排程或無人值守推送。往後的部件 checkpoint 使用 STATE.review_tool_sync 記錄；不以窄部件收據覆蓋舊完整產品證據資格。此次初始化 checkpoint 為遵循既有規則亦保留舊正式 run 的 370 個檔案參照，但只新增 29 個環境／結果／交接文字檔。日常 review 同步不因此要求重跑舊全產品測試或重新下載整個歷史倉庫。

## 隱私與異地恢復

只上傳程式、可重建設定與已匿名化合成證據。私人作品、客戶資料、字型、資料庫、密鑰、`.venv`、`.tools`、快取、本機路徑設定不進 Git。圖片依既有 metadata-first 政策處理，hash 不冒充可下載附件。

另一台電腦在不存在的新目錄取得確認提交，依工具 README 重建環境，先檢查再啟動 `review_app.py`。私人資料另外安全移轉。原始碼進度與已發布 EXE 分開：目前可下載成品仍為 review-v0.1.0-beta.2；任何新打包／發布需另有使用者授權。

## 目前待辦

本輪原生 Windows 31 項回歸通過，PDF14項全過；舊 offscreen 空白 fixture 失敗保留。DirectWrite 原情境未能重現，已具備本機診斷；OCR 未配置。見 [本輪報告](pdf-dwrite-20261024/REPORT.md)。不升舊完整產品或 EXE 資格。


## 最小化共享歷史 payload（2026-10-24）

自動審核要求本輪勿重傳整份共享歷史 AGENTS／STATE／WORK_LOG。三者與遠端基底保持一致；只更新精簡交接及 review 專屬 [STATE.json](pdf-dwrite-20261024/STATE.json)。本輪 checkpoint／收據寫入該部件狀態；新的交接是目前進度入口，舊共享 STATE 指標保留歷史用途。依然使用 dev_checkpoint.prepare／acknowledge，以不含全域 STATE 的明確部件 view 驗證，不能覆寫舊完整產品資格或冒稱未同步的 checkpoint 已確認。
