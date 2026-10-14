# Human／GPT 接續：v0.1.14 三個實作工作包完成

先AGENTS→STATE→本檔→THREE_PACKAGES_DESIGN→REQUIREMENTS／FEATURES／PROGRESS→最新run與收據。長期全清單目標仍PROJECT_GOAL／ROADMAP；下一包MARKING_TRUST_NEXT_PLAN為PLANNED，先读完整原條款、寫具名scope與BEGIN再code，避免重做本輪已完成程式。

本輪三包：CORE040041語意／共用stable-ID搜尋／安全viewport與唯讀衍生SVG；CORE042043有界批次只讀預檢、exact SHA＋頁去重、SQLite單worker／結果audit原子保存／合作取消與明確續跑；CORE044045真實匯入例外的exact依赖影響、固定排序與來源定位、選中項hash差異重試／有理由排除／明確恢復、revision CAS與交易歷史。從訓練工作台「批次匯入／取消與續跑」「來源匯入例外中心」、兩模式「安全多選／精確對齊」進入。

最新固定source `192db957a927e6fcdedf7b62ef835748bf238717`，RUN-EXCEPTION-CENTER-002：229PASS／0SKIP、60件本機附件、source unchanged。最後hidden-lock真RED→GREEN：Qt隱藏locked框會清除scene selection，現在保留完整selection_intent，所有locked IDs共同守移動範圍。001的228PASS是修復前歷史，不當現版驗收；其FAIL／前後回歸均保留。

使用者後續改「證明文件略過上傳，事件保存GitHub，開發速度優先」。9件最新run的重複GUI／PDF證明附件有明確未上傳例外，見EVIDENCE_PUBLICATION_EXCEPTIONS與2026-10-14-EVIDENCE-UPLOAD-PRIORITY；停止其二進位重試。原檔／60件manifest／全部測試不刪、功能驗收不降低。最新51／60件附件與code／tests／JUnit／claims保存，第一／第二包原49／54件全量永久證據仍有效歷史。保存範圍checkpoint只對列入的code/tests/docs/已接受證據REMOTE_VERIFIED；舊全附件`--require-evidence` Gate仍未满足，不宣称全60永久保存。完整本機恢復ZIP在旧THREE-EVIDENCE-RECOVERY；STATE有新scope receipt入口。

126列＝75父需求＋45CORE＋6GOV。CORE39→45新增完成6，GOV6；75父題0完整／46部分／24未實作／2受阻／3延後，全部仍未完整。EXCEPTION-END相對BEGIN有4個驗收test-list scope變更（040041加hidden-lock，044045填具名測試），未刪測試或降低條件；整輪相對原39CORE基準新增6、刪除0、原既有scope變更0。全部當前CORE／GOV按229真結果SELF_VERIFIED，非Windows／真實AI全面視覺／RTX5050／VivoBook／印刷或獨立驗收。

下一包：UI040／041／055／007／008的標記完整性與可信樣本准入。來源／slot／revision facts、人工確認與訓練准入分開；匯入SUCCESS與例外排除都不自動入訓練。雜訊規則要有前提、支持／反例、白名單／追溯與回滾；不可因字串或Logo矩形交疊就刪資料。待決UI066報告及未實測外部條件保持真缺口；無EXE、無main自動合併、無agent、UI048最後與印刷後置。

數學採stable-ID圖／集合、token AND、SHA-256 exact identity、有限狀態機＋單worker＋CAS、嚴重性與exact影響lex排序；參考Adobe Layers、Qt 6.8及SQLite官方方法，不複製未知許可代碼。原生Illustrator階層及slot↔SVG映射未知即UNKNOWN，viewport不降低全slot輸出Gate。

Checkpoint節奏未嚴格達10分鐘，審查／工具中斷有長間隔；來源code/docs及部分tree中途已保存。具體時刻／例外與恢復見WORK_LOG、COPYRIGHT_PRIVACY_EVENTS、APPROVED_EVIDENCE_UPLOAD_STATE；不得改寫歷史PREPARED為ACK。所有舊交接、失敗、接受與中斷事件保留在WORK_LOG／证据attempts。

乾淨checkout缺少核准9件證明附件時，按 EVIDENCE_PUBLICATION_SCOPE_CHECK.md 逐項核對source／tests／claims及現存附件；僅容許精確例外，其他缺漏不略過。保留舊strict Gate未滿足，不重做證據上傳。
