# Template AI｜矩形區域自動排版與模板 AI

## Human／AI 從這裡開始

開發或恢復先讀 [AGENTS.md](AGENTS.md) → [開發狀態](docs/dev/STATE.json) → [交接](docs/dev/HANDOFF.md) → [要求與功能清單](docs/dev/FEATURES.md)／[機器登錄](docs/dev/REQUIREMENTS.json) → [工作紀錄](docs/dev/WORK_LOG.md)。[checkpoint 流程](docs/dev/DEVELOPMENT_PROTOCOL.md)與[證據設計／成熟來源](docs/dev/EVIDENCE_DESIGN.md)供 Human 和 GPT 共用。不要只讀歷史第一版狀態。每輪開發的計數見 [進度統計](docs/dev/PROGRESS.md)，前後差異見 docs/dev/progress/。

**開發以零例行問答、checkpoint 與 GitHub 持久化為核心。EXE 已延後，不再自動打包或重試；先完成清單要求及其證據。**

**v0.1.26：新增程式內問題報告、安全HTML／JSON離線保存與歷史重開／版本定位。** 詳見[報告操作指南](docs/dev/DIAGNOSTIC_REPORTS_USER_GUIDE.md)。產品不自動外傳，正式驗收以STATE為準。

**v0.1.25：擴充客戶建檔／搜尋與逐欄回寫、加密資料庫部分備份、尺寸Logo只讀管理、當次排版單worker控制、候選局部修改、多作品安全批次、來源重掃、分類評估／隔離修復與重大規則重審。** 操作與每項未做範圍見 [使用指南](docs/dev/SEVENTY_USER_GUIDE.md)，最新驗收與父需求數量以 STATE／PROGRESS 為準。這些是明列範圍實作，仍不是全部父需求完整完成。幾何學習不是完整自動辨識或深度模型；分類評估不冒稱模型推論／獨立品質PASS；完整個資權限、指定設備及印刷仍待後續。

## 開啟與快速試用

目前採原始碼啟動；EXE 打包與 Windows 成品驗收延後。最新來源綁定驗收見 [STATE](docs/dev/STATE.json) 與 [進度](docs/dev/PROGRESS.md)，證明媒體保存例外見 [本輪清單](docs/dev/SEVENTY_PARENTS_PUBLICATION.json)；程式／測試／文字證據完整保存，原附件及hash清單保留。

原始碼：安裝 Python 3.11 後，Windows 雙擊 `START_WINDOWS.bat`；或安裝 `requirements-lock.txt`，執行 `python app.py`。

最快路徑：「模板與 Logo」加入合成示範 → 驗證並發布 →「排版與輸出」填入匿名示範 → 開始排版 → 輸出 PDF／PNG／JPG。

## 核心功能

- AI／PDF／SVG／PNG／JPG 只讀匯入，Inkscape 解套與 Qt PDF／SVG 備援；內容快取和獨立檔名登錄。
- 框選矩形作品、毫米標定、欄位／完整 Logo 標記、視覺核對與人工確認。
- 多作品獨立保存、歷史恢復、重開返回上次來源／作品；過期標記不能覆蓋新版本。
- 標記形成有來源的規則模板；草稿、發布與新版本，正式版本唯讀。
- 固定字級與實際字型量測、受限字寬適配、人物公司歸屬及同尺寸 Logo。
- 合法本機字型複本持久保存、啟動時核對及載入；不安裝系統、不隨交付包重發字型。
- 同尺寸乾淨固定背景、來源／實際呈現並排核對、向量或圖像呈現、內容雜湊與失聯保護；可指定欄位文字色彩。
- 同尺寸同容量候選、完整映射、無解／缺 Logo 阻擋與過期判定。
- PDF／PNG／JPG、獨立 PREVIEW、安全排他寫檔。

## 文件與驗證

- [操作說明與限制](docs/FIRST_VERSION.md)、[實際狀態](docs/FIRST_VERSION_STATUS.md)、[第三方選型](docs/THIRD_PARTY.md)
- [本輪開發授權](docs/decisions/2026-10-12-FIRST-VERSION-AUTHORIZATION.md)
- [24 小時開發授權與本輪進展](docs/decisions/2026-10-13-CONTINUED-DEVELOPMENT.md)
- [功能清點與建議計畫](docs/DEVELOPMENT_PLAN.md)、[需求基準](docs/REQUIREMENTS_BASELINE.md)
- [較新定案](docs/decisions/2026-10-12-RECTANGULAR-LAYOUT-VISUAL-IMPORT.md)、[續行規範](docs/CONTINUATION.md)

```bash
python -m unittest discover -s tests -v
python tools/validate_first_version.py
```

驗證產生實際測試、真實 Qt 畫面、合成 PDF／PNG／JPG 與檔案雜湊。真實私人 Illustrator 樣本、16 GB＋RTX 5050／VivoBook 效能及實體印刷仍需指定樣本與設備實測。

請以合成／合法去識別資料測試，原稿、商用字型、Logo 或個資不自動送到 GitHub。所有定案與實際成果持久化到 GitHub，研究候選／已實作／已驗證各自標示。

## 字型替代候選唯讀流程

所有模式選單「共用字型管理中心」→「替代候選排名與唯讀預覽」。輸入完整單行文字、固定pt、框寬與最小水平比例，查詢後明確選取候選，再重新核驗預覽；可勾選比較中心原先選定字面的自然字寬。來源身份、覆蓋率、mm字寬、水平比例、比較差異、排名及排除理由均可查；原稿未知保留未知。每輪最多64字面／64 MiB資產大小、10個展示候選，超額提示部分搜尋。預覽不套用模板或安装系統字型，受控草稿另從明確審核流程進入；完整父題仍見功能清單。

## 受控字型替代與歷史

從核准本機候選進入「模板影響／草稿替代審核」，只將臨時驗證文字填入明確選取的一欄，再背景量測差異。高風險逐欄查看實際字形預覽並核准後，主動勾選、確認範圍，才建立新版本草稿。原草稿／發布版本保留，其他欄位、字級、尺寸與Logo不改。全批交易／CAS與持久歷史可從共用選單「字型替代審核歷史」Undo／Redo；後續編輯／發布會阻擋覆蓋。核准是草稿操作，仍須實際人物資料、版面與正式輸出驗證，不表示原稿外觀相同或字型嵌入授權。

## 原稿與前後矩形同步對照

逐欄詳審進入三視圖：原稿衍生參考、原模板已知文字、僅本欄替代的完整矩形。共用縮放／平移，列表或框選同一stable ID同步高亮與定位；可符合全頁／矩形／所選框。精確來源歷史版次與crop可逆映射；未物理標定圖片標參考單位，來源失聯及原字型未驗證保留未知。對照不寫模板／字型／DB；返回後明確核准仍須背景再驗與套用前驗證，檔案／來源context／template clock異動阻擋。

完整長期目標與全部75父題路線見 [PROJECT_GOAL](docs/dev/PROJECT_GOAL.md)／[PROJECT_ROADMAP](docs/dev/PROJECT_ROADMAP.md)。本輪三視圖與定位附件見RUN-CANVAS-COMPARE-002；SELF_VERIFIED合成測試不代表真實AI视觉／Windows／指定硬體或獨立品質。

## 安全多選與精確對齊

訓練標記／模板工作台「安全多選／精確對齊」進入同一進階編輯器。畫布Ctrl複選／框選、清單複選與面板共享stable ID集合；mixed值不複製第一件，僅明確dirty欄位產生候選。原藍框／新綠框及old/new mm差異先核對，再原子保存；沒有新差異不建空歷史。明確基準可六向對齊、兩軸等邊界間距、group delta；保留固定pt、pin／style、未選物件及Logo比例，locked或未核對跨owner範圍整組拒絕。

Lock／Unlock是獨立明確候選與核准；舊編輯、保存、發布與字型替代同受lock保護。持久歷史重開可UndoRedo，hash／clock擋ABA與後續編輯，晚期audit失敗全rollback；source幾何變更取消原visual確認。主窗口手工未保存／未套用時不丟棄或覆蓋。所有警告仍涵蓋全slot，來源文字與字距未知、未提供人物文字的readability須另排版核驗。正式證據見RUN-OBJECT-TOOLS-001，全部父題完成進度仍看PROGRESS。

## 語意搜尋、批次匯入與例外處理

「安全多選／精確對齊」的語意樹／清單／畫布共用同一stable ID。搜尋與暫時隱藏／淡化／隔離保留真實選取範圍，locked仍阻擋整組移動，完整輸出Gate不減少物件。來源結構是驗證快取的唯讀衍生SVG；原生Illustrator圖層與未知映射不猜測。

訓練工作台「批次匯入／取消與續跑」選多檔／資料夾及頁次，先只讀預檢与SHA＋頁去重，確認精確範圍後開始單worker匯入。合作取消保存目前項後停止；重開可明確續跑未開始項，不重做SUCCESS。結果與audit同交易，原檔只讀；作品／模板近似仍UNKNOWN。

「來源匯入例外中心」查看已保存失敗／中斷／排除項，搜尋與可解释固定排序、追溯exact來源／作品／模板影響及明確定位。選取失敗項重新預檢、核對新舊hash再重試；排除需要理由，排除項可以恢復待辦。這些操作不自動核准可信樣本或規則訓練，資料版本過期／背景故障保留歷史與恢復操作。
