# 連續三包驗收契約（2026-10-14）

使用者授權持續完成三個新完整工作包。本輪基準 v0.1.11、39 已驗 CORE；依 PROJECT_ROADMAP 次序。每包是一條可操作的 GUI／持久化／失敗恢復流程；以下子項不冒充父需求完整完成。Linux 匿名合成 SELF_VERIFIED；不含 EXE、Windows／指定硬體證據、真實 AI 視覺一致性、未實作辨識模型與跨作品規則發布。

## 包 1：語意與來源結構的安全索引（CORE-040／041；UI-035）

- 同一 stable slot ID 的人物 ROOT、個人欄位、確認公司引用／共享公司索引；未知關聯明示。共享引用只索引同一物件，不建立新 DB 實體。樹、清單、畫布及屬性選取同步；搜尋／切換保留選取及清楚的命中／隱藏選取數。
- 搜尋 owner、種類、名稱、鎖定／共享／問題及取得的來源結構，固定排序；群組選取列出真實成員。暫時隱藏／淡化／隔離及顯示全部只改 viewport，不寫 DB、不改發布或輸出 Gate；鎖定仍獨立生效。
- 可驗證快取 SVG 的有序階層、ID／label／tag 唯讀呈現，明確標為衍生 SVG，不能稱 Illustrator 原生圖層。未提供證據的語意↔SVG映射為 UNKNOWN，不猜幾何或姓名。來源異動、重複 ID、缺少資料、超限／不安全 XML 均明示，無誤選或自動合併。
- 測試：真 Qt 兩模式入口／共享引用定位／搜尋選取保留／viewport DB 不變與全量 Gate／lock gate；有序 SVG、來源 hash 異動／未知映射／資源預算；匿名 GUI、machine audit 永久證據。

## 包 2：批次只讀匯入與持久佇列（CORE-042／043；UI-003／042／051）

- 多檔及資料夾有界掃描，唯讀預檢、SHA-256 exact 來源／頁次去重與已登錄重用，清楚區分檔案去重、作品去重 UNKNOWN、模板近似 UNKNOWN；近似不刪資料。預檢確認一次才啟動匯入，不假稱啟動尚未實作的自動辨識／訓練。
- GUI 真背景單件序列，SQLite 佇列與單件結果／attempt／進度持久；原始檔不寫入。轉換前後比對預檢 hash，註冊與單件結果原子寫入；單件錯誤隔離其他仍繼續；不可隔離 DB／稽核失敗停止並保留恢復點。
- 合作取消在目前轉換完成後停止，不強殺 Inkscape；目前項結果保存，未開始項可明確續跑。重開 RUNNING 項轉為需重試，SUCCESS 不重複執行；重用前檢查來源／快取健康。限制 200 項、50 MiB／單檔、單 worker；不是硬體效能承諾。
- 測試：exact duplicate／來源改動／健康重用／folder limits；持久恢復、取消、單件失敗隔離、交易晚期失敗 rollback；真 Qt 確認／進度／取消／重開續跑，GUI+machine audit。

## 包 3：匯入例外中心與單件處理（CORE-044／045；UI-004／005）

- 由真實批次單件結果生成持久待辦；嚴重性、類型、來源、受影響 source／artwork／template exact ID 及計數可追溯。穩定排序鍵而非臆造 AI 分數；可切換嚴重性／來源／類型，搜尋、篩選、詳情与來源定位。
- 失敗與中斷項隔離不删除來源；重試須明確確認精確選取項及新 hash 差異，僅重跑選中失敗／中斷項，不重跑成功項；排除需理由及確認，不等於成功／可信樣本／規則核准。已排除可明確恢復待辦。
- stale batch revision／雙擊／來源異動／背景失敗／DB晚期失败不能暗改其他項，controls 恢復；錯誤證據及 attempt 歷史保留。修正作品與規則發布另有工作包，不在此冒稱實作。
- 測試：impact 來源 exact IDs、stable排序與篩選；retry／exclude／restore CAS 与 rollback、重開历史、GUI真操作与源定位／失败恢复；匿名畫面及machine audit。

## 方法與參考

數學：索引為 stable ID→多引用的有向圖；選取是去重集合、search為固定欄位 token AND 匹配。SHA-256 content identity 不等於視覺／語意相同。佇列有限狀態機＋單 worker＋revision CAS；待辦 lexicographic key（阻擋程度、確實影響數、stable ID）可重現。採自行實作，不複製未審授權第三方碼。

參考已讀官方資料： [Adobe Layers](https://helpx.adobe.com/illustrator/desktop/manage-layers/create-and-organize-layers/layers-overview.html) 的定位／眼睛／鎖定各自分開；[Qt 6.8 QTreeWidget](https://doc.qt.io/qt-6.8/qtreewidget.html) 的 model item／selection；[Python sqlite3](https://docs.python.org/3/library/sqlite3.html) 交易與執行緒限制。實際執行環境 Python 3.11，不能以新文件 API 假稱本機版本支援。

## 執行與證據

先 BEGIN baseline 與本契約 GitHub 讀回，再逐包實作。每包具名 tests 登錄、固定 source commit/tree、formal run／真 GUI／永久附件、清單差異、HANDOFF／STATE／WORK_LOG、REMOTE_VERIFIED checkpoint。所有後續 code 變更使目前舊證據失效，下一包 formal 重驗所有已做 CORE。目標 6–8 分鐘 prepare 留上傳餘裕；任何超 10 分鐘確認間隔如實記錄。完整完成三包才结束本輪；checkpoint／部分 PASS 不中止工作。

## 後續保存優先序修正（功能驗收不變）

使用者明確改為略過證明附件上傳、將事件持久化並優先開發。依 EVIDENCE-UPLOAD-PRIORITY 決策，最新run的9件重複證明附件停止重試；原檔／原manifest／FAIL記錄不刪，功能及229項驗收不變。完整程式、JUnit、claims與51件可保存附件逐檔讀回；保存範圍checkpoint明列9件例外，不宣稱60件皆永久保存或舊strict Gate已PASS。三個具體實作工作包已完成，完整75父題仍續做。
