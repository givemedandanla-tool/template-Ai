# 本地分析與合成驗收：原 8 包／50 條範圍核對

來源 `a288b1e294f1108ab4cebaf0d99e477e87e2e7f0`；[正式回歸](../../docs/evidence/runs/RUN-LOCAL-RECOVERY-ALL8-003/run.json)：`PENDING_FULL_FORMAL_RUN`。

私人作品與字型保持本地，未要求提供。原始完整驗收仍為 8 包 PARTIAL、0 包完整真實資格；這不等於本輪未開發，而是避免把合成／Linux 證據當成真實作品或裝置資格。原有 50 條不增加、不刪減。

| 工作包 | 已實作及可測範圍 | 限制／後續本地驗證 |
|---|---|---|
| 01 本地匯入與可追溯觀察 | Inkscape 外觀／語意分路、原始 PDF 字形、Qt PDF/SVG 備援、局部 OCR 與實際本機字面比對；完整多 run／多字型來源綁定及影像推估可進入核對後的學習資料。推估標 DERIVED，來源原生值仍可 UNKNOWN。 | 私人 Illustrator 結構、無 PDF 相容或不可讀檔案、來源未標定與複雜書寫不保證還原。全字庫搜尋分批、可取消、有歧義／未完成提示；仍需本地來源與字型核對。複合結構標註目前有後台 API，尚非完整圖形化精靈。 |
| 02 跨作品家族與低支持保留 | TRAIN-only HDBSCAN、至少五獨立 lineage 支持、重複來源不增加支持、孤例保留、共同功能風格鍵不依來源 run ID 分裂。22 份實際匯入測試作品形成兩個家族，未建立逐作品全域模板。 | 合成作品的家族真值由生成器事先指定；不能當真實客戶作品的分群或泛化品質。實際角色／群組／雜訊仍需來源觀察與核對。 |
| 03 聯合文字／結構規則 | 群平衡聯合 Ridge、GMM 提議與 mixture-of-regressions BIC 選模、來源相對關係／baseline／gap／錨點、物件等距、詞邊界與塑形字元群分散、自然／分散末行、混合字型與 label/value/欄位圖示。另以獨立 VALIDATION 群及 Clopper–Pearson 下界校準聯合適合區域。 | 字元分散需明確塑形邊界及實體額外間距上限；RTL 分散、任意垂直／旋轉／Type3 複雜字面未普遍支援。label/圖示框與動態分段需已核對來源規則；不自動從未知像素推得全部文法。容量只代表已驗證條件，非全域欄位上限。 |
| 04 條件模板與有限約束排版 | SciPy 指派、Qt 實際量測及 Kiwi 約束求解，保留資料身份／歸屬、客戶相對位置與核心字形規則。已支持尺寸優先於無證據預覽分支；驗證連續尺寸內的新尺寸及混合字面新內容。 | 有限搜尋不證明全域最優；未知尺寸、未觀察角色組合與無證據風格不取得正式資格。欄位圖示不代替公司 Logo 身份；既有來源、字型、Logo、權利與輸出 Gate 持續生效。 |
| 05 輸入檢索、可重現優選與排序 | 候選先通硬 Gate，再以群平衡 pairwise logistic 排序；實際聯合風格距離為特徵，穩定決勝及版本化偏好保證重複輸入可重現。封存 NDCG／基準／信賴區間及本地正式資格檢查器已實作。 | 自製偏好標記只證明機制，未提供真實美學偏好；未校準分數不是機率，最佳僅限搜尋與驗證範圍。真實資格需本地獨立封存結果，測試資格資料不當生產證書。 |
| 06 回饋、資格與版本生命週期 | 既有 TrainingStore/交易/版本/權利撤回重用，回饋分偏好／修正／政策，保存前後稿與意圖。正式 ranker 資格綁精確權重、政策、封存評估；版本啟用／回退不改舊模型。 | 實際美學回饋與真實資料資格尚未建立。資格與容量的進階操作目前為後台 API，不是完整 GUI 引導；缺證據仍拒絕正式啟用，不透過合成案例繞過門檻。 |
| 07 本體流程、持久接續與私密診斷 | 本體支援匯入→學習→輸入→排版→相對微調→局部更正→預覽確認→輸出／重開；來源核對頁新增本地字型還原診斷與候選草稿。診斷以固定代碼、影響、補救與版本呈現；匯出採白名單，不自動上傳。GitHub 保存程式、匿名證據、交接與 checkpoints。 | 網站／手機／EXE 依使用者決策延後；未聲稱其介面／裝置已驗證。GitHub 不保存私人作品、字型或本機 DB，需自行備份本地資料。先進複合標註、容量校準與正式資格尚未全數做成圖形操作精靈。 |
| 08 可重跑合成驗收與實際規模測試 | 22 件已知真值作品實際匯入／來源綁定／訓練，12 TRAIN、6 VALIDATION、4 HOLDOUT；十件實際評估與獨立結果核對，模型權重和來源不被評估改寫。另有實際 1000/3000 PDF 相容 AI 匯入、原始字形、字面量測、共用 fit 與第17件暫停／重開。 | 合成／Linux 結果不冒充真實授權作品泛化、美學、Windows/VivoBook 或物理印前。規模測試不包含私人 AI 私有結構或完整 Windows 字庫影像搜尋，並跨診斷／UI 修訂執行，未聲稱固定整個專案版本的效能。 |

逐條機器對照含原文、測試模組、正式來源與限制，見同名 JSON。

| 原條款 | 當前軟體範圍 | 完整原條款 |
|---|---|---|
| AI-LEARN-01-A01：已知字級與均勻變換可核實；未知字型／點陣估計不變成10pt真值 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-01-A02：去重與lineage拆分避免同作品改版跨TRAIN與TEST | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-01-A03：相同來源的角色／群組／圖形分層有可追溯觀察版本 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-01-A04：資料／來源修訂失效與批次取消續行保持精確身份 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-01-A05：重用TrainingStore歷史及交易，舊資料與原稿不改寫 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-01-A06：來源 text run／glyph cluster／baseline／pt／容器及四類風格觀察帶單位與可信來源，缺證據為UNKNOWN，預設值不當訓練真值 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-02-A01：至少5不同設計lineage共同支持家族，禁止一作品一學成模板 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-02-A02：同源重複不增加支持或洩漏內容身份特徵 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-02-A03：HDBSCAN孤例／低可信保留，不強併／靜默丟棄 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-02-A04：重估版本與成員對應可重現，不假稱partial_fit | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-02-A05：四類風格及角色／容器關係用於跨作品家族，來源去重與反例不被同座標或同字串掩蓋 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A01：共用對齊／間距及可選／重複／流向由多作品資料學出 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A02：資料分布改變會改變規則，刪去支持導致降級 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A03：統計軟偏好與硬政策／來源信心分離且保存反例 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A04：尺寸或內容證據不足不擬造回歸／外推可信度 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A05：分開學字內／詞內與物件等距；語系、合法邊界、單字／零邊界與最後一行有明確規則，越權模式不自動啟用 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A06：學具來源的pt、角色字級比例及文字／容器聯動；新規則實例由核心依核准聯合條件調整字級、字寬與欄位尺寸，不提供客戶細參數控制，未知或越適用範圍不任意縮放 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A07：學角色／群組相對關係、baseline、gap及錨點，保留獨立來源支持與矛盾反例 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-03-A08：學容器欄列／label-value／optional-repeat-flow、欄位收合及同模板條件交換變體，保留資料ID、歸屬與完整內容，不列舉每案模板 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A01：未見文案／欄位組合可生成非原庫複製的新實例 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A02：在已學適用範圍內未見尺寸可由條件規則產生 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A03：群組／文字多行量測與實際渲染一致且資料完整 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A04：非凸拓撲分支與搜尋預算有完整性狀態，非法版面不放行 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A05：多來源generation_reference核驗，不能偽造單一source或published狀態 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A06：字型／Logo／鎖定／舊模板與現有輸出Gate完整回歸 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A07：新風格子集由版本化政策編譯到同一Qt文字布局與Kiwi；舊模板固定pt、分散角色、Logo與正式Gate不回退 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A08：受控SET_RELATION優先在同模板合法交換／重排，超出適用能力再比較相容模板；同命令冪等、循環與歸屬衝突有原因，不修改全域模板 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-04-A09：跨候選／尺寸適配保留意圖與穩定映射，依UI-061預覽確認；高影響不可默默採用，客戶確認不冒充正式發布 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-05-A01：依輸入能力檢索家族，硬Gate前置且所有結果可追溯 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-05-A02：偏好訓練按query分組，舊幾何規則評分不冒充獨立標註 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-05-A03：封存偏好topK／NDCG及基準比較有明確分母與信賴區間 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-05-A04：最佳僅限已搜且已驗證範圍；所有複數合法結果含同分須有版本化預設優選與穩定決勝，客戶明確關係優先；未校準分數不當機率 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-06-A01：回饋區分偏好／必要修正／政策，輸出成功不等於好看 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-06-A02：訓練／驗證／測試與來源權利／撤回版本不洩漏 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-06-A03：PENDING評估／明確政策啟用／回退不改寫舊模型 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-06-A04：來源與支持證據變動可失效並精確恢復受影響模型／結果 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-06-A05：保存前稿＋明確意圖＋後稿＋接受拒絕＋適用範圍，缺理由保持未知，個案接受不得直接改全域政策 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-07-A01：匯入->共用學習->家族->輸入->新排版為主流程，不逐作品建模板 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-07-A02：家族／暫態實例與低可信例外可理解，代表性抽查不逐件聊天 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-07-A03：工作暫停／重啟／新對話可依倉庫與本機持久資料接續 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-07-A04：程式／匿名指標／checkpoints保存GitHub；不自動上傳原稿／字型／個資 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-07-A05：客戶端先完整初稿，三階段可返回；客戶表達必要相對位置，欄位尺寸／字級／字寬／切齊／分散與數值間距由核心規則控制，不加入客戶細參數、單雙排或必選模板庫；專業後台維持既有能力 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-07-A06：網頁手機發同一語意操作契約，驗證資源權限／期望版本／冪等／晚到結果；拖曳中只代理回饋，放開核心精排，提供非拖曳等效操作 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-07-A07：確認綁定精確資料／結果；相同有效輸入重複下單沿用有效已確認版，不因多合法解或模型更新任意換印紋；新資料無解保留並標stale，撤回版面不退電話；正式封存不把JSON重算當精確回播 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-08-A01：真實授權lineage隔離封存集驗證跨作品泛化，合成結果另列 | PENDING_FULL_FORMAL_RUN | REAL_LOCAL_CORPUS_VALIDATION_NOT_RUN |
| AI-LEARN-08-A02：硬錯誤0與資料完整100%；可行率分母及未知／搜尋狀態透明 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-08-A03：偏好驗收與基準比較獨立，缺標註不宣稱學成最佳美學 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-08-A04：1000／3000作品持久批次、資源／延遲／取消／恢復以實測保存 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-08-A05：多人／公司／字型／Logo／參考Windows與VivoBook資格依實際範圍驗收 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
| AI-LEARN-08-A06：四類風格在獨立授權lineage封存集及長短／多語／多筆／多人／多公司情境分項驗證；網站／實體手機／印前各列證據，不以37項原型PASS代替 | PENDING_FULL_FORMAL_RUN | NOT_FULLY_VERIFIED |
