# 內部輸入與學習排版接線驗證

白話摘要：既有表格、人物卡片及舊客戶資料可接續到新學習稿件；同份資料可產稿、拖動位置、更正、復原／重做、確認並輸出。圖片庫保留稿件尺寸，匯入與背景工作使用主視窗服務。超長貼上保留原文並明確阻止未確認採用，錯誤與安全報告提供白話摘要及專業詳情。

凍結來源 `bd1e9c5aff9d049d5b5d0bb339bf4bc5d135a2da`，完整 `RUN-INPUT-INTEGRATION-ALL-007`：1798／1798PASS、230健康模組、原1779測試ID保留、新19項唯一測試、原生capture exit0、384個附件hash核對、來源未變。CORE-089九條逐條PASS。這些是Linux／合成作品範圍的軟體自我驗證，不是私人Windows／原生AI完整還原／實體印刷資格；原AI8包50條完整真實資格仍8部分、0完整。

現有操作入口見INTERNAL_DRAFT_INPUT_QUICK_GUIDE.md。接口見INPUT_LEARNING_INTERFACE_MAP.md；逐條證據見INPUT_INTEGRATION_CLAUSE_AUDIT_20261020.json。固定舊款式與已確認稿保留版本，固定模板多尺寸批次仍屬原工作區；學習稿按實際尺寸核對，不混稱已接學習家族多尺寸批次。PNG／PDF／JPG格式保留；沒有宣稱新增原本未支援的SVG輸出。

完整001／002為補查接點與身份／畫面問題而主動中斷。003實際找到候選metadata過大：修為不可變候選內容加hash參照，保留1MiB單筆限制，選用時核對內容；異常不覆寫現稿。失敗與中斷紀錄保存在docs/qa/plans，未混作通過。005在1403PASS時因原生截圖發現舊頁首／輸入提示覆寫學習稿而中斷；改唯讀共用狀態，保留基本診斷且排除固定模板框位規則，關閉時late editing回呼亦有owner生命週期保護。006共1798測試全PASS，但擷取把QGraphicsView外框當內容而失敗；實際可見內容733×409。只修正擷取／測試量測為viewport，維持240×180門檻，應用程式未再改動。007完整重跑才採用；004原1798條中1條小視窗外框捲動定位未達驗收，已保留並修正顯示邊界，不放寬原測試。

另以原生Linux xcb視窗重跑5個既有情境全PASS（原生來源73c7722與本輪應用程式逐檔一致，僅導覽測試／擷取工具量測修正；見NATIVE_APPLICATION_SOURCE_EQUIVALENCE_20261020.json），保留6張真實介面截圖（RUN-INPUT-INTEGRATION-NATIVE-003）；這是同測例的補充平台證據，不增加1798唯一測試數。初次外層180秒不足的部分結果保留，600秒時限重跑成功完成（最終原生耗時見NATIVE-003紀錄），程式來源不變。

本輪也已接入專案GUI skill／UI/UX Pro Max、Qt Designer、原生QUiLoader與本地Xvfb／xdotool，乾淨工具重建通過。成熟設計系統／開源編輯器研究與共用簡潔面板方案見GUI_PANEL_DESIGN_PLAN_20261020.md、GUI_TOOLING_READINESS_20261020.md。概念稿與工具smoke不當正式產品面板重設計或新手訪測結果。網頁／手機／EXE維持延後。
