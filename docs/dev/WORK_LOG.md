# 開發工作紀錄

## 十包 1/10 正式驗收

RUN-TEN-QUALITY-002 source9bf8479aec0f8ca1557e53e8caaa7506707f2637：243PASS／0SKIP、62實際本機附件與source unchanged。對應 CORE-046/CORE-047 全具名PASS；原所有已實作CORE與GOV一同重驗。GUI/media本機保留及source-bound豁免清單，metadata/tests/JUnit/claims/audit/checkpoint保存；只對核准保存範圍讀回，不宣稱所有新media永久保存。完成checkpoint後直接包2，不等待HUMAN。


## 2026-10-14：包1真正RED與誤記摘要修正

- CP-TEN-QUALITY-SOURCE摘要錯寫10PASS；實際target1FAIL，完整RUN-TEN-QUALITY-001為243測試／242PASS／1FAIL，無capture，未標completed。原checkpoint摘要／run不覆寫，這段修正與真正RED保留；不能沿用它宣告包1完成。
- 根因是舊navigation_clean用make_slot(preserve=True)比較卻未還原stable id，重建Slot隨機ID使已選框永遠被判未套用。新helper直接還原id並比較actualcoords與整份保存狀態，取消舊錯誤比較。額外確保clean選取可重複定位且DB不變；dirty model与未套用coords分別實際阻擋。測試teardown的stale-close原本會開warning造成等待，改為assert後明確丟棄測試fixture與有界45秒，不降低產品斷言。
- 修正後重新target與唯一新的RUN-TEN-QUALITY-002，未通過前仍0／10，不降驗收／不刪FAIL。


## 2026-10-14：包1可恢復實作

- 標記診斷schema／stable IDs／semantic mapping／bounds／包含／公司unknown／必要person name、400單work問題／2000頁問題顯式預算、逐作品分頁／exact定位／既有editor已實作。初GUI定位RED因pan模式不可選／主slot未保存不被舊selected-property guard核對；新training_navigation檢查整份主slot與revision／props並明確定位mode，FAIL日誌保留。
- 已讀Label Studio公開README人工標記與MLflow dataset.py source/digest追蹤設計；採自製schema／stable sort／source hash，不導入服務／複製其碼。references：https://raw.githubusercontent.com/HumanSignal/label-studio/develop/README.md；https://raw.githubusercontent.com/mlflow/mlflow/master/mlflow/data/dataset.py 。publication適配4test、原framework8回歸PASS，治理不算十包之一。
- 包1未正式結案；先WIP checkpoint，補actualGUI audit及完整242回歸，再包2。原始父題／CORE新增20計數保留，並未全部完成。


## 2026-10-14：十個新工作包開始

- 最新目標10包（不重算已完成3包）。基準45CORE／229PASS、126列；新增20待做CORE046..065、146列。原75父題0完整／46部分／24未實作／2受阻／3延後，GOV6。原UI007／008／040／041／055／056全條款已讀；scope／驗收與演算法在TEN_PACKAGES_DESIGN開始前保存。
- UI040合法匹配只需一次核准；不把反覆確認當安全流程。UI055用途／source／label／dataset角色分離，UI056只C不D；記錄未知，不自動訓練神經模型。Library同DB最小延伸。
- 沿用使用者證明文件上傳可略過與開發優先授權，新增run公開metadata／測試／source／claims及實際GUI audit，原binary本機留存并精确記錄略過。不能以資料缺少略過功能驗收；先補clone可恢復治理，再包1，治理不算十包之一。


最終保存範圍snapshot175340ad／tree7bc349e8，905檔逐一讀回且收據REMOTE_VERIFIED；81／90核准附件保存，当前run51／60，9件例外明示。CHECK正常PASS，publication核對在原本機與乾淨9缺失view皆PASS；原全附件Gate未滿足而非PASS。收據／額外交接与核對文件另小提交讀回。統計见THREE_PACKAGES_FINAL_VERIFICATION；checkpoint累計59，本輪新增9，4段超10分鐘，最大7759.92秒（審查中途source/code及partial已另保存）。詳見THREE_PACKAGES_CHECKPOINT_CADENCE。

## 2026-10-14：三包實作結案與證明上傳優先序修正

- 使用者明確決定若只是證明文件就略過上傳、事件持久化GitHub並優先開發。停止原未接受9件附件二進位重試；原檔／60附件manifest／失败測試都保留，名單／bytes／hash公開保存。未轉藏payload或換通道；功能验收不降低。公開保存範圍例外與完整全附件Gate未滿足分開记錄。
- 三包CORE040..045全部實作并具名驗收；最終source192db957，229PASS／0SKIP、source unchanged。第一包201PASS49附件与第二包216PASS54附件全量readback；最終51／60附件與所有code/tests/JUnit/claims、事件文件保存。最后hidden-lock真RED修復與25相关回归保留，RUN001的228是歷史。
- CORE39→45新增完成6、刪除0、原既有scope改動0；EXCEPTION-END內4個test-list scope新增驗收（040041 hidden-lock、044045具名testlist），不降低条件。父題UI004005仅PARTIAL，75為0完整／46部分／24未實作／2受阻／3延後，GOV6、126列。全部CORE45／GOV6以當前229結果SELF_VERIFIED，原父题未冒稱完整。
- eb11f23f先逐檔897保存79／90批准附件；另外history／locked成功blob在最後保存範圍提交一起讀回。新scope checkpoint使用乾淨staging，明确排除9件證明例外，只對实际manifest確認，旧full ZIP与PREPARED記錄不覆寫。舊require-evidence全附件Gate不宣稱PASS。
- 下一包MARKING_TRUST_NEXT_PLAN：先原UI040／041／055／007／008完整條款、BEGIN、具名契约，再标記完整性／可信样本。3个具體實作工作包完成；無EXE／main合併／代理，未作Windows／真實AI全面視覺／指定硬體／獨立驗收聲明。


## 2026-10-14：具體90件已核准，附件API阻塞恢复

- 固定清單全90件bytes／SHA256／Git blob SHA本機匹配；使用者明確核准全部90，另從GitHub讀出immutable manifest驗證對應。多次同API具名单件檢視後成功；API回應由structuredContent.sha取值，UTF8 blob fetch無法讀PNG不是新隱私事件。實際Git tree核對restored PNG hash成功。
- 某些create_blob仍拒絕因API只有content／encoding／repository，審查未能關聯檔名；object-tools-difference再被拒且最後呼叫被中止。保持原匿名位元、全部失败紀錄，不換通道或隐藏payload。工具cell失聯有界恢復，未force ref；成功blob清單改持久保存，避免volatile store丟失。
- 截至本段，仍11件原附件未完整tree保存；三包實作229PASS但遠端只2／3，不能宣告完成。45CORE全部本機已做／具名PASS，當前新版遠端完成仍pending。父題0／46／24／2／3，GOV6、126列。準備完整恢復ZIP與允許附件部分snapshot，恢復路徑見UPLOAD_STATE；不將partial snapshot作完整receipt。


## 2026-10-14：最後边界實際RED与修复

- RUN-EXCEPTION-CENTER-001 228PASS／60附件已产生，但最後檢查新hidden-lock-intent test實際RED：锁定成员隐藏后QGraphics会丢该scene selected，visible member setPos从(8,19)变(9,19)，默默漏掉保留的UI selection scope。保留RED，没有放宽期望。
- ObjectCanvas保存完整selection_intent，position guard查全部scene locked IDs与intent交集；drag候选沿完整intent，不因隐藏偷偷剔除。重新25物件回归与新229formal继续；旧228 run是修复前历史，不冒称当前完成。

## 2026-10-14：第三包可恢復階段

- exact来源／作品／模板／Logo依赖索引与固定lex排序，ExceptionDialog搜索／filter／定位／hash差異重试／exclude原因／restore及同交易CAS歷史已實作；選中重試runner新增精確ID範圍，不重跑其他READY或SUCCESS。資料完整性例外在action中quick_check＋FK gate。
- 6backend首次PASS；GUI fixture漏MainWindow import的5ERROR完整保留exception-initial.log，修正import后实际GUI验收继续，不降低断言。完整第三包尚未驗收／远端完成。
- 第二包216PASS54附件与readback765檔f656abcb完成；PNG無檔名payload審查多次拒絕，實際檔名hash＋view核對后改為獨立單件同API call明確綁定purpose，成功；不换通道／不刪证据。後續控binary單件scope，source checkpoint先保存降低程式丟失窗口。

## 2026-10-14：第二包正式216PASS

- source882af2c7，216PASS／0SKIP，54附件、source未變；新CORE042043全部验收。43已驗CORE，2待做；父題不冒升完整。实际GUI preflight→RUNNING→CANCELLED→重開resume DONE；14目标PASS后补modal范围变更及dirty导航，最后15PASS。
- 新SVG post-read资源边界修正與shared树可见定位纳入全回归。源路径列改善先显示filename完整路径tooltip；200件确认摘要有界且精確范围指紋防变更。
- 下一步只处理真实失败／中断结果的exact依赖索引及安全retry/exclude/restore，不把pendingimport误当可信训练。

## 2026-10-14：包2可恢復階段12PASS

- 批次預檢與健康exact重用、單worker SQLite結果＋audit同交易、session ownership、防多視窗接管、合作取消／重開續跑已實作；12具名backend／真Qt PASS。晚期結果audit回滾source與item並轉INTERRUPTED、GUI恢復操作。
- 仍須永久GUI與正式全回歸，未把包2記完成；不宣稱自动語意學習。第一次apply_patch因source_imported名稱context不符，沒有部分改寫，核對後修正。使用者已明確授權匿名證據及事件報告／等效替代，保存正式修正。

## 2026-10-14：證據上傳自動審查阻塞與有界處理

- 第一包201PASS／49附件仍local；完整附件checkpoint PREPARED，不宣稱REMOTE_VERIFIED。PDF因Noto字型被拒，實際pdffonts＋本機copyright＋上游OFL核對可嵌字，保存授權證據；再次PNG被拒，逐張view_image查34張確屬固定匿名fixture後仍被拒，理由需要具體使用者核准。已明確詢問，未繞通道／未刪證據／未降低验收。
- 依較高優先「完成未受阻工作」及三包任務繼續包2／3；安全替代只保存code/docs，binary仍待核准，完整REMOTE驗收掛起。避免新增未持久code，checkpoint ZIP／部分遠端快照與STATE明示；不能當完整驗收。確認間隔已超10分，如實記錄。

## 2026-10-14：三包第一包完成

- CORE040／041，201PASS、49永久附件、source12f02a90。初期GUI選取fixture沒先捲到可見列，保留FAIL，補真scroll與增大樹區；24相關回歸PASS。41CORE已驗／4新CORE待做；父題狀態未假升完整。接續批次匯入与持久佇列。

## 2026-10-14：連續三包開始

- 新指令三包：semantic／batch import／exception center；scope／驗收 THREE_PACKAGES_DESIGN 固定，開始前讀回。基準120列／39CORE verified，新增6待實作；不冒稱父題完整或自動辨識／訓練已做。無代理／EXE；每包 formal 全回歸、checkpoint，完成一包直接下一包。

## 2026-10-14：v0.1.11整包正式194PASS

- 固定source 2f2d32bf313616414b86bf866faef73dac884a3f，RUN-OBJECT-TOOLS-001：194PASS／0SKIP、44附件、48验收PASS、source不变。全部具体子项已验，最後snapshot 67ea91a0／tree80c70aa4，623檔包括44附件逐檔讀回，require-evidence PASS；整包REMOTE_VERIFIED。新增7 checkpoint累計50，5個確認間隔超10分鐘，最大1036.163秒（17分16秒）；如實保存，未宣稱節奏嚴格達標。下一包計画持久化SEMANTIC_INDEX_NEXT_PLAN，不當已實作。
- CORE36→39新增／完成3，父題UI036→PARTIAL後0完整／44部分／26未實作／2受阻／3延後，GOV6，120列；原父題未完整完成仍75。
- before/after故障log／真6新GUI与JSON audit永久保存；接下來UI035原要求索引／検索／安全檢視，不猜原生AI层。

## 2026-10-14：整包實作與正式前194PASS

- 新17具名測試＋原177，全回歸194PASS／0SKIP；來源／模板兩模式真QTest、drag候選取消、dirty mixed只改選中、post-prompt保留主手工內容、DB／font／pub lockGate、持久history與CAS。
- 6件實際GUI多選／mixed／差異／history／lock／training及machineaudit可產生並目視核對，正式run將全部保存44附件。
- Registry三CORE具體tests已登錄、狀態IMPLEMENTED_PENDING；父題不得先當完整。下一步固定source metadata、正式RUN-OBJECT-TOOLS-001、證據與計數／交接／讀回。

## 2026-10-14：editor安全修正與追加核驗

- 舊MainWindow保存與Undo／Redo加入loaded db revision/hash，Library保存BEGIN IMMEDIATE CAS；保存／切換拒絕stale時保留人工內容。真實ABA故障test修正後PASS。
- 一般publish亦檢查locked oldslot，字型新草稿後端雙重阻擋；舊Logo屬性不等比／轉一般文字拒絕。候選桌面resize／警告區改可捲、顯示actual非dirty值；實際3way和拖曳PASS。
- 下一步檢驗發布lock繞過／字型forge、重開history鎖定、主窗口background手工變動與錯誤後retry；整包正式證據尚未產生。

## 2026-10-14：傳統editor安全RED

- 14backend／真GUI3way／group drag候選／mixed patch／兩模式與retry全PASS。新增pin/style與cross-owner GUI亦PASS。
- 原legacy test先保存導致舊UndoStack清空，第一FAIL沒有實際展示ABA；保留原log，補保存後再次手工更改的真實fixture（不放寬期望）。REAL-ABA-RED實際驗證舊Undo把未保存手工x10退回x9，在外部資料已更改又回復後仍未阻擋。
- 保存兩份FAIL logs；下一步舊MainWindow持有DB revision/hash，保存與Undo先檢查，失敗保留手工內容；完整包尚未完成。

## 2026-10-14：物件GUI可恢復階段

- 新ObjectToolsDialog兩模式entry、複選清單／框選畫布／mixed dirty面板、實際green差異與old/new table、lock及persistent歷史可操作；23原字型審核回歸PASS、首次真GUI預覽與截圖生成。
- 目視第一圖發現右panel長內容與下方warnings擠壓，改scroll panel與readOnly可捲文字、showEvent fit；不是只靠測試數冒稱UI完成。
- 仍須QTest實際3way／drag／retry／lock全paths／兩模式與完整formal证據，checkpoint後繼續。

## 2026-10-14：物件核心可恢復階段

- 新Slot.locked相容defaultFalse、純mm提案／dirty patch／cross-owner gate／完整Logo比例、六向align／等邊界gap／group delta已實作；8具名backend測試PASS。
- SQLite object_edits鎖內重新計算與hash＋revision CAS，apply／source history／audit同交易；重開UndoRedo／晚期audit rollback／ABA／发布拒絕已驗。lock保護亦接一般template/source save與font replacement backend。
- 還沒完成GUI與所有驗收，不宣告整包完成；下一步實際兩模式advanced editor／3way／preview／lock與歷史。

## 2026-10-14：CORE037／038／039整包開始

- 使用者要求持續到整包完成；按原UI034／035／036与已保存計畫，scope及不可降低验收先OBJECT_TOOLS_DESIGN，整合進階共同編輯器至兩模式，原單選途徑同受lock。
- 基準117列／36CORE已驗，新增3待開發=39CORE；父題0／43／27／2／3，GOV6。先BEGIN讀回再改碼，所有舊当前evidence將因新code取消判定、保留歷史、正式重驗。
- 環境ready／connected／network enforced，來源branch f1b3a542；沒有一般外部credentials，Github用既有connector，無代理／EXE。

## 2026-10-14：v0.1.10完整對照大工作包正式PASS

- 精確測試來源36307d58ed8f10e6549ba3580a20541244b036db／tree305cbd40fe75d940f46274ca8190ddda5fe52cd5，RUN-CANVAS-COMPARE-002：177 PASS、0 SKIP、37附件、45個驗收全PASS、來源前後不變。
- 包含source／before／after完整矩形、同步zoom／pan／fit／stable ID定位、歷史crop／pixel／未標定單位、健康與預算、unknown不fallback、worker失敗retry／stale／三階段核准與套用前核驗。resize故障與修復測試、001完整結果保留。
- CORE34→36，新增並完成2／刪除0／既有scope修訂0；父題0完整／43部分／27未實作／2受阻／3延後，75仍未完整完成。GOV6；117列。最後差異用FINAL快照，不覆寫END歷史。
- 最後snapshot fb3f6c31／tree98d364b9、550檔逐檔讀回，37附件含於manifest、require-evidence PASS；本輪6個REMOTE_VERIFIED累計43。FIXED→VERIFIED另664.35秒超10分鐘64.35秒，皆如實保留；已實際讀原UI034／035／036條款，下一包scope／數學算式／驗收方向存OBJECT_TOOLS_NEXT_PLAN.md（PLANNED）；按原條款做三向多選與混合值、精確對齊分布，長期全清單目標不撤銷。

## 2026-10-14：GitHub catalog故障與有界恢復

- RESIZE-RED的49項差異上傳完、binary blob SHA已核對，create_tree因工具catalog changed拒絕。沒有移動分枝；checkpoint維持pending，未宣稱REMOTE_VERIFIED。
- 工具重新可用後一次重試，沿用已存binary SHA（tree接受且506檔逐一讀回）；adc28fd4成功。沒有再上傳受限字型／DB，不force更新。
- IMPLEMENTED收據05:46:18到RED確認06:55:45之間（約69分27秒）遠超10分鐘目標；網路／工具延遲如實記錄，本機PREPARED與原碼遠端保留，不宣稱頻率達標。
- 每次GitHub工具呼叫加入60秒有界等待，超時保留pending並先核對ref，避免同操作無限等候。下一步resize固定、具名回歸、新RUN002。

## 2026-10-14：CORE-036窗口resize故障與重驗

- RUN-CANVAS-COMPARE-001：176PASS／37附件，但最終擴大操作驗收發現resizeAnchor NoAnchor令實際中心從(43,11.5)漂至约(29.6,35.94)，故本包不宣告完成。
- 故障真實trace保存CORE-036/resize-before-fix.log；001原碼／結果完整保留，當前完成判定取消，補可恢復checkpoint後修正／新正式run。
- PROGRESS...END是001通過當刻快照，最後差異將另存FINAL，不覆寫歷史。snapshot首次baseline只傳ID被拒，改完整相對路徑後成功；沒有偽造結果。

## 2026-10-14：CORE-035／036正式驗收前

- 完整回歸176 PASS／0 SKIP（含8新對照組）；實際匿名GUI三視圖與定位圖可生成，已目視檢查。
- 高風險審核含顯示後／明確核准提示後／套用前背景再驗；原來源／衍生快取／背景或目標字型異動不放行。草稿clock與來源context變化亦阻擋。
- Qt原碼scene/view映射與商用並排定位、仿射換算自行實作；檔案／像素預算不宣稱指定硬體實測。
- GitHub獨立blob上傳改最多4件一批，tree／commit／ref lease與逐檔讀回仍順序，無多代理。下一步凍結精確來源commit，正式RUN與不可變附件、功能計數。

## 2026-10-14：CORE-035／036可恢復實作

- ENGINE-GUI dc424abe讀回461檔；精確來源、三矩形、同步唯讀與審核已實作，6新組／23既有測試PASS。
- 第一次生成進度時把待驗證status誤寫IMPLEMENTED，dev_progress拒絕；修正為既有IMPLEMENTED_PENDING_VERIFICATION並重新render，不改治理工具放行非法狀態。
- 下一步新增實際三視圖附件、核准提示期间異動與正式回歸；當前不得宣稱完成。

## 2026-10-14：全清單目標與CORE-035／036開始

- 最新使用者要求持續實作所有清單；全75父題原要求保留，順序／真正阻塞保存PROJECT_GOAL與PROJECT_ROADMAP。不是全清單完成宣告。
- 本包精確歷史來源映射、原稿／前後矩形與共用唯讀同步畫布，整合逐欄審核；驗收先保存CANVAS_COMPARE_DESIGN，基準CORE34／GOV6，父題0完整／43部分／27未實作／2受阻／3延後。
- BEGIN先GitHub讀回；再修改程式，所有当前完成證據需正式重驗。EXE／印刷不重做、不使用代理。

# 持久工作紀錄

每條紀錄應含要求 ID、動作／結果、測試、確切 checkpoint／commit、限制與下一步。最新資料置頂；資料可供 Human 與 GPT 覆核。歷史版本不是即時完成度。

## 2026-10-14：v0.1.9受控替代大功能完成並永久GitHub讀回

- 完整snapshot `bcef39a942912272ab32aae2348efa6b976577dc`，446檔Git blob SHA逐檔match、31件附件與進度差異永久保存；check --require-evidence PASS：115列、40個CORE／GOV明列範圍、168具名測試。最後收據／STATE另提交讀回。
- 本輪6個REMOTE_VERIFIED checkpoint，累計37。最後確認間隔652.7秒，超過600秒目標約53秒；PREPARED於2026-10-14T04:58:22.514134+00:00已完成，程式已遠端保存。附件／完整tree延遲不冒稱全輪≤10分鐘；後續提早凍結證據、以有界上傳批次降低確認窗口，歷史超時照實保留。
- 完整大功能含CORE-032／033／034，新增及完成3；CORE31→34、GOV6，UI-033未實作→部分；父題0完整／43部分／27未實作／2受阻／3延後。原scope不減，新增3／刪除0／既有scope修訂0。
- 後續大工作包已持久化：來源／模板畫布與逐欄雙向對照定位。原稿身份／全UI-033／Windows／正式品質未全部完成，不混稱產品整體完成。

## 2026-10-14：v0.1.9完整受控字型替代正式驗收PASS

- 精確程式來源ecb863bf3ee62277318e31792517945ed6674ccd；RUN-FONT-REVIEW-001：168 PASS／0 SKIP、31件匿名附件、43個acceptance全部PASS，來源前後hash不變。23項新驗收含真實GUI工作流、交易晚期失敗、CAS／ABA、重開Undo／Redo、票據過期、私密字元不落DB與實際Italic／PDF／PNG。
- 正式runner首次使用收據提交metadata而來源SHA指定IMPLEMENTED，來源Guard在測試前拒絕；source-metadata-rejected.log保留，重新GitHub讀回並使用獨立凍結source commit/tree後正式執行。未建立失敗run、未以錯誤來源冒稱PASS。
- 要求112→115新增3，CORE31→34完成3，GOV6不變；UI-033由未實作變部分，75父題完整0／部分43／未實作27／受阻2／延後3。新增3／刪除0／既有scope修訂0；相異粒度不混算。
- 下一步來源／模板畫布與逐欄before-after定位對照。全UI-033／Windows／原稿視覺／正式輸出與嵌入授權仍未全面驗收，EXE／印刷延後、UI-048最後。最終完整附件checkpoint讀回尚待，不以本機PASS冒稱遠端完成。

## 2026-10-14：真實審核／草稿／Undo畫面核對與最後輸入失效修正

- STYLE-FIXED 448d428b已讀回408檔。完整真實worker流程擷取差異、詳審預覽、新版草稿歷史與Undo，重開確認Redo持久。匿名audit不含Alex Example原文字，包含一欄目標Book pin與完整前後版本。
- 視覺核對發現輸入失效後詳細面板與表格風險文字仍可能显示舊數值／核准字樣；已清除成未核驗，具名stale測試補對可見狀態的驗收。欄位名轉中文，stable id保留tooltip與機器記錄，不顯示為使用者主要標籤。
- 最終來源待IMPLEMENTED checkpoint與正式全套run；本輪仍持續至完整工作包持久化，不停止在修正或小checkpoint。

## 2026-10-14：受控替代完整流程與款式故障修正完成待正式證據

- GUI checkpoint 0237e3ef已讀回403檔。新增23項focused全部PASS，含多模板晚期回滾、失效票據、LOW同字面修復、私密缺字集合不落DB、真實GUI全流程及重開Undo／Redo。
- NimbusSans-Italic實際樣本揭露Qt setStyleName仍取Regular；診斷列raw family/style與table差異確認，改QFontDatabase.font取得weight／italic等完整屬性，保留所有glyph-table身份Gate。after-style-resolution-fix.log 18PASS，不以換掉失敗樣本或放寬fingerprint避開。
- 主編輯QFontComboBox顯示foundry別名可能丟pin／Italic；保存原slot與顯示選取關聯，幾何／色彩修改保留原family／style／asset；before-editor-pin-fix與after-editor-pin-fix（23PASS）完整日志保留。
- 新增真正worker／GUI擷取審核差異、逐欄核准、草稿歷史、Undo與匿名audit，重開核對新草稿與Redone歷史。正式全套與永久保存仍待，不標完成。

## 2026-10-14：審核GUI／持久歷史整合與樣本故障紀錄

- ENGINE 021968bd已讀回397檔；候選入口→逐欄文字→背景差異→詳審實際PNG→明確勾選→新版本草稿→歷史Undo／Redo流程已接上。
- 真實Qt worker GUI流程及CAS／ABA／晚期全批回滾初步通過。Italic驗收指定liberation2路徑不存在造成1FAIL，保留完整missing-test-fixture.log，改用環境實際存在的Italic資產；未跳過或刪測試，款式真正渲染仍需PASS。
- Audit僅保存臨時文字hash與缺字數，不保存缺字字元集合；新草稿與歷史同交易。GUI輸入改動清除核准／勾選，未保存主編輯拒絕套用，背景回呼重載範圍／歷史不再沿用旧報告。
- 尚待補風險LOW、私密文字、票據過期與多模板Undo故障驗收，正式全套及永久實際附件。

## 2026-10-14：受控替代引擎與交易可恢復階段

- BEGIN 7870a47c已REMOTE_VERIFIED，395檔含收據保存。新增Slot款式、模板單調edit clock、背景逐欄影響／字形高度量測、内部票據、新版草稿全批交易與持久Undo／Redo引擎。
- schema以新增tables相容舊資料，不修改原發布模板；prepare票據只源自內部重驗，回傳report不能冒造核准。碼尚待完整GUI與故障驗收，不標完成。
- 已實際閱讀Qt 6.8 qundostack.cpp undo／redo及obsolete／macro範圍判斷，借用command前後狀態思路，自行實作持久SQLite版本。
- 下一步：具名交易／CAS／ABA／回滾測試、GUI逐欄審核與歷史操作、正式來源run。

## 2026-10-14：受控替代大功能啟動，先保存契約

- 開工require-evidence PASS；遠端9531224c／main436ca2d7確認，CORE-031已完整完成，不重做。基準112列／31 CORE／6 GOV，75父題0完整／42部分／28未實作／2受阻／3延後。
- 使用者新增下一步後繼續至一個大功能完成；接續UI-033，把CORE-032影響審核、CORE-033交易新草稿與持久Undo／Redo、CORE-034款式渲染一致整合端到端工作包，新增3列，舊scope不降標。
- 先BEGIN再改碼／schema；參考InDesign、Qt command原碼、SQLite交易、集合覆蓋／幾何與hash＋單調clock CAS。完整契約見FONT_REVIEW_DESIGN.md；EXE／印刷與最后UI-048順序不變。

## 2026-10-14：CORE-031目標完整完成，GitHub讀回與治理PASS

- 完整snapshot `bd52b1c2115b13bb7c538d92e90e29420ce664fe`／tree `a5848ed590b0a1ae4fcf2c2c7af263816130b64f`，389檔全部Git blob SHA match，26件附件與基準／結束統計永久保存。check --require-evidence PASS：112列、37個明列CORE／GOV範圍、145具名測試。
- 新增4個REMOTE_VERIFIED checkpoint，總計31；確認間隔小於10分鐘。最後未保存操作零風險不作保證；完整收據／STATE再小提交讀回。
- 本輪功能完成1，CORE30→31／GOV6；75父題狀態不變。目標完成不是全產品或完整UI-032／033完成；具體下一步單欄影響與人工審核已持久化。
- 工作分支與PR未合併main，PR metadata仍待同步，沒有重試EXE。

## 2026-10-14：CORE-031正式驗收PASS，保存完整證據中

- 來源17ce93d86c68df281c1d4868e6a65ba389215704；RUN-FONT-CANDIDATES-001：145 PASS／0 SKIP、26件永久待保存附件；來源前後fingerprint不變。40個具名acceptance全部PASS，包含CORE-031的4條與舊36項範圍重新驗證。
- 正式候選排名及預覽GUI已視覺核對，部分搜尋統計在預覽後仍可見；單行PNG含實際字形，量測報告可供Human／GPT檢視。
- 要求111→112新增CORE-031，完成30→31；6 GOV不變。75父題完整0／部分42／未實作28／受阻2／延後3；新增1／刪除0／既有scope_changed0。基準／結束不可變快照已生成。
- 正式runner完成後才準備完整附件checkpoint；前一小收據提交僅包含當時已固定的run來源JSON，不將其當完整證據保存完成。
- 本功能的完整唯讀契約已驗收；最終完成須等完整VERIFIED snapshot及收據讀回。下一步為UI-033明列單欄影響與人工審核工作包。

## 2026-10-14：CORE-031 完整實作待正式驗證

- WIP a60a6c8995164e84d5c12575a3a1db75976bab4f 已讀回357檔；v0.1.8引擎／GUI／實際PNG及原子输入失效接上。23項候選focused PASS，既有18項中心PASS。
- 補充量測完整性flag：比較字面在量測末尾異動不可發布舊字寬；單純框宽不足仍能顯示有效自然字寬，缺字／身份失敗則未知。
- 真實Qt背景生成候選／預覽截圖與PNG已視覺核對；發現預覽狀態可能掩蓋部分搜尋警示，增永久統計label及具名驗收。匿名報告與實際附件納入正式runner，無字型原bytes或私人來源上傳。
- Fontconfig上游兩個web讀取入口不可用，改實際閱讀維護者歷史fcmatch.c的FcSortCompare／FcSortWalk，參考理由如實列設計；不複製第三方代碼。
- 下一步：IMPLEMENTED來源checkpoint、正式145項全套run與26件附件、永久證據及完成差異。此時不標VERIFIED。

## 2026-10-14：CORE-031 目標啟動，先保存完整候選唯讀契約

- 開工check PASS；確認工作分支82e5bf5d、main仍436ca2d7，無pending。基準111列／30 CORE完成／6 GOV／75父題保持。
- 使用者明確/goal要求候選硬篩、排名、唯讀預覽端到端驗收；新增CORE-031，原父題不降標。FONT_CANDIDATES_DESIGN.md列六項驗收、參考與有界預算。
- 先BEGIN GitHub讀回再改碼；單一checkpoint或部分測試不是停止條件，不重試先前卡住的PR metadata工具。
- BEGIN 8ce4461d0f830578620c2d87ea330b781e5957a1已讀回352檔；引擎、候選GUI與有界PNG已接上。既有18項字型中心及新增20項候選驗收PASS，包含真實worker與失敗重試；此時尚待正式全套證據及永久附件，未標完成。


## 2026-10-14：v0.1.7 字型中心／字形毫米診斷／真實背景交接完成

- 來源 `f347495579a8d43e191ce8e8471e0b90aaaaf3f5`，RUN-FONT-CENTER-002：122 PASS／0 SKIP、22件紀錄與實際匿名附件，包含中心／診斷畫面，已視覺核對。18個focused驗收含真正Qt worker／GUI執行緒、成功／worker錯誤／callback錯誤／重試，非只mock背景。
- CORE-028資產身份／家族款式／健康／模板欄位影響／來源與狀態搜尋及既有匯入修復入口；CORE-029 Unicode集合覆蓋、实际cmap、no-fallback shaping／字面table核對、固定pt毫米寬度與水平可行區間／stale阻擋；不改字級或發布模板。
- CORE-030修正共用Job／Signals生命周期與明確GUIqueued交接；真實worker曾結束卻留busy的故障已重現與修正，前輪未完成run不當PASS。
- 清單108→111，新增CORE-028／029／030三列；刪除0／既有驗收範圍修訂0。功能子項27→30已驗證，治理6不變；75父題完整0／部分42／未實作28／受阻2／延後3，75仍有未完成條件。基準／結束快照與當前Human／Machine統計已生成。
- InDesign／fontTools公開cmap原碼／Qt glyph-run shaping與集合、點mm換算、比例可行區間參考詳見FONT_CENTER_DESIGN.md；自行實作、無新外部依賴、字型只留本機。
- VERIFIED snapshot `73e67f1aff392973af9cbcddc170508876816c7f` 已逐檔核對347檔，22件新版附件、實際before／after日志、要求與前後進度差異全部永久保存。本輪6個已確認checkpoint，總計27個；收據與STATE另保存避免自參照。
- 本輪各確認checkpoint間隔小於10分鐘；歷史超時窗口仍如實保留，不宣稱最後未保存操作零風險。
- 下一步：UI-032只讀替代候選硬篩／排序預覽，未知原稿參考不做視覺等同評分。Windows／TTC／完整字重／嵌入授權／替代高風險審核仍待。

## 2026-10-14：CORE-028／029 字型中心開始

- 開工檢查PASS；讀 UI-032、字型／排版原碼與最新功能清單，108列基準已保存。使用者要求繼續開發與數學／開源／商用參考，不重問例行保存授權。
- InDesign字型一覧／影響、fontTools cmap原碼思路與Qt實際解析／shaping作為參考；加入Unicode集合覆蓋率、固定點數毫米轉換及水平可行區間，不把名義glyph進位當完整shaping。設計參考與限制見FONT_CENTER_DESIGN.md。
- 新增CORE-028共用管理中心與CORE-029字形／字寬診斷，清單108→110；原75父題仍全部保留。先BEGIN，再做有證據的明列子範圍。
- BEGIN `db3039a5ade7716bfda5f905465b3732af7d7ef7` 已讀回304檔。已接中心查詢／影響／背景健康驗證，以及無fallback shaping／字型table核對／Unicode覆蓋／毫米適配診斷；輸入在背景診斷期間變更時，舊結果不套用新輸入。
- GitHub PR說明更新先前兩次被中止；本輪用已成功的程式／文件快照API持久化，不反覆卡住同一PR操作。
- WIP `7e2664adc461a254f34c1c09305775794352185f` 已讀回308檔；14初版具名驗收通過，再加入實際Qt背景執行緒測試與2件真實字型中心／診斷截圖，不只mock背景工作。
- 初版程式 `2db34fad5943aec86821d39ad0d16a9497cedc63` 已讀回311檔；真實背景測試FAIL並在清理時busy未恢復觸發modal，主動中止focus／RUN-FONT-CENTER-001，該run未完成不能當PASS。
- 實際debug activeThreadCount=0但dialog／window仍busy、inventory未收到；before-fix.log保存真實結果。新增CORE-030共用worker／Signals生命週期及GUI queued交接子項（UI-051／003），清單110→111，不把修正故障冒充完整佇列完成。
- 故障snapshot在日志仍寫入時prepare，讀回擋下差異；以原ZIP的凍結字節（當時日志为空）完成不可變snapshot `4986603780e50c8616209bd765d434c9d0d64708` 317檔確認，再於修正checkpoint保存完整before／after日志，不覆寫歷史。
- 修復run_job持有Job／Signals生命週期至GUI queued callback完成，成功／worker錯誤／GUI callback錯誤均恢復busy與釋放；真實字型背景與3種交接故障合計18項focused驗收通過。
- 下一步修正版SOURCE checkpoint、RUN-FONT-CENTER-002 全套122項與22件預期附件；run001未完成及失敗原因保留。

## 2026-10-14：v0.1.6 批次來源恢復與進度回報完成

- 測試來源 `8e8d2bab1789966636b1ac6d7b9a160aaab05cfc`；RUN-BATCH-RELINK-003：104 PASS／0 SKIP、20 件紀錄與實際附件，含新批次來源預覽；實際核對後補列高／完整tooltip／關閉鈕本地化。17產品具名測試＋4進度測試，103／104前輪歷史不沿用新碼。
- CORE-026內容定位：指定單根／受限資源背景讀取、長度預篩、候選各讀一次按hash分組、獨立原登錄／相同副本歧義、預設不選／不勾、取消與部分狀態、接點範圍防護。
- CORE-027交易復原：CAS全批長度／內容／版次核對，末段審核事件失敗亦全批回滾；復原驗舊位置並保存新revision及完整歷史，不重綁客戶或改原檔／舊模板。
- GOV-006本輪定案已實作：render產生機器／人類統計，check偵測登錄漂移，前後stable ID快照與需求／範圍／完成差異。
- 清單105→108（新增CORE-026、CORE-027、GOV-006，刪除0、既有驗收範圍修訂0）。功能子項25→27已驗證，治理5→6；75父題保持完整0／部分42／未實作28／受阻2／延後3，75仍有未完成條件。不能把子項或治理數當父題完成率。
- 對帳：docs/dev/progress/PROGRESS-20261014-BEGIN.json／END.json；當前PROGRESS.md／CURRENT_PROGRESS.json。所有狀態與驗收引用已重新對新版run檢查。
- 最終snapshot `2437a98437087b3cb79b45a6d06b97bbb05adee6` 已讀回300檔；本輪新增7個checkpoint，總計21個已確認。本輪各中途保存間隔低於10分鐘；歷史26／14分鐘超時紀錄保留，未冒稱零風險。收據與STATE另行保存。
- 下一步：UI-032共用字型管理中心子包，完整來源依賴／多根／Windows／客戶映射仍待。

## 2026-10-14：CORE-026／027／GOV-006 開始

- 讀功能清單與 UI-049 全文，基準 105 列：75 父题（0 完整、42 部分、28 未實作、2 受阻、3 延後）、25 CORE／5 GOV 已驗證。
- 使用者定案每次開發回報前後計數與需求變化，已持久化規則與不可變 BEGIN 進度快照。新增兩個功能子包及一個治理子包，總列 108；新增拆分不等於父題完成。
- 第一個 BEGIN 保存設計與規則；登錄更新腳本首次語法錯誤未改資料，已修正並分開 PLAN checkpoint 保留真實過程，不覆寫 BEGIN。
- 使用者本輪再次授予訊息後 24 小時所有 GitHub 文件／分支修改權限，繼續同分支保存，不例行要求再次確認。
- PLAN `e315744d0c67f5c462d8e8cb599d2a7e8b0a8b93` 218 檔已確認。進度工具4項具名驗收通過；背景掃描／CAS 全批交易／新版本復原與 GUI 已實作，尚待產品具名測試及全套證據。
- WIP `7a79ef609f11cc145732179024c6efd104caddce` 226 檔已確認；已加入 16 項批次具名驗收，含最終事件失敗全批回滾及後來版次不被舊批次復原覆蓋。新增真實批次候選預覽截图，勾选維持預設未核准。
- 程式 snapshot `d550d9471da370703b9b31fb7ee820f1498c5fae` 已讀回 229 檔；RUN-BATCH-RELINK-001 103 PASS／0 SKIP、20 件附件。
- 自我檢查補上未標為一般 symlink 的目錄接點實際位置限制，避免進入範圍外目錄；模擬測試不冒稱 Windows 真機驗收。新碼／驗收將重新全套驗證，保留第一輪紀錄。
- HARDENED `95f3d296151b01db6d17de859825f1ed7e0dcaf2` 252 檔已確認，RUN-BATCH-RELINK-002 104 PASS／0 SKIP、20 件附件。實際截圖發現表列高度使第二行來源識別／狀態／bytes 不易閱讀，補自適應列高及完整 tooltip，關閉鈕本地化；不把截圖只生成當作視覺驗收完成。
- 下一步：UI 可讀性來源 checkpoint，RUN-BATCH-RELINK-003 及結束清單統計。

## 2026-10-13：v0.1.5／CORE-025 完成

- 測試来源 `dc76b95fa5ff288d09d4474be2732191b3caa78c`；RUN-FONT-REPAIR-002 83 PASS、0 SKIP、19 件紀錄／實際匿名附件。12 字型修復驗收含實際 PDF 输出、模板 pin 保留、隔離 hash、例外回復、PREPARED 模擬中斷与回復也失敗的鎖釋放。
- 商用 InDesign、開源 Blender／DVC／FontForge 思路與 SHA-256／串流及交易方法已落到產品；來源與授權範圍見兩份設計文檔，未複製第三方代碼、未引入其服務。
- 新源碼後重新驗證，30 子範圍按具名条件 SELF_VERIFIED；75 父题仍非全部完成。Windows、真實 AI、指定硬體、完整字重、批次来源與印刷不冒稱完成。
- 永久證據最終快照 `b11b054a85b626288a99a3a6016cc274f6655e55` 已讀回 211 檔；總計 14 個已確認 checkpoint，本輪新增 7 個。收據／STATE 另提交保存。
- 下一步：UI-049 受控批次定位、候選影響預覽、版本核對／勾選／復原；完整字型版本另包。

## 2026-10-13：CORE-025 開始

- CORE-024 永久證據 snapshot `956e9ecb7078e250682564e1d8cf6954230f5f8e` 161 檔確認；收據／STATE 在 `712448eeb24e373946cc112ba0f41307f7244327` 保存。
- 字型修復只恢復同內容核准複本，隔離損壞副本，保留 pin；加入修復 PREPARED 意圖與啟動核對，避免把跨 SQLite／檔案操作冒稱單一原子交易。
- BEGIN `37d1f2c19ed54215cec1e0258632dd2666e15a7d` 已讀回 164 檔。11 個具名字型修復測試通過，包括新 PDF 實際匯出、模板 pin、隔離 hash、正常例外回滾與 PREPARED 重開核對。
- 檔案／SQLite 不冒稱跨存储原子交易；持久意圖及 SAVEPOINT 保留失敗回滾時的寫入鎖。Windows 鎖檔與斷電仍需真機驗收。
- 第一輪 RUN-FONT-REPAIR-001 在 `b72b44ba945f7cf567b72b1d785cdb162e5fdbd3` 的 82 測試通過。自我檢查补上「回復檔案也失敗」釋放 SQLite 鎖與重開核對；12 項字型驗收通過，新版需重新全套驗證。歷史 82 PASS 不沿用為新碼證據。
- 下一步：修正版來源 checkpoint、83 項來源匹配證據与永久附件，不打包 EXE。

## 2026-10-13：CORE-024 完成

- v0.1.4 測試來源 `285a9e14cf063dc71b04ebc28d4af35efa499bb1`；RUN-SOURCE-RELINK-001 71 PASS／0 SKIP，19 件實際匿名附件／文字紀錄，來源未改變。
- 7 個具名測試涵蓋搬移改名、原稿只讀與 provenance、同名異內容拒絕、過期 revision、事件回滾、狀態與 GUI 背景路徑／重開。
- 原始 sources 登錄、作品與模板不替換；位置及不可變歷史另存。stat 競態防護屬本機正常異動防護，不是惡意檔案系統認證。
- 下一步：永久證據 checkpoint 讀回；再做 UI-032 同內容字型資產修復，批次重連留後續。

## 2026-10-13：CORE-024 開始

- 使用者再次授權 24 小時必要操作，持續功能開發；不宣稱部署常駐執行服務。
- 參考商用 InDesign、Blender／DVC 開源實作與 SHA-256 串流方法，設計見 SOURCE_RELINK_DESIGN.md。
- 單件內容重連先做；原始登錄不可變、另存位置／歷史、CAS 版本防護及同交易審核事件。
- 修改來源前先取消舊當前完成判定；保留歷史證據，重新驗證後恢復具名範圍完成。
- BEGIN 已讀回 135 檔，commit `8dd116abf6db6f65114563d7064a01de8758ca38`。7 個來源重連測試通過；首次 GUI 測試清理重複關閉窗口造成阻塞，已修正測試清理，不列作產品成功證據。
- 下一步：程式可恢復 checkpoint、完整來源匹配測試与永久附件；再進入字型修復。

## 2026-10-13：v0.1.3／CORE-023 完成具名範圍

- 程式來源 commit `6a392639ef7ca8e35ff74ced9e203b7847dff664`。RUN-SOURCE-CACHE-001：64 tests全數PASS、零SKIP，19件紀錄／匿名實際附件。
- 23 CORE加5 GOV按各自的明列範圍SELF_VERIFIED；75原題仍不是全數完成。來源快取完整性不等於完整批次來源重連，metadata checksum不是安全簽章。
- 版本化快取加入圖片／SVG內容hash、metadata checksum、同來源／同頁及固定路徑檢查，損壞時重新轉換；拒絕符號連結，轉換失敗不回退為成功，原檔保持只讀。
- 產品工作包BEGIN到IMPLEMENTED收據約14分鐘，也超過10分鐘目標；已保留實際時刻，不將保存頻率冒稱嚴格達標。下一輪應在長工作包中途先做WIP checkpoint。
- 全部.log及二進位合成附件納入最終checkpoint並逐檔讀回；新增遠端附件完整Gate。最終snapshot commit `19b300cec125149b2adc0e32987d376d2638ab75`確認132檔，入口與收據另提交保存。
- 下一步：UI-049的受控來源重連子包（內容hash驗證、變更拒絕、原登錄保留），其次字型資產修復。EXE／印刷／指定設備與未決產品報告不提前做。

## 2026-10-13：CORE-023 開始（先保存再改碼）

- 五點框架 READY 與收據已永久保存；確認提交 `bc5448f2a4c44c1a503b5ad59d21caf61dad33e8`。
- 下一要求 CORE-023：衍生快取內容、頁碼與 metadata 驗證；異動／損壞時不重用並重建，原始來源保持只讀。
- 故障測試先重現 3 個FAIL與1個ERROR；修正後6個快取測試通過，包括符號連結不改原檔，原始紅／綠紀錄保存於docs/evidence/regressions/CORE-023。
- 發現框架的副檔名白名單漏了.log，初始遠端快照沒有全部文字日誌；本包補.log並增加require-evidence的遠端附件包含檢查，避免只在本機看得到卻宣稱已保存。
- 舊 run 保留可查，但新來源版本開發時先取消當前 completed，重新驗證前不沿用舊 PASS。FRAMEWORK READY 歷史收據仍有效，产品新版本完成另產證據。
- 先做 SOURCE-CACHE-BEGIN checkpoint，完成修改／測試後再做可恢復 checkpoint 與RUN-SOURCE-CACHE-001。

## 2026-10-13：五點框架 READY，遠端快照已確認

- GOV-001～005：框架已實作，源碼 commit `f5da9c41e432e0b7b3927ae9b51c5e94645406b3`；RUN-FRAMEWORK-001 的 58 項具名測試全部 PASS，19 個紀錄／匿名附件。
- 原有 22 CORE 與 5 GOV 以明列範圍 SELF_VERIFIED；75 父主題未被自動標完整完成，CORE-023 尚未實作。所有狀態見機器登錄。
- 已停用 EXE 的 push／PR 觸發；只保留手動日後交付。本輪不等待或重跑 EXE。
- 起始、框架實作、自動狀態共三個 checkpoint 已讀回；prepare 自動加入 pending，acknowledge 自動更新入口指針。
- 首輪建置工具期間起始收據至實作收據約 26 分鐘，未達新訂的 10 分鐘節奏；已記錄此差距，後續以短工作包與自動 pending／入口更新控制保存，不宣稱歷史每次都已達標。
- READY快照 commit `38374fd23b21fedcc7d2df15cf8ae34cd94f3718` 已讀回101檔（含匿名實際附件）；收據與入口指針另行保存。下一步為 CORE-023：來源快取 hash、損壞 metadata、只讀重新轉換及故障驗收。

## 2026-10-13：治理框架建置中

- 來源：使用者的六點指令，原文見 `docs/decisions/2026-10-13-CHECKPOINT-EVIDENCE-POLICY.md`。
- 要求：GOV-001～005。先做框架，再做产品 CORE-023；EXE 改為只保留人工 dispatch，不重新嘗試。
- 已確認起始 checkpoint：`CP-20261013-FRAMEWORK-START`，GitHub commit `02af3a8d556830a0e699dd80e6dbb3535a984c28`，62 檔讀回一致；本機 ZIP 為額外恢復點。
- 已新增 AGENTS／Copilot 入口、STATE、交接、要求登錄、證據研究、快照與一致性工具；保留 75 原題與 23 CORE／5 GOV。
- 尚待：治理測試、框架提交及新版證據 run；此時不把框架或原有 CORE 標完成。
- 修正歷史索引：UI-058 是當次排版候選恢復，已完成的作品標記歷史屬 UI-038 子集，不能混稱。
- 下一步：執行治理自測→checkpoint→GitHub 讀回→以確切 commit 產生證據→READY checkpoint，再開始 CORE-023。
