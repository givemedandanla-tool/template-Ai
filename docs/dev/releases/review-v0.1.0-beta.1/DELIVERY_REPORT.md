# 作品判讀與核對工具：第一版交付

已於2026-10-23公開發布 **0.1.0-beta.1**。這是新的獨立判讀／核對工具，不是舊版完整排版程式的升級，也未啟動模型訓練或產出模板。

[下載Windows程式ZIP](https://github.com/givemedandanla-tool/template-Ai/releases/download/review-v0.1.0-beta.1/TemplateAIReview-v0.1.0-beta.1-windows-x64.zip) · [GitHub Release](https://github.com/givemedandanla-tool/template-Ai/releases/tag/review-v0.1.0-beta.1) · [完整第一次使用說明](QUICK_START.md)

## 第一次操作

1. 完整解壓ZIP，進入TemplateAIReview資料夾，執行TemplateAIReview.exe；保留旁邊的_internal與engines。
2. 先加入一份作品副本，按「開始判讀」，核對作品範圍。
3. 點原稿標記，查看或修正文字、種類及歸屬。每項選「已核對」或「暫時無法確定」，再按「套用這項修正」，接著下一項。
4. 按「保存進度」；全部核對後按「完成這份核對」。關閉重開確認資料仍在。
5. 技術資料從「查看全部判讀資料」開啟，點項目可定位原稿；不必人工填滿底層數據。
6. 有問題從「更多 → 匯出問題報告」，先查看內容，再手動提供報告與版本、操作步驟；不要上傳私人原稿、字型或資料庫。

上述倉庫教學已補清楚核對狀態／套用步驟；ZIP內使用說明仍為固定建置來源的較精簡版本，沒有為教學補述重新產生或替換程式。

## 實際驗證

- Windows相關來源回歸181項：180通過、1項選配OCR略過、0失敗／錯誤；16個隔離模組。
- 真正frozen EXE：32項操作檢查通過，包括啟動、SVG/PDF相容AI/外框例子、背景判讀、標記修正、總覽定位、保存重開及安全報告。均為合成測例，不能當私人作品品質驗收。
- CI正常入口顯示視窗1.287135秒；只代表該次Windows runner，不保證使用者硬體相同。
- 原發布包保護全部通過。精確排除83個已核對來源與版本的sklearn上游測試資料；執行資料、授權與私人資料攔截規則保留。
- 草稿與公開Release各實際下載一次，兩次都逐檔核對13,094個檔案；不是只看版本號或API。
- 維護端另讀回公開SHA256SUMS、11份安全證據及原生Git精確來源／tag；來源／hash完全相符。

## 版本與保存

- Tag：review-v0.1.0-beta.1；精確建置來源：1562f4d09ed64564f100885f9ddcb6a7efb6e1db。
- Windows執行：[run40021575484](https://github.com/givemedandanla-tool/template-Ai/actions/runs/40021575484)，所有步驟success。
- ZIP：319,256,683 bytes（304.47 MiB）；SHA256：86d6fd93020c12b26ad9147114f6ce2e5618918397e36fe33e8ef14e77e5153d。
- [本地持久化安全證據](windows-published-40021575484/ROOT_READBACK.json)；完整包內清單、每階段耗時、測試、下載與上游排除稽核位於同目錄。
- 原始安全證據分支：review-release-evidence/v0.1.0-beta.1，目錄runs/40021575484-1-1562f4d09ed6/。
- 程式碼／交接存於feature/review-tool-v0.1.0，request固定於建置來源；未合併main、未覆寫舊版。GitHub API的targetCommitish預設main不作來源證據，實際tag直接指向上述來源。

## 仍須知道

Inkscape與必要Python/Qt隨包附帶，不必另外安裝。私人作品與修正資料留本機，正常使用離線；獨立資料目錄不自動遷移舊資料庫。

OCR中／英文模型已附，Tesseract執行器尚未內嵌；缺引擎時明示未知，人工補標退路已驗證，不宣稱Windows OCR辨識通過。字型／間距／結構不確定時保留候選或未知。原生AI私有結構、真作品效果、使用者硬體、新手可用性及實印品質仍待本地回饋。程式未簽章，遇系統阻擋請核對來源與SHA並回報，勿關閉防護。

既有完整產品的來源資格過期／外部資格沒有被本元件通過結果改寫；原未提交timeout/adopt工作保留。前六次取消／失敗與根因保存在LOCAL_VALIDATION及對應目錄。使用Pro/Codex既有能力、免費工具與公開GitHub標準runner；未啟用新付費API、模型、試用或雲端服務。未查核帳戶帳單，不虛構扣款金額。

交付後先等待本機一份作品的實測與安全報告，再按review版本規則修正；不自行擴張成下一個部件。
