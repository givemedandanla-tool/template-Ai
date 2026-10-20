# Template AI 當前接續點（完整007待驗）

CORE089九條，原1779測試保留、新19、總1798／230模組；GUI skill／Qt Designer／QUiLoader／Xvfb／xdotool接入、原生舊UI5情境6截圖、成熟方案研究均完成。私人資料留本地、網頁／手機／EXE延後，原AI8完整真實資格仍8部分／0完整。171登錄原164完成暫待完整重驗。

最新應用程式來源73c7722已完整006測1798全PASS／230健康模組，NATIVE003同來源5情境全PASS／6截圖；但006capture失敗：舊導覽擷取量到QGraphicsView外框（0可見），實際viewport733×409符合240×180。已用不改行為的診斷重現，僅修正tools/capture_workbench_navigation.py及同名導覽測試，門檻／2秒等待不改；可見寬度也改量真實裁切區。應用程式／輸入測例／其他工具均未再修改。修正後capture全流程PASS、qt_errors=[]；導覽16條全PASS。失敗證據保留INPUT-FULL-006-CAPTURE-FAILED.log與INPUT-CAPTURE-VIEWPORT-DIAGNOSTIC.log，不把006當完整PASS。

下一步：16已通過→CP-20261020-INPUT-CAPTURE-SOURCE→fresh native Git讀回→RUN-INPUT-INTEGRATION-ALL-007（可4 module-workers；600秒各module；全部1798／230／capture0／附件hash／來源未變才採用）。應用程式凍結不再改；若只是舊擷取量測錯誤，先記錄真實區域再修工具，不能偽造視窗或放寬標準。保存NATIVE_APPLICATION_SOURCE_EQUIVALENCE_20261020.json，證明NATIVE003來源與最終source只差上述2個量測檔；Native003正確保留原SHA，不能改成新工具SHA。

歷史：001／002補查中斷；003metadata實際失敗→不可變候選hash參照；004小視窗1FAIL→外框定位+2及真viewport檢查；005在1403PASS因原生截圖發現舊頁首覆寫而中斷→統一唯讀狀態，基本資料診斷保留、不混固定模板slot-fit，晚到editingFinished避免已刪owner。006應用程式全PASS／capture量測失敗，沒有新app bug。

正式成功後：/tmp/adopt_input_evidence.py run007、/tmp/finalize_input_gui_docs.py（兩者已改007，需核對Native003實際SHA與equivalence）、governance render/check --require-evidence、progress snapshot，CP-20261020-INPUT-GUI-FINAL推送／逐檔Git讀回。已準備/tmp/discover_gui_projects.py；最終checkpoint後再次掃描，後端設定草稿可固定到final receipt HEAD（完整檢查1專案template-Ai；UI/UX上游為工具依賴；/workspace/.git為空保護目錄，不是倉庫）。更新雲端草稿只保存配置，不發佈快照；可將新設定回覆／pin以doc-only commit再讀回，不改已驗證程式。

面板方案GUI_PANEL_DESIGN_PLAN_20261020.md、工具GUI_TOOLING_READINESS_20261020.md、現有操作INTERNAL_DRAFT_INPUT_QUICK_GUIDE.md均已GitHub保存；概念稿不是正式新面板。實際新語意：輸入→學習稿→相對拖動／資料更正→同版確認／PNG/PDF/JPG；舊款式／已確認稿保留，固定模板多尺寸批次仍原模式。空間只刪有hash／REMOTE_VERIFIED／遠端祖先佐證的舊ZIP快取，最新3source保留，詳INPUT-FINAL-CACHE-SPACE-RECOVERY-20261020.json。
