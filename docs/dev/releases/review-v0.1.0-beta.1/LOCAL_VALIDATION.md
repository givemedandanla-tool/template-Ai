# 首版來源驗證與限制

本元件由既有 dev 提交 3274d2f945486fdc10d158de5352127f06223e84 建立 feature/review-tool-v0.1.0。既有未提交 timeout/adopt/source-run 資料保留，不納入本次提交。

已實際開啟獨立 Qt 視窗；最近 GUI 隔離模組 5/5 PASS，正常入口 --capture 亦成功。來源模式 smoke source-004 為31項檢查、5張真正視窗圖：SVG、PDF-compatible .ai、純外框SVG、真OCR與缺OCR退路、修正／歸屬／共享、框選調整、關係、總覽定位、保存重開、關閉放棄及安全報告。皆為明確合成作品，不能證明私人AI還原品質。正式來源完整模組與Windows結果由發布管線產生。

調查中曾發現OCR僅帶模型不帶 tsv config 時無輸出，已改明確 tessedit_create_tsv 開關；另不含讀取文字的外框SVG與缺引擎反例均保留。GUI測試曾因總覽新增區段後固定列索引而失敗，改按尺寸區段名稱定位，未放寬比例斷言。探索性混跑Qt模組的結果不作正式資格；正式各模組獨立程序。

舊產品 dev_governance check 仍報『證據已過期：程式／測試／fixture已變更』，屬舊完整來源快照資格，未改舊證據或冒稱全產品通過。本元件採 COMPONENT_RELEASE_POLICY 獨立來源manifest、相關核心及真EXE驗收；不提升舊產品主checkpoint、完整AI功能或外部資格。

首版Tesseract執行器選配；已附固定中／英模型，但沒有執行器時明確UNKNOWN，人工補標可用。Windows、實際Release下載須管線成功後才標完成。

沒有購買／啟用試用／額外API或模型服務；使用既有Codex能力、免費本機工具與公開倉庫標準GitHub Windows runner。帳戶實際帳單未查核，不承諾帳戶整體零帳單。

正式Linux隔離執行：166項通過、0失敗、0錯誤、0跳過，16個獨立程序模組。來源2e3677ba339bb0a1f6633272c8ea6886fee6d8b8，來源manifest a0eeee325e02b155bf90b11e161127400dd684a639a413ee1715a914cc0eb2db；包含6項GUI回歸。Windows仍須獨立通過。

首個Windows run 40012250996 在真正視窗截圖覆核後由維護者主動取消，當時尚未發布tag／Release；取消後證據／artifact步驟沒有可用產物而失敗，不能當成EXE驗證通過。修正重點是套用／核對狀態固定在右側底部，不需捲動，以及量測文字不覆蓋原稿。第二次run採精確HEAD淺取回（元件不依賴history/diff），保留全部來源hash／相關測試／真正EXE／下載要求。
