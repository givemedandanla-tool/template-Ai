# 本輪：桌面 GUI 與離線回報開發中

契約：GUI_OFFLINE_DELIVERY_CONTRACT_20261020.md；CORE-090。使用者已明確授權專項agent協作及持續完成。四類外部條件/延後項暫擱；網頁/手機/EXE未加入。

基底33d24c2，原1798測試ID必須保留；來源變更後原165 scoped完成轉待重驗，不能拿舊PASS驗證新GUI。既有AI8包50條真實資格不變。

root整合desktop_workspace；offline_diagnostics負責離線診斷與app.py；guided_operations負責引導/家族面板；gui_tooling_research負責更多skills/agent規格與bootstrap。共享檔界線在開發紀錄，統一root commit/push。下一步完成實作、目標測試、原生GUI與完整回歸，逐checkpoint遠端讀回。

WIP1：新desktop_workspace已接正式MainWindow；三工作區導航/固定footer/嵌入真DesignSession畫布與進階選項/白話狀態。學習頁也重組，舊工具仍可由更多入口使用。離線日誌/安全ZIP/guard、進階引導、3新skill與5agent角色已實作；目標測試通過不當完整回歸。後續須新製作路徑具名測試及來源凍結全回歸，舊1798全部保留。

來源準備WIP2：本輪新增51具名測試，原1798保留，合計1849待完整回歸。新桌面11案例來源圍欄擷取中；四類暫擱不影響GUI核心。WIP1的base metadata輸入錯誤已保留並棄用，不ack；實際WIP來源e95eb68逐檔Git讀回。後續checkpoint直接用git rev-parse HEAD取得基底。
