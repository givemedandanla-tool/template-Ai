# GUI 設計工具接入紀錄

本輪狀態更新：正式桌面工作台、進階操作引導及離線回報已完成CORE-090十條自我驗證；以[交付結果](GUI_OFFLINE_FINAL_REPORT_20261020.md)及STATE為準。下方保留開發前方案／工具準備紀錄。Designer .ui仍為概念工具，正式程式是desktop_workspace；Windows、私人作品、指定設備、印刷與真人新手資格維持未驗證。

白話摘要：Codex 現在可用本地設計 skill 查詢面板設計建議，用 Qt Designer 視覺編輯概念稿，再用原生 Qt 視窗檢查操作與截圖。已實際執行，並從空工具目錄重新下載、核對與驗證。這些工具協助改善設計；不是已經完成整套產品面板重設計。

## 已接入並驗證

| 工具 | 接入方式 | 已做驗證 |
| --- | --- | --- |
| template-ai-gui 專案 skill | AGENTS.md 明確入口；bootstrap 建立 `.agents/skills/template-ai-gui` 指向版本化文件 | 從根目錄可讀 SKILL；沒有覆蓋既有其他 skill；本地查詢成功 |
| UI/UX Pro Max | MIT 固定56ea9cf；74份原始文件／程式／CSV／LICENSE與逐檔SHA256保存 | 離線 BM25 UX／設計方向查詢；bootstrap全部hash核對 |
| Qt Designer6.8.3 | 專案既有 PySide6 工具；無新增GUI執行期套件 | 真實視窗／物件檢視器打開ProductionWorkspaceConcept，截圖已視覺核對 |
| Qt QUiLoader／QTest | 同一份`.ui`載入原生視窗 | 鍵盤輸入、點按更新、空姓名錯誤、原預覽保留、焦點返回、技術詳情展開 |
| Xvfb／xdotool | Debian簽章metadata核對來源，再固定SHA256，僅解壓至工作區獨立目錄 | 真實xcb視窗與輸入焦點；TCP關閉；測後僅終止自己啟動的程序 |

沒有新增 agent API／付費服務，也沒有為此導入 React、Tailwind、Web Components 或 GPL Qt Fluent 元件。現有截圖／QTest用於驗證設計，不能替代設計方法或真人可用性訪測。

## 指令

從倉庫根目錄：

```bash
.venv/bin/python docs/dev/gui_tooling/bootstrap_gui.py --with-x11
.venv/bin/pyside6-designer docs/dev/gui_tooling/production-workspace.ui
QT_QPA_PLATFORM=offscreen .venv/bin/python docs/dev/gui_tooling/preview.py --capture /tmp/template-ai-gui-preview
.venv/bin/python docs/dev/gui_tooling/verify_designer.py --output /tmp/template-ai-designer-smoke
```

實際乾淨重建還以 `--tool-root /workspace/template-ai-gui-tools-clean-restore` 完成下載與驗證，再以同參數啟動Designer及原生互動。bootstrap不修改全域套件、Python lockfile、資料庫或作品。固定原生套件只適用Debian13amd64；其他系統使用該系統的Qt Designer，不能強行解壓此組二進位。基礎Qt依賴沿用cloud_setup.sh。

預設查詢完全本地，不傳私人檔案。上游沒有Qt stack，專案適配skill提供正確路徑與桌面限制。平台雲端技能目錄未必即時更新；AGENTS與倉庫內canonical skill在新對話可直接讀取，不宣稱已安裝成雲端插件。

## 證據與失敗保留

`docs/evidence/runs/RUN-GUI-TOOLING-001/`保存原生截圖、工具smoke、已核對適用的查詢、hash清單與設定草稿回覆。這個目錄是工具驗證證據，不混入正式1798個測試數。

首次Designer smoke錯把MDI文件名稱當原生X視窗標題；第二次在無視窗管理器的Xvfb中未取得原生焦點。失敗log留docs/qa/plans/DESIGNER-001-FAILED.log與002，第三次使用僅本工具視窗的windowfocus成功。Designer的Ctrl+R送鍵已記錄，但未觀察到獨立預覽視窗，**不宣稱Designer快捷預覽已驗證成功**；可用預覽是已實測的QUiLoader原生視窗。編輯畫面可看到物件檢視器及表單，MDI空間較窄需捲動。

初始整體skill查詢落在通用網站Hero；一次重試匹配Productivity Tool／Flat Design。仍排除landing／網站字型／動畫，適用結果及專案取捨列入方案；首次未核對結果未作設計來源持久化。

## 雲端啟動持久化

安裝指令維持`bash tools/cloud_setup.sh`，接續本地GUI bootstrap與離屏概念稿smoke。start instructions指向AGENTS／STATE／交接及專案GUI skill。

後端已確認設定草稿saved且requires_publish=true，回覆見`CLOUD_GUI_CONFIG_DRAFT_RECEIPT_20261020.json`。**目前環境已完成驗證，設定草稿儲存成功；設定尚未因此套用或發布為新環境快照**。若需新實例自動使用，需在環境設定儲存並發布。倉庫仍保存完整重建指令，沒有因草稿待發布而停止其他工作。

補充：最終凍結來源73c7722的既有輸入介面也在原生Linux xcb／Xvfb上跑過同5情境，全PASS、6截圖；見RUN-INPUT-INTEGRATION-NATIVE-003，185.717秒測例／186.437秒啟動至完成。包含剪貼簿長文、真實滑鼠拖動、巢狀Logo視窗、主預覽與同稿輸出，以及statusBar／timer後的學習稿狀態。這是原5測例的補充平台證據，不增加唯一測試數，也不作Windows／印前資格。可重現腳本保存docs/qa/plans/INPUT-NATIVE-003-REPRODUCTION.py，執行前需改用新的輸出目錄以保留歷史。

最終設定另已後端確認：唯一專案template-Ai固定至`648ad72d43f06b9df106abaf699948f94c120869`，包含完整程式／正式證據／最終checkpoint收據與交接；原install/start草稿保留。完整倉庫探索沒有錯誤，上游UI/UX clone明列為工具依賴，根目錄空`.git`保護目錄不冒充倉庫。回覆及探索見CLOUD_GUI_REPOSITORY_DRAFT_RECEIPT_20261020.json與gui_tooling/CHECKOUT_DISCOVERY_20261020.json。後續僅文件提交保存這筆後端回覆，不改已驗證程式；草稿仍需環境設定儲存並發布才能啟用新快照，目前環境已可用。
