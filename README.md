# template-Ai｜矩形區域自動排版與模板 AI

狀態：**需求訪談已收斂（52 題）；技術研究初稿；尚未開始程式開發。**

## 目標
Windows GUI：從歷史 Adobe Illustrator .ai 等來源學習矩形區域內的排版規則，歸納可解釋、可審核、可重用模板，依輸入資訊與指定矩形尺寸完成排版、數位驗證及 PDF/PNG/JPG 輸出。Inkscape 等匯入方式以視覺一致且可訓練驗收；實體印刷分析留待軟體完善後。

## 較新定案
- [矩形抽象、Inkscape 視覺訓練、印刷後移、效能範圍及 GitHub 持久化](docs/decisions/2026-10-12-RECTANGULAR-LAYOUT-VISUAL-IMPORT.md)
- [功能清點與建議開發計畫](docs/DEVELOPMENT_PLAN.md)
- [功能追蹤表](docs/UI_FEATURE_INVENTORY.csv)

## 文件導覽
- [需求基準](docs/REQUIREMENTS_BASELINE.md)
- [技術研究初稿](docs/TECHNICAL_RESEARCH.md)
- [驗收與研究待辦](docs/VALIDATION_PLAN.md)
- [開發續行與決策規範](docs/CONTINUATION.md)

## 當前狀態與界線
- 52 題需求已結束，後續修訂需記錄差異，不自行增加訪談題數。
- **尚未證實** Illustrator 解析、字型量測、規則推導、未知尺寸生成與輸出品質可達到要求。
- 本倉庫文件是需求及研究基準，不是功能完成證據。
- 不將客戶真實個資、商用字型或未授權 AI 設計檔直接提交 GitHub。
- 不在缺乏實際測試時宣稱成功，不以模擬結果取代 Illustrator 實機驗證。
