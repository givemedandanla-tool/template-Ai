# CORE-031：字型替代候選篩選、排名與唯讀預覽

2026-10-14（Asia/Taipei）。使用者本輪 /goal 的單一里程碑；先保存契約，再改碼。UI-032 的候選子功能完整驗收不代表 UI-032／UI-033 父題全部完成。

## 參考與方法

- 商用 [InDesign Find/Replace Font](https://helpx.adobe.com/indesign/desktop/fonts/find-and-replace-fonts.html)：參考列出缺失／使用字型、提供明確選擇與受影響資訊；不假稱能改匯入圖形內字型。本包唯讀，不套用、安裝或修改 Logo。
- 開源 [Fontconfig FcFontSort／匹配設計](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-devel/) 與 [維護者歷史原碼 fcmatch.c](https://github.com/behdad/fontconfig/blob/master/src/fcmatch.c)：實際閱讀 FcSortCompare 按 score 優先級逐項比較及 FcSortWalk 的 charset 合併／去重。上游 GitLab／cgit 本輪工具無法取得，改讀維護者歷史版本，不冒稱最新實作。參考其排序／覆蓋檢查思路，自行實作 lexicographic tuple；本包每個候選須獨立全覆蓋，禁止借其他字型補缺字，不複製第三方代碼或引入隱式 fallback。
- [Qt QTextLayout](https://doc.qt.io/qt-6.8/qtextlayout.html)：重用既有 cmap、完整 glyph-run／字面 table 核對；量測與預覽共用實際 shaping、kerning 及固定 1000 px em，Qt 字型物件留在工作執行緒。
- 數學：所需 Unicode 非空白集合 S 必須全部有非零 glyph；固定 pt 的自然字寬 W 與框寬 B，r=min(1,B/W)，r≥使用者最小水平比例才可列候選。先硬篩，再按 `(來源核實級別, |W/Wref−1|（僅有可量測比較字面時）, 1−r, 穩定身份與款式)` 升序排名；無參考時省略第二項，不能編造視覺相似分數。Wref 來自使用者明確選定的可量測字面，不宣稱是原稿字型。

## 不可變驗收條件

1. **輸入與硬篩**：使用共用中心文字、固定字級、框寬、水平比例；空白／非法輸入分開處理。缺字、未知引用、未核准、失聯、異動、無法解析、字面不一致及水平比例不足須有逐條排除原因；不得借用同名字型通過。
2. **排名與比較**：核准內容身份優先於來源未知 Qt 候選；已知比較字面顯示自然字寬差異及必要水平比例；失聯／缺字比較字面不給假的數字。穩定身份與款式打破同分，输入顺序不改排名。可查候選及排除條目、來源限制與排名理由。
3. **負載限制**：單輪最多64字面量測、最多10個展示候選、64 MiB資產大小預算，原快照部分結果與任何超額均明示 PARTIAL。不宣稱搜遍所有字型；重複身份／款式單輪去重，不以名稱合併不同身份。不跨輪快取過期量測。
4. **唯讀實際預覽**：共用中心可啟動候選查詢、明確選取候選再預覽。預覽前重新量測／核對 hash 與字面身份，繪製相同文字、固定 pt 與明列水平比例；輸入改動、字型異動或解析結果不同時阻擋過期預覽。使用有界 PNG 畫面、框位及單行寬度，不宣稱完整墨跡邊界／模板／原稿視覺一致／正式輸出或嵌入授權通過。
5. **背景與安全**：真實 Qt worker 完成／失敗回 GUI，恢復控制與可重試；輸入在工作中改變使結果失效。查詢／預覽前後模板、發布字型 pin、字型登錄及來源內容不變；候選不預設選取，不提供套用或系統安裝。
6. **完整交付**：具名單元及實際 GUI 流程、錯誤／stale／檔案異動驗收、必要回歸全部 PASS；實際匿名候選／預覽截圖與 PNG 附件永久保存 GitHub。要求、基準／結束統計、工作紀錄、交接、確切來源 commit/tree 及最終快照逐檔讀回；測試缺設備或 skip 不能當已完成。

## 執行與完成邊界

BEGIN 契約／checkpoint → 候選引擎與測試 → GUI 預覽與故障驗收 → exact source checkpoint → 正式全套 run → 完整附件 checkpoint → 收據、交接與讀回。每包／10分鐘保存，checkpoint 不是等待使用者繼續的理由。

Windows 實機、TTC 全字面與同名字型多版本共存、原生 Illustrator 身份、正式套用／UI-033逐欄批次審核、完整模板品質與嵌入權利另包；不是本候選唯讀功能的成功條件。原父題原驗收不刪減；UI-048最後，印刷／EXE延後。真正阻塞則保存證據與恢復方法，不能標完成。
