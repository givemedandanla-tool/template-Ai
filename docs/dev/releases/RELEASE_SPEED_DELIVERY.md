# 修正版發佈加速：實作與驗證完成

2026-10-23。已完成4項工程交付：固定輸入驗證快取、保守影響選測規則、完整階段計時、GitHub持久化。產品程式與既有tools／tests bytes保持原code manifest `f1a2cf7a817e7e3d0dca43ff93458f52d1526638aa816e7d223204f6abdf2908`；沒有發新產品Release、改版號、覆寫beta.1／beta.2或合併main。

## 實測結果

以下是標準公開Windows runner的單次觀察，包含實際cache還原成本；不是使用者電腦效能，也不是固定發版分鐘保證。

| 階段 | 實際秒數／結果 |
| --- | --- |
| 冷輸入準備＋cache miss查找 | 61.11秒，取得並驗證29個物件，共1508883223 bytes |
| 另一乾淨runner：遠端cache還原＋同等完整重驗 | 37.27秒；其中還原14.47秒，重驗22.80秒；實際cache hit=true |
| 同機本地熱重驗 | 10.77秒，沒有重新取得上游資產 |
| 首次cache保存成本 | 12.22秒，已另記，不從比較中隱藏 |
| 舊Git索引／新batch索引 | 34.53秒／5.17秒；相同產品來源、同樣選中Windows19模組 |
| 原Windows產品回歸 | 199／199 PASS、0 runtime error；Qt隔離與原方法／斷言保持 |
| 真正EXE與引擎 | 原21操作／重啟＋5引擎情境全PASS，24次呼叫均包內 |
| 未發布包的傳輸後校驗 | 本地HTTP實際傳輸，13060檔全部匹配 |
| 最新行政工具回歸 | 本地及Windows42／42 PASS、0skip；含真Git batch fixture及真發布CRLF source-map反例 |

熱cache的「0 bytes」只指沒有重新向PyPI／公開Release抓取物件；Actions本身仍傳送快取，傳輸byte數沒有獨立量測，不能宣稱整個工作完全不下載。冷熱準備都驗27個wheel、11837個引擎檔及125份精確來源。沒有刪除驗證來取得較快數字。

首次原生完整路徑在[run39894882425](https://github.com/givemedandanla-tool/template-Ai/actions/runs/39894882425)／來源7e8cf994執行，含37個當時行政案例。後續僅修改發布防護、報告分類及Git索引；以[run39897343317](https://github.com/givemedandanla-tool/template-Ai/actions/runs/39897343317)／來源bb431f68實跑最新42個Windows行政案例與真實整庫依賴索引。沒有把兩者冒稱同一次完整新跑；[組合驗證](release-speed-validation/final-validation-composition.json)核對未改的cache／build／EXE路徑函式與pin、validate早返回及相同19模組清單。產品、原測試與既有驗證器bytes未變，沿用原1986案例完整來源資格，不因行政工具改動重跑無影響的產品全套。

新流程本輪未建立新GitHub Release，因此**不是新發布版本的公開端到端下載驗收**；本地HTTP校驗已明確標示。下次真正發版仍執行草稿及公開後兩次真正GitHub下載、完整程式ZIP逐檔校驗及來源再驗。不能把約21分鐘的本輪診斷流程與過去約28分鐘的公開發版直接相比計算整體加速百分比，兩者工作量不同。

## 具體改動

1. 27個現有Windows cp311/x64 wheel固定官方URL／版本／大小／SHA；核對需求檔後離線安裝，保留pip check。沒有升級產品相依。
2. 從固定beta.2 ZIP只重用Inkscape及原始授權，不取出舊TemplateAI.exe；完整manifest／版本／每檔SHA再驗。來源ZIP沿用公開且精確的125物件包，不再每版重組及上傳同一908MB；新Release以說明、manifest及SOURCE_DOWNLOADS.json提供免費明確連結。
3. Actions cache以平台、Python完整版本及完整鎖檔綁定；已驗輸入先保存，後續產品失敗不抹去。續接build必須同source及INPUTS_VERIFIED狀態並再次驗輸入。只存明列公開依賴，不存venv、workspace、客戶資料、模型或舊成品。
4. 固定長期builder分支`release-speed-check/20261023-001`，解決兄弟版本分支無法共享cache的GitHub限制。新版本仍需獨立授權、提交標記及精確同HEAD的版本request參照；舊tag／Release存在就拒絕，不自動覆寫。普通dev/main/PR不打包。
5. base∪head反向import圖加雜湊綁定動態契約，自動產生選測原因；核心、資料、打包、測試、未知擴大，低風險已知關聯加固定底線，報告資料不誤當執行程式。改用git cat-file --batch與限縮路徑，避免逾千次Windows程序啟動。尚未導入coverage context學習索引，靜態圖不代表所有行為已被證明。

完整操作、來源重用及授權規則見[已採用政策](RELEASE_SPEED_POLICY.md)。版本號規則未改；新發版唯一程式版號仍template_ai/__init__.py，另需新使用者發版授權，不以本次工具優化授權偷偷發布新產品。

## 失敗與修復有保留

native001在輸入階段59秒拒絕來源map，沒有進入產品測試。原報告保留。真beta.2 map的Windows CRLF bytes是48199、SHA b8d3db…；Git LF lock是47178、SHA bc0271…。已用真正發布manifest重現原因。仍精確核對vendor manifest及每檔SHA，只將其與Git lock的關係改為JSON內容核對；沒有改pin、降低SHA要求或接受不明元件。補了此反例、同source階段續接、新發版來源及metadata分類測試。錯誤報告也加上bounded error message／traceback，便於下次定位。

舊版tag與公開beta.2 manifest／SHA內容已再次讀回確認未變，見[保留證據](release-speed-validation/published-release-preservation.json)。所有失敗、37與42案例的不同來源及原生資料分開保存。

## 費用、保存與尚未驗證項

只使用既有公開GitHub標準Windows runner、固定免費工具與內含cache。第一次實查cache用量0、需約1.51GB；保存條件為既有≤8GiB且新增≤2GiB，不提高10GiB預設、帳務或預算。用量未知則不新增遠端cache。沒有新付費API、試用、額度、付費runner、Codespaces、模型或子代理；不據此宣稱整個帳戶帳單為零。

證據在[本輪資料夾](release-speed-validation/)、`release-speed-evidence/v1`與原開發分支。最後checkpoint／收據以STATE為準，仍必須包含正式004全部369附件，不能用窄metadata讀回取代。新產品下一次真正公開發布仍要重新走其發布下載Gate；私人作品品質、使用者硬體、印刷、新手與完整OS斷網資格維持原NOT_VERIFIED，既有172／166scope／75父題與AI8包50資格不改。

下次只需說：「以目前已發布版本修正〔問題〕，依修正版加速規則驗證並發布新測試版；保留必要EXE與下載檢查、不新增費用。」Codex會處理版本、影響範圍、cache、授權記錄、驗證與checkpoint，無需您操作建置工具。
