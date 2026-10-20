# GUI 專項覆核紀錄（開發中）

本輪實際使用 offline_diagnostics、guided_operations、gui_tooling_research 及 gui_review 專項 agent；角色可由 gui_tooling/agent_task.py 重建。這是同團隊自我覆核，不是外部獨立驗收。

## 已找到並修正

- 重組選單時 QMenuBar.clear 刪除原 QAction，實際啟動失敗；改逐一保留並移除，再分組重用。
- 小視窗主要動作被外層捲動區裁切；固定 footer。960×640 自建視窗實測 canvas 484×261，primary 150×38 完整可見。
- 學習排版期間 MainWindow.busy 使停止按鈕失效；自有 worker 執行時維持停止可用，實測取消完成後 busy 回復。
- 同一 session 外部更新／接續其他稿件時，嵌入畫面可能過期；核對資料／尺寸／身份、刷新 revision，未匹配時回到主預覽。
- 嵌入製作原先未公開其他候選／採用變更／正式資格／已保存檔，補更多稿件選項及必要採用主動作。
- 已捕捉錯誤不會進 uncaught hook；主錯誤、學習與引導入口接安全分類，原文不進日誌。
- 本地 SVG 可引用藏有遠端內容的巢狀資源；統一前置檢查及測試由離線子項補齊。
- START_WINDOWS.bat 每次啟動安裝依賴會連網；拆分明確的首次準備與離線啟動。

## 目標驗證與限制

review agent 已用真實合成模型完成輸入圖→求解→可拖框→主動作確認→持久確認→進階選項→背景取消。這是開發過程目標 smoke，完整來源凍結回歸與原生證據仍待進行；不得拿先前來源／單張截圖宣稱完整交付。

暫存圖 /tmp/gui-review-960-fixed.png、gui-review-learned.png 僅供開發檢查；正式交付另保存永久來源與 hash。新手真人訪測、Windows／私人作品／指定硬體／印前不在本輪自我驗證資格。
