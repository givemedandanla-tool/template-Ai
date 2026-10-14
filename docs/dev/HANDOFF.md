# Human／GPT 開發交接

依序讀 AGENTS.md、STATE.json、REQUIREMENTS.json／FEATURES.md、PROGRESS.md／CURRENT_PROGRESS.json、WORK_LOG最新紀錄／checkpoint收據、DEVELOPMENT_PROTOCOL.md。每輪先保存新要求基準、結束保存差異與同數字回報。

## 最新已驗證版本

v0.1.7，確切來源 `f347495579a8d43e191ce8e8471e0b90aaaaf3f5`；RUN-FONT-CENTER-002：122 PASS／0 SKIP、22件實際匿名附件與紀錄，含字型中心／診斷。初版RUN-FONT-CENTER-001未完成，不當PASS；before-fix／after-fix具名故障紀錄保留CORE-030。

111列＝75父題＋30 CORE＋6 GOV。原始父題完整0／部分42／未實作28／受阻2／延後3，75仍有未完成條件；功能子項27→30（新增CORE-028／029／030），治理6不變。新增3、刪除0、既有驗收範圍修訂0；拆分增加不當原題完成率。對帳見PROGRESS-20261014-FONT-CENTER-BEGIN／END.json。

## 本輪成果及注意

CORE-028共用字型中心：GUI取得SQLite／Qt候選快照，背景只讀hash與可解析家族款式，列核准複本／主機Qt候選／模板待處理引用、健康／身份／影響，搜尋篩選與既有合法匯入／同內容修復。Qt來源未核實不冒稱Windows已安裝或原稿字型。

CORE-029：實際cmap不同codepoints覆蓋率，無fallback shaping及glyph-run字面主要tables核對，固定1000px em按pt轉mm及水平比例；缺字／字面不符／低比例／非法單行／空文本／背景期間改輸入等如實阻擋。不暗改字級、截字或改模板；診斷不等於完整模板／原稿身份／嵌入授權。TTC只有可解析字面，其他字面未知。

CORE-030：實際背景測試揭露Job完成但GUI訊號遺失。MainWindow持有_background_jobs及Signals parent、明確QueuedConnection，success／worker error／callback error均在GUI恢復busy並釋放，真實字型worker及後續重試通過。不能以mock或pool已空當GUI完成。不是完整公平佇列／取消／斷電候選恢复。

故障CP在before-fix日志仍寫入時prepare，讀回擋下不一致；以原ZIP冻结字節（當時日志空）完成不可變FAILURE snapshot，再在ASYNC-FIXED保存完整before／after。不得改歷史記錄或稱錯誤來源已驗證。

最終snapshot `73e67f1aff392973af9cbcddc170508876816c7f` 已逐檔讀回347檔；本輪新增6個已確認checkpoint，總計27個。收據與STATE另提交保存避免SHA自參照，實際before／after日志與22件新版附件已包含。

## 下一工作包

UI-032 少量替代候選只讀預覽子包，先讀原決策474行、UI-033、FONT_CENTER_DESIGN.md、font_catalog.py。可按所需字形全部覆蓋、固定點數shaping與框位可行比例做硬篩，再以可核實來源／字寬保持度排序；無可信原稿／原字型幾何就標未知，不能給外觀等同、找回原稿字型或原版審美的分數。限制候選数量與worker負載，以set-membership和已驗證字面量測快取避免重复解析；先拆CORE-031、基準／BEGIN／具名驗收。

預覽不替換發布模板、不自動核准全域字型映射、不取消同名字型不同檔防混用 Gate。真正套用、範圍／差異／高風險逐筆審核依UI-033另包；完整不同版本同家族／TTC／字重需精確字面身份與渲染可重現驗收，不能只去掉現有拒絕判斷。Windows安裝單獨產品操作同意；原稿／字型權利未知仍須明示，不用本輪環境操作授權替代字型散布／使用授權。

UI-049多根／掃描進度續跑／完整外部依賴與客戶映射、獨立品質、真實AI視覺與硬體仍待。印刷／EXE延後，UI-048最後功能／真實個資使用前完成。下一輪從功能清單按核准範圍推進。

## 恢復與GitHub

每包與10分鐘保存；pending_remote先補確認，不累積未保存碼。程式／驗收改動使舊當前證據失效，歷史保留。完整附件checkpoint讀回後才當永久完成，收據／STATE再提交避免SHA循環。本輪PR metadata兩次歷史呼叫被中止，改以已可用tree／commit／ref API保存必要程式與文件；可複用審查說明見PR_REVIEW.md，不反覆卡住同一操作，不宣稱PR頁面標題已改。工作分支仍dev/v0.1-first-version／PR #2未合併main。
