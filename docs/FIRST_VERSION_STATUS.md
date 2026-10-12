# v0.1 實作與驗證狀態

日期：2026-10-12。使用者已授權「開始照計畫製作第一版軟體」，來源見 `decisions/2026-10-12-FIRST-VERSION-AUTHORIZATION.md`。本版建立 P1～P3 的最小核心鏈及必要標記規則學習／資產能力，不宣稱整個 P0～P10 產品完成。

## 已實作

Python 3.11＋PySide6 6.8.3 三模式 GUI；SQLite 來源／模板／標記／Logo；SHA-256 快取與獨立來源；Inkscape CLI 和 Qt PDF／SVG；人工矩形作品／欄位框、毫米標定、幾何規則模板學習、草稿／發布／新版本、固定字級／字型字形量測、人物公司歸屬、同尺寸 Logo、候選配對／排序、資料完整性與過期版本、PDF／PNG／JPG、非正式 PREVIEW、排他寫檔。

## 已執行的本地驗證

雲端 Linux、Python 3.11.16、PySide6 6.8.3、Inkscape 1.4。

- 15 項 unittest 通過：固定字級／長文字、超界／重疊、未映射聯絡、缺字型、人物公司混配、Logo 缺失／尺寸及公司不符、版本不可覆寫、異名同內容、重開恢復、過期候選、預覽標示及檔案失敗保護。
- 真實 Inkscape SVG→SVG／PNG，以及合成 PDF 更名 .ai 的 PDF 相容匯入成功。此為合成相容案例，**不是 Adobe Illustrator 原生私有檔全面验收**。
- 真實 Qt GUI 啟動、標記／排版工作區截圖成功。
- 實際合成 PDF／PNG／JPG，Qt PDF 讀回 90×54 mm 頁面及可渲染結果。
- 來源→標記→學習模板→人工發布→配對→數位輸出通過；runtime `pip check` 通過。

執行 `python tools/validate_first_version.py` 生成 `artifacts/TEST_RESULTS.txt`、`VALIDATION.json`、畫面與數位輸出。本次本地文字證據保存於 `docs/evidence/v0.1-linux/`。這是自我驗證，未進行獨立審查。

## Windows 打包

已加入 CI：Python 3.11、Inkscape 1.4.2、功能測試、PyInstaller onedir、實際封裝 EXE 啟動截圖、ZIP／SHA-256 與 artifact。**對應 run 實際成功前狀態為待驗證，不宣稱 EXE 已建置。** 安裝、工作流程權限或 artifact 配額失敗要如實記錄。

## 待完成與範圍

- 真實私人 AI 檔視覺一致需可信參考與人工核對，未宣稱所有 AI 都可匯入。
- 本版為標記幾何規則學習，未實作全自動作品切分／語意／OCR 智慧框、聚類歸納與深度模型。
- 每人物支援一家公司，多人物可共享；一人物多公司留後續。
- 單尺寸候選與模板毫米編輯已實作；多尺寸同步、候選人工修正／保護與無模板特製排版留後續。
- 客戶重訂／主檔、完整加密備份／來源重連、持久字型庫、重大重審／獨立資料集中心及完整 UI-048 權限尚未完成。
- 16 GB＋RTX 5050 與 ASUS VivoBook 尚未指定機器實測；VivoBook 型號待補。核心走 CPU，GPU 加速未實作。
- 軟體完善後才做實體印刷分析；數位通過不代表印製品質驗收。

後續先用合法匿名真實來源驗證 Inkscape 差異與標記有效性，補多作品、字型與 Logo 例外，再擴充可信樣本和智慧框。既有未決報告格式與低優先補樣不自動加入交付。
