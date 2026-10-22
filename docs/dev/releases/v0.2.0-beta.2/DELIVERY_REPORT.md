# v0.2.0-beta.2：隨包 Inkscape 已發佈

狀態：**RELEASE_PUBLISHED_DOWNLOAD_VERIFIED**，2026-10-22。

[下載 Windows 程式 ZIP，約317 MB](https://github.com/givemedandanla-tool/template-Ai/releases/download/v0.2.0-beta.2/TemplateAI-v0.2.0-beta.2-windows-x64.zip)。完整解壓，執行 `TemplateAI/TemplateAI.exe`，保留 `_internal` 及 `engines`，不需另裝 Python 或 Inkscape。首次使用會驗證內附元件，請稍候。字型仍使用您電腦合法安裝的版本。另附約908 MB的開源元件來源 ZIP 是授權與開發用途，日常不必下載。

## 這次完成什麼

- 固定使用包內 Inkscape 1.4.2，電腦另裝版本、PATH及環境變數不會取代它。缺檔或損壞會明確阻擋向量功能並保留安全報告與點陣讀取，不偷偷換用系統工具。
- 驗證完整引擎檔案清單、雜湊與版本綁定；工具身分納入分析快取，改版建立新快取，保留舊來源與已確認稿保護。
- 修正內層快取型別損壞時的重建與安全報告的純標準庫路徑。沒有撤回人物／公司歸屬、穩定ID、固定字級／ScaleX、無解及正式輸出檢查。
- 另附242份原始相依授權檔、版本鎖及125份精確對應來源封存檔。來源與限制見 [Inkscape 散佈說明](../INKSCAPE_REDISTRIBUTION.md)。
- [局部除錯白話操作規則](../../CHANGE_IMPACT_DEBUGGING_QUICK_GUIDE.md)及[完整方案](../../CHANGE_IMPACT_DEBUGGING.md)已交付。依反向依賴、實際測試關聯及設定／外部工具契約推導保守範圍；未知時擴大。帶權集合覆蓋只用於排序，不能刪除必要檢查。**自動選測器尚未實作。**

## 實際驗證

| 檢查 | 實際結果與界線 |
| --- | --- |
| 正式來源資格化 | 1986唯一案例PASS，原1963保留＋23新增；262健康模組、27原版GUI作業；含相同來源環境修復復驗，**不是單次全新全跑**。原始失敗完整保留，見[source qualification](source-qualification.json)。 |
| 本次Windows來源 | 199／199 PASS、19健康模組、0 runtime error；原方法、斷言及等待限制不變，Qt新程序隔離保留。 |
| 真正EXE | 原14項操作＋7項新程序重啟檢查全部PASS；含學習、輸入、預覽、真拖動、改資料、確認、預覽輸出、正式輸出阻擋、暫停／續跑、安全報告。 |
| 真正引擎呼叫 | 三個有效情境共24次，全部實際呼叫 `engines/inkscape/bin/inkscape.exe`；無系統安裝／有系統安裝／錯誤環境變數及PATH均有驗證。 |
| 元件損壞 | 包內執行檔遺失與DLL受損兩案PASS；不改用外部版本，安全報告CLI及點陣讀取仍可用。 |
| 授權與來源 | 11837份runtime檔案、242份原始授權、125份對應來源均依固定大小及SHA驗證。 |
| 發佈下載 | Windows流程實際下載草稿資產並驗證，再公開、重新下載驗證；公開包13060檔全部匹配。雲端工作區另對公開manifest／SHA檔逐byte核對，兩大型ZIP只做公開HEAD大小核對，沒有冒稱在雲端另下載全部。 |
| 局部故障注入 | 正確路由2案PASS；故意改成環境變數優先、缺包時改用系統的兩個mutant均被測試抓到。這是受控示範，與上列真引擎證據分開。 |
| 靜態差異 | 相同工具設定與beta.1比較：0新增、3453既有、1解除；既有型別／解析候選仍待判讀，未刷新基準，不能稱全無錯誤。 |

原真實私人作品、使用者硬體效能、實體印刷、獨立新手及完整OS斷網資格仍未通過；正式run整體goal仍因這些外部資格為FAIL，沒有以測試版發佈升級完整產品資格。Illustrator自動化、私人.ai完全還原、網頁／手機及未採用教學草案不在本次交付。

## 發現及處理的問題

來源完整嘗試遇過短碼撞合法SHA的舊測試誤判、損壞快取內層型別缺陷及暫存空間不足；原結果與相同來源復驗皆保留。Windows另外修正Git長路徑及TMP短名比較問題。

真正EXE的診斷也曾失敗：第45秒的C背景堆疊擷取輸出破損frame並以0xc0000005退出。改以持有frame參照、在GIL下讀取的Python計時器記錄，仍保留45秒門檻及外部240秒硬期限；只在授權GitHub frozen驗證環境生效，一般本地啟動不裝此替代。原EXE斷言不變。本次exercise實跑64.297秒，確實在45秒成功擷取後繼續完成14檢查；resume 37.343秒、7檢查PASS。這是本專案的實際反例與修復驗證，不宣稱普遍CPython缺陷。

可重跑小型示範：`python docs/dev/releases/verify_frozen_diagnostic_timer.py`。它驗證dump、取消及一般啟動保護三案；只是隔離示範，不能當Windows證明。若native擴充卡住GIL無法出Python堆疊，外部240秒仍會判失敗。未放寬hang、來源、字型或輸出Gate。

## 版本、保存及後續

- 來源／不可變tag：`af97b108b3a19c0d4eab3a6741ab716c732e0aea`／`v0.2.0-beta.2`。未合併main、未覆寫beta.1。
- [正式Windows流程](https://github.com/givemedandanla-tool/template-Ai/actions/runs/39810636090)；[原生讀回](windows-native-004/native-git-readback.json)、[下載檢查](windows-native-004/download/download-verification.json)、[公開讀回](public-readback.json)、[tag讀回](tag-readback.json)。
- 程式ZIP：316795056 bytes，SHA256 `2cae59805aa95f5c626dc6df799f2777b79e96344250a674bda370649b43a4f1`。
- 來源ZIP：908375828 bytes，SHA256 `3250070bd39362b87dd9c7c97f9b2fa132ceeeee57d815579264c5e87f079b6a`。
- 工作分支仍為 `dev/v0.1-first-version`；精簡交接及最後已確認checkpoint以 `docs/dev/STATE.json`、收據及 `ACTIVE_DEVELOPMENT_HANDOFF.md` 為準。正式004全部附件不得被窄metadata讀回取代。

請先備份，用獨立資料副本試用。[操作與安全回報說明](../WINDOWS_BETA_QUICK_START.md)有本地報告入口；回報版本、步驟、預期／實際結果及手動匯出的安全ZIP即可，私人作品、字型、資料庫與模型留本機。未簽署程式，Windows可能顯示發行者不明，請核對Release及雜湊。沒有新增付費服務、API、試用、額度或子代理；不能由本次操作推論整個帳戶帳單為零。
