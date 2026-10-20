---
name: template-ai-qt-interaction-review
description: Verify Template AI's real PySide6 widgets, keyboard paths, form recovery and shared layout contracts using existing QTest and native windows.
---

# Template AI Qt 操作審查

先讀根目錄 AGENTS、目前契約、INPUT_LEARNING_INTERFACE_MAP 與相關測試。
已有 PySide6/QTest、Xvfb/xdotool；不為桌面程式加入 Playwright 或另一套輸入引擎。

1. 依任務追查真實按鈕至同一核心：填資料→產稿→拖動／位置選單→更正→確認→輸出。
   測試不能以替代 MainWindow／假 session 遮蔽接線；允許隔離檔案選擇等外部邊界。
2. 以實際 QTest 點擊和鍵盤事件驗證。等待 Qt 事件／明確完成狀態，設定有界逾時；
   保留 worker 的失敗與晚到結果，不能 sleep 後直接斷言成功。
   pytest-qt 的公開 tutorial 用於參照互動／等待原則；沿用本專案 unittest/QTest，未新增依賴。
3. 每個常用操作須有可理解文字、明確焦點與合理 Tab 順序；欄位有標籤，圖示有名稱。
   拖動保留可發現的相對位置選單／鍵盤替代，兩者走同一核心命令。
4. 驗證更正資料不被位置復原覆寫；取消不丟輸入；修改後舊確認失效；
   已確認稿固定版本；未知容量顯示待核對，不偽稱合法或無解。
5. 小視窗要量測實際可見 viewport。檢查長中文、空資料、缺字型／Logo、
   背景取消、重啟與狀態恢復。以來源／資料版本驗證，不能只檢查一個標籤。
6. 白話問題摘要包含發生什麼、影響什麼、下一步，技術詳情保留；
   禁止原文截短、錯誤消失或預覽與輸出不同稿。
7. QTest／Linux 通過不等於 Windows 輸入法、完整無障礙或真人新手驗收。
   依嚴重度回報可重現問題及未執行情境，不放寬舊斷言以取得 PASS。

本機工具：`python docs/dev/gui_tooling/agent_task.py --role interaction-reviewer --goal '核對實際工作區'`。
參考來源與 LICENSE：../../EXTENSIONS.json、../../research/pytest-qt/。
