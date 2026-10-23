# DesignObservation v1：第一層實作規格

狀態：IMPLEMENTATION_SLICE；對應AI-LEARN-01，尚非整包完成或模型訓練。來源：既有訪談去重索引、有效跨作品契約及已查核的Qt／fontTools／NetworkX／Kiwi工程參考。

## 責任與界線

以每件作品為觀察單位，保留來源檔／頁、作品／事實修訂、標記區域、人物／公司／欄位圖與資料引用。內容雜湊用於來源分組，不作人物或客戶身份；跨作品人物對應仍需證據。每件作品的觀察不自動建立模板、不取得樣本准入或規則發布資格。

這個schema可先獨立落地，供後續DataRequirementProfile／FieldCapabilityProfile使用；三項訓練設計待辦仍待完整schema／實檔對映／驗證校準，不因基礎實作標完成。

## 標量及證據

`ObservedScalar(value,unit,status,basis,evidence_refs)`：value為有限實數或null，禁止bool／NaN／Infinity。unit明列mm／pt／ratio／count；status為UNKNOWN、ANNOTATED、OBSERVED、DERIVED。UNKNOWN必須null；其他狀態必須有值、依據與引用。來源觀察、人工設計參數與計算導出值分開。

已知來源pt與完整物理仿射矩陣可用兩軸範數相等、內積為零判斷均勻縮放／旋轉，再導出有效pt。未知或只具模板設計字級、非均勻縮放／斜切時不推定唯一來源pt。這只是量測工具，不授權依文字長度修改字級。

## 作品觀察記錄

- `schema_version`、`extractor_version`、`input_signature`：重現與失效依據。
- `pins`：沿用TrainingStore的source/work/page/link revision與work digest。
- `facts_ref`：事實記錄ID、修訂與digest；文字採穩定引用，避免在圖中重複保存個資或膨脹metadata。
- `coordinate_systems`：來源頁mm、作品mm、來源crop及source-to-work仿射。實際墨跡框、標記框與作品尺寸不得混同。
- `qualification`：事實狀態、作品視覺確認與訓練准入分開；產生觀察不代表合格、已訓練或已發布。
- `lineage`：source content group、work/source身份；更完整的跨檔／家族lineage仍接既有QualityGroups／dataset機制，不由同檔推定同家族。
- `nodes`：WORK_CONTAINER、PERSON_GROUP／COMPANY_GROUP／UNKNOWN_OWNER、FIELD_ROLE、TEXT／ANNOTATION／LOGO／UNKNOWN觀察。ID依作品與原穩定ID導出，不以姓名字串或位置合併。
- `edges`：contains、owned_by、observes_role、person_company與derived_relative_geometry；只表達具來源的標記關係。人物欄位各自成組，公司引用保留；不把同字串當共享。
- `counts`：已標記人物、欄位角色、文字／區域觀察分開；未建立規範化語意fact與實際run對應時，真實邏輯資料數／渲染實例數維持UNKNOWN。

欄位觀察保留來源文字run／glyph cluster／baseline／pt／實測advance／字寬縮放／tracking／分散等有型別欄位，但首版只在有來源時填入。現有Slot預設font／size_pt／align／tracking及衍生SVG宣告不自動升成原稿真值；目前無原生AI字型／glyph證據的值皆UNKNOWN。標記框與其正規化錨點可記為ANNOTATED／DERIVED，不能冒稱原設計可用容器或已學風格。

## 儲存、整合與失效

重用`training_records(kind='DESIGN_OBSERVATION',id=work_id)`、training_history及既有交易。新版更新採CAS；相同輸入重做不增加修訂。完整範圍簽章包括pins、facts、noise dependencies、source cache hashes及extractor version，不用全庫epoch使無關作品失效。

提供計畫、保存、查詢狀態與交易內refresh API；既有自動作品分析保存觀察與AUTO_UNIT引用於同一交易。保留原有明確GEOMETRY_TRAINING_LOCAL的相容路徑，但不將其逐件幾何草稿當成跨作品學習；本層不新增逐作品模板。

作品／來源／事實／雜訊或cache依賴改變時，舊觀察標STALE；新分析重建並保留歷史。來源實檔與快取需核對，不能只相信資料庫中舊hash。版本衝突、事件寫入失敗或超過資源預算需回滾；既有逐作品隔離與取消流程保留。原AI、舊模板及舊FACTS不做遷移重寫，舊工作可按需建立新觀察。

## 本輪驗證與未宣告部分

針對未知字級、均勻／非均勻仿射、座標框、多尺寸與多人隔離、共享公司關聯、確定性ID、CAS／重開／失效／交易回滾、既有自動流程引用與取消重用測試。只用合成／去識別來源；不以此宣稱原生AI全面恢復、真實glyph抽取、完整lineage泛化或已訓練模型。

處理預算與1MiB metadata上限是工程限制，不是學到的欄位／人物容量。缺少來源或超出預算明示原因，不靜默截斷。本輪不做網頁／手機或新的標記UI。


## 2026-10-19 original source and lineage slice

Extractor version design-observation-2-original-text adds original_text_evidence: hash-verified original SVG declarations/physical similarity transforms or pinned pypdf5.9.0 PDF-compatible AI text-state/font-program evidence. Page scope is explicit: no automatic work/field/person assignment; exact glyphs, original font-asset identity and unsupported native data remain UNKNOWN. PDF visitor matrices are context, never exact glyph baselines; SVG declared anchors are not glyph ink origins. The source-page evidence digest participates in observation signatures. Existing QualityGroups projections also pin known cross-file correlation and invalidate stale plans without merging identities. Unsupported/budget-limited inputs retain explicit states with no pretend-complete truncated runs. Targeted59 checks pass; real corpus/full AI01 qualification and full current-source regression remain pending.
