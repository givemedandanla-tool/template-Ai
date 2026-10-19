# Template AI 精簡接續

程式來源 `96b1eb9dc23fe39fd5233d17513cc42f8ed547f8`；分支 `dev/v0.1-first-version`／PR #2，未合併main。完整 `docs/evidence/runs/RUN-LOCAL-RECOVERY-ALL8-005/run.json`：1733/1733 PASS、222健康獨立模組程序、0未處理runtime error、原生capture exit0、369附件逐件hash通過、來源未變。保留原1685個ID，新增48；不累加歷史／目標測試。整體FAIL僅5外部資格未驗證（Windows安裝、實際原生AI1/2/4人、VivoBook），軟體PASS分開判讀。

執行 `python tools/resume_status.py`，讀STATE及[本輪報告](AI_LOCAL_RECOVERY_FINAL_REPORT_20261019.md)、[本地指引](LOCAL_LEARNING_RECOVERY_GUIDE.md)、[8包50條核對](AI_LOCAL_RECOVERY_50_CLAUSE_AUDIT_20261019.md)。模型參數見 LOCAL_LEARNING_MODEL_DETAILS.md。GitHub最後snapshot/receipt以STATE.last_confirmed_checkpoint及pending_remote為準；若仍在發布，只補完保存／require-evidence檢查，不重跑已通過測試。

本輪已實作本地雙路復原、OCR/字面比對、跨作品共同規則、複合字面/標籤/圖示、明確詞/塑形群分散、物件等距、容量CI、排序資格及私密診斷。語意/外觀證據各綁實際管道/hash，查詢ID可重建且不改原稿。缺證據為UNKNOWN/拒絕，不把預設10pt當真值。進階複合來源標註、容量校準及正式資格有後台API，尚非完整GUI精靈。本體支援輸入→完整稿→相對微調→局部更正→預覽確認→輸出/重開，確認稿重複下單保留精確檔案。

22件合成作品（12TRAIN/6VALIDATION/4HOLDOUT）→2共用家族、0逐作品全域模板、10件評估/容量校準/穩定輸出。1000/3000 PDF相容AI實際匯入/原始glyph/字面量測/fit PASS：739.731s/2186.786s；17件暫停重開前綴一致、原稿不變。性能跨診斷/UI修訂，與固定來源回歸分列，不含私人AI結構、完整Windows字庫搜尋或指定設備資格。

歷史001/002主動中斷、003/004有真實來源管道/Logo真值失敗，四輪均未採用；原因與結果在各run/interruption.json，兩個失敗ID在005均PASS。詳細修正及目標測試在WORK_LOG/targeted-009/010，不重寫原失敗。原8包50條完整資格仍8部分/0完整真實資格；舊28題25完整/3部分；原75主題69驗證/3部分/3延後，CORE87/GOV7同範圍重驗，169registry的163scoped完成數不變。

私人作品/字型/DB/模型/確認稿留本機，不再索取上傳；本機資料需本地備份，GitHub不代存。無付費AI API/自動上傳；診斷僅由使用者自願匯出固定代碼/數量/版本白名單。客戶只表達相對位置，pt/hscale/欄框/切齊/分散由核心控制。網站/手機/EXE延後，card-interface只作情境參考。按需讀檔，新對話只帶版本與交接；無明確指令不啟動代理、不合併main。checkpoint節奏偏差與capture期間先保存靜態測試Git提交的原因已如實記錄。

2026-10-19編輯工具方案已獲使用者明確授權實作：TEMPLATE_EDITING_TOOLS_RESEARCH_20261019.md／TEMPLATE_EDITING_RESEARCH_SOURCES_20261019.json。回讀23項訪談索引與相關程式／測試；提出大量家族管理及單一家族規則編輯，既有目錄／畫布／批次／版本沿用。目前CORE-088 IN_PROGRESS，契約TEMPLATE_EDITING_IMPLEMENTATION_CONTRACT.json，16項工具驗收(B01-B08/S01-S08)。沿用原工具，持續本體實作與驗證；原75主題及AI8包50條不變，新增CORE功能分開計數。網頁／手機／EXE維持延後。
