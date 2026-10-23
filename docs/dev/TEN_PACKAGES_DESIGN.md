# 連續十個新工作包：標記、規則與可信訓練（2026-10-14）

使用者要求「持續工作直至完成10個工作包」。以已完成三包之v0.1.14／45CORE／229PASS為基準，本次十個為新的完整可操作工作流程，不把checkpoint、治理、單一小修正或原三包重算。全部沿用同一Library SQLite、來源／作品／stable slot IDs及事件；無代理、EXE或main合併。原75父需求完整範圍保留，以下子項不冒稱父需求完整。

開始前已讀原UI007／008／040／041／055／056完整條款、現有code與最新證據。UI040一次核准後合法命中自動排除、不重複問；噪音排除只改訓練候選，不刪原稿／正式版面。UI055樣本准入、資料集與真正訓練分開；UI056只能C分布與缺口提示，不補樣、不用任意數量門檻判品質。

## 共通驗收

每包必須：現有工作台入口→真Qt選取／詳情／必要產品確認→實際結果／DB歷史→重開恢復；錯誤／過期／確認期間範圍變更恢復操作。所有寫入有exact ID／來源hash／revision CAS與同交易audit，晚期失敗全rollback；不信任caller可偽造的after／approved。空輸入／無候選／重複／限額／源檔變更均有原因。沒有OCR／原生結構／外觀／客戶歸屬證據時保留UNKNOWN，不冒稱深度模型／Windows／指定硬體或獨立驗收。

使用者最新保存優先序沿用「如果這只是證明文件就略過，持久化在GIHUB文件中就好，已開發速度為首要目標」。本輪真GUI／數位二進位證明在本機生成并保留逐檔hash，GitHub優先code、測試、JUnit、claims、環境、checkpoint、事件與machine audit；不再因二進位上傳審查反覆停頓。各run具體略過檔案明列TEN_PACKAGES_PUBLICATION，原run／FAIL不刪；保存範圍與完整全部附件Gate分開，不宣稱未上傳圖片可下載。此例外不略過程式實作或功能驗收。每包正式來源對應回歸；至少每10分鐘及可恢復階段checkpoint，盡量6～8分鐘先凍結。

## 1／10：標記完整性與衝突定位（CORE046／047；UI040）

有界逐作品／來源標記診斷：duplicate stable ID、重複語意映射、有效邊界、已知必要姓名／公司binding、人物容量與欄位屬性；未標定、原生內容／Logo完整性證據未知明示。矩形包含與普通相交分別解釋，不自動刪合法複合Logo。固定severity／exact ID排序、搜尋、作品／框定位、進入既有安全編輯器；維持完整發布Gate、不將警告當PASS。測試test_training_quality：多人物／可選欄位／包含、bad IDs/bounds、排序／readonly、真GUI定位与dirty主畫布保護。

## 2／10：來源觀察與作品事實確認（CORE048／049；UI007／039）

在同一作品保存人工提供的來源物件觀察：stable observation/slot ID、完整文字、物件type／來源區域、來源證據／未知性、真實欄位或管理註記的分類。明確確認exact作品事實，前後／observer／source hash／work revision及可追溯撤銷；源檔／作品變更使舊確認失效。原文字只本機DB，公共測試限合成；不發布通用規則或自動准入樣本。測試test_training_facts：非法／重複觀察、來源變更、CAS／late event rollback、重開、真GUI确认／取消／過期与觀察範圍。

## 3／10：單作品雜訊與可重用候選（CORE050／051；UI040／007）

觀察選取的「只排除此作品」與「剔除並記住」明確分開。局部exclude不刪Slots或原稿；記住只建立具來源正例／反例、完整literal、來源type、明確作品相對region、NONE或明確核准NFC正規化、保留例外的PENDING規則。姓名／公司／完整Logo或未核實字串不無条件子字串排除。詳情及diff，明確原範圍／可撤銷。測試test_noise_authoring：兩操作差異、完整字串／正規化、真實欄位保護、範圍驗證、stale/rollback、GUI選取／確認。

## 4／10：風險分級規則審核中心（CORE052／053；UI008）

統一規則list搜尋／分組／排序與詳情，支持／反例、scope、exact目前作品／模板影響、缺證／risk／conflict、版本差異；不是AI任意分數。相同前提的已驗證低風險可選中批次批准，高風險逐條詳審；明確最終批准／拒絕／暫緩、原因及revision history。核准不能默默擴大原範圍，source evidence與反例重新驗證。測試test_rule_review：batch資格／跨scope／高風險review、缺證拒絕、CAS／原子交易、產品確認與controls recovery。

## 5／10：一次核准後自動命中與追溯（CORE054／055；UI040／041）

新人工觀察／作品分析對已核准完整literal＋type＋region精確匹配，自動排除符合條件的訓練候選，不重問既有批准。已確認真實欄位／Logo、白名單、未知來源／模糊文字／規則衝突保持原資料与例外狀態。持久命中exact observation/work/rule version、原因、實際排除／保留／疑義計數，GUI回來源定位。源檔与Slots、正式輸出不改。測試test_noise_hits：後續作品無重複prompt、假名／substring／Logo／未知保留、hit穩定可重開、來源改動及不降低學習Gate。

## 6／10：誤判恢复、白名單與規則回滾（CORE056／057；UI041）

局部「不是雜訊／只保留此項」與可重用白名單新版PENDING分開；準確影響預覽。停用／變更／回滾明確批准、immutable版本及CAS，更新真正受影響hits／樣本依賴，其他來源與人工事實不改。回滾不重寫發布模板或假稱模型已解污染。測試test_noise_recovery：單項恢復、白名單优先、不同版本差異、精確impact／部分／unknown、late rollback、GUI與重開。

## 7／10：可信樣本准入與污染隔離（CORE058／059；UI055）

人工事實／來源視覺核對／當前source/work/facts revisions、必要語意／幾何／權利範圍有證據才由明確產品確認准入；候選與APPROVED／STALE／QUARANTINED／REVOKED分開。正確label與原錯誤反例分開；不自動訓練。隔離與撤銷preview exact dataset／template/job使用依賴，immutable audit、不從歷史擦除、不聲稱既有模型參數已清除。測試test_trusted_samples：權利/unknown／標記矛盾、stale source/revision、late rollback、准入／撤銷GUI、用途與版本追溯。

## 8／10：資料集角色、去重與幾何學習（CORE060／061；UI055／007）

exact樣本id／label revision／source hash／crop／dimension／用途／rule依赖的不可變dataset manifest，TRAIN／VALIDATION／HOLDOUT／UNASSIGNED角色，同內容或同來源多作品不能洩漏跨集；近似UNKNOWN，異名來源與客戶關係不合併。只有明確核准且仍健康的TRAIN樣本可經使用者啟動現有幾何規則學習，生成新的DRAFT模板及dataset provenance；保留原與發布版本，不宣稱神經模型／独立品質。測試test_dataset_learning：exact dedup不消來源、holdout與group隔離、manifest可重現、revocation/source changed failclosed、實際draft/source pins及GUI。

## 9／10：覆蓋與資料分布檢視（CORE062／063；UI052／056C）

可追溯總source／artwork／候選／准入／隔離／各dataset角色分母与掃描範圍，來源無作品或未知健康不漏算。按已知尺寸／人物／公司／exact group分類與drilldown，Logo/native effects不知即UNKNOWN、分類重疊明示；選取分組回樣本／來源。無有效／未知代表性只中性提示，不任意配額、不補樣或把量多當品質合格；current source/revocation再計數，旧快照保留但不冒當current。測試test_quality_coverage：空庫／待審/holdout隔離、同內容異名／分母、multi分類／unknown、版本撤銷、真GUI readonly／定位。

## 10／10：可恢復受控訓練佇列（CORE064／065；UI003／007／042／051）

對選中exact有效dataset/樣本預檢、明確範圍確認、單worker真實進度與持久結果／audit；每件source／revision／規則／用途重新檢查。幾何模板只新DRAFT；未准入、holdout或過期阻擋，單件錯誤隔離、不可隔離DB失敗停止。合作取消／重開顯示中斷與明确resume，不重复SUCCESS；owner/CAS防跨視窗接管／双击，晚期失敗rollback、不自動发布或宣稱完整深度模型。測試test_training_pipeline：真正worker／進度／取消／重開／stale／跨owner／late event rollback、成果保護与10包整合真Qt流程。

## 方法與邊界

自製算法：stable-ID圖＋去重集合與固定排序；矩形交／包含分類；完整Unicode文字與明確NFC；lex风险／scope分組；SHA-256 canonical manifest／有限狀態機／revision CAS；同源group集合隔離，污染依赖圖精确傳播。參考既有Adobe Layers與Qt／SQLite官方資料；本輪另核對Label Studio人工標記治理與MLflow資料集來源追蹤公開設計，吸收思路不導入服務或複製不明許可碼。所有新增model用語只指現有幾何規則內化。

資源：單work最多200slots／200觀察、每次操作最多200選項、GUI查詢分頁；內容hash只讀有界檔案，原稿大圖不於統計載入。不能將此上限冒稱VivoBook／RTX5050真機效能已驗。缺真實AI、獨立樣本、设备與完整客戶資料維持外部缺口；UI048最後、印刷／UI056D後置。

每包SOURCE freeze→具名backend／GUI＋正式全回歸→進度END與current完成證據→保存範圍checkpoint／收據／GitHub tree讀回。每包完成後自行下一包，不停在checkpoint或部分PASS；目標10／10完整具體實作工作包才結束本輪。
