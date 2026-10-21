# v0.2.0-beta.1 發佈狀態

**目前尚未確認Windows EXE建置或發布成功。** 不能把本地來源驗證、推送請求或暫存附件當成可下載成品。

本輪已完成程式與發佈接線，並實際修復：
- 打包後的背景工作與還原副本啟動入口；從其他資料夾啟動也能找到正確程式。
- 測試版版本號導致診斷報告被拒絕；保留嚴格版本及隱私白名單。
- 暫停後刷新清單自行建立整頁空作品，影響接續分割；清單刷新現在保持唯讀。
- 兩個測試攔截器改依真正參數定位，原逾時／取消／回滾／接續斷言未放寬。

## 已執行

- Linux完整回歸：1958／1958 PASS，258健康程序、0runtime；原1942全保留，新16。
- 原版GUI：27／27 PASS，原腳本／斷言／時限未改；在隔離負載下執行。
- 來源GUI兩階段操作：合成學習、輸入、產稿、拖動、更正、確認、允許預覽輸出、報告、暫停／重啟及重播；此項為Python來源，不是假稱frozen Windows。
- 602個程式／工具／測試檔Python3.11語法檢查，以及下載校驗替換負例、限定發佈觸發與交接負例。
- 正式run：docs/evidence/runs/RUN-WINDOWS-BETA-LINUX-001。software_execution_status=PASS；原5外部未驗證條款仍使整體status=FAIL，不改為生產合格。

172要求／75父題（69已驗證、3部分、3延後）、90 CORE／7治理範圍與AI8包50條真實資格維持原狀；本次沒有增加父題或虛增完成率。詳細run及失敗歷史均保留，未刷新查重／型別警告基準。

## 尚待實際完成

1. 已完成：CP-20261021-WINDOWS-BETA-SOURCE-002獨立Git讀回11713條（含record），355正式附件全部涵蓋；隔離還原PASS，require-evidence publication-scope Gate PASS。Windows步驟仍待完成。
2. 推送具體最終候選到release-request/v0.2.0-beta.1，取得GitHub標準Windows runner實際結果。
3. Windows15模組共171案例全PASS無skip，實際frozen EXE兩階段檢查通過，才建立不可變tag及Pre-release。
4. 上傳ZIP／manifest／SHA256，實際下載草稿與公開後附件，逐檔核對，保存release-evidence分支回執。

本雲端環境Git讀寫正常，但api.github.com仍回Forbidden；所需API／uploads／objects主機的環境網路草稿已保存，尚未生效。需在平台環境設定套用後再確認既有GitHub連線及Actions／Release權限，無需向聊天提供API key。沒有讀到Windows執行回執，不捏造建置／發布／下載結果。

## 使用與界線

未來成品為TemplateAI-v0.2.0-beta.1-windows-x64.zip，完整解壓後開啟TemplateAI.exe；先以本機資料副本試用。Inkscape、合法字型與可選OCR工具／模型需本機就緒；包內不放私稿／客戶庫／私人字型／訓練資料，無自動上傳。錯誤從「問題與報告」手動匯出安全ZIP回Codex。

真實作品學習品質、完整私人.ai還原、使用者Windows硬體／效能、實印、新手及完整網路隔離資格待本機回饋。教學／外部知識庫仍為未採用草案，網頁／手機仍延後。

沒有新付費API、模型、試用、付費runner、Codespaces、付款或帳務設定；未啟用子代理。請求的是既有GitHub標準runner，沒有帳戶扣款證據，不聲稱整個帳戶帳單為零。

正式來源快照956c89c86522615a7833accfba0c4b72727766be；source／fixture版本570ecebe，code manifest3cd6da4b。CP001還原因/tmp分割區不足失敗保留，改用workspace建立新CP002，未刪他人成果或加資源。
