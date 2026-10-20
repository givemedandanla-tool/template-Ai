# 內部輸入與學習排版接口清單

白話摘要：目前製作資料由內部人員填寫。既有表格、人物卡片、客戶資料與圖片選擇都要傳入同一份製作資料，再產生可拖動的稿件。學習模型不會改寫已確認稿；固定舊版、新家族及已確認檔案各自有明確版本。獨立網頁／手機仍延後。

本輪契約：`INPUT_LEARNING_INTEGRATION_CONTRACT.json`／CORE-089。表中程式已接線，實際驗證狀態以本輪來源綁定run為準；早期1779PASS不是本輪證據。

| 入口 | 真正資料／版本來源 | 進入排版與預覽的路徑 | 必須保留與檢查 |
|---|---|---|---|
| 相容簡易表格 | MainWindow.people／companies | input_data → production_bridge.current_graph → InputGraph；已啟用學習時generate → attach → DesignSessions | 原有分號拆多筆行為保留；採用後stable ID，表格成唯讀摘要，不默默改寫欄位 |
| 人物卡片 | InputGraphDialog的當次複本 | 採用 → MainWindow.adopt_input_graph；稿件更正 → replace_input | 姓名、職稱、電話、Email、LINE、IG、地址，多筆相同字串仍是不同ID |
| 公司與共享聯絡 | InputGraph.people／companies／fields／links | compile保留source_entity_id、欄位ID與引用 → input_facts | 同人多公司、多人同公司、共享資料的真實owner與users；編輯共享影響須確認 |
| 客戶搜尋／預填 | CustomerStore的exact snapshot／style | customer_catalog.apply_reorder或CustomerDialog.prefill → adopt_input_graph | 主檔版本、前導零、人物欄位ID不重編；當次更正不自動回寫主檔 |
| 舊客戶確切款式 | reorder_template_id、已發布固定模板 | 原LayoutSession／原固定版型規則 | 明確沿用原款式版本；解除限定後才使用學習路徑，不能默默換版 |
| 圖片／Logo選擇 | LogoStore公司實體、尺寸及資產引用 | graph.companies.logo_id → resolve_logos → synthesize／原generate | 公司名稱不是身分證明；不同公司／尺寸不可互借；核准與權利檢查保留 |
| 尺寸設定 | MainWindow.out_w／out_h | attach固定成稿件width_mm／height_mm | 同尺寸續接，改尺寸建立另份稿件；稿件頁顯示固定尺寸，避免改顯示值卻仍輸出舊尺寸 |
| 自動排版 | active模型或固定舊款式、版本化policy | MainWindow.generate → 已啟用學習則同一DesignSessions；無模型保留原固定模板路徑 | 啟用記錄損壞／撤回時報原因，不偷偷降級；未知容量不當確定無解 |
| 預覽／拖動調整 | DESIGN_SESSION／DESIGN_RESULT | 共用稿件頁RelativeCanvas；publish_preview回主視窗 | 真實拖動形成左右上下意圖；保護owner與未受影響拓撲；字級字寬由核心規則控制 |
| 局部更正與返回 | replace_input僅更新data_revision | 真實InputGraphDialog → 保留位置意圖 → 結果stale → 重算 | 不能拿舊確認輸出新資料；超過2048保存預算時保留輸入框原文、阻止採用並說明 |
| 位置復原／重做 | intents／layout_undo／layout_redo | DesignSessions版本交易 → 同一求解器 | 只恢復位置要求，不把新電話退回舊值；新位置操作清除redo分支 |
| 進度／停止／接續 | 持久稿件版本、owned DraftSolveWorker | family／configuration邊界取消，交易前再核對revision | 單一背景工作、可停止；晚到結果不能覆蓋新資料；關閉先停止worker，重開稿件可重新求解 |
| 候選切換 | 結果中實際算得choices／attempts | 明確選擇 → 新result版本 → 舊確認失效 | 顯示實際方案，不虛構候選；跨家族需檢視採用，不能把切換當正式發布 |
| 輸入／容量建議 | 已啟用／稿件固定模型；DESIGN_CAPACITY | input_advice；實際稿件joint_demand → capacity_advice | 使用同一聯合需求量測；無足夠驗證明示未知；工程預算不冒充學習上限 |
| 確認／輸出 | DESIGN_SESSION.confirmation與exact result | 稿件按鈕及舊MainWindow.export_current都轉到同份DesignSessions.export | 精確資料／模型／政策／字型圖片依賴，格式與正式資格仍重新驗證 |
| 已確認稿／重訂 | DESIGN_OUTPUT_DEFAULT → DESIGN_ACCEPTED_ARTIFACT | attach先查有效確認稿，優先其原session；找回exact bytes | 新模型不迫使重排；原session已修改時提供唯讀確認檔案，不冒充新版已確認；新ID不靠相同字串猜同客戶 |
| 錯誤與報告 | 固定白話摘要與原始專業詳情 | production_report；既有安全ZIP的report_html | 白話說明目前情況、影響與下一步；原數值／代碼與安全allowlist不移除，不把摘要變成核准 |

驗證包含真實Qt模態視窗、剪貼簿貼上、滑鼠拖動、舊表格按鈕、回主視窗預覽與實際預覽檔。檔案儲存對話框可指定匿名測試路徑，輸入視窗及拖動不得以假物件替代。

專業家族編輯、來源標記與模型管理保留各自工作區。簡潔／現代共同製作面板的視覺重整與工具研究在本輪接線回歸後進行；本清單不宣稱已交付新網站、手機或私人作品生產資格。
