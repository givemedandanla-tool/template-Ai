# 雲端 GUI 開發環境設定收據與重建說明

設定草稿 revision 6 已保存，**仍需平台發布**；這不代表已重建或套用到其他環境。目前環境已用實際 MainWindow、原生 xcb、QTest 驗證工具接線。

專案固定至 `6ce180c53e2f36f87f8ae185c43993c5f54fea29`（已含最終驗收與checkpoint收據）；其程式碼與已驗證的 `4ebfff6f` 相同，後續提交只有metadata。GUI工具依賴 checkout 明確排除環境專案成員；Git發現清單見 qa/plans/GUI-CLOUD-CHECKOUT-DISCOVERY-FINAL.json。既有網路政策、秘密與runtime requirements保持不變，不保存秘密值。

## 首次安裝腳本

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /workspace/template-Ai
bash tools/cloud_setup.sh
.venv/bin/python docs/dev/gui_tooling/bootstrap_gui.py --with-x11
QT_QPA_PLATFORM=offscreen .venv/bin/python docs/dev/gui_tooling/preview.py --capture /tmp/template-ai-gui-setup-smoke
gui_setup_capture_dir="$(mktemp -d /tmp/template-ai-native-setup.XXXXXX)"
.venv/bin/python docs/dev/gui_tooling/capture_owned_workspace.py --native --output "$gui_setup_capture_dir/owned"
```

加入的是自有視窗原生smoke；Qt Designer .ui預覽仍是概念工具，不能代替正式排版證據。使用新/tmp目錄，不讀私人作品。

## 新對話啟動指示

```text
在 /workspace/template-Ai 工作，先依序讀 AGENTS.md、docs/dev/STATE.json、docs/dev/ACTIVE_DEVELOPMENT_HANDOFF.md，再跑 .venv/bin/python tools/resume_status.py。保留未提交變更及 dev/v0.1-first-version／PR2，不重設分支、不自動合併 main。按需搜尋路徑與關鍵字、分段讀取，一般工具輸出不超過1600 tokens；不用整串聊天或大型日誌接續。

正式桌面工作台在 template_ai/desktop_workspace.py，重用 MainWindow／輸入圖／DesignSessions／家族及原模板核心；Qt Designer 的 production-workspace.ui 仍是概念工具，不能當正式排版。以 STATE 最新證據及程式來源hash判斷完成範圍；整體run FAIL若僅舊外部資格，不可誤稱已自驗軟體功能未開發。沒有新source、失敗或未決風險時，不重跑完整回歸。

GUI任務先讀 docs/dev/gui_tooling/SKILL.md，按需讀其 skills/desktop-visual-review/SKILL.md、skills/qt-interaction-review/SKILL.md、skills/gui-code-review/SKILL.md；可重用固定MIT版 UI/UX Pro Max、Qt Designer、QTest及隔離Xvfb/xdotool。執行 .venv/bin/python docs/dev/gui_tooling/bootstrap_gui.py --with-x11 可重建4個專案skill入口及簽章核對工具；agent_task.py --list 可看5個專項角色。只有使用者或適用指令明確授權才啟動agent。實際視窗驗證可用 capture_owned_workspace.py --native --output 新目錄；不放寬鍵盤或舊回歸斷言。不要為桌面引入React／另一個輸入或排版核心，也不使用付費設計服務。

日常使用完全本地，私人作品、字型、模型、客戶原文與資料庫不傳GitHub或外部AI。參照 docs/dev/DESKTOP_WORKSPACE_USER_GUIDE_20261020.md、docs/dev/LOCAL_DESKTOP_QUICK_START.md及docs/dev/OFFLINE_SUPPORT_USER_GUIDE_20261020.md：首次依賴準備與離線啟動分開；使用者從「問題與報告」手動匯出安全ZIP，再在Codex提供。沒有自動上傳或遙測。來源、字型、容量、資格的UNKNOWN不能冒充PASS；相對位置可調，印刷字級／字寬／欄位大小／切齊／分散依核心規則，不恢復客戶細參數控制。

真實作品學習品質、分析邊界、Windows／指定硬體與原先延後功能維持使用者暫擱，等本地回饋，不反覆索取私人作品。網頁／手機／EXE延後。本輪GUI完成不改寫原AI8包50條完整真實資格。里程碑更新精簡交接、建立checkpoint並保存既有GitHub分支，再用新Git fetch及逐檔blob讀回確認。保留平台HTTPS proxy／CA、既有網路政策、秘密及runtime requirement設定，不擴充無關網路或憑證。
```

3個新增skill／5個agent任務角色可由專案bootstrap重建；角色模板不是已獲永久平行授權。來源／LICENSE／hash在gui_tooling。正式GUI及離線回報已驗收；未宣稱Windows、私人作品、指定設備、印刷或真人新手資格。

保存草稿及GitHub收據不自動發布雲端設定，也不改動使用者本機資料。私人作品、字型及資料庫維持本地；下一輪由使用者自行提供安全離線報告。
