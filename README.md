# Template AI｜矩形區域自動排版與模板 AI

**v0.1.1 可操作研究版已實作，本地 Linux 33 項測試通過；Windows EXE 建置仍受阻。** 三模式桌面工作台：來源標記、模板與 Logo、排版與數位輸出。本版增加人工核准固定背景、實際呈現比對與文字色彩。第一版學習為人工確認標記的幾何與語意規則內化；完整自動辨識／深度模型、客戶重訂、完整權限與實體印刷分析留後續計畫。

## 開啟與快速試用

Windows 成品由 [First Version Windows Validation](https://github.com/givemedandanla-tool/template-Ai/actions) 工作流程打包；只有成功且產生附件的執行才有可下載 EXE ZIP。完整解壓縮後開啟 `TemplateAI-v0.1.exe`。不能把待執行工作流程當成已完成 Windows 驗收。

原始碼：安裝 Python 3.11 後，Windows 雙擊 `START_WINDOWS.bat`；或安裝 `requirements-lock.txt`，執行 `python app.py`。

最快路徑：「模板與 Logo」加入合成示範 → 驗證並發布 →「排版與輸出」填入匿名示範 → 開始排版 → 輸出 PDF／PNG／JPG。

## 核心功能

- AI／PDF／SVG／PNG／JPG 只讀匯入，Inkscape 解套與 Qt PDF／SVG 備援；內容快取和獨立檔名登錄。
- 框選矩形作品、毫米標定、欄位／完整 Logo 標記、視覺核對與人工確認。
- 標記形成有來源的規則模板；草稿、發布與新版本，正式版本唯讀。
- 固定字級與實際字型量測、受限字寬適配、人物公司歸屬及同尺寸 Logo。
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
