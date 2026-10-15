# 程式要求與功能清單

本檔由 REQUIREMENTS.json 生成；完整 UI 主題與具明確驗收範圍的 CORE 分開。完成只表示該列的驗收範圍，不代表全產品或 Windows／真實 AI 已驗證。

| ID | 功能／要求 | 實作狀態 | 完成 | 範圍／延後條件 | 證據 |
| --- | --- | --- | --- | --- | --- |
| UI-001 | 三模式主視窗 | PARTIAL | 否 | 三模式入口、可收合面板與共用工具一致 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-002 | 模式切換狀態 | PARTIAL | 否 | 模式切換保留有效當次狀態，恢復擴充依 UI-058 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-003 | 訓練區批次匯入與啟動 | PARTIAL | 否 | 預檢確認一次啟動，三層去重不混淆 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-004 | 訓練例外處理 | PARTIAL | 否 | 單件例外隔離，其餘合法工作繼續 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-005 | 例外中心智慧待辦排序 | PARTIAL | 否 | 待辦排序與影響數有來源，不能自動解除隔離 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-006 | 例外修正工作台 | PARTIAL | 否 | 原稿／疊圖／前後對照，修正可撤銷且不改原檔 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-007 | 修正套用與 AI 學習確認 | PARTIAL | 否 | 確認作品事實不自動發布跨作品規則 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-008 | 待審核規則中心 | PARTIAL | 否 | 低風險批次、高風險逐條，啟用均有人為核准 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-009 | 模板庫瀏覽方式 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 原UI-009完整已核准條款；穩定實體尺寸／capacity目錄、純唯讀預覽與明確編輯／exact版型採用，未知與過期來源不假稱通過 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| UI-010 | 模板版本編輯機制 | PARTIAL | 否 | 正式版本唯讀，草稿持久，驗證及核准後發布 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-011 | 模板編輯器物件操作 | PARTIAL | 否 | 畫布／語意樹／屬性同一物件與歸屬 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-012 | 物件移動縮放與智慧對齊 | PARTIAL | 否 | 毫米幾何、吸附及鎖定，草稿違規不可發布 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-013 | 文字框智慧編輯介面 | PARTIAL | 否 | 字級定案不依字數改變，無合法解不截字 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-014 | 文字框無解診斷與輸入密度分級提醒 | PARTIAL | 否 | 實測無解與證據不足分開，禁止暗縮字級 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-015 | 使用者資料輸入警告介面 | PARTIAL | 否 | 欄位提醒、整體狀態與問題定位判定一致 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-016 | 新增人物、公司與多筆聯絡資料 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 原UI-016全部已核准條款：人物ROOT卡片、stable圖、多公司與共享引用、安全複製解除刪除、Undo/Redo、當次資料及既有輸出Gate不放寬 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| UI-017 | 共享公司與聯絡資料編輯 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 原UI-017全部已核准條款：人物ROOT卡片、stable圖、多公司與共享引用、安全複製解除刪除、Undo/Redo、當次資料及既有輸出Gate不放寬 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| UI-018 | 自動排版結果與候選模板呈現 | PARTIAL | 否 | 先硬驗證後候選排序，未完成搜尋不稱全域最佳 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-019 | 印刷預檢與高保真 Logo 預覽輸出 | PARTIAL | 否 | 本輪修訂：數位視覺／輸出品質前期驗證；實體印刷分析移至軟體完善後 P10 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-020 | 複合公司 Logo 與來源品質管理 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-021 | 複合 Logo 訓練校正、Logo 資料庫與缺圖占位 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-022 | Logo 資料庫管理與審核介面 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-023 | 同公司 Logo 版本選用與按尺寸獨立 Logo 庫 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-024 | 各尺寸 Logo 庫管理與新尺寸預測專區 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-025 | Logo 框位等比適配與安全候選比較 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-026 | 公司 Logo 自動匹配、選擇與匯入介面 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-027 | 多尺寸驗證總覽、部分正式輸出與黑底白字預覽檔 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-028 | 黑底白字占位預覽檔格式與非正式標示 | PARTIAL | 否 | PNG 預設與非正式標示保留；數位內容與比例驗證，實體印刷分析後移 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-029 | 批次輸出清單、智慧命名與安全儲存 | PARTIAL | 否 | 正式／預覽分流，預設不覆寫，逐檔真實狀態 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-030 | 批次輸出失敗診斷與安全重試 | PARTIAL | 否 | 只重試失敗項，保護成功檔，半成品不作正式成功 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-031 | 字型缺失與 Illustrator 特殊文字效果處理 | PARTIAL | 否 | 本輪修訂：Inkscape 等路徑視覺一致且可訓練可完成匯入；原生資訊缺失如實標記 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-032 | Windows 字型庫、智慧匹配、匯入與受控安裝介面 | PARTIAL | 否 | 程式載入與 Windows 安裝不同，系統安裝需明確同意 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-033 | 字型替代影響範圍與風險分級批次審核 | PARTIAL | 否 | 替代前逐欄影響，勾選低風險批次，高風險逐筆 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-034 | 畫布、物件清單與屬性面板同步安全編輯 | PARTIAL | 否 | 三向多選同一集合，混合值不被默默覆蓋 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-035 | 語意樹、Illustrator 圖層與搜尋／鎖定管理介面 | PARTIAL | 否 | 已取得的原圖層或衍生物件結構分層呈現，不虛構原生結構；隱藏不減驗證範圍 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-036 | 多物件精確對齊、等距分布與群組位移 | PARTIAL | 否 | 明確基準與差異預覽，對齊不改字級／Logo 比例 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-037 | 畫布縮放、平移、快速定位與同步對照檢視 | PARTIAL | 否 | 縮放平移只改視角，實際尺寸須校準才承諾 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-038 | 多作品總覽、智慧辨識框與作品上直接標記／修正 | PARTIAL | 否 | 矩形作品範圍與雙層標記；適用 Inkscape 衍生來源，視覺一致且有效可訓練 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-039 | AI 智慧資料辨識框的畫布快捷標記與人工校正 | PARTIAL | 否 | 標記中介資料與真物件編輯區別，確認可追溯 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-040 | 智慧標記完整性衝突檢查與可重用雜訊剔除規則 | PARTIAL | 否 | 核准雜訊條件後自動排除，不反覆問也不刪原稿 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-041 | 雜訊規則庫、命中追溯、例外白名單與安全回滾 | PARTIAL | 否 | 命中追溯、單項恢復、白名單及規則回滾可核對 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-042 | 訓練可恢復進度、精確去重與客戶資料庫重訂關聯 | PARTIAL | 否 | 異名同內容共用分析、保留來源客戶映射及斷點 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-043 | 智慧客戶建檔、版型關聯與正式資料結構方案 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-044 | 舊客戶多條件搜尋、多尺寸版型比較與安全沿用重訂 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 原UI-044完整已核准條款；穩定實體尺寸／capacity目錄、純唯讀預覽與明確編輯／exact版型採用，未知與過期來源不假稱通過 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| UI-045 | 客戶主檔與當次製作逐欄差異、選擇性回寫與版本保護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整原始軟體條款；Linux合成／實際Qt及數位檔自我驗證。Windows、私人AI全面保真、實體印刷及獨立覆核另列未驗證，既定延後順序不變。 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-046 | 疑似重複客戶比對、受控合併與可追溯拆分恢復 | PARTIAL | 否 | 合併須確認、別名可查，拆分不覆蓋後續新值 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-047 | 本機關聯資料智慧備份、加密驗證與安全還原移轉 | PARTIAL | 否 | 加密完整性及隔離還原，缺資產不宣稱完整可用 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-048 | 客戶個資存取權限、遮罩與稽核：最後完成功能 | DEFERRED | 否 | 核心功能完善後最後接入；正式真實個資使用前必須完成 | 無有效新版證據 |
| UI-049 | Illustrator 來源搬移失聯、內容驗證與受控批次重新連結 | PARTIAL | 否 | 來源重連以內容驗證，不憑同名，原檔不修改 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-050 | AI 來源資料夾智慧監看、安全增量匯入與版本衝突審核 | PARTIAL | 否 | 監看事件需重掃核實，寫入未穩定不分析 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-051 | 低配置友善、公平審核佇列與安全續跑 | PARTIAL | 否 | 參考 16 GB 整機 RAM＋RTX 5050 與待補規格 VivoBook；CPU 核心、限流及檢查點 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-052 | 全來源與作品審核覆蓋率、風險分級與安全批次結案 | PARTIAL | 否 | 分母不漏來源，未審不可結案，重大错誤可重審歷史批次 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-053 | 獨立樣本品質驗收、分類誤判診斷、版本比較與品質阻擋 | PARTIAL | 否 | 獨立資料分類品質保留；解析品質依視覺一致、訓練有效性及已取得證據判定 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-054 | 品質失敗根因分析、受控局部修復、獨立再驗收與安全回退 | PARTIAL | 否 | 根因候選隔離、回歸及獨立再驗收，兩版有問題不假退回安全 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-055 | 人工修正可信訓練樣本池、標記版本與資料污染防護 | PARTIAL | 否 | 樣本准入與訓練分離，污染可追查 exact 資料集與模型 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-056 | 訓練樣本類別覆蓋儀表板、缺口提醒與資料分布透明化 | PARTIAL | 否 | C 分布與缺口提醒；D 系統補樣不得提前做 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-057 | AI 未涵蓋情境的分級風險提示、安全草稿與硬性無解阻擋 | PARTIAL | 否 | 低把握、缺證據、已證實無解區別，忽略警告不能放行 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-058 | 當次自動排版的真實進度、低負載執行、安全取消與候選恢復 | PARTIAL | 否 | 真實進度、短期恢復；按指定參考機實測 RAM、VRAM 與 CPU／GPU 路徑；既有標記歷史是 UI-038 子能力，不能充當當次排版候選恢復已完成 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-059 | 當次排版變更依賴局部重算、人工編輯保護與版本衝突防護 | PARTIAL | 否 | 局部失效、人工位置保護，舊運算結果不可覆寫新版 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-060A | UI-060 補充決策 A｜排版完成後結果呈現、多方案比較與問題定位 | PARTIAL | 否 | 推薦與候選對照、問題定位，未搜尋完整不稱最佳 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-061 | UI-061｜多候選與多尺寸修改同步、套用範圍及局部回復（正式決策） | PARTIAL | 否 | 來源內容依 ID 同步，幾何分候選尺寸，跨目標先比對 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-062 | template-Ai｜UI-062 跨模式 GUI 操作導覽、工作狀態與安全返回（正式決策） | PARTIAL | 否 | 上下文返回有效位置，失效安全降級不丟人工內容 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-063 | template-Ai｜UI-063 右側工作面板：智慧自適應、常用工具固定與問題提示（正式決策） | PARTIAL | 否 | 上下文工具可釘選，不適用對象不能錯用舊值 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-064 | template-Ai｜UI-064 畫布快捷鍵、滑鼠手勢與誤觸衝突防護（正式決策） | PARTIAL | 否 | 焦點與中文輸入法優先，模式／Undo 作用域不混淆 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-065 | template-Ai｜UI-065 多物件／多候選／多作品批次修正：風險分級、差異預覽與安全回復（正式決策） | PARTIAL | 否 | 精確範圍預覽、部分成功、冪等重試與安全回復 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-066 | template-Ai｜UI-066 去重決策 A：重用既有診斷 GUI，僅保留獨立報告格式與安全交接補充規格 | PARTIAL | 否 | 既有診斷重用；獨立報告必要性格式交接尚 OPEN | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-067 | template-Ai｜UI-067 GUI 全面對帳、去重、衝突檢查與最少必要訪談（正式決策） | PARTIAL | 否 | 全面對帳只問真缺口，治理不算新產品功能 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-052-REVIEW | 重大共通錯誤跨歷史批次重審追加核准 | PARTIAL | 否 | 依賴追溯、暫停信任、逐項再審，保留歷史與原成品 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| UI-056-D | 進階分布失衡與系統化補樣 | DEFERRED | 否 | 正式版本完善後另行評估，不加入本期交付 | 無有效新版證據 |
| UI-066-R1 | 獨立診斷報告內容、程式內閱讀與HTML／JSON安全封裝 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 只處理真缺口，不重問診斷和預覽；2026-10-15已確認問題資訊需程式內可讀與程式外可保存，未採納提案全部細節 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| UI-066-R2 | 報告本機保存、去識別與人工交接 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 只處理真缺口，不重問診斷和預覽；2026-10-15已確認問題資訊需程式內可讀與程式外可保存，未採納提案全部細節 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| REV-01 | 矩形區域自動排版與模板 AI；X-04 結案 | PARTIAL | 否 | 同一矩形模型，名稱不再待決；既有客戶人物公司與資產功能沿用 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| REV-02 | Inkscape 等視覺一致且可訓練的 AI 匯入 | PARTIAL | 否 | 真實參考視覺無可辨識差異且有效可訓練；完整原生結構非共同必要條件 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| REV-03 | 軟體完善後再做實體印刷分析 | DEFERRED | 否 | 前期數位輸出與幾何仍驗證，實體樣張／設備／材料條件後移 | 無有效新版證據 |
| REV-04 | 16 GB＋RTX 5050 至 ASUS VivoBook 效能範圍 | PARTIAL | 否 | VivoBook 型號待補；16 GB 整機非程序可占滿預算，實測 CPU／GPU 與峰值資源 | [run](../../docs/evidence/runs/RUN-DIAGNOSTIC-REPORTS-002/run.json) |
| CORE-001 | 固定字級與長文字無解阻擋 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-002 | 資料完整映射與人物容量 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-003 | 缺字型與幾何檢查 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-004 | 人物公司與同尺寸 Logo 防混配 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-005 | 數位三格式尺寸與安全寫檔 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-006 | 候選過期與非正式預覽標示 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-007 | 模板發布歷史不可覆寫 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-008 | 同內容快取與獨立來源登錄 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-009 | 人工標記規則模板閉環 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-010 | Inkscape SVG 與 PDF 相容 AI | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-011 | 多頁 PDF 正確頁與備援 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-012 | 匯入前像素預算 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-013 | 固定背景實際向量與圖像輸出 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-014 | 背景核准、内容与失聯保護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-015 | 背景 GUI 核對及版本保護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-016 | 人工文字色彩 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-017 | 多作品與上次來源上下文 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-018 | 標記歷史、遷移與競爭寫入 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-019 | 模板固定學習來源版次 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-020 | 發布與審核同一交易 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-021 | 字型持久複本與新程序載入 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-022 | 字型核准、異動與失敗保護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-023 | 來源快取完整性與損壞恢復 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成來源衍生快取完整性，非完整批次來源重連；checksum非安全簽章 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| GOV-001 | 開發 checkpoint 與安全恢復 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| GOV-002 | Human／GPT 開工交接與下一步 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| GOV-003 | 要求與個別證據完成 Gate | IMPLEMENTED_PENDING_VERIFICATION | 否 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| GOV-004 | 持久 AI 入口与零例行問答 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| GOV-005 | EXE 延後且不自動打包 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-024 | 單件來源內容驗證與安全重連 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成來源單件重連與歷史保留；非完整批次重連或來源內容替換 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-025 | 核准同內容字型複本修復與中斷核對 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／環境既有字型與匿名模板；非完整字重版本或 Windows 安裝 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-026 | 受控範圍背景來源定位與候選影響預覽 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成來源；單根受限掃描與人工勾選，不代表完整跨設備資產管理 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-027 | 批次來源重連交易、歷史與安全復原 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／合成來源批次位置交易與當前內容驗證，不更改客戶映射或源檔 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| GOV-006 | 每輪功能清單統計、基準與需求差異回報 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Human／GPT 開發治理報告，非 UI-066 產品報告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-028 | 共用字型管理、資產身份與模板影響查詢 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／環境既有字型、合成模板及匿名診斷文字；非完整Windows／TTC／字重版本／替代與嵌入授權 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-029 | 實際字形覆蓋、固定字級毫米量測與框宽診斷 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／環境既有字型、合成模板及匿名診斷文字；非完整Windows／TTC／字重版本／替代與嵌入授權 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-030 | 背景工作生命週期與GUI成功／錯誤交接 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux Qt 真實worker訊號持有／GUI queued交接與busy恢復；非完整公平佇列／當次候選恢復或斷電续跑 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-031 | 字型替代候選硬篩、可解釋排名與唯讀預覽 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 候選只讀端到端功能；Linux環境字型／匿名文字單行診斷，不代表完整UI-032、Windows、原稿一致或UI-033套用 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-032 | 字型替代影響、逐欄量測與人工審核 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整受控草稿替代端到端工作包；Linux／匿名樣本，不代表原稿一致、全UI-033／Windows或正式輸出授權 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-033 | 受控字型替代新版本草稿、全批交易及持久復原重做 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整受控草稿替代端到端工作包；Linux／匿名樣本，不代表原稿一致、全UI-033／Windows或正式輸出授權 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-034 | 字型款式持久與候選、排版及渲染身份一致 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 完整受控草稿替代端到端工作包；Linux／匿名樣本，不代表原稿一致、全UI-033／Windows或正式輸出授權 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-035 | 實際來源與前後矩形渲染 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／匿名合成來源；精確歷史crop映射與完整矩形唯讀對照，不代表原生AI字型識別、真實視覺一致或完整父題 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-036 | 唯讀同步視圖、欄位定位與字型審核整合 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／匿名合成來源；精確歷史crop映射與完整矩形唯讀對照，不代表原生AI字型識別、真實視覺一致或完整父題 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-037 | 三向安全多選與混合共同屬性 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／匿名；既有來源標記或保存草稿的進階物件編輯器整包，兩模式入口及既有編輯鎖定policy；未驗原生AI／完整父題／Windows／hardware／獨立品質 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-038 | 持久物件鎖定與全編輯途徑保護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／匿名；既有來源標記或保存草稿的進階物件編輯器整包，兩模式入口及既有編輯鎖定policy；未驗原生AI／完整父題／Windows／hardware／獨立品質 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-039 | 精確幾何差異、原子套用與持久UndoRedo | IMPLEMENTED_PENDING_VERIFICATION | 否 | Linux／匿名；既有來源標記或保存草稿的進階物件編輯器整包，兩模式入口及既有編輯鎖定policy；未驗原生AI／完整父題／Windows／hardware／獨立品質 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-040 | 人物 ROOT 語意引用、搜尋及 viewport 安全檢視 | IMPLEMENTED_PENDING_VERIFICATION | 否 | THREE_PACKAGES_DESIGN 的完整具體包；Linux／匿名合成；不等於全部父題／原生AI／自動辨識學習／Windows／hardware／獨立覆核 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-041 | 衍生 SVG 結構唯讀索引與未知映射保護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | THREE_PACKAGES_DESIGN 的完整具體包；Linux／匿名合成；不等於全部父題／原生AI／自動辨識學習／Windows／hardware／獨立覆核 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-042 | 批次來源唯讀預檢、exact 去重及啟動確認 | IMPLEMENTED_PENDING_VERIFICATION | 否 | THREE_PACKAGES_DESIGN 的完整具體包；Linux／匿名合成；不等於全部父題／原生AI／自動辨識學習／Windows／hardware／獨立覆核 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-043 | 單 worker 持久匯入佇列、取消及續跑 | IMPLEMENTED_PENDING_VERIFICATION | 否 | THREE_PACKAGES_DESIGN 的完整具體包；Linux／匿名合成；不等於全部父題／原生AI／自動辨識學習／Windows／hardware／獨立覆核 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-044 | 可解釋例外排序、exact 影響及來源定位 | IMPLEMENTED_PENDING_VERIFICATION | 否 | THREE_PACKAGES_DESIGN 的完整具體包；Linux／匿名合成；不等於全部父題／原生AI／自動辨識學習／Windows／hardware／獨立覆核 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-045 | 例外單件重試、排除與恢復的 CAS 歷史 | IMPLEMENTED_PENDING_VERIFICATION | 否 | THREE_PACKAGES_DESIGN 的完整具體包；Linux／匿名合成；不等於全部父題／原生AI／自動辨識學習／Windows／hardware／獨立覆核 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-046 | 標記完整性與有界幾何語意診斷 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包1的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-047 | 診斷搜尋排序與精確來源框定位 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包1的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-048 | 人工來源觀察與作品事實確認 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包2的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-049 | 事實revision差異與確認撤銷 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包2的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-050 | 單作品雜訊排除與精確作用範圍 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包3的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-051 | 有正反例的可重用雜訊候選 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包3的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-052 | 可解釋規則分組與審核詳情 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包4的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-053 | 低風險批准／逐條詳審與版本CAS | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包4的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-054 | 核准後後續精確命中自動排除 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包5的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-055 | 持久命中追溯與疑義保留 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包5的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-056 | 局部誤判恢复與可重用白名單 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包6的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-057 | 規則停用回滾與exact依賴影響 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包6的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-058 | 來源與用途核對的可信樣本准入 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包7的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-059 | 污染隔離撤銷與exact使用追溯 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包7的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-060 | exact資料集manifest與同源角色隔離 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包8的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-061 | 可信TRAIN樣本幾何草稿學習 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包8的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-062 | 審核覆蓋分母與分頁定位 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包9的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-063 | 樣本分布／未知分類與中性缺口提示 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包9的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-064 | 受控幾何學習單worker與持久結果 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包10的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-065 | 合作取消／中斷恢复與精確續跑 | IMPLEMENTED_PENDING_VERIFICATION | 否 | TEN_PACKAGES_DESIGN 包10的完整具體流程；Linux／匿名合成；原父題、OCR／原生AI、深度模型、Windows／hardware／独立品質非本子項完成宣告 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-066 | 逐欄輸入問題、整體待驗狀態與exact儲存格定位 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 逐欄輸入問題、整體待驗狀態與exact儲存格定位；未宣稱估計為無解，正式輸出仍既有Gate；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-067 | 依實體尺寸樹隔離既有核准Logo及唯讀跨尺寸參考區 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 依實體尺寸樹隔離既有核准Logo及唯讀跨尺寸參考區；新尺寸參考不入庫／不核准；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-068 | 單一Library內人工客戶建檔、stable人物與欄位ID、前導零及確切模板關聯 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 單一Library內人工客戶建檔、stable人物與欄位ID、前導零及確切模板關聯；AI擷取／安全批次建檔仍後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-069 | 受控多條件搜尋、身份確認後引用確切版本預填當次資料 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 受控多條件搜尋、身份確認後引用確切版本預填當次資料；縮圖比較及完整重訂擴充仍後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-070 | 逐欄勾選差異確認與客戶revision CAS原子回寫 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 逐欄勾選差異確認與客戶revision CAS原子回寫；共享公司及跨實體回復後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-071 | 疑似重複只讀雙方比對與線索，不自動合併 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 疑似重複只讀雙方比對與線索，不自動合併；合併／別名／拆分尚未實作；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-072 | 一致SQLite快照、驗證加密檔與新目錄隔離還原、外部資產明示缺失 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 一致SQLite快照、驗證加密檔與新目錄隔離還原、外部資產明示缺失；排程／完整資產可攜備份／活躍庫合併後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-073 | 明確根目錄人工重掃、雙次穩定內容核對、增量分類與只讀來源 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 明確根目錄人工重掃、雙次穩定內容核對、增量分類與只讀來源；事件自動監看／自動增量匯入後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-074 | 固定HOLDOUT資料集版本的分類預測與人工真值比對、混淆計數及不足Gate | IMPLEMENTED_PENDING_VERIFICATION | 否 | 固定HOLDOUT資料集版本的分類預測與人工真值比對、混淆計數及不足Gate；原生AI模型／正式門檻與品質合格發布後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-075 | exact失敗評估建立隔離根因修復待辦、候選版本對照與無證據回退阻擋 | IMPLEMENTED_PENDING_VERIFICATION | 否 | exact失敗評估建立隔離根因修復待辦、候選版本對照與無證據回退阻擋；自動模型修復／訓練／部署後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-076 | 當次候選逐模板單worker真進度、邊界暫停／續跑／取消及generation過期防護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 當次候選逐模板單worker真進度、邊界暫停／續跑／取消及generation過期防護；跨啟動敏感恢復／硬體實測後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-077 | 當次exact候選／尺寸的局部幾何變更隔離、明確範圍差異與版本保護 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 當次exact候選／尺寸的局部幾何變更隔離、明確範圍差異與版本保護；共享語意ID跨尺寸同步與局部回復後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-078 | 既有右側物件工具上下文與釘選可見性、不適用與stale清空 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 既有右側物件工具上下文與釘選可見性、不適用與stale清空；完整MainWindow右面板自適應後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-079 | 重用既有object_edit具名目標的跨作品低風險差異／逐項結果與冪等防重 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 重用既有object_edit具名目標的跨作品低風險差異／逐項結果與冪等防重；統一跨候選修復及跨尺寸幾何轉換後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-080 | 診斷入口路由重用既有問題與定位、版本與未知不改Gate | IMPLEMENTED_PENDING_VERIFICATION | 否 | 診斷入口路由重用既有問題與定位、版本與未知不改Gate；R1/R2仍BLOCKED，不產獨立報告；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| GOV-007 | 機器GUI路由／決策去重對帳與未決分流檢查 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 機器GUI路由／決策去重對帳與未決分流檢查；純治理，不計CORE產品能力；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-081 | 明確規則依賴跨歷史樣本重審，人工確認後暫停信任且保留歷史 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 明確規則依賴跨歷史樣本重審，人工確認後暫停信任且保留歷史；其他模型／Logo／客戶依賴全面掃描與解除重審後續；Linux匿名合成SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-082 | 共用診斷快照與離線HTML／JSON安全交接包 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 共用診斷快照與離線HTML／JSON安全交接包；DIAGNOSTIC_REPORTS_CONTRACT十二條完整驗收／Linux匿名SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-083 | 既有GUI報告保存重開與exact版本定位 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 既有GUI報告保存重開與exact版本定位；DIAGNOSTIC_REPORTS_CONTRACT十二條完整驗收／Linux匿名SELF範圍 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-084 | 人物ROOT穩定實體圖與安全共享操作 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 當次人物卡片、真實引用／獨立複本、受控差異、Undo/Redo、多公司模板port與公司聯絡資料；不改已發布模板／原稿／固定字級 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-085 | 正規化客戶語意關聯與當次資料逐欄整合 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 單一CustomerStore穩定實體／外鍵、舊欄位ID安全遷移、exact版型預填、共享影響、三方CAS回寫、歷史值受控恢復；不宣稱自動AI建檔或全多尺寸縮圖／新增刪除主檔同步完成 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-086 | 實體尺寸容量目錄、同索引雙檢視與明確編輯 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 單一模板庫尺寸→capacity、縮圖／列表、搜尋狀態版本篩選、跨分頁穩定多選、可讀詳情、實際框位示意／驗證來源圖，瀏覽停用舊物件編輯target；需明確進入既有編輯區 | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |
| CORE-087 | 客戶尺寸版型來源並排與身份確認exact預填 | IMPLEMENTED_PENDING_VERIFICATION | 否 | 多類欄位／格式電話只讀搜尋、同名同電話保持獨立、身份確認只看該客戶確切款式、歷史來源hash裁切／未知／過期檢查、雙尺寸並排、確認前後CAS及來源新鮮度、僅改當次資料並保持原Gate | [run](../../docs/evidence/runs/RUN-FULL70-CATALOG-001/run.json) |

驗收細節、來源、具名測試、父要求、阻擋與下一步請讀 [REQUIREMENTS.json](REQUIREMENTS.json)。歷史 UI CSV 是來源索引，不再當作即時完成度。
