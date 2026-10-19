# template-Ai 開發入口（Human 與 GPT 共用）

**核心規則**：[零例行對話、上下文節制與GitHub持久化](docs/dev/CONTEXT_AND_PERSISTENCE_RULES.md)。先搜尋路徑／關鍵字再讀相關段落，一般工具回傳≤1600 tokens；新對話先跑`python tools/resume_status.py`，只讀精簡接手，不展開整倉庫、完整聊天或大型日誌。大型圖片／PDF／模型／設計檔以檔案工具按頁／區域處理，禁止大量base64／全文回填。

**開始或恢復工作前，依序讀取**：
1. `docs/dev/STATE.json`：目前 checkpoint、工作包、下一步及阻擋。
2. `docs/dev/ACTIVE_DEVELOPMENT_HANDOFF.md`：精簡當前交接；僅按需讀`HANDOFF.md`最新相關段，歷史／詳細決策分檔，不整份展開。
3. `docs/dev/PROJECT_GOAL.md`／`PROJECT_ROADMAP.md`與STATE.active_contract，恢復全清單目標及當前驗收；再讀 `docs/dev/REQUIREMENTS.json` 與 `docs/dev/FEATURES.md`：要求、驗收條件及完成證據。
4. `docs/dev/WORK_LOG.md` 最新紀錄；`STATE.json` 指向的 checkpoint 收據與證據 run。
5. `docs/dev/DEVELOPMENT_PROTOCOL.md`：保存、GitHub 讀回及證據覆核規則。

不要只讀歷史 `CONTINUATION.md` 就開工；它是歷史索引。核對 main 與尚未合併工作分支，本專案目前在 `dev/v0.1-first-version`／PR #2。

## 2026-10-19最新設計澄清

先讀docs/decisions/2026-10-19-CORE-ADAPTATION-SWAPS-AND-DEFAULTS.md及docs/dev/SWAP_ADAPTATION_AND_DEFAULT_PREFERENCE_TRAINING_PLAN.md。同模板合法交換優先，所有多合法結果有預設優選，客戶明確關係優先。新實例字級／字寬／欄位尺寸／切齊／分散由核心規則聯動，無客戶細參數控制；舊模板／定稿版本保留。自動採用背景候選仍OPEN。這是未實作設計更新，不把歷史1567PASS當新能力已完成。

## 目前實作狀態（2026-10-18）

AI01觀察資料／儲存／自動分析基礎已部分實作；18新增測試包含於當前1567項正式回歸，全數PASS、198程序正常、native附件通過。新8工作包仍1partial、0完整完成／驗證，3訓練設計待辦0完成，尚未訓練；舊段落的0實作為先前歷史。以STATE與ACTIVE_DEVELOPMENT_HANDOFF為準，下一步可信來源字型／glyph與完整lineage，不再重問已決訪談。

## 核心宗旨

- 每個工作包需參照數學演算法、成熟開源與商用軟體公開思路；保存實際來源／版本／hash、重用選擇及驗證，不重造已有引擎或平行資料庫。本輪具體依據見`docs/dev/TWENTY_ENGINEERING_BASIS.json`。

- 零例行問答、持久化優先。使用既有授權與要求自主推進，不反覆詢問是否繼續、是否保存、是否使用已定方案；必要未決資訊記為 BLOCKED，先做其他已授權工作。遵守較高優先指令要求的必要狀態訊息。
- **每個可恢復工作包、每 10 分鐘、中斷前、環境／資料結構變更前後都建立 checkpoint**。本機 ZIP 只是 PREPARED；GitHub commit/tree 逐檔讀回後才是 REMOTE_VERIFIED，收據也要保存 GitHub。不得覆寫歷史 checkpoint。
- 首先執行 `python tools/dev_governance.py check`；讀取下一個已核准且未完成的要求。框架或證據不完整先修治理，不把未測試功能標為完成。
- 修改前寫要求 ID、验收條件、預計測試及 checkpoint；修改後保存程式、工作紀錄、狀態與證據，更新機器登錄並產生人類清單。最後再次執行 check。
- 每次開發保留功能清單基準／結束快照，從 REQUIREMENTS.json 生成 CURRENT_PROGRESS.json／PROGRESS.md；最終回報原始需求各狀態、已驗證 CORE 功能子項、GOV 治理及本輪新增／修訂／完成差異。部分實作不得當整項完成，新增拆分不冒充完成率提高。計數改變同步保存 GitHub；新定案見 docs/decisions/2026-10-14-PROGRESS-REPORTING.md。
- 完成狀態只能由對應測試與證據判定。未執行／跳過／失敗、只測 Linux、只用合成樣本均如實標示；不可用整批 PASS 證明所有需求已完成。
- **EXE 不屬目前工作目標**。不得重跑失敗打包、建立新 EXE CI 或把 EXE 當功能完成條件。既有流程只保留人工 dispatch；之後有新明確交付指令才處理。
- 先完成核心軟體要求；印刷分析在軟體完善後，完整 UI-048 權限維持最後功能順序，UI-056-D 與待決報告需求不提前加入。
- 重要變更用分支＋PR，不自行合併 main；自我驗證不是獨立覆核。不把真實個資、私人 AI 原稿、受限字型與密鑰上傳 GitHub。
- 此文件不授權多代理。沒有使用者的明確要求，不啟動其他 agent。

## 可重現命令

```bash
python tools/dev_governance.py check
python tools/dev_checkpoint.py prepare --id CP-UNIQUE --base-commit <SHA> --summary '<內容>' --next '<下一步>' --requirements <ID>
python tools/run_evidence.py --run-id RUN-UNIQUE --source-commit <SHA> --commit-json <GitHub讀回commit.json> --tree-json <GitHub讀回tree.json>
python tools/dev_governance.py render
```

GitHub 操作可用正常 Git CLI 或連接器。來源 commit 與 tree 必須實際讀回；沒有 Git HEAD 的工作區不得虛構 HEAD，使用已確認遠端 SHA 與快照。上傳中斷時保留本機快照與 pending 記錄，下次先恢復保存。

## 本輪使用者核准的證明附件保存例外

2026-10-14使用者後續指令以開發速度優先，9件證明附件略過上傳，精確決策與清單在STATE／EVIDENCE_PUBLICATION_EXCEPTIONS。乾淨checkout的原check若只因該9件附件失聯，先執行docs/dev/EVIDENCE_PUBLICATION_SCOPE_CHECK.md的只讀核對，再按STATE直接下一包；不重複要求授權或上傳證明附件。其他程式／測試／metadata缺失、hash不符或功能失敗仍需先修。此例外不宣稱全附件require-evidence Gate已PASS，不更動原run／失败测试或父需求完成判定。新來源仍要正式回歸，EXE規則不變。

## 目前使用者持續開發指令
本輪零例行問答與跨對話接續目標見 `docs/dev/ACTIVE_DEVELOPMENT_HANDOFF.md`。以 STATE.active_contract 最新契約為準；每個可恢復階段及每10分鐘保存GitHub checkpoint，不把子包或目標測試PASS當完整父題。

## 2026-10-17 核心產品定義澄清

使用者明確拒絕一作品一模板作為Template AI目標；核心為跨作品學習共用設計規則、生成模板，對新輸入檢索最佳候選或合成自動排版。最新方案／契約見STATE.active_contract與AI_CROSS_WORK_LEARNING_PLAN.md；新學習8工作包目前0實作／0驗證。舊25/28與1549測試屬既有流程範圍，不能當新核心AI已完成。新方案及數值尚屬工程建議；不改寫舊不可變證據、不因規劃而增加完成數。

## 2026-10-17 四類風格與 card-interface 對帳

詳見docs/dev/CARD_INTERFACE_STYLE_LEARNING_REVIEW.md與有效contract：8包50規劃驗收，0實作／0驗證。先讀固定版本原型交接及最新核心／UI-013/061/062；區分重用、擴充、規格衝突、未驗證。客戶字級／字寬／tracking／單雙排控制已撤回；示例computePlan、70%與FNV不作正式排版／印前。觀察到新風格不等於有權取消固定pt、分散語意、預覽確認或正式Gate。

## 2026-10-18 已確認的結構／文字共同學習

設計依據見docs/decisions/2026-10-18-FIELD-STRUCTURE-TEXT-EQUIVALENCE-LEARNING.md及activecontract.field_structure_learning_basis：分割／對齊／排列與文字配置互相約束，條件等效角色及可變文法支持更靈活排列與更少重複模板。等效先核對角色／語意／歸屬／政策，再驗實際文字；同框不能唯一推定字級或任意交換資料。不強併家族、不改固定pt或正式Gate。這是已確認設計原則；仍8包50規劃條款0實作／0驗證。

## 2026-10-18 最新排程：本體先行，網頁／手機延後

使用者指令見docs/decisions/2026-10-18-CORE-FIRST-DEFER-WEB-MOBILE.md。先在既有Template AI本體完成學習、規則／等效欄位、生成／排版、排序回饋與持久驗證。card-interface是保存的未來使用情境及核心設計參考；網頁／手機實作與裝置驗收延後。可準備共用資料／操作／結果與版本邊界，不提前搭前端或公開API平台。契約delivery_priority及條款delivery_scope/scope_parts區分當前核心與保留後續需求；延後不等於完成，未來前端不阻擋本體工作。

## 2026-10-18 已確認：本體端到端互動必須交付

見docs/decisions/2026-10-18-DESKTOP-END-TO-END-INTERACTION.md與contract.body_interaction_goal。本體需可實際輸入→初稿→微調相對位置→局部更正返回→預覽確認→驗證輸出；底層函式或契約本身不足。延後的是獨立網站／手機／裝置適配，不是本體必要互動。AI07 A05/A06/A07範圍已釐清，4情境為原50驗收細化且尚未執行；不取消固定pt、資料歸屬、來源／資產／正式Gate或恢復已撤回客戶控制。

## 2026-10-18 訪談：先學容量與字串區間再引導輸入

見docs/decisions/2026-10-18-LEARNED-CAPACITY-INPUT-GUIDANCE.md及contract.learned_capacity_input_policy。容量／區間依尺寸、家族、角色組合、字型固定pt與資產條件化，經驗證後供本體輸入引導／限制。訓練最大值不直接當硬上限，單欄區間不能證明聯合可行；保留UNKNOWN與實際Gate。A/B/C重排範圍尚未選定；下一題釐清最適品質目標。未訓練、未定數值、未新增完成數。

## 2026-10-18 訪談已定義：合格訓練風格為適合區間

見docs/decisions/2026-10-18-QUALIFIED-TRAINING-STYLE-SUITABLE-REGION.md及contract.qualified_training_style_region。以合格TRAIN作品的有證據風格特徵學條件／聯合區域，保留多種與低支持合格風格；UNKNOWN不當真值、封存資料不回填擬合。品質來源已決，合格集合／標記及准入證據待訪談。適合區間不豁免正式Gate，未定數值／未訓練／未新增完成數。

## 2026-10-18 最新訪談範圍：模型／資料處理先行

見docs/decisions/2026-10-18-MODEL-FIRST-INVERSE-REQUIREMENTS.md與contract.model_first_interview_scope。先談資料表示／模型輸出／參數及訓練驗證；交互設計待結果再談，既有需求反推等效群／條件替代／相對關係／聯合容量等必要模型資訊。AI08改依賴06，移除07交互前置；07最終目標保留，等可檢查結果再恢復討論。下一題談等效群的語意粒度，未回答的合格集合題暫緩，不代選。仍8包50條0實作／0驗證。

## 2026-10-18 新增3項訓練設計待辦

依使用者指令，activecontract.training_design_todos登錄TRAIN-DESIGN-01資料需求、02欄位／容器能力、03條件相容／等效／替代；人類清單docs/dev/AI_TRAINING_DESIGN_TODOS.md。目前3項TODO_DESIGN、0完成；設計子待辦不增加原8包50驗收或功能完成數。先做schema／特徵／參數／訓練／參照與驗證設計，再實作；兩個邏輯視角不預設兩個獨立模型，類別／閾值與跨類權限留待設計。交互仍待訓練結果再談。


## 2026-10-18 訪談先查既有決策，避免重複

使用者要求重新詳讀舊訪談並停止相似概念重問。先讀docs/dev/AI_TRAINING_INTERVIEW_REVIEW.md與AI_TRAINING_INTERVIEW_DECISION_INDEX.json；多人／共享／同檔多作品／客戶庫／雜訊／合格風格／容量與兩個視角均已定案。UI-043取代UI-042舊交易分類，不設曾設計／已購買或購買證明。剛提出的多人欄位獨立／共用題已撤回，無需再問；作品可檢視事實與工程參數改由來源／驗證處理。提問前核對語意重複與後續取代，僅真正新的且阻擋工作的使用者決策才提問。此索引不增加需求／完成數；新AI與3設計待辦狀態不變。
