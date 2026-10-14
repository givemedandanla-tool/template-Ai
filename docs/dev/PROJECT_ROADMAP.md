# 全75父題開發順序與驗收缺口

完整原scope／來源保留PROJECT_ROADMAP.json；CORE子項不替代父題全部條款。

| 階段 | ID | 要求 | 現況 | 已驗證子項 |
| --- | --- | --- | --- | --- |
| 1 | REV-01 | 矩形區域自動排版與模板 AI；X-04 結案 | PARTIAL | CORE-009 |
| 1 | REV-02 | Inkscape 等視覺一致且可訓練的 AI 匯入 | PARTIAL | CORE-010, CORE-011 |
| 1 | UI-001 | 三模式主視窗 | PARTIAL | 尚無 |
| 1 | UI-002 | 模式切換狀態 | PARTIAL | CORE-017 |
| 1 | UI-006 | 例外修正工作台 | PARTIAL | CORE-035 |
| 1 | UI-009 | 模板庫瀏覽方式 | PARTIAL | 尚無 |
| 1 | UI-010 | 模板版本編輯機制 | PARTIAL | CORE-007, CORE-015, CORE-020 |
| 1 | UI-011 | 模板編輯器物件操作 | PARTIAL | 尚無 |
| 1 | UI-012 | 物件移動縮放與智慧對齊 | PARTIAL | CORE-003 |
| 1 | UI-013 | 文字框智慧編輯介面 | PARTIAL | CORE-001, CORE-034 |
| 1 | UI-031 | 字型缺失與 Illustrator 特殊文字效果處理 | PARTIAL | CORE-003, CORE-035 |
| 1 | UI-032 | Windows 字型庫、智慧匹配、匯入與受控安裝介面 | PARTIAL | CORE-021, CORE-022, CORE-025, CORE-028, CORE-029, CORE-031, CORE-034 |
| 1 | UI-033 | 字型替代影響範圍與風險分級批次審核 | PARTIAL | CORE-022, CORE-032, CORE-033, CORE-035, CORE-036 |
| 1 | UI-034 | 畫布、物件清單與屬性面板同步安全編輯 | PARTIAL | CORE-013, CORE-014, CORE-015, CORE-016, CORE-037, CORE-038, CORE-039 |
| 1 | UI-035 | 語意樹、Illustrator 圖層與搜尋／鎖定管理介面 | PARTIAL | CORE-038, CORE-040, CORE-041 |
| 1 | UI-036 | 多物件精確對齊、等距分布與群組位移 | PARTIAL | CORE-039 |
| 1 | UI-037 | 畫布縮放、平移、快速定位與同步對照檢視 | PARTIAL | CORE-036 |
| 1 | UI-038 | 多作品總覽、智慧辨識框與作品上直接標記／修正 | PARTIAL | CORE-017, CORE-018 |
| 1 | UI-039 | AI 智慧資料辨識框的畫布快捷標記與人工校正 | PARTIAL | 尚無 |
| 1 | UI-062 | template-Ai｜UI-062 跨模式 GUI 操作導覽、工作狀態與安全返回（正式決策） | PARTIAL | 尚無 |
| 1 | UI-063 | template-Ai｜UI-063 右側工作面板：智慧自適應、常用工具固定與問題提示（正式決策） | NOT_IMPLEMENTED | 尚無 |
| 1 | UI-064 | template-Ai｜UI-064 畫布快捷鍵、滑鼠手勢與誤觸衝突防護（正式決策） | PARTIAL | 尚無 |
| 2 | UI-003 | 訓練區批次匯入與啟動 | PARTIAL | CORE-008, CORE-030, CORE-042, CORE-043 |
| 2 | UI-004 | 訓練例外處理 | PARTIAL | CORE-044, CORE-045 |
| 2 | UI-005 | 例外中心智慧待辦排序 | PARTIAL | CORE-044, CORE-045 |
| 2 | UI-007 | 修正套用與 AI 學習確認 | NOT_IMPLEMENTED | CORE-009, CORE-019 |
| 2 | UI-008 | 待審核規則中心 | NOT_IMPLEMENTED | 尚無 |
| 2 | UI-040 | 智慧標記完整性衝突檢查與可重用雜訊剔除規則 | NOT_IMPLEMENTED | 尚無 |
| 2 | UI-041 | 雜訊規則庫、命中追溯、例外白名單與安全回滾 | NOT_IMPLEMENTED | 尚無 |
| 2 | UI-042 | 訓練可恢復進度、精確去重與客戶資料庫重訂關聯 | PARTIAL | CORE-008, CORE-018, CORE-023, CORE-042, CORE-043 |
| 2 | UI-055 | 人工修正可信訓練樣本池、標記版本與資料污染防護 | NOT_IMPLEMENTED | CORE-019 |
| 3 | UI-014 | 文字框無解診斷與輸入密度分級提醒 | PARTIAL | CORE-001 |
| 3 | UI-015 | 使用者資料輸入警告介面 | NOT_IMPLEMENTED | CORE-002 |
| 3 | UI-016 | 新增人物、公司與多筆聯絡資料 | PARTIAL | CORE-002 |
| 3 | UI-017 | 共享公司與聯絡資料編輯 | PARTIAL | CORE-004 |
| 3 | UI-018 | 自動排版結果與候選模板呈現 | PARTIAL | 尚無 |
| 3 | UI-019 | 印刷預檢與高保真 Logo 預覽輸出 | PARTIAL | CORE-005, CORE-013 |
| 3 | UI-020 | 複合公司 Logo 與來源品質管理 | PARTIAL | 尚無 |
| 3 | UI-021 | 複合 Logo 訓練校正、Logo 資料庫與缺圖占位 | PARTIAL | 尚無 |
| 3 | UI-022 | Logo 資料庫管理與審核介面 | PARTIAL | 尚無 |
| 3 | UI-023 | 同公司 Logo 版本選用與按尺寸獨立 Logo 庫 | PARTIAL | CORE-004 |
| 3 | UI-024 | 各尺寸 Logo 庫管理與新尺寸預測專區 | NOT_IMPLEMENTED | 尚無 |
| 3 | UI-025 | Logo 框位等比適配與安全候選比較 | PARTIAL | CORE-004 |
| 3 | UI-026 | 公司 Logo 自動匹配、選擇與匯入介面 | PARTIAL | 尚無 |
| 3 | UI-027 | 多尺寸驗證總覽、部分正式輸出與黑底白字預覽檔 | PARTIAL | 尚無 |
| 3 | UI-028 | 黑底白字占位預覽檔格式與非正式標示 | PARTIAL | CORE-006 |
| 3 | UI-029 | 批次輸出清單、智慧命名與安全儲存 | PARTIAL | CORE-005 |
| 3 | UI-030 | 批次輸出失敗診斷與安全重試 | PARTIAL | CORE-005 |
| 3 | UI-051 | 低配置友善、公平審核佇列與安全續跑 | PARTIAL | CORE-012, CORE-030, CORE-043 |
| 3 | UI-057 | AI 未涵蓋情境的分級風險提示、安全草稿與硬性無解阻擋 | PARTIAL | 尚無 |
| 3 | UI-058 | 當次自動排版的真實進度、低負載執行、安全取消與候選恢復 | NOT_IMPLEMENTED | 尚無 |
| 3 | UI-059 | 當次排版變更依賴局部重算、人工編輯保護與版本衝突防護 | PARTIAL | CORE-006 |
| 3 | UI-060A | UI-060 補充決策 A｜排版完成後結果呈現、多方案比較與問題定位 | PARTIAL | 尚無 |
| 3 | UI-061 | UI-061｜多候選與多尺寸修改同步、套用範圍及局部回復（正式決策） | NOT_IMPLEMENTED | 尚無 |
| 3 | UI-065 | template-Ai｜UI-065 多物件／多候選／多作品批次修正：風險分級、差異預覽與安全回復（正式決策） | NOT_IMPLEMENTED | 尚無 |
| 4 | UI-043 | 智慧客戶建檔、版型關聯與正式資料結構方案 | NOT_IMPLEMENTED | 尚無 |
| 4 | UI-044 | 舊客戶多條件搜尋、多尺寸版型比較與安全沿用重訂 | NOT_IMPLEMENTED | 尚無 |
| 4 | UI-045 | 客戶主檔與當次製作逐欄差異、選擇性回寫與版本保護 | NOT_IMPLEMENTED | 尚無 |
| 4 | UI-046 | 疑似重複客戶比對、受控合併與可追溯拆分恢復 | NOT_IMPLEMENTED | 尚無 |
| 4 | UI-047 | 本機關聯資料智慧備份、加密驗證與安全還原移轉 | NOT_IMPLEMENTED | 尚無 |
| 4 | UI-049 | Illustrator 來源搬移失聯、內容驗證與受控批次重新連結 | PARTIAL | CORE-023, CORE-024, CORE-026, CORE-027 |
| 4 | UI-050 | AI 來源資料夾智慧監看、安全增量匯入與版本衝突審核 | NOT_IMPLEMENTED | 尚無 |
| 5 | UI-052 | 全來源與作品審核覆蓋率、風險分級與安全批次結案 | NOT_IMPLEMENTED | 尚無 |
| 5 | UI-052-REVIEW | 重大共通錯誤跨歷史批次重審追加核准 | NOT_IMPLEMENTED | 尚無 |
| 5 | UI-053 | 獨立樣本品質驗收、分類誤判診斷、版本比較與品質阻擋 | NOT_IMPLEMENTED | 尚無 |
| 5 | UI-054 | 品質失敗根因分析、受控局部修復、獨立再驗收與安全回退 | NOT_IMPLEMENTED | 尚無 |
| 5 | UI-056 | 訓練樣本類別覆蓋儀表板、缺口提醒與資料分布透明化 | NOT_IMPLEMENTED | 尚無 |
| 5 | UI-066 | template-Ai｜UI-066 去重決策 A：重用既有診斷 GUI，僅保留獨立報告格式與安全交接補充規格 | NOT_IMPLEMENTED | 尚無 |
| 5 | UI-067 | template-Ai｜UI-067 GUI 全面對帳、去重、衝突檢查與最少必要訪談（正式決策） | NOT_IMPLEMENTED | 尚無 |
| 6 | REV-04 | 16 GB＋RTX 5050 至 ASUS VivoBook 效能範圍 | PARTIAL | 尚無 |
| 6 | UI-066-R1 | 是否需要獨立報告及最小格式內容 | BLOCKED | 尚無 |
| 6 | UI-066-R2 | 報告本機保存、去識別與人工交接 | BLOCKED | 尚無 |
| 7 | REV-03 | 軟體完善後再做實體印刷分析 | DEFERRED | 尚無 |
| 7 | UI-048 | 客戶個資存取權限、遮罩與稽核：最後完成功能 | DEFERRED | 尚無 |
| 7 | UI-056-D | 進階分布失衡與系統化補樣 | DEFERRED | 尚無 |
