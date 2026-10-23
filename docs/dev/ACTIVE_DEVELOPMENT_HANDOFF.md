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
