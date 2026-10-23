---
name: template-ai-gui
description: Improve Template AI's PySide6 desktop workspace, visual hierarchy, beginner language, form feedback and accessible interaction using local UI/UX guidance and Qt Designer.
---

# Template AI GUI 設計與實作

先讀 AGENTS.md、STATE.json、ACTIVE_DEVELOPMENT_HANDOFF.md，再按需讀
INPUT_LEARNING_INTERFACE_MAP.md 與 GUI_PANEL_DESIGN_PLAN_20261020.md。
使用者／已核准規格優先。這是既有 PySide6 桌面程式，網頁與手機延後。

## 設計工作流程

1. 先盤點實際入口、狀態及可重用元件，避免新增第二套輸入核心。
2. 讀本目錄 vendor/ui-ux-pro-max/SKILL.md；使用其一般 UX／style 資料。
   本地指令（從倉庫根目錄）：
   `.venv/bin/python docs/dev/gui_tooling/vendor/ui-ux-pro-max/scripts/search.py 'error summary validation' --domain ux -n 3 --json`
   新整體方向可用 `'productivity tool workspace' --design-system -p 'Template AI' --json`。
   目前上游沒有 Qt stack；不得假稱有 Qt 產生器或採用 React/Tailwind 範例。
   網站首頁、Google Fonts、GSAP 與 CTA 轉換建議不適用本體。
   核對每個匹配；離題結果最多縮窄重試一次，仍不適用就明確棄用。
3. 原則：一個共用製作面板、清楚標籤、主預覽、依狀態的一個主動作、
   就近錯誤與可回復操作；專業設定按需展開。採用成熟設計系統的原則，
   不直接引入商用／GPL 元件或複製網頁程式。
4. GUI 顯示尺寸／字型只影響操作介面；不能套入印刷字級、字寬、欄位尺寸規則。
   不恢復已撤回的客戶字級／字寬／單雙排控制。
   拖動及替代點選／鍵盤操作都必須呼叫同一個相對位置意圖核心；不能自由改印刷幾何。
   固定款式／新學習稿／已確認稿分清版本；不得默默改稿。
5. 草圖：`.venv/bin/pyside6-designer docs/dev/gui_tooling/production-workspace.ui`。
   預覽：`QT_QPA_PLATFORM=offscreen .venv/bin/python docs/dev/gui_tooling/preview.py --capture /tmp/template-ai-gui-preview`。
   `.ui` 是工具驗證用概念稿，尚未接正式排版核心，不能當成功能交付。
   bootstrap_gui.py 可重建本地 skill 入口及簽章驗證的 Linux 視覺工具。
6. 實作後檢查真實視窗、鍵盤焦點、長中文、縮放與錯誤恢復，必要時用 QTest／Xvfb 截圖。
   Qt Designer 不能證明印前／Windows 資格；截圖不能代替新手可用性訪測。
7. 報錯／報告先提供「發生什麼、影響什麼、接下來怎麼做」，技術詳情另層保存。
   私人輸入、作品、字型、資料庫留本地；查詢僅用一般設計詞。
8. 依主倉庫 checkpoint／GitHub 讀回規則保存方案、修改與測試。
   不啟動付費服務、不安裝無關插件、不因技能存在就自動啟動平行代理。

## 新增專項工具與 agent

本輪使用者已授權以專項 agent 協作重構 GUI；這不成為其他任務的永久授權。
`bootstrap_gui.py` 同時核對 EXTENSIONS.json 的15件公開來源並重建以下專案 skill：

- [桌面視覺審查](skills/desktop-visual-review/SKILL.md)：適配 OpenAI screenshot 與
  Anthropic frontend-design；只擷取自建測試視窗，採用白話文案與截圖審查原則。
- [Qt 操作審查](skills/qt-interaction-review/SKILL.md)：真視窗、鍵盤、焦點與版本回復。
- [GUI 程式審查](skills/gui-code-review/SKILL.md)：適配 Superpowers 只讀審查模板，
  保留本專案的授權、單一 checkout 與 checkpoint 規則。

`python docs/dev/gui_tooling/agent_task.py --list` 列出可重用的5個專項任務規格，
由主代理交給實際 collaboration 工具使用；不改平台模型或虛稱安裝新的模型種類。
完整來源、採用／棄用及實際驗證見 GUI_ADDITIONAL_TOOLING_20261020.md。

## 來源與限制

UI/UX Pro Max MIT 固定版與原始檔 hash 見 UPSTREAM.json；保留 LICENSE。
本 skill 是專案適配層，不修改上游建議原文。`.agents/skills/template-ai-gui`
是可重建的本地發現入口；即使平台未更新技能清單，也可依 AGENTS.md 直接讀本檔。
