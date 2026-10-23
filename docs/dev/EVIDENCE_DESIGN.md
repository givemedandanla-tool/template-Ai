# 適合 Human 與 GPT 覆核的要求及證據方案

研究日期：2026-10-13。採用版本化 Markdown／JSON、個別測試結果與匿名附件，先不引入新的付費服務或重型資料庫。

| 參考方案 | 成熟思路 | 本專案的採用方式 |
| --- | --- | --- |
| [OpenAI Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | 程式代理在工作目錄階層讀取持久指令 | 根 AGENTS 固定讀取 STATE、交接、要求、證據及工作紀錄；workspace 本機入口也指回倉庫 |
| [GitHub Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/copilot-in-your-ide/customize-copilot/configure-custom-instructions/add-repository-instructions-in-your-ide) | 倉庫指令供代理及覆核使用 | `.github/copilot-instructions.md` 轉到同一入口，避免兩套規則 |
| [GitLab requirements](https://docs.gitlab.com/user/project/requirements/) | 需求識別碼與測試報告關聯 | 每條需求／CORE 驗收條件具固定 ID，只以具名測試滿足個別條件；不採「全部需求 passed」泛化 |
| [GitLab JUnit reports](https://docs.gitlab.com/ci/testing/unit_test_reports/) | 結構化個別成功、失敗、跳過及檔案定位 | 每次真實 unittest 產生 JSON 與 JUnit，保留失敗細節；方便其他 CI／Human 工具閱讀 |
| [Allure test result format](https://allurereport.org/docs/how-it-works-test-result-file/)／[attachments](https://allurereport.org/docs/attachments/) | 穩定測試識別、參數、狀態與可檢查附件 | run.json 連到確切測試、驗收條件、來源 commit、環境與 PNG／PDF／JPG；無需安裝完整 Allure 服務 |
| [DVC experiment management](https://doc.dvc.org/user-guide/experiment-management) | 程式、參數、指標、資料版本可重現關聯 | source manifest、合成 fixture ID/hash 與輸出 hash；將來有大資料／模型才評估 DVC 遠端，而非現在空稱已部署 |

## 證據包契約

每個 run 包含 `run.json`、`source-manifest.json`、GitHub 讀回 `commit.json`／`tree.json`、`tests.json`、`junit.xml`、原始測試日誌、`claims.json`、附件清單與合成實際產物。

- **版本**：測試對象的不可變 commit、逐檔 Git blob SHA 與 SHA-256；程式、测试或 fixture 改動讓舊證據標 STALE，不能沿用原 PASS。
- **驗收**：要求 ID → acceptance ID → 精確 TestCase ID → 實際結果。預期行為寫在要求中，實際斷言在引用測試檔；GPT 可讀源碼並重新執行。此版不宣稱已捕獲每次 assert 的運算元；量測型驗收另保存實際數值／期待值，不以摘要代替。
- **環境**：Python、PySide6、Inkscape、OS、Qt 平台、實際命令與限制。Linux 合成來源證據不能證明 Windows、VivoBook、RTX 5050 或原生私人 AI。
- **附件**：匿名實際 GUI 與 PDF／PNG／JPG，具 MIME、bytes、hash 及相對路徑；附件內容永久保存到該 run 的 GitHub 路徑。圖片需由覆核者實際查看，無任意相似度門檻冒稱原稿一致。
- **審查**：實作、SELF_VERIFIED、AI_REVIEWED、INDEPENDENTLY_REVIEWED 分開。AI 覆核必須另寫 reviewer、來源 commit、看過的要求／檔案／附件、問題及重現結果；模型不得自填獨立審查。

## AI 覆核步驟

讀入口／STATE；驗證 checkpoint 收據；執行 governance check；挑下一需求，核對 acceptance、源碼與 tests；讀對應 run 的個別結果和附件；以相同 commit 重新執行；將差異、失敗與範圍寫入獨立 review 記錄，才決定該範圍是否可標完成。沒有連接倉庫或工具的純聊天 GPT 不能被此框架保證自動讀檔；支援 AGENTS 的 Codex 與有 repository instructions 的代理會取得入口，其他使用者從 README 的「AI 從這裡開始」进入。

## 狀態與防止誤報

父需求：NOT_IMPLEMENTED、PARTIAL、IMPLEMENTED_UNVERIFIED、VERIFIED、DEFERRED、BLOCKED。`completed` 為單獨布林，VERIFIED 需具條件完整、逐項必測 PASS、有效來源版本及可讀證據；本地 CORE 完成仍保留平台／資料範圍。跳過＝未驗證；測試總數＝不等於需求覆蓋率。範圍變更必須保留較新使用者來源，不偷偷縮小驗收來提高完成率。

## 本輪界線

此為開發治理與開發者證據，不是 UI-066 未決的產品診斷報告格式。EXE 只保留人工日後交付工具，不列本期功能 Gate。不可用文檔自動發現能力，宣稱已建立 24 小時自主編碼服務。初始實作均為自我驗證；未做獨立 Human／AI 覆核。
