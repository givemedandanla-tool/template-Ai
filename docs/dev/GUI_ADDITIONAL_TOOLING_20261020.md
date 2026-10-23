# GUI 重構的新增 skill 與專項 agent

本輪使用者已確認：先完成整體 GUI 與進階操作引導；分析邊界、真實作品學習品質、
Windows／效能及原延後項目暫置。Codex 可使用開發工具與專項 agent 協作，
本地成品仍完全離線，私人作品、字型、客戶資料與資料庫不提供到研究或工具查詢。
正式範圍與驗收以 [GUI_OFFLINE_DELIVERY_CONTRACT_20261020.md](GUI_OFFLINE_DELIVERY_CONTRACT_20261020.md) 為準。

## 已接入的能力

原 `template-ai-gui`、UI/UX Pro Max MIT 與 Qt Designer 保留。本輪新增以下專案適配 skill，
以 `.agents/skills/` 的相對 symlink 發現，完整內容保存在倉庫；新對話不依賴聊天歷史。

| 專案 skill | 用途 | 實際採用依據 |
| --- | --- | --- |
| `template-ai-desktop-visual-review` | 真實桌面視窗截圖、版面與白話用語審查 | OpenAI screenshot、Anthropic frontend-design 的適用原則 |
| `template-ai-qt-interaction-review` | Qt 鍵盤／焦點、表單回復、拖動替代與版本接線驗證 | 既有 PySide6/QTest，參照 pytest-qt 的真實 widget／事件操作方法 |
| `template-ai-gui-code-review` | 對照要求、來源版本與使用者工作做精簡只讀審查 | Superpowers 的 requesting-code-review／code-reviewer 模板 |

這些是專案適配層；上游原文與 LICENSE 保留，未直接改成一套網站工作流。
GUI 顯示字型與間距不修改印刷參數，已撤回的客戶字級、字寬、單雙排控制不恢復。

## 來源與採用界線

精確原檔 URL、SHA-256、檔案大小及複製位置見
[gui_tooling/EXTENSIONS.json](gui_tooling/EXTENSIONS.json)，共15件公開來源、85144 bytes。

| 來源 | 固定 commit | 授權 | 採用範圍 |
| --- | --- | --- | --- |
| `openai/skills` screenshot | `49f948faa9258a0c61caceaf225e179651397431` | Apache-2.0 | 原生截圖 helper、明確目標視窗與圖片審查；Linux/xcb 已執行，Windows／macOS 未執行 |
| `anthropics/skills` frontend-design | `dbd4588f9e1033efb41dad4bef2f7947c8993d44` | Apache-2.0 | 白話命名、具目的的層級、先規劃再截圖自評、空畫面及錯誤給下一步 |
| `obra/superpowers` requesting-code-review | `bb92a77741419a4ab5f06e711a283343f1ada0c3` | MIT | 明確來源／目標／版本、只讀角色、可重現且分嚴重度的問題報告 |
| `pytest-dev/pytest-qt` tutorial | `53457e0c802cd602d7045a6a11f3039f9fb8c699` | MIT | 只作方法參照，保留 unittest/QTest；未安裝 pytest-qt 或聲稱執行其上游測試 |

Anthropic webapp-testing 已實讀並排除：它以 Playwright 操作瀏覽器／伺服器，
不適合目前原生 PySide6。未安裝瀏覽器測試框架、網站套件或付費服務。
frontend-design 的網站 hero、品牌字型、手機與動效建議不覆蓋既有桌面需求。
Superpowers 的整套強制派代理、worktree 或 merge 流程沒有啟用。

來源查證時 GitHub API 受目前 HTTP 規則拒絕；使用已允許的 native HTTPS Git
`ls-remote` 取得 commit，再由允許的 raw.githubusercontent.com 取得固定版本原檔。
沒有改 allowlist、繞過 proxy、關閉 TLS 或新增 secret。

## 可重用的專項 agent 任務

`gui_tooling/agents/` 保存5個角色：視覺設計、Qt 接線整合、操作／鍵盤審查、
離線／隱私審查、GUI 程式審查。每個角色說明範圍、輸入、修改權及回報格式。

```bash
.venv/bin/python docs/dev/gui_tooling/agent_task.py --list
.venv/bin/python docs/dev/gui_tooling/agent_task.py --role interaction-reviewer --goal '核對正式工作區與資料版本一致'
```

產生的任務由主代理透過實際 collaboration 工具交付。這不是自動新增平台模型或
宣稱有另一種代理執行器；本輪實際 agent 的工作與測試須另外保存，不能以角色檔代替執行。
使用者本輪明確授權協作；其他任務仍先遵守當時的使用者／AGENTS 授權。

## 重建與工具驗證

```bash
.venv/bin/python docs/dev/gui_tooling/bootstrap_gui.py
.venv/bin/python -m unittest discover -s tests -p test_gui_tooling_extensions.py -v
.venv/bin/python docs/dev/gui_tooling/capture_owned_workspace.py --native --output /tmp/template-ai-owned-review
```

bootstrap 已實際重複執行：核對原74件、新15件來源 hash，重建共4個 skill 入口及列出5個角色。
新3項測試通過：竄改上游可執行 helper 被拒、manifest 不能指向工具目錄外、
重建可重跑且不覆寫使用者已有的 skill 內容。原生 X11 安裝仍走既有已驗簽／hash 鎖定流程。

原生工具初次驗證以暫存空白 Library 開啟真實 MainWindow，官方 screenshot helper
只擷取指定自有 winId；3頁均取得1280×860圖片，無1像素 test mode，圖片已實看。
這是工具啟用及基準畫面證據，不是新 GUI 已完成的證明。

目前 capture_owned_workspace.py 另驗證每頁一次實際 Tab 焦點移動、整個 template_ai
Python 來源擷取前後 hash 不變，輸出 owned-workspace-review.json。原生擷取須在來源凍結後
重跑，正式新版結果由本輪交付報告引用；修改中來源不會被工具冒稱為穩定通過。

## 保證範圍

- 工具只開隔離空白測試庫，未讀私人資料；原生 Xvfb 關閉 TCP，截圖限定明確自有視窗。
- 開發工具不加入成品依賴、不匯入 runtime、不替使用者自動截圖或上傳報告。
- 截圖／Qt 通過不等於真人新手可用性、完整無障礙、Windows 輸入法、真實模型品質或印前資格。
- 本輪 agent 是同一團隊專項工作；正式證據依既有 SELF_VERIFIED 範圍，不改成外部獨立認證。
