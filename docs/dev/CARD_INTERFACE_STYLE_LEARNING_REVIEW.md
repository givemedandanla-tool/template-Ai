# 四類風格學習與 card-interface 核心整合對帳

2026-10-17。使用者要求學習分散對齊、字級縮放、資料相對布局、欄位分割與對齊，並指定依 card-interface 閱讀順序核對最新版核心。本文件是已完成的閱讀／方案，**不是引擎或網站已實作**。新增要求已記錄；工程設計為 PROPOSED，政策 OPEN 不因本次存檔轉為核准。

## 1. 實際閱讀基準

- card-interface/main：`ebf3ccb0b3ab2e7ab602ce2f224186c401e29ea0`；README → AGENTS → START_HERE → DESIGN_DECISIONS → STATUS_AND_GAPS，再讀 UX_SPEC、ARCHITECTURE、TEMPLATE_AI_INTEGRATION、TESTING；核對最終 index.html 的 measure／computePlan／sortedContacts／applyTarget／doSolve／undoLayout／safeImport／confirmDraft、測試與報告。
- Template AI：`12604350b5b92c5dad32b80fe80246bea21a6940`，分支 `dev/v0.1-first-version`。遠端該分支與本機相符；main 為 `436ca2d7db10fab3de3d9700538dee701cd81a97`，工作不在 main。此後本輪提交僅保存文件／收據。
- 整合指引的舊觀察 `eaf794e…` 不是最新版本；本輪重讀 layout/custom_layout/candidate_risk、text_policy/render、candidate_sync/layout_session/workbench_navigation 相關段。前三個檔案在該舊觀察至本輪基準間無差異；UI-061／062 仍須看目前登錄與程式，不能只沿用決策文件當年「未開發」的標頭。
- 現行 UI-013 CLAUSE-2/3/4/6、UI-061、UI-062 正式決策及 REQUIREMENTS 均已核對。UI-061／062 目前登錄 VERIFIED，證據是 CURRENT008 的受控 Linux 軟體範圍；不推論網站／真手機已驗證。
- [來源與 SHA 記錄](../qa/plans/CARD-INTERFACE-REVIEW-BASELINE-20261017.json)；[本輪原型測試](../qa/plans/CARD-INTERFACE-PROTOTYPE-RERUN-20261017.json)。原型無開源授權；本輪只參照設計與契約，不複製另一倉庫程式或資產。

## 2. 四種分類

「可直接重用」指沿用契約或呼叫既有核心；不是把 Python/Qt 直接貼進瀏覽器。

| 分類 | 對象與已讀事實 | 實作處理 |
|---|---|---|
| REUSE | 先完整初稿→可選微調→確認；無客戶字級／字寬／單雙排／必選模板庫 | 網頁／手機沿用體驗契約；後台專業工具與客戶面板分開 |
| REUSE | 穩定人物／公司／欄位 ID；資料／版面版本分離；改內容後舊確認失效 | 重用既有語意映射、版本柵欄與局部復原；不能靠相同字串合併 |
| REUSE | 真實字型量測、Kiwi、風險與印前 Gate、每尺寸公司 Logo、候選同步／安全返回 | 正式核心為權威，前端用結果顯示；不可拿 browser measureText 取代 |
| EXTEND | 拖曳代理＋落點在原型可操作，但只有同人物聯絡資料上下關係 | 建核心語意命令與核准拓撲變換；pointermove 只做前端回饋，放開才求解 |
| EXTEND | 跨作品風格／家族、條件文法、偏好回饋、正式生成實例資格 | 依原8工作包擴充，使用原 SQLite、求解器與 Gate，不另造配方引擎／主檔 |
| EXTEND | 原型主表姓名40／職稱60／公司60字元，局部編輯120、匯入又較嚴（G08） | 核心共用schema及round-trip，不能將原型入口不一致帶入正式產品 |
| EXTEND | 網頁／手機入口、冪等／期望版本、正式結果封存 | 抽取既有核心服務邊界；跨裝置登入／保存期限為 OPEN，不先做永久訂單庫 |
| CONFLICT | 因長字串而縮小／放大 pt；任意擴張分散欄位 | UI-013 禁止前者；text_policy 目前限有核准記錄的職稱／地址。可觀察學習，但未核准不可啟用越界規則 |
| CONFLICT | 把 custom repair 直接當通用拖曳；低影響跨模板默默採用 | custom_layout 保留原不重疊拓撲，已有合格模板會拒絕修復；UI-061 跨目標套用需差異預覽確認，layout_session 亦有採用／人工保護。需新增受控操作入口，不能偽裝無解 |
| CONFLICT | 為每案建立全域模板／設 published 繞過審查 | 原型與新產品目標都拒絕前者；現行正式 Gate 不接受客戶確認冒充模板／規則發布資格 |
| UNVERIFIED | paired/flow、70% 字寬、90×54、1～2人、一家公司、95ms、FNV指紋 | 全是示例；不可升格產品上限、可讀性門檻、效能 SLA、安全簽章或正式回播 |
| UNVERIFIED | 真手機、跨裝置一致、真實模板／字型／Logo、色彩／材料／製版成本、安全與無障礙 | 原型37項不覆蓋這些；按 STATUS_AND_GAPS G01～G14 分項實測，不標示已上線／可送印 |

## 3. 先把觀察資料補齊

現有 Slot 主要是一個框及單行文字屬性，不能只靠框推論字內分散、行基線或欄位文法。DesignObservation 增加四組型別資料，欄位均帶 source/hash、MEASURED/SOURCE_DECLARED/ESTIMATED/UNKNOWN/HUMAN_CONFIRMED、量測單位與不確定度：

| 組別 | 應保存的參數 |
|---|---|
| text_runs | 實際 font face/hash、pt、字重、來源變換、自然成形 advance、glyph/cluster 與 baseline、行框／實際 glyph 位置、字距及可分散邊界 |
| alignment_style | 模式、軸、作用單位 grapheme/word/field/group、左右錨點、最後一行政策、允許角色／語系／群組、設計間距與上下限、來源支持 |
| font_hierarchy | 基準角色、基準 pt、角色間 pt 比例／log 比例、允許的成品尺寸／設計情境、字型差異、來源支持、政策版本 |
| layout_structure | 語意角色與實體綁定、容器樹、欄／列、群組、padding/gutter、同基線／同邊界／先後順序、optional/repeat/flow、分隔線角色 |

缺 glyph 位置時，字內分散標 UNKNOWN；點陣／轉曲作品可學群組幾何，但不得將 OCR 框高當真實 pt 或假造字距。相同公司電話兩次出現仍以欄位 ID／引用關係區分，不能被語意分割合併掉。

## 4. 四類風格如何學與如何執行

### 4.1 分散對齊

先辨別「字／詞間距」與「整筆資料物件等距」。後者是群組布局，不應改動電話或 Email 內部字距。從來源文字 run 的自然字形 advance 與實際起點／終點差估計剩餘空白，只在合法的 grapheme/word 邊界分配。初步候選量 `delta=(目標 span−自然成形 advance)/合法可擴張邊界數`；邊界數為0、負空白、超政策上限均不能硬拉。結合字形位置與顯式樣式辨識，僅靠這個式子不能斷定來源使用分散對齊。

物件等距則以 `(容器可用長度−各物件實測長度總和)/(物件數−1)` 提候選 gap，單物件另處理；負值改走核准重排或阻擋，不擠壞 Logo／刪文字。結合 kerning、連字、組合字、標點、語系與最後一行政策；不可用 Unicode codepoint 數冒充可分散邊界數。

在同家族／角色／情境中彙整模式支持率與 gap median/MAD，學出條件偏好及反例。先支援有核准記錄的職稱／地址，任何新角色或 per-word/per-line 邊界政策保持提案，不能由支持率自動核准。現有 tracking_geometry 可重用固定 pt 量測與有界搜尋；要做逐行／選擇性邊界需擴充共享文字布局資料，Qt 量測與 render 使用同一 run 位置，不能僅改 CSS text-align:justify。

### 4.2 字級縮放／層級

分開學四件事：**字級 pt、角色字級比例、字形水平 ScaleX、字距 tracking**。例如 `r_role=log(pt_role/pt_body)`，在字型 face／用途／尺寸情境內用穩健統計學比例及適用範圍；跨字型還需真實量測和可讀性核對。外框高度及 CSS px 不是 pt。每個已知字級必須能追溯至來源樣式與變換。

現行可行路徑是：先按欄位語意、核准設計層級與物理尺寸決定候選字級 → 凍結當次各角色 pt → 同一輸入適配只調核准框位／ScaleX／tracking／對齊／換行。手機螢幕縮放只是顯示，不改印刷 pt。不要透過反覆選較小字級候選來偷偷實現長文字縮字；同一核准設計配置的字級選擇輸入不得含字數／字寬等內容長度代理。

學到「長地址常用更小字」可以保存為觀察；啟用長度驅動縮字、拖曳引起配置字級切換、依人物數自動換字級，仍涉及 UI-013 與 card-interface D21 的 OPEN 邊界，這輪不改核准政策，也不加客戶控制。若未來要改，另存明確政策差異／核准範圍，再做回歸；不把單次學習模型輸出當授權。

### 4.3 資料間相對位置

學 field/group/container 的關係圖，節點是角色＋歸屬，邊可為 above/below/left_of/right_of/same_baseline/align_edge/inside/spacing。座標正規化之外保留 mm；gap 可對容器或基準行高正規化。用附近對象、同行／同欄候選產邊，避免無界全物件配對；按多個獨立 lineage 的支持與反例學共用關係。

先由文法列舉有限合法順序／分組，再把選定拓撲編成線性約束，例如 `y_mobile >= y_tel+h_tel+gap`、`baseline_a=baseline_b`、`x_a=x_b`。Kiwi 求座標，不能單獨發明結構或自動處理任意不重疊的非凸選擇。資料完整性、所有權、核准客戶關係及保護是必要條件，美感分數不能抵銷。

拖曳只新增／取代明確關係，分開保存系統偏好與客戶意圖。SET_RELATION 需穩定 field_id、scope(candidate/size)、expected_data/layout_revision、policy_version、request_id；核心重新驗證，循環衝突／非法歸屬／過期操作保留有效成果。同一命令重送無額外位移，晚到求解結果不能覆蓋新稿。

### 4.4 欄位分割與對齊

不是按字串中空格機械切欄。先用來源圖層／框／基線／空白與語意形成候選區塊，再辨識人物區、公司區、標籤＋值、圖示＋值、聯絡群、欄／列、重複群組；資料歸屬優先於視覺接近。空白和裝飾分隔線只是證據，不等於一條業務欄位。

學容器樹與對齊線、欄數／欄寬比例、padding/gutter、標籤寬、baseline、區塊間距、repeat/optional、何時換列及缺欄後如何收合。同家族可學到合法分割／合併條件；不列舉每種電話數量成一張固定模板。群組子結構是否可組合要有同家族規則及資產證據，不能任意剪接不同模板。

同筆文字的多行只改顯示 flow，不拆／改原始欄位 ID，不遺失資料；電話／Email／社群ID不能任意斷開。實際行基線、行距、斷行及寬高必須由正式字型布局輸出並整張重新 Gate。正規化欄位分割可提出規則，但尚無現成證據證明本專案已能自動學成。

## 5. 從 card-interface 補出的其他必要學習

| 還需學什麼 | 訓練資料／方法 | 執行與驗證 |
|---|---|---|
| 多筆／多人／多公司可變結構 | 同家族獨立作品的角色／引用／容量、optional/repeat；未知不能當刪除規則 | 輸入新增／移除欄位、重複字串不同主人、未完成第二人，驗證無損映射 |
| 文字流與閱讀順序 | 語系、baseline、行距、合法換行、標籤／值組合 | 長中英混排／標點／組合字，量測與輸出一致；不靠縮 pt 解決 |
| 留白、密度與視覺層級 | 容器占用率、群組間距、強調角色、色彩／背景角色 | 獨立偏好比較，不能把框塞得下當美學真值；色彩印前另驗 |
| Logo／固定圖形／背景的共存 | 完整資產及用途、尺寸專用證據、可避讓／不可變形範圍 | 缺失／不合尺寸／來源未知不得借其他作品 PASS；不學壓扁 Logo |
| 最小必要改動與保留意圖 | 同一資料的前稿＋操作意圖＋後稿＋範圍＋接受／拒絕；缺理由保持未知 | 固定硬關係後比較無關區域移動，模板切換仍遵循預覽／確認與版本保護 |
| 偏好適用範圍 | 個案／個人／公司／家族範圍、反例、獨立選擇對 | CatBoost PairLogit 僅排可行候選；一次接受不直接寫全域規則 |
| 可重現與依賴 | 資料／意圖／基準稿／規則模型／政策／模板／字型／Logo／引擎完整 pin | 封存真實結果，修改介面不重新生成定稿；JSON進度重算不冒稱封存 |

版本柵欄、冪等、安全授權與確認失效是確定的工程契約，不是需要 AI 自己學的規則。資源權限必須在公開入口成立，不受完整後台 UI-048 排期影響。正式保存期限／跨裝置服務等仍是產品 OPEN，先設契約不自造第二套永久庫。

## 6. 訓練與現成方案分工

沿用 [跨作品主方案](AI_CROSS_WORK_LEARNING_PLAN.md) 的 lineage 去重／70-15-15 TRAIN/VAL/封存TEST、HDBSCAN 家族、median/MAD 與有足夠情境支持的條件擬合、Cassowary 幾何及 CatBoost PairLogit。四類特徵加入同一觀察→家族→規則→合成管線，不各造一套模型／資料庫。小資料先穩健規則；RANSAC 不負責學離散對齊模式，CatBoost 不負責合法性，LLM 不作正式幾何權威。

成熟依據仍是先前已固定版本／hash 的 Qt/fontTools/Kiwi、scikit-learn、CatBoost、Figma公開 Auto Layout 型別（容器／flow/wrap/padding/alignment 思想），以及 LayoutDM 條件生成研究。見 [工程來源](AI_CROSS_WORK_ENGINEERING_REFERENCES.json)。card-interface 的 REFERENCES 提供 CHILI GraFx 物件政策、Customer’s Canvas 工作流、Scout、Konva 等後續線索；本輪只讀該參考文件，未重訪各外站，不把其版本／授權／效果當新增核實依據。無採購、付費 API、模型租賃或新套件安裝。

學習結果需帶適用條件、獨立來源支持、誤差與反例，不聲稱模型能任意增加參數／變更政策。新規則經候選→驗證→明確啟用／回滾生命週期；已確認稿不因新模型自動改寫。

## 7. 實作順序與檔案邊界

1. **AI-LEARN-01／02**：source_analysis 補原稿字型／run／容器與可信來源，training_store 擴現有型別紀錄；將家族特徵納入相對布局與四類風格。先解決「看不出原稿字級」再訓練，預設10pt不是標籤。
2. **AI-LEARN-03／04**：學條件文法與風格分布，編譯已核准子集到 Kiwi；text_policy/layout/render 共用實際 glyph／flow。保留舊模板與固定 pt 政策；新增具多來源 provenance 的生成實例資格，不能 `state=published` 造假。custom_layout 既有 repair 路徑保留；受控關係編輯為另一入口，重用求解與 Gate。
3. **AI-LEARN-05／06**：先合法性再偏好排序；記錄前後稿／意圖／接受拒絕／作用範圍，候選規則檢驗與回滾。沒有偏好標註時保持幾何基準，不宣稱學會最佳美感。
4. **AI-LEARN-07／08**（2026-10-18排程修正）：先在Template AI既有本體接通端到端流程、持久接續與核心驗證，整理共用操作／結果契約。三階段客戶前端、網頁／手機實作及裝置驗收延後；card-interface繼續作為未來需求參考，不複製computePlan。

首個整合垂直切片：一個實際常用尺寸、單人聯絡群 → 真實核心初稿 → 手機移到市話下方 → 核心重排／驗證 → 更正電話 → 撤回排列而保留新電話 → 確認當前精確結果 → 依明確保存契約重開相同結果。若此尺寸沒有核准可變關係／生成資格，先保持待驗預覽，不能用原型確認繞過 Gate。通過此切片不代表多人、多尺寸或正式送印全部完成。

## 8. 新增驗收及本輪結果

在原8工作包中加14條風格／整合驗收，36→50 **規劃條款**；8包仍0實作／0驗證。本次不修改原75父題或既有 CORE/GOV 完成數。詳見 [有效契約](AI_CROSS_WORK_LEARNING_CONTRACT.json)，所有新增條款均 NOT_IMPLEMENTED_NOT_EXECUTED。

實作驗收應含：來源真字級與 UNKNOWN；字內／物件分散及單字/多語/最後一行；同家族長短文字固定 pt；多家族／多尺寸／反例的相對布局與欄位收合；重複ID／歸屬／循環／重送／過期；原先合格稿可受控編輯；拒絕高影響切換保留舊稿；新資料無解保留資料；撤回不退電話；完整正式 Gate 與封存一致。真實授權 heldout 逐項量化，不能只跑合成機制測試宣稱學成。

本輪實際完成閱讀、對帳、參數／資料／整合方案及公開合成測試重跑：card-interface 原型 Chromium **37/37 PASS**，文件檢查 **13文件／31連結 PASS**，HTML SHA與保存原檔一致；本輪瀏覽器154.0.8037.57，與原存報告144版分開。未改 card-interface，未改核心／UI／測試／依賴、未訓練、未建網站／手機服務。舊 CURRENT008 仍是歷史軟體證據，沒有重跑1549項冒充新能力。


## 9. 2026-10-18 已確認的共同學習依據

使用者已確認：[欄位結構、文字配置與等效欄位共同學習](../decisions/2026-10-18-FIELD-STRUCTURE-TEXT-EQUIVALENCE-LEARNING.md)。第3～4節各特徵應共享觀察／家族／規則，結構與文字互相提供限制，進而判定條件相容的等效角色及合法替換／收合／延伸。機器依據見有效契約field_structure_learning_basis；不能僅憑框大小交換資料或強併模板，仍須當次文字量測及既有Gate。這是已確認設計原則，程式仍未實作。


## 10. 本體優先的交付邊界（2026-10-18）

[最新決策](../decisions/2026-10-18-CORE-FIRST-DEFER-WEB-MOBILE.md)將網頁／手機實作延後；本文件的客戶操作、前端切片與裝置測試屬保留的未來需求。當前用其意圖／資料／版本／驗證需求準備核心，在既有Template AI本體實作與自我驗證；不以客戶前端完成作為本輪核心交付前置條件。


## 11. 本體需承接可操作體驗（2026-10-18）

[最新確認](../decisions/2026-10-18-DESKTOP-END-TO-END-INTERACTION.md)：本體要能實際輸入、取得初稿、微調關係、更正與返回、預覽確認及驗證輸出。第10節延後前端不涵蓋本體必要互動；現有桌面介面承接此流程並驗證同一核心，獨立網頁／手機畫面與觸控適配另排。
