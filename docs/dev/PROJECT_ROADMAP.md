# 全75父題狀態與接續順序

44原父題軟體條款SELF_VERIFIED／28部分／3延後；固定70完成42、剩28。CORE87／GOV7獨立統計。

最新28父題的239條原驗收、實作位置及具名測試見[TWENTYEIGHT_CLAUSE_AUDIT.json](TWENTYEIGHT_CLAUSE_AUDIT.json)；正式601/601 PASS、Qt錯誤0、擷取成功、來源未變。每題的驗收來源為REQUIREMENTS.json，不從測試數或子項數推父題完成。

下一項：UI-031完整軟體缺口對帳；沿既定順序，不重做已結案28題。UI-048最後，REV-03／UI-056-D按既定延後；不建EXE。Windows、私人AI全面與獨立覆核未驗證。

|順序組|原父題|名稱|狀態|下一步／證據|
|---|---|---|---|---|
|1|REV-01|矩形區域自動排版與模板 AI；X-04 結案|PARTIAL|依既有UI要求逐包補齊並整體驗收；不重問名片／門禁卡，不增加第二套商品引擎；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|1|REV-02|Inkscape 等視覺一致且可訓練的 AI 匯入|PARTIAL|以獲授權匿名或合法替代真AI樣本逐例比對並真正進訓練管線；不能拿縮圖或合成SVG通過代替；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|1|UI-001|三模式主視窗|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-002|模式切換狀態|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-006|例外修正工作台|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-009|模板庫瀏覽方式|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-010|模板版本編輯機制|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-011|模板編輯器物件操作|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-012|物件移動縮放與智慧對齊|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-013|文字框智慧編輯介面|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-031|字型缺失與 Illustrator 特殊文字效果處理|PARTIAL|以合法匿名真AI逐例核對字形／遮罩／Logo並實際學習；完整私有原生結構不是共同必要條件；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|1|UI-032|Windows 字型庫、智慧匹配、匯入與受控安裝介面|PARTIAL|補Windows能力探測及明確安裝授權，驗證載入不等於安裝、缺字／失聯／異動不借字型通過；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|1|UI-033|字型替代影響範圍與風險分級批次審核|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-034|畫布、物件清單與屬性面板同步安全編輯|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-035|語意樹、Illustrator 圖層與搜尋／鎖定管理介面|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-036|多物件精確對齊、等距分布與群組位移|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-037|畫布縮放、平移、快速定位與同步對照檢視|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-038|多作品總覽、智慧辨識框與作品上直接標記／修正|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-039|AI 智慧資料辨識框的畫布快捷標記與人工校正|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|1|UI-062|template-Ai｜UI-062 跨模式 GUI 操作導覽、工作狀態與安全返回（正式決策）|PARTIAL|補跨既有工具的安全返回鏈，測失聯或版本變動不錯定位、不丟未套用內容、不自動重算或回寫；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|1|UI-063|template-Ai｜UI-063 右側工作面板：智慧自適應、常用工具固定與問題提示（正式決策）|PARTIAL|補按模式／類型／多選的工具優先序與全部屬性入口，測釘選保持可見但不適用時停用不帶舊值；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|1|UI-064|template-Ai｜UI-064 畫布快捷鍵、滑鼠手勢與誤觸衝突防護（正式決策）|PARTIAL|補中央指令作用域與安全提示，測文字Ctrl+Z不撤銷畫布、Delete不誤刪共享／鎖定物件；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|2|UI-003|訓練區批次匯入與啟動|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-004|訓練例外處理|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-005|例外中心智慧待辦排序|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-007|修正套用與 AI 學習確認|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-008|待審核規則中心|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-040|智慧標記完整性衝突檢查與可重用雜訊剔除規則|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-041|雜訊規則庫、命中追溯、例外白名單與安全回滾|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-042|訓練可恢復進度、精確去重與客戶資料庫重訂關聯|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|2|UI-055|人工修正可信訓練樣本池、標記版本與資料污染防護|PARTIAL|補可核實相關群組、防洩漏與各用途消費紀錄，測隔離後所有真正依賴失效且原資料保留；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-014|文字框無解診斷與輸入密度分級提醒|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-015|使用者資料輸入警告介面|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-016|新增人物、公司與多筆聯絡資料|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-017|共享公司與聯絡資料編輯|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-018|自動排版結果與候選模板呈現|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-019|印刷預檢與高保真 Logo 預覽輸出|PARTIAL|補安全區／裁切等已核准數位檢查與高保真參考；實體設備／材料印刷依REV03後移，不作本期阻塞；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-020|複合公司 Logo 與來源品質管理|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-021|複合 Logo 訓練校正、Logo 資料庫與缺圖占位|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-022|Logo 資料庫管理與審核介面|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-023|同公司 Logo 版本選用與按尺寸獨立 Logo 庫|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-024|各尺寸 Logo 庫管理與新尺寸預測專區|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-025|Logo 框位等比適配與安全候選比較|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-026|公司 Logo 自動匹配、選擇與匯入介面|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-027|多尺寸驗證總覽、部分正式輸出與黑底白字預覽檔|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-028|黑底白字占位預覽檔格式與非正式標示|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-029|批次輸出清單、智慧命名與安全儲存|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-030|批次輸出失敗診斷與安全重試|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|3|UI-051|低配置友善、公平審核佇列與安全續跑|PARTIAL|補保守資源預算和不飢餓佇列；逐來源逐作品審核，測重啟／磁碟失敗；不新增急件分類；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-057|AI 未涵蓋情境的分級風險提示、安全草稿與硬性無解阻擋|PARTIAL|補安全草稿與分尺寸風險理由，測忽略警告不放行、缺經驗不自動宣稱無解；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-058|當次自動排版的真實進度、低負載執行、安全取消與候選恢復|PARTIAL|補合法短期恢復及exact依賴核對／明確放棄，測異常／滿碟不能冒稱落盤；不建永久訂單庫；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-059|當次排版變更依賴局部重算、人工編輯保護與版本衝突防護|PARTIAL|補增量排程、保留手工布局與新舊差異選擇，測舊worker不能覆蓋新版、局部重算仍需整體驗證；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-060A|UI-060 補充決策 A｜排版完成後結果呈現、多方案比較與問題定位|PARTIAL|補結果比較與選取狀態保留，測排序更新不悄悄覆蓋人工選擇、不宣稱部分搜尋為最優；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-061|UI-061｜多候選與多尺寸修改同步、套用範圍及局部回復（正式決策）|PARTIAL|補精確目標／可套用屬性比較與獨立幾何重算，測跨尺寸不直接複製座標、回復不動其他人工修改；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|3|UI-065|template-Ai｜UI-065 多物件／多候選／多作品批次修正：風險分級、差異預覽與安全回復（正式決策）|PARTIAL|補各操作家族及跨尺寸語意映射，測只重試失敗、整批回復不覆蓋後續新值／不改字級或Logo比例；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|4|UI-043|智慧客戶建檔、版型關聯與正式資料結構方案|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|4|UI-044|舊客戶多條件搜尋、多尺寸版型比較與安全沿用重訂|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|4|UI-045|客戶主檔與當次製作逐欄差異、選擇性回寫與版本保護|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|4|UI-046|疑似重複客戶比對、受控合併與可追溯拆分恢復|PARTIAL|補合併前全影響預覽與雙方CAS、別名及拆分；測後續新值不被歷史拆分覆蓋；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|4|UI-047|本機關聯資料智慧備份、加密驗證與安全還原移轉|PARTIAL|補可選範圍與完整依賴Manifest、排程／保留政策及隔離還原驗證；缺資產必須報不完整；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|4|UI-049|Illustrator 來源搬移失聯、內容驗證與受控批次重新連結|PARTIAL|補多根搜尋／歧義選擇及完整影響摘要，測不同內容同名不重連、映射與原稿不改；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|4|UI-050|AI 來源資料夾智慧監看、安全增量匯入與版本衝突審核|PARTIAL|補事件只是提示的監看器及有界匯入佇列，測暫存檔、寫入中、漏事件／離線／改名均重新核實；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|5|UI-052|全來源與作品審核覆蓋率、風險分級與安全批次結案|PARTIAL|補未審／排除／失聯／待人工區分和版本化結案，測無作品來源與異名客戶不得漏掉；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|5|UI-052-REVIEW|重大共通錯誤跨歷史批次重審追加核准|PARTIAL|補跨家族直接／間接依賴與逐項重審結論，測舊通過保留歷史、原成品不刪、新證據不足不自動恢復；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|5|UI-053|獨立樣本品質驗收、分類誤判診斷、版本比較與品質阻擋|PARTIAL|補真實推論與獨立有權樣本、各類門檻／樣本量依據；測關鍵歸屬錯誤與分類退步不得用平均分掩蓋；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|5|UI-054|品質失敗根因分析、受控局部修復、獨立再驗收與安全回退|PARTIAL|補受控候選執行及反向退步測試，測舊測試用於修復後需新holdout、兩版均差不可聲稱退回安全；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|5|UI-056|訓練樣本類別覆蓋儀表板、缺口提醒與資料分布透明化|PARTIAL|補已核准C的可追溯分類與門檻依據／未知處理；測重疊類別不灌大總數、不自動產生補樣任務；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|5|UI-066|template-Ai｜UI-066 去重決策 A：重用既有診斷 GUI，僅保留獨立報告格式與安全交接補充規格|PARTIAL|完成原六項→現有證據對帳；可被既有證據涵蓋者直接結案，不另造新功能或要求所有其他父題先完成；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|5|UI-067|template-Ai｜UI-067 GUI 全面對帳、去重、衝突檢查與最少必要訪談（正式決策）|PARTIAL|補逐條規格→元件→測試→證據矩陣與過期引用修訂；純治理不算新軟體功能；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|6|REV-04|16 GB＋RTX 5050 至 ASUS VivoBook 效能範圍|PARTIAL|取得可用參考環境後測冷啟動、尖峰RAM／VRAM、GUI反應與取消；16GB是整機上限而非程式可占滿；完整原FULL條款保留，見PARTIAL_70_GAP_REPORT|
|6|UI-066-R1|是否需要獨立報告及最小格式內容|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|6|UI-066-R2|報告本機保存、去識別與人工交接|VERIFIED|完整原條款已自我驗證；docs/evidence/runs/RUN-TWENTYEIGHT-FULL-002/run.json|
|7|REV-03|軟體完善後再做實體印刷分析|DEFERRED|依來源拆分尚未完成的驗收子條件；不得用已做子集標完整主題完成|
|7|UI-048|客戶個資存取權限、遮罩與稽核：最後完成功能|DEFERRED|依來源拆分尚未完成的驗收子條件；不得用已做子集標完整主題完成|
|7|UI-056-D|進階分布失衡與系統化補樣|DEFERRED|依來源拆分尚未完成的驗收子條件；不得用已做子集標完整主題完成|
