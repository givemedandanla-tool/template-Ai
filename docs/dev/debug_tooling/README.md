# 除錯與程式查重：本機開發幫手

這套工具協助 Codex 找線索、保留既有問題並檢查新增問題；不影響你日常開啟 Template AI。產品程式、私人作品、字型、資料庫及模型沒有因本輪而改動。

## 現在裝好了什麼

| 幫手 | 用途 | 固定版本 |
| --- | --- | --- |
| Ruff | 常見未定義名稱／語法線索 | 0.17.1；啟用 F821/F822/F823，語法錯誤仍會回報 |
| Pyright | 呼叫參數、回傳值、可能空值及其他基本型別線索 | 1.1.414，basic；使用實際應用程式 Python |
| jscpd | 找符合 10 行／70 token 門檻的相同程式片段 | 5.4.1，strict／Python；不啟用語意模型或 API |
| diagnosing-bugs | 重現→根因→修正→回歸的有界調查流程 | mattpocock/skills 固定 commit，MIT |
| dry-refactoring | 閱讀兩段程式與呼叫者，判斷是否值得共用 | kucherenko/jscpd 固定 commit，MIT |

來源與完整性在 TOOLCHAIN.json、requirements-tools.txt 與 node/package-lock.json。頂層授權為 MIT；保留原套件內授權與本目錄授權副本，不把開發工具放入產品／EXE。

兩個專案 skill 入口是 `.agents/skills/template-ai-diagnosing-bugs` 與 `.agents/skills/template-ai-dry-refactoring`；canonical 內容在 skills/，上游原文在 vendor/。本輪已明確讀取並用於示範及判讀。當前平台 executor skill 清單沒有自動顯示新入口，因此原生自動載入仍未驗證；可直接要求 Codex 讀對應 SKILL.md，不能把檔案存在當成平台已載入。

## 下次可以直接說

「請讀 docs/dev/debug_tooling/README.md，使用既有除錯與查重工具檢查本輪修改。保留既有基準；新增程式也要與未修改舊程式比較。單一 Codex、零新增費用，不自動重構或推送。」

若有實際錯誤，補上想完成的工作、實際結果及安全問題報告。私人原稿與完整工作目錄不需要提供。

## 首次準備與重建

先準備既有應用程式 `.venv`、Python >=3.11、Node >=18 與 npm。這些是開發者工具需求，不會改成產品啟動需求。本輪實測是 Linux／Python 3.12.14／PySide6 6.8.3；Windows 與原生 Python 3.11 尚未驗證。

在專案根目錄明確執行：

```text
python docs/dev/debug_tooling/bootstrap.py
python docs/dev/debug_tooling/bootstrap.py --check
python docs/dev/debug_tooling/quality.py selftest
```

只有第一個準備命令允許下載固定工具；pip 核對官方 wheel SHA256，npm ci 核對 lock/SRI，停用安裝腳本、audit、fund 與更新提示。一般檢查不執行 pip/npm/npx、不下載模型、不連接分析服務。工具預設在已忽略的 `.cache/debug-tooling/`；可用 `TEMPLATE_AI_QUALITY_HOME` 指定隔離位置。本輪為節省工作區空間，該路徑連到本機暫存工具目錄，可用同一命令重建。

完全離線重建時，從相同作業系統／架構複製工具目錄中的 wheels/ 與 npm-cache/ 到新工具目錄，再執行 `bootstrap.py --offline`。本輪已在全新工具目錄實際重建成功。不同平台需在明確準備階段另備相符套件，不假設 Linux 快取適用 Windows。

## 一般檢查

```text
python docs/dev/debug_tooling/quality.py check --scope application
python docs/dev/debug_tooling/quality.py check --scope tools
python docs/dev/debug_tooling/quality.py check --scope tests
```

application 包含 template_ai/ 與 app.py；tools 包含既有 tools/ 及本輪兩個工具入口；tests 包含原測試及本輪獨立工具測試。明確列入新／未追蹤檔案，不只掃 Git diff。第三方、產生檔、建置、快取、虛擬環境與私人資料排除；詳細清單／理由在報告。

每次結果保存在隔離工具目錄的 runs/。可用 `--output 新目錄` 指定位置，既有目錄不覆寫。`--python 應用Python路徑` 可指定既有應用環境，缺件只報錯，不自動安裝。

退出狀態：check 的 0 表示沒有新增診斷，1 表示有新增診斷，2 表示工具／設定／範圍出錯。scan 的 0 只表示掃描完成，結果仍可包含大量既有診斷。原工具退出碼與指令另外保留，不能把有診斷的掃描稱為乾淨。

Ruff 與 Pyright 有各自完整輸入清單；jscpd 的 sources 統計只包含達到固定長度／token 門檻的檔案，所以同時報告全部輸入、短檔案與合格來源數，不調低門檻膨脹涵蓋率。零合格來源會阻擋；原始檔或設定掃描中變動也會阻擋。

## 基準不是免責清單

baselines/ 分別保存三個範圍的初始診斷、指令、版本、設定 hash、來源逐檔 hash 與環境。相同問題移動行號不會被誤算為新增；同樣問題多出一份，仍會被當成新增。

基準內問題保留為待辦，不代表已修正。基準只適用相同工具／設定／入口／Python／PySide6／平台，環境不同會拒絕比較。升級或搬到 Windows 時，先說明差異，另外保存基準，不覆寫現有檔案。

初次基準建立命令需要既有 report.json、明確理由及不存在的新目的檔：

```text
python docs/dev/debug_tooling/quality.py baseline --report 掃描目錄/report.json --output 新基準.json --reason 初次建立的具體理由
```

不要用這個命令把新增問題重新收進基準來取得通過。改名／近似／結構相似屬後續人工判讀，不是本輪 exact 基準；若日後另開檢查模式，須分開固定設定與基準。

## 首次結果與限制

576 個 Python 輸入：應用270、工具60、測試246。Pyright 診斷分別4212／521／7065；它們是待判讀資訊，不是11798個已確認產品錯誤。本輪新增工具／測試沒有 Ruff／Pyright 診斷；兩個新增 Node 路徑型別問題已修正。

jscpd：應用0、工具2、測試5組相同片段，僅限固定門檻。6組有理由保留，1組列低優先共用函式候選。全部判讀、呼叫者及理由在 BACKLOG.json，不以查重數字驅動重構。

Ruff 有3筆已確認解析限制：分號後合法的 match 變數被誤判，0.17.1／0.16.0／0.15.6皆可重現。保留這3筆診斷並標示工具限制，未改產品或隱藏警告；Ruff 在這3檔的名稱分析不完整。所有檔案另以實際 CPython 編譯及3.11語法模式核對，Pyright也涵蓋這3檔。這不是原生3.11或Windows實測。

11項工具測試及7項既有相關測試以既有程序隔離入口執行，18 PASS／0 runtime error。隔離示範驗證9項行為，包含新增對未修改舊程式、保留舊診斷、抓新錯誤及只修示範後清除新增；不代表修正了產品錯誤。原1850項完整產品回歸沒有重跑，原產品程式與資格狀態未變。

## 保存與費用

本輪沒有推送、PR、CI、EXE、子代理、外部模型、試用、新付費資源或帳務變更。無法核實 GitHub 額度／連帶服務，因此只保存本機提交、checkpoint 與可恢復差異包。沒有帳務證據，不能推論實際帳單數字。

本機恢復包：`.cache/debug-tooling/delivery/DEV-QUALITY-001-local-delivery.zip`。包含精確 base/head、差異 patch、Git bundle、逐檔與封裝 hash、還原核對結果及白話說明。需搭配基底 `0e7b8aee82331ff6efa02a1a8233ff85689b660a`；patch已在隔離目錄核對並實際套用，不包含私人資料或工具二進位檔。

雲端草稿追加了受檔案存在檢查保護的重建說明，已讀回、未發布；不會把仍在本機的原碼說成已上 GitHub。詳見 CLOUD_SETUP.md、reports/cloud-draft.json。平台草稿不是原碼遠端備份。
