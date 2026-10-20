---
name: template-ai-desktop-visual-review
description: Review the real Template AI desktop GUI with owned-window screenshots and public visual-design guidance, without exposing private artwork.
---

# Template AI 桌面視覺審查

先讀根目錄 AGENTS.md、目前 STATE、GUI_PANEL_DESIGN_PLAN_20261020.md 與本輪契約。
本 skill 是 Codex 開發輔助；不加入軟體執行依賴、雲端 AI 或遙測。

1. 先確認實際介面工作：匯入與學習、模板整理、填資料看稿、確認輸出。
   沿用已核准的低門檻、完整稿件為主、單一明確主動作與專業工具按需展開。
2. 按需讀 ../../vendor/anthropic-frontend-design/SKILL.md。
   採用具體命名、先規劃再對照需求、自行截圖審查、錯誤提供下一步的做法。
   使用者已確認的操作原則優先；不重新詢問已知用途、不套網站 hero、品牌字體、
   動效或手機版需求。系統已安裝中文字型只供 GUI；不改印刷字級與字寬。
3. 擷取前讀 ../../vendor/openai-screenshot/SKILL.md。優先 Qt 自有視窗擷取；
   需要原生視窗證據時用官方 helper 的 --window-id，只擷取自行建立的測試視窗。
   禁止截整桌面、其他程式、私人作品或真實客戶資料。測試模式的1像素輸出不作證據。
4. 從倉庫根目錄執行：
   `.venv/bin/python docs/dev/gui_tooling/capture_owned_workspace.py --native --output /tmp/template-ai-owned-review`
   這會以隔離空白本地庫開啟正式 MainWindow，再逐頁擷取；不開既有使用者資料庫。
   X11 工具缺失時依 bootstrap_gui.py --with-x11 重建，保留簽章與 hash 驗證。
5. 使用 view_image 檢查實際圖片；評估主動作、字體可讀性、留白與層級、
   中文長字、窄視窗與焦點。截圖只能證明當次畫面；真人新手可用性另列未驗證。
6. 逐項回報「畫面位置、使用者遇到什麼、影響、具體改善、如何驗證」。
   產生可復原 checkpoint；不把研究或擷取成功當正式排版／Windows／印前合格。

上游來源、完整 LICENSE 與檔案 hash：../../EXTENSIONS.json。
