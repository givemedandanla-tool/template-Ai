# 目前：第五輪 Windows 首版發布流程

run40017431358，精確source b9b3160563bdc3e92df4d32a76cbb0fc9a1c5e9e。新工具8個模組已於前輪Windows通過（103項含1個選配OCRskip）；舊GUI轉檔測試已修測試helper/安全cleanup，74原assert AST不變、12/12真Qt本機PASS、13s延遲正例及原12s負例皆有界完成。所有產品程式未因測試修正更動，外層240s仍保留。

下一步等此精確source的全部Windows模組→clean build→真正EXE/worker/包內Inkscape/保存重開→package→新tag草稿與公開兩次實際下載校驗。尚未發布，不能稱EXE已驗。若FAIL讀review-release-evidence/v0.1.0-beta.1各run小型JSON/log，按實際根因修正，不覆寫既有tag。來源checkpoint精確讀回見STATE.review_tool_release_request.source_checkpoint。

私人作品/字型/DB留本地，舊未提交timeout/adopt成果保留；不合併main、不提升舊完整產品及真實作品/訓練資格。首版OCR執行器選配；本元件是判讀/人工核對，不是AI訓練/模板生成。

---

# 當前：Windows首版驗證受阻，尚未發布

目前request source446e571648df28727faa6e00d2f27e1113281275、run40015130560進行。run40014149436自然FAIL，沒有build/tag/Release：舊bundled測試長短路徑字面比較（已改samefile，hash拒絕不變）；test_import_exceptions舊GUI首例FAIL後cleanup modal，240秒測試程序逾時。保留真實失敗於releases/review-v0.1.0-beta.1/windows-failure-40014149436。

已補即時原trace與timeout ERROR分類／自有程序樹清理／後續獨立模組繼續，整體仍FAIL禁止發布。17項診斷工具測試通過；不能當Windows元件PASS。之前來源e5844ef7本機169項PASS，現source需Windows獨立驗證，不能沿用舊source資格。

下一步讀取run40015130560完整aggregate與即時trace，按真原因最小修正；全source gate通過後真正Windows EXE／兩次GitHub下載校驗才交付。私人作品／字型仍本地，未新增付費API或服務。舊未提交timeout/adopt工作保留、舊產品主checkpoint/資格不變。

---

# 目前階段：獨立核對工具首版 Windows 發布

元件實作已提交，Linux相關核心＋真Qt共166項獨立模組測試通過，0失敗／0錯誤／0skip；詳見releases/review-v0.1.0-beta.1/LOCAL_VALIDATION.md。版本review-v0.1.0-beta.1，入口review_app.py，EXE TemplateAIReview.exe。下一步是精確request分支Windows CI、真正EXE操作與兩次GitHub下載校驗，未完成前不能稱已發布。

數據／原稿／人修分層，unknown不猜，More可明確追加重新判讀新找到的同頁作品；新頁續跑保留既有人修。首版OCR執行器仍選配但模型隨包；學習／模板產出不是本元件範圍。既有未提交timeout/adopt/full-run成果保留。舊全產品governance來源證據過期未升級，元件採獨立release policy。

---

# 當前工作：最小作品判讀核對工具首版

2026-10-23使用者已授權製作第一版並發布到GitHub，取代下列歷史僅討論限制。讀STATE.review_tool_release_request、analysis_review_ui/FIRST_RELEASE_PLAN.md。獨立分支feature/review-tool-v0.1.0，根入口review_app.py，模組template_ai/review_tool，版本review-v0.1.0-beta.1；新資料目錄隔離，不改舊版或main。當前實作／驗收／發布仍進行中，尚未交付EXE。

B工作台＋C引導、肉眼資訊／歸屬常用、數據總覽雙向定位、原稿及人修保護、未知留缺失都有效。模型學習／模板產出不在首版範圍。發布須真Windows EXE、明確source／manifest與下載校驗。原未提交timeout/adopt/full-run成果與產品主checkpoint保持原狀。

---

# 當前精簡交接：最小作品判讀核對工具

## 當前指令與範圍

2026-10-23使用者要求把本次結論保存GitHub，再開始討論「實機UI」（取代前一則「實機AI」）。目前是設計討論，不是實作、訓練或新EXE發布授權。倉庫dev/v0.1-first-version／PR2；不合併main、不覆寫既有Release。

## 必讀

1. [UI設計基準](analysis_review_ui/DESIGN.md)：B原稿中心＋C引導，已確認原則／待定細節。
2. [按鈕與狀態草案](analysis_review_ui/BUTTONS_AND_STATES.md)：尚需實機逐畫面核對。
3. [觀察資料與能力契約](analysis_review_ui/OBSERVATION_CONTRACT.md)：完整記錄供後續AI學習，不冒稱現有資料已全部取得。
4. [決策](../decisions/2026-10-23-ANALYSIS-REVIEW-UI-FIRST.md)、STATE.analysis_review_redesign與獨立文件checkpoint收據。

文件快照已REMOTE_VERIFIED：`3fdadb20`，15件（14個設計／交接／參考檔＋checkpoint本身）；[讀回收據](../checkpoints/CP-20261023-ANALYSIS-REVIEW-UI-DESIGN-001.receipt.json)。這是文件輔助範圍，產品主收據與資格不變。

## 已確認

- 日常面板僅肉眼可見資訊、範圍／群組及人物公司共享等歸屬；底層數字照存但隱藏。
- 單一「查看全部判讀資料」入口，保留中央原稿；點數據定位原稿，點原稿同步數據。尺寸／間距／切齊／基線／分散／群組／歸屬有相應視覺化。
- 框、墨跡、容器分開；推估及未知明示；看數據不改原稿。重要隱藏缺失仍用白話提醒。
- 原判讀／人工修正、作品事實／家族規則／稿件／模型分層。保存≠核對≠訓練／模板可用。
- 私人作品、字型、DB、標記及模型留本地。GitHub只保存規格、程式與合成／安全證據。

## 下一步

先討論首次開啟／接續畫面、視窗與縮放、同檔多作品清單，再逐一核對判讀中／失敗、核對、總覽及保存重開。使用者尚未選定這些細節；不重問B+C或資料分層等已決事項。核准畫面以實際UI來源產生，概念生成圖不是實機規格。

## 保留問題與原工作

現行公開EXE仍v0.2.0-beta.2。Inkscape隨包，OCR仍選配；observation關係與typography仍有UNKNOWN；啟動可見狀態及首檔安全逾時缺口未修妥。沒有新產品／Windows／私人作品／學習品質資格，原完成數與外部條款不變。

STATE先前的runtime_timeout_feedback、adopt_source.py與RUN-IMPORT-ZERO-FIELDS-001工作保留，不把新設計收據當產品主checkpoint或自動採用舊背景run。先前交接原文已存[歷史](history/ACTIVE_HANDOFF_BEFORE_ANALYSIS_REVIEW_UI_20261023.md)。
