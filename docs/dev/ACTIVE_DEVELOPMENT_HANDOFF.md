# Template AI 當前接續點（完整005待驗）

本輪內部輸入整合CORE-089九條，1779原測試保留、新19、總1798／230模組。最新STATE與接口表為準。

完整004來源3634393已完成1798條：1797PASS／1FAIL，小視窗預覽外框可見高度未達原驗收；capture因測試未全過停止，不採用。詳細INPUT-FULL-004-SMALL-WINDOW-FAILED.log。實際重現：canvas兩側因內容寬而被裁，捲動定位把下框剛好放在viewport exclusive邊界，visibleRegion僅剩上框1px。改navigate_mode的外框定位邊距加2px，保留原尺寸標準，再加真正canvas viewport可見高度檢查。不是提高等待時間或移除舊驗收。

最新viewport／input／navigation局部38條PASS（INPUT-VIEWPORT-38-001.log）；現在建立CP-20261020-INPUT-VIEWPORT-SOURCE、原生Git讀回，啟動完整RUN-INPUT-INTEGRATION-ALL-005。原始001／002主動中斷、003metadata過大失敗保留，003不可變候選hash參照已在004本地端到端PASS。

GUI skill／Qt Designer／QUiLoader／Xvfb／xdotool接入及乾淨工具重建已PASS；GUI_PANEL_DESIGN_PLAN_20261020.md、GUI_TOOLING_READINESS_20261020.md與INTERNAL_DRAFT_INPUT_QUICK_GUIDE.md已整理。Concept不是正式新面板；原生QUiLoader可預覽、Designer快捷預覽未證實。既有相對位置選單保留，避免重複開發。

私人資料留本地；網頁／手機／EXE延後，不合併main。原AI8包50完整真實資格仍8部分／0完整。171登錄原164完成暫待完整重驗，未把局部當完整PASS。完成005後才執行/tmp/adopt_input_evidence.py、/tmp/finalize_input_gui_docs.py，驗證當前來源／完整附件，再保存最終GitHub checkpoint。
