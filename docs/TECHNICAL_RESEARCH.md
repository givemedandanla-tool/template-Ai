# 技術研究初稿 v0.1（2026-10-12）

> **2026-10-12 較新定案優先**：產品統一為矩形區域自動排版與模板 AI；Inkscape 等解析路徑以「視覺無可辨識差異＋有效可訓練資料」驗收，不要求全部來源完整還原 Illustrator 私有結構；實體印刷分析移至軟體完善後；效能參考為 16 GB 系統 RAM＋NVIDIA RTX 5050 至 ASUS VivoBook（具體型號待補）。詳見 [本輪需求修訂](decisions/2026-10-12-RECTANGULAR-LAYOUT-VISUAL-IMPORT.md)。下文保留歷史決策，衝突部分以上述使用者較新修訂為準；實作／實測仍未執行。

**狀態：資料來源初步查證；非已完成的全面技術選型、實驗或授權審查。**

## 研究原則
成熟方案優先、研究後內化；保留來源 URL、版本、授權、限制、實測證據。不要無必要重造輪子。Writer 與獨立驗證角色分離；沒有測試證據不得宣稱 VERIFIED。

## 已查證的候選來源

| 項目 | 來源 | 已知事實 | 建議與未決問題 |
|---|---|---|---|
| Adobe Illustrator 桌面腳本 | https://helpx.adobe.com/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html | Adobe 官方文件說明 Illustrator 可透過 JavaScript/ExtendScript 等腳本自動化 | **研究候選**：在安裝 Illustrator 的 Windows 上提取物件與文字資訊；需驗證實際效果外框、圖層、字元縮放及多作品切分 |
| Illustrator Scripting Guide | https://github.com/docsforadobe/illustrator-scripting-guide | 社群維護的 Illustrator scripting guide，非 Adobe 官方支援承諾 | **參考**：建立原生物件屬性提取 PoC；需確認版本相容性 |
| pypdfium2 / PDFium | https://github.com/pypdfium2-team/pypdfium2 | Python PDFium bindings，專案標示 Apache-2.0 / BSD-3-Clause，PDFium BSD-style 且含第三方依賴 | **候選**：PDF 相容部分的渲染/檢視；不等同原生 AI 完整解析，需查實際打包授權與能力 |
| PyMuPDF | https://github.com/pymupdf/PyMuPDF 及 https://pymupdf.io/licensing | 提供 PDF 解析、渲染、操作能力；AGPL 與商業授權雙路線 | **評估但不預設採用**：若未確定開源/商業授權符合交付方式，不納入正式依賴 |

來源查閱日期：2026-10-12。上述**未鎖定版本、未進行安裝/實測**；選型前需固定 release/commit、授權檔、依賴清單與 Windows 測試結果。

## 建議研究方向（假設，不是決定）
1. **原生解析優先**：對照 Illustrator scripting 取得可編輯文字、效果、群組/圖層與物件幾何；PDF 相容內容與 OCR 僅作備援，不應把文字曲線當作原始可編輯文字。
2. **分層資料模型**：來源檔→候選作品→人物/公司/欄位→幾何與字型量測→學習規則→模板→發布版本；每項推論留 provenance/confidence/unknown。
3. **重複辨識分層**：檔案位元雜湊、標準化作品指紋、模板結構等效性分開判定；近似不自動刪原始樣本。
4. **匹配與排版**：先盤點既有名片專案 peopleCapacity、Hungarian assignment、等效欄位群、水平壓縮與特製排版；再比較成熟的 assignment / constraint optimization 方案。禁止憑記憶聲稱原始碼已可重用。
5. **驗證**：語意與硬性幾何約束採可重現的確定性檢查；審美模型僅對已合格候選排序，人工發布。
6. **字型**：區分字型實際可用、替代估算及未知狀態；正式輸出前必須以實際字型重算並驗證。
7. **資料安全**：本機處理真實客戶資料；GitHub 只保存程式/規格/匿名化測試樣本，不保存未授權 AI 檔與字型。

## 尚需進一步調查
- Illustrator 文件的 live effect「效果→路徑→外框物件」對 scripting/匯出結構的影響；是否能恢復原始文字、真實 bounds、水平縮放。
- PDF/A、PDF/X、字型嵌入及印刷輸出條件，按實際印刷廠要求定義。
- Windows GUI 框架、向量渲染、幾何限制求解、字型 shaping、相似度/聚類等成熟工具的版本與授權矩陣。
- 實測既有名片自動排版倉庫，不要假定本倉庫已包含其程式碼。
- 效果量測、測試集切分（防止相似作品資料洩漏）、跨尺寸泛化及人工審美評分的可重現驗證。

## 不應誤判
- .ai 可能有 PDF 相容內容，但不保證所有 .ai 均可由 PDF 工具讀取，也不保證能恢復原生 Illustrator 文字與效果。
- 觀察到的排版相關性不等於已證實的因果。
- OCR 辨識結果不能直接取代精確字型/字寬量測。
- 文件查證不等於 Windows/Illustrator 實機驗證。
