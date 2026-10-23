# DEV-QUALITY-001 交付結果

本輪已完成本地工具建置、固定來源、離線重建、真實掃描、初始基準、判讀與交接。產品程式未修改；新增工具與既有產品資格分開。兩個skill可顯式讀取使用，當前平台自動辨識仍未驗證。

| 範圍 | Python輸入 | CPython／Pyright | jscpd合格來源 | Ruff診斷 | Pyright診斷 | exact重複組 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 應用與入口 | 270 | 270 | 265 | 3個解析限制 | 4212 | 0 |
| 開發工具 | 60 | 60 | 59 | 0 | 521 | 2 |
| 測試 | 246 | 246 | 244 | 0 | 7065 | 5 |

全部576檔都明確傳入jscpd；8檔不符合固定門檻。查重僅說明exact、10行／70token範圍，未驗證所有改名、近似與語意重複。

新增工具原碼／測試的 Ruff／Pyright 診斷為0。開發中發現的2筆新型別問題已修正。產品沒有新確認的行為錯誤；舊Pyright診斷全部保留，不能當作已確認缺陷。已對一個Qt動態屬性診斷做實際賦值／讀回核對；storage兩筆回傳型別有前置非空條件，列型別表達候選，不擅改產品。

7組exact判讀：6保留（獨立入口／匯入／字型初始化），1低優先候選（批次擷取對話框回應helper）；未重構。詳見 BACKLOG.json。

驗證：工具11／11 PASS＋原GUI工具與本地啟動7／7 PASS，沿用fresh module程序與timeout，0未處理runtime；隔離示範9項斷言通過；全新工具目錄由wheelhouse／npm快取離線重建成功。正式application check再次執行：新增0、既有4215筆仍在；tools/tests以同一份完整掃描結果對初始基準分類，沒有為數字重複掃描。

Ruff三個解析限制保留且有最小重現／版本比較；CPython實際3.12.14及3.11語法模式通過，不冒稱原生3.11／Windows。demo001/002與初次工具測試的設定失敗留在 reports/attempts.json；原Ruff誤判細節見 reports/ruff-parser-compatibility.json。未放寬產品斷言、未改忽略以取得通過。

原產品計數不變：75父題69已驗證／3部分／3延後；CORE90／90、GOV7／7依既定範圍；原AI8包50條完整真實資格仍8部分／0完整。沒有把18項工具驗證加成產品完成率，也沒有宣稱重跑原1850回歸。

遠端寫入受費用條件阻擋：只做既有Git讀取；沒有push／PR／Actions／新runner／Codespaces／付費API／外部模型／代理／試用／帳務變更。原GitHub基底仍為0e7b8aee，本輪提交與checkpoint僅本機。雲端僅保存不執行或發布的工具重建草稿，保留repository ref／network／secret需求，與程式備份分開。

精確最終本機HEAD、恢復包SHA256、bundle／patch核對見 `.cache/debug-tooling/delivery/receipt.json`；封裝內亦有同份收據。checkpoint保持PREPARED，不製造REMOTE_VERIFIED收據。操作及下次簡短指令見 README.md。
