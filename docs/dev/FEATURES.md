# 程式要求與功能清單

本檔由 REQUIREMENTS.json 生成；完整 UI 主題與具明確驗收範圍的 CORE 分開。完成只表示該列的驗收範圍，不代表全產品或 Windows／真實 AI 已驗證。

| ID | 功能／要求 | 實作狀態 | 完成 | 範圍／延後條件 | 證據 |
| --- | --- | --- | --- | --- | --- |
| UI-001 | 三模式主視窗 | PARTIAL | 否 | 三模式入口、可收合面板與共用工具一致 | 無有效新版證據 |
| UI-002 | 模式切換狀態 | PARTIAL | 否 | 模式切換保留有效當次狀態，恢復擴充依 UI-058 | 無有效新版證據 |
| UI-003 | 訓練區批次匯入與啟動 | PARTIAL | 否 | 預檢確認一次啟動，三層去重不混淆 | 無有效新版證據 |
| UI-004 | 訓練例外處理 | NOT_IMPLEMENTED | 否 | 單件例外隔離，其餘合法工作繼續 | 無有效新版證據 |
| UI-005 | 例外中心智慧待辦排序 | NOT_IMPLEMENTED | 否 | 待辦排序與影響數有來源，不能自動解除隔離 | 無有效新版證據 |
| UI-006 | 例外修正工作台 | PARTIAL | 否 | 原稿／疊圖／前後對照，修正可撤銷且不改原檔 | 無有效新版證據 |
| UI-007 | 修正套用與 AI 學習確認 | NOT_IMPLEMENTED | 否 | 確認作品事實不自動發布跨作品規則 | 無有效新版證據 |
| UI-008 | 待審核規則中心 | NOT_IMPLEMENTED | 否 | 低風險批次、高風險逐條，啟用均有人為核准 | 無有效新版證據 |
| UI-009 | 模板庫瀏覽方式 | PARTIAL | 否 | 按實體尺寸及 peopleCapacity 分類並保持搜尋選取 | 無有效新版證據 |
| UI-010 | 模板版本編輯機制 | PARTIAL | 否 | 正式版本唯讀，草稿持久，驗證及核准後發布 | 無有效新版證據 |
| UI-011 | 模板編輯器物件操作 | PARTIAL | 否 | 畫布／語意樹／屬性同一物件與歸屬 | 無有效新版證據 |
| UI-012 | 物件移動縮放與智慧對齊 | PARTIAL | 否 | 毫米幾何、吸附及鎖定，草稿違規不可發布 | 無有效新版證據 |
| UI-013 | 文字框智慧編輯介面 | PARTIAL | 否 | 字級定案不依字數改變，無合法解不截字 | 無有效新版證據 |
| UI-014 | 文字框無解診斷與輸入密度分級提醒 | PARTIAL | 否 | 實測無解與證據不足分開，禁止暗縮字級 | 無有效新版證據 |
| UI-015 | 使用者資料輸入警告介面 | NOT_IMPLEMENTED | 否 | 欄位提醒、整體狀態與問題定位判定一致 | 無有效新版證據 |
| UI-016 | 新增人物、公司與多筆聯絡資料 | PARTIAL | 否 | 多人多公司、多聯絡方式保持各自語意所有權 | 無有效新版證據 |
| UI-017 | 共享公司與聯絡資料編輯 | PARTIAL | 否 | 實體共享、複本、解除關聯與刪除區別 | 無有效新版證據 |
| UI-018 | 自動排版結果與候選模板呈現 | PARTIAL | 否 | 先硬驗證後候選排序，未完成搜尋不稱全域最佳 | 無有效新版證據 |
| UI-019 | 印刷預檢與高保真 Logo 預覽輸出 | PARTIAL | 否 | 本輪修訂：數位視覺／輸出品質前期驗證；實體印刷分析移至軟體完善後 P10 | 無有效新版證據 |
| UI-020 | 複合公司 Logo 與來源品質管理 | PARTIAL | 否 | Logo 圖形加文字整體保護，OCR 不拆商標 | 無有效新版證據 |
| UI-021 | 複合 Logo 訓練校正、Logo 資料庫與缺圖占位 | PARTIAL | 否 | 候選核准入庫，缺圖同框位黑底白字只作占位 | 無有效新版證據 |
| UI-022 | Logo 資料庫管理與審核介面 | PARTIAL | 否 | 同尺寸跨模式入口共用，候選未核准不入正式庫 | 無有效新版證據 |
| UI-023 | 同公司 Logo 版本選用與按尺寸獨立 Logo 庫 | PARTIAL | 否 | 已知尺寸不跨庫，唯一新尺寸例外仍須目標核准 | 無有效新版證據 |
| UI-024 | 各尺寸 Logo 庫管理與新尺寸預測專區 | NOT_IMPLEMENTED | 否 | 新尺寸預測專區與正常尺寸庫隔離 | 無有效新版證據 |
| UI-025 | Logo 框位等比適配與安全候選比較 | PARTIAL | 否 | 等比完整放入，留白不自動失敗，不能裁切變形 | 無有效新版證據 |
| UI-026 | 公司 Logo 自動匹配、選擇與匯入介面 | PARTIAL | 否 | 單一有效版可預覽，多版歧義人工選擇並綁版本 | 無有效新版證據 |
| UI-027 | 多尺寸驗證總覽、部分正式輸出與黑底白字預覽檔 | PARTIAL | 否 | 各矩形尺寸獨立排版／數位驗證，部分正式輸出明確確認；印刷分析後移 | 無有效新版證據 |
| UI-028 | 黑底白字占位預覽檔格式與非正式標示 | PARTIAL | 否 | PNG 預設與非正式標示保留；數位內容與比例驗證，實體印刷分析後移 | 無有效新版證據 |
| UI-029 | 批次輸出清單、智慧命名與安全儲存 | PARTIAL | 否 | 正式／預覽分流，預設不覆寫，逐檔真實狀態 | 無有效新版證據 |
| UI-030 | 批次輸出失敗診斷與安全重試 | PARTIAL | 否 | 只重試失敗項，保護成功檔，半成品不作正式成功 | 無有效新版證據 |
| UI-031 | 字型缺失與 Illustrator 特殊文字效果處理 | PARTIAL | 否 | 本輪修訂：Inkscape 等路徑視覺一致且可訓練可完成匯入；原生資訊缺失如實標記 | 無有效新版證據 |
| UI-032 | Windows 字型庫、智慧匹配、匯入與受控安裝介面 | PARTIAL | 否 | 程式載入與 Windows 安裝不同，系統安裝需明確同意 | 無有效新版證據 |
| UI-033 | 字型替代影響範圍與風險分級批次審核 | NOT_IMPLEMENTED | 否 | 替代前逐欄影響，勾選低風險批次，高風險逐筆 | 無有效新版證據 |
| UI-034 | 畫布、物件清單與屬性面板同步安全編輯 | PARTIAL | 否 | 三向多選同一集合，混合值不被默默覆蓋 | 無有效新版證據 |
| UI-035 | 語意樹、Illustrator 圖層與搜尋／鎖定管理介面 | PARTIAL | 否 | 已取得的原圖層或衍生物件結構分層呈現，不虛構原生結構；隱藏不減驗證範圍 | 無有效新版證據 |
| UI-036 | 多物件精確對齊、等距分布與群組位移 | NOT_IMPLEMENTED | 否 | 明確基準與差異預覽，對齊不改字級／Logo 比例 | 無有效新版證據 |
| UI-037 | 畫布縮放、平移、快速定位與同步對照檢視 | PARTIAL | 否 | 縮放平移只改視角，實際尺寸須校準才承諾 | 無有效新版證據 |
| UI-038 | 多作品總覽、智慧辨識框與作品上直接標記／修正 | PARTIAL | 否 | 矩形作品範圍與雙層標記；適用 Inkscape 衍生來源，視覺一致且有效可訓練 | 無有效新版證據 |
| UI-039 | AI 智慧資料辨識框的畫布快捷標記與人工校正 | PARTIAL | 否 | 標記中介資料與真物件編輯區別，確認可追溯 | 無有效新版證據 |
| UI-040 | 智慧標記完整性衝突檢查與可重用雜訊剔除規則 | NOT_IMPLEMENTED | 否 | 核准雜訊條件後自動排除，不反覆問也不刪原稿 | 無有效新版證據 |
| UI-041 | 雜訊規則庫、命中追溯、例外白名單與安全回滾 | NOT_IMPLEMENTED | 否 | 命中追溯、單項恢復、白名單及規則回滾可核對 | 無有效新版證據 |
| UI-042 | 訓練可恢復進度、精確去重與客戶資料庫重訂關聯 | PARTIAL | 否 | 異名同內容共用分析、保留來源客戶映射及斷點 | 無有效新版證據 |
| UI-043 | 智慧客戶建檔、版型關聯與正式資料結構方案 | NOT_IMPLEMENTED | 否 | 客戶關聯尺寸版型，不設購買分類，編號保留前導零 | 無有效新版證據 |
| UI-044 | 舊客戶多條件搜尋、多尺寸版型比較與安全沿用重訂 | NOT_IMPLEMENTED | 否 | 搜尋核對身份，沿用確切版型開新稿並重驗 | 無有效新版證據 |
| UI-045 | 客戶主檔與當次製作逐欄差異、選擇性回寫與版本保護 | NOT_IMPLEMENTED | 否 | 只回寫明確勾選欄位，過期主檔版本阻擋 | 無有效新版證據 |
| UI-046 | 疑似重複客戶比對、受控合併與可追溯拆分恢復 | NOT_IMPLEMENTED | 否 | 合併須確認、別名可查，拆分不覆蓋後續新值 | 無有效新版證據 |
| UI-047 | 本機關聯資料智慧備份、加密驗證與安全還原移轉 | NOT_IMPLEMENTED | 否 | 加密完整性及隔離還原，缺資產不宣稱完整可用 | 無有效新版證據 |
| UI-048 | 客戶個資存取權限、遮罩與稽核：最後完成功能 | DEFERRED | 否 | 核心功能完善後最後接入；正式真實個資使用前必須完成 | 無有效新版證據 |
| UI-049 | Illustrator 來源搬移失聯、內容驗證與受控批次重新連結 | PARTIAL | 否 | 來源重連以內容驗證，不憑同名，原檔不修改 | 無有效新版證據 |
| UI-050 | AI 來源資料夾智慧監看、安全增量匯入與版本衝突審核 | NOT_IMPLEMENTED | 否 | 監看事件需重掃核實，寫入未穩定不分析 | 無有效新版證據 |
| UI-051 | 低配置友善、公平審核佇列與安全續跑 | PARTIAL | 否 | 參考 16 GB 整機 RAM＋RTX 5050 與待補規格 VivoBook；CPU 核心、限流及檢查點 | 無有效新版證據 |
| UI-052 | 全來源與作品審核覆蓋率、風險分級與安全批次結案 | NOT_IMPLEMENTED | 否 | 分母不漏來源，未審不可結案，重大错誤可重審歷史批次 | 無有效新版證據 |
| UI-053 | 獨立樣本品質驗收、分類誤判診斷、版本比較與品質阻擋 | NOT_IMPLEMENTED | 否 | 獨立資料分類品質保留；解析品質依視覺一致、訓練有效性及已取得證據判定 | 無有效新版證據 |
| UI-054 | 品質失敗根因分析、受控局部修復、獨立再驗收與安全回退 | NOT_IMPLEMENTED | 否 | 根因候選隔離、回歸及獨立再驗收，兩版有問題不假退回安全 | 無有效新版證據 |
| UI-055 | 人工修正可信訓練樣本池、標記版本與資料污染防護 | NOT_IMPLEMENTED | 否 | 樣本准入與訓練分離，污染可追查 exact 資料集與模型 | 無有效新版證據 |
| UI-056 | 訓練樣本類別覆蓋儀表板、缺口提醒與資料分布透明化 | NOT_IMPLEMENTED | 否 | C 分布與缺口提醒；D 系統補樣不得提前做 | 無有效新版證據 |
| UI-057 | AI 未涵蓋情境的分級風險提示、安全草稿與硬性無解阻擋 | PARTIAL | 否 | 低把握、缺證據、已證實無解區別，忽略警告不能放行 | 無有效新版證據 |
| UI-058 | 當次自動排版的真實進度、低負載執行、安全取消與候選恢復 | NOT_IMPLEMENTED | 否 | 真實進度、短期恢復；按指定參考機實測 RAM、VRAM 與 CPU／GPU 路徑；既有標記歷史是 UI-038 子能力，不能充當當次排版候選恢復已完成 | 無有效新版證據 |
| UI-059 | 當次排版變更依賴局部重算、人工編輯保護與版本衝突防護 | PARTIAL | 否 | 局部失效、人工位置保護，舊運算結果不可覆寫新版 | 無有效新版證據 |
| UI-060A | UI-060 補充決策 A｜排版完成後結果呈現、多方案比較與問題定位 | PARTIAL | 否 | 推薦與候選對照、問題定位，未搜尋完整不稱最佳 | 無有效新版證據 |
| UI-061 | UI-061｜多候選與多尺寸修改同步、套用範圍及局部回復（正式決策） | NOT_IMPLEMENTED | 否 | 來源內容依 ID 同步，幾何分候選尺寸，跨目標先比對 | 無有效新版證據 |
| UI-062 | template-Ai｜UI-062 跨模式 GUI 操作導覽、工作狀態與安全返回（正式決策） | PARTIAL | 否 | 上下文返回有效位置，失效安全降級不丟人工內容 | 無有效新版證據 |
| UI-063 | template-Ai｜UI-063 右側工作面板：智慧自適應、常用工具固定與問題提示（正式決策） | NOT_IMPLEMENTED | 否 | 上下文工具可釘選，不適用對象不能錯用舊值 | 無有效新版證據 |
| UI-064 | template-Ai｜UI-064 畫布快捷鍵、滑鼠手勢與誤觸衝突防護（正式決策） | PARTIAL | 否 | 焦點與中文輸入法優先，模式／Undo 作用域不混淆 | 無有效新版證據 |
| UI-065 | template-Ai｜UI-065 多物件／多候選／多作品批次修正：風險分級、差異預覽與安全回復（正式決策） | NOT_IMPLEMENTED | 否 | 精確範圍預覽、部分成功、冪等重試與安全回復 | 無有效新版證據 |
| UI-066 | template-Ai｜UI-066 去重決策 A：重用既有診斷 GUI，僅保留獨立報告格式與安全交接補充規格 | NOT_IMPLEMENTED | 否 | 既有診斷重用；獨立報告必要性格式交接尚 OPEN | 無有效新版證據 |
| UI-067 | template-Ai｜UI-067 GUI 全面對帳、去重、衝突檢查與最少必要訪談（正式決策） | NOT_IMPLEMENTED | 否 | 全面對帳只問真缺口，治理不算新產品功能 | 無有效新版證據 |
| UI-052-REVIEW | 重大共通錯誤跨歷史批次重審追加核准 | NOT_IMPLEMENTED | 否 | 依賴追溯、暫停信任、逐項再審，保留歷史與原成品 | 無有效新版證據 |
| UI-056-D | 進階分布失衡與系統化補樣 | DEFERRED | 否 | 正式版本完善後另行評估，不加入本期交付 | 無有效新版證據 |
| UI-066-R1 | 是否需要獨立報告及最小格式內容 | BLOCKED | 否 | 只處理真缺口，不重問診斷和預覽 | 無有效新版證據 |
| UI-066-R2 | 報告本機保存、去識別與人工交接 | BLOCKED | 否 | 只處理真缺口，不重問診斷和預覽 | 無有效新版證據 |
| REV-01 | 矩形區域自動排版與模板 AI；X-04 結案 | PARTIAL | 否 | 同一矩形模型，名稱不再待決；既有客戶人物公司與資產功能沿用 | 無有效新版證據 |
| REV-02 | Inkscape 等視覺一致且可訓練的 AI 匯入 | PARTIAL | 否 | 真實參考視覺無可辨識差異且有效可訓練；完整原生結構非共同必要條件 | 無有效新版證據 |
| REV-03 | 軟體完善後再做實體印刷分析 | DEFERRED | 否 | 前期數位輸出與幾何仍驗證，實體樣張／設備／材料條件後移 | 無有效新版證據 |
| REV-04 | 16 GB＋RTX 5050 至 ASUS VivoBook 效能範圍 | PARTIAL | 否 | VivoBook 型號待補；16 GB 整機非程序可占滿預算，實測 CPU／GPU 與峰值資源 | 無有效新版證據 |
| CORE-001 | 固定字級與長文字無解阻擋 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-002 | 資料完整映射與人物容量 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-003 | 缺字型與幾何檢查 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-004 | 人物公司與同尺寸 Logo 防混配 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-005 | 數位三格式尺寸與安全寫檔 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-006 | 候選過期與非正式預覽標示 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-007 | 模板發布歷史不可覆寫 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-008 | 同內容快取與獨立來源登錄 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-009 | 人工標記規則模板閉環 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-010 | Inkscape SVG 與 PDF 相容 AI | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-011 | 多頁 PDF 正確頁與備援 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-012 | 匯入前像素預算 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-013 | 固定背景實際向量與圖像輸出 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-014 | 背景核准、内容与失聯保護 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-015 | 背景 GUI 核對及版本保護 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-016 | 人工文字色彩 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-017 | 多作品與上次來源上下文 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-018 | 標記歷史、遷移與競爭寫入 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-019 | 模板固定學習來源版次 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-020 | 發布與審核同一交易 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-021 | 字型持久複本與新程序載入 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-022 | 字型核准、異動與失敗保護 | VERIFIED | 是 | Linux／合成或環境字型的明列子範圍；完整父要求仍待續 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-023 | 來源快取完整性與損壞恢復 | VERIFIED | 是 | Linux／合成來源衍生快取完整性，非完整批次來源重連；checksum非安全簽章 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| GOV-001 | 開發 checkpoint 與安全恢復 | VERIFIED | 是 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| GOV-002 | Human／GPT 開工交接與下一步 | VERIFIED | 是 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| GOV-003 | 要求與個別證據完成 Gate | VERIFIED | 是 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| GOV-004 | 持久 AI 入口与零例行問答 | VERIFIED | 是 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| GOV-005 | EXE 延後且不自動打包 | VERIFIED | 是 | 本輪五點開發框架；不保證最後未保存操作零風險或離線 GPT 自動讀檔 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-024 | 單件來源內容驗證與安全重連 | VERIFIED | 是 | Linux／合成來源單件重連與歷史保留；非完整批次重連或來源內容替換 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-025 | 核准同內容字型複本修復與中斷核對 | VERIFIED | 是 | Linux／環境既有字型與匿名模板；非完整字重版本或 Windows 安裝 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-026 | 受控範圍背景來源定位與候選影響預覽 | VERIFIED | 是 | Linux／合成來源；單根受限掃描與人工勾選，不代表完整跨設備資產管理 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-027 | 批次來源重連交易、歷史與安全復原 | VERIFIED | 是 | Linux／合成來源批次位置交易與當前內容驗證，不更改客戶映射或源檔 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| GOV-006 | 每輪功能清單統計、基準與需求差異回報 | VERIFIED | 是 | Human／GPT 開發治理報告，非 UI-066 產品報告 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-028 | 共用字型管理、資產身份與模板影響查詢 | VERIFIED | 是 | Linux／環境既有字型、合成模板及匿名診斷文字；非完整Windows／TTC／字重版本／替代與嵌入授權 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-029 | 實際字形覆蓋、固定字級毫米量測與框宽診斷 | VERIFIED | 是 | Linux／環境既有字型、合成模板及匿名診斷文字；非完整Windows／TTC／字重版本／替代與嵌入授權 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |
| CORE-030 | 背景工作生命週期與GUI成功／錯誤交接 | VERIFIED | 是 | Linux Qt 真實worker訊號持有／GUI queued交接與busy恢復；非完整公平佇列／當次候選恢復或斷電续跑 | [run](../../docs/evidence/runs/RUN-FONT-CENTER-002/run.json) |

驗收細節、來源、具名測試、父要求、阻擋與下一步請讀 [REQUIREMENTS.json](REQUIREMENTS.json)。歷史 UI CSV 是來源索引，不再當作即時完成度。
