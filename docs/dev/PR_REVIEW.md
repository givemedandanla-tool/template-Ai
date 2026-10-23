# PR #2 審查說明：v0.1.14

建議標題：`feat: v0.1.14 語意索引、可恢復批次匯入與來源例外中心`

在矩形模板工作台加入三條可操作流程：同一stable-ID語意／共用引用搜尋與安全viewport、批次只讀預檢與單worker持久取消／續跑、來源例外exact影響排序／定位及受控重試／排除／恢復。原稿保持只讀，來源SVG明確為衍生資料且未知映射保留；匯入SUCCESS或例外排除不視為可信訓練。

批次與例外採SQLite交易、revision CAS及持有session，單件結果／source註冊／audit全rollback或同交易保存；selected retry不執行其他READY與SUCCESS。字型、人物公司、Logo、模板版本及數位PDF／PNG／JPG既有功能納入回歸。最後修正隱藏locked物件時Qt selectedItems丟失的範圍漏洞，保存完整selection_intent，真RED／GREEN紀錄保留。

固定source192db957a927e6fcdedf7b62ef835748bf238717；RUN-EXCEPTION-CENTER-002：229PASS／0SKIP、source unchanged。JUnit、具名claims、來源與環境、實際GUI與數位輸出證據永久保存；9件重複證明附件依使用者最新指令略過上傳，原manifest／本機附件不改。完整全附件Gate未满足，不宣稱全部60永久保存。保存範圍及事件見EVIDENCE_PUBLICATION_EXCEPTIONS、COPYRIGHT_PRIVACY_EVENTS與STATE。

功能CORE39→45新增完成6，GOV6；126列，75父題0完整／46部分／24未實作／2受阻／3延後。SELF_VERIFIED限Linux／匿名合成，非Windows、真實AI全面視覺、指定硬體或獨立覆核；EXE／印刷延後、UI048最後。main與PR未合併。下一包標記完整性與可信樣本准入見MARKING_TRUST_NEXT_PLAN。

本文件是可直接用於審查的描述；沒有宣稱GitHub PR頁面標題已同步更新。
