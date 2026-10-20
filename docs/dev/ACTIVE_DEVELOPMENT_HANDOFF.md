# Template AI 目前接續點（完整006待驗）

本輪CORE089九條／原1779測試保留、新19、總1798／230模組。先完成舊輸入接新家族／規則、再接GUI設計工具；GUI skill／Qt Designer／QUiLoader／Xvfb／xdotool與商用開源研究已完成並GitHub持久化。網頁／手機／EXE延後、私人資料留本地、原AI8完整真實資格仍8部分／0完整。

完整001／002為補查中斷；003實際metadata超過1MiB，改不可變候選hash參照；004完成1798：1797PASS／小視窗1FAIL，改外框捲動inclusive/exclusive邊界並保留原驗收、補實際viewport高度。005在1403PASS／0FAIL主動中斷：原生截圖發現舊navigation頁首與輸入提示覆寫學習稿狀態。所有失敗／中斷保留，不採作完整PASS。

最新修正：read-only learning_input_status統一頁首／輸入狀態；排除固定模板slot-fit警告，但保留基本姓名／公司引用診斷。已啟用規則、未產稿時也正確引導；固定舊版／明確固定候選維持原路徑。報告在選用學習規則時接新稿件。新增同ID回歸斷言核對statusBar／timer之後仍為當前學習稿。相關38條PASS；最後基本診斷／主流程／固定舊版／小視窗6條PASS，且沒有關閉時的Qt回呼錯誤。

下一步：6條已通過→CP-20261020-INPUT-STATUS-SOURCE→原生Git讀回→完整RUN-INPUT-INTEGRATION-ALL-006。來源凍結後不要再改程式。1798全PASS、230健康模組、capture0、來源未變、附件hash正確才採用；整體仍可能因原5外部資格FAIL，但軟體PASS不可混真實印前資格。

原生Linux xcb舊UI補驗：前來源e4f44f8的5既有情境全PASS／6截圖，RUN-INPUT-INTEGRATION-NATIVE-002；001外層180秒不足保留，002在184.219秒成功。不增加測試數。原生截圖人工覆核才抓到本次頁首問題；最終來源凍結後再跑同5情境NATIVE-003，確保修正可見。操作指南INTERNAL_DRAFT_INPUT_QUICK_GUIDE.md；現代面板仍概念稿與未來重整方案，非正式新介面。

正式完成後使用/tmp/adopt_input_evidence.py與/tmp/finalize_input_gui_docs.py（需更新至006及最新NATIVE003），再跑governance render/check與progress snapshot，保存最終checkpoint。核心官方工具與契約／baseline均在GitHub，臨時helper僅目前環境便利工具。
