# CORE-028／029：共用字型查詢與字形／字寬診斷

2026-10-14（Asia/Taipei），UI-032 的已核准子包。先讀原決策與 FONT_REPAIR_DESIGN.md，保留所有原需求與已發布字型 pin。

## 三類參考與實作取捨

- 商用 [InDesign Find/Replace Font](https://helpx.adobe.com/indesign/desktop/fonts/find-and-replace-fonts.html)：參考字型一覧、實際使用／缺失查詢與影響呈現。此包不替換模板字型，不能把匯入圖稿中的原生字型宣稱已識別。
- 開源 [fontTools TTFont／getBestCmap 原碼](https://fonttools.readthedocs.io/en/latest/_modules/fontTools/ttLib/ttFont.html)：參考 Unicode cmap 的實際字形映射，而非以字型名稱或 OS/2 字元範圍猜覆蓋。自行實作並重用既有 Qt，不複製第三方原碼、不新增 fontTools 依賴。
- [Qt QRawFont](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QRawFont.html) 與 [QTextLayout](https://doc.qt.io/qt-6/qtextlayout.html)：前者讀取實際檔案／字形，後者執行 shaping 與 kerning。以無 fallback 的實際 glyph run 及字型 table 核對，不能將 glyph 名義進位總和冒充已正確 shaping 的排版寬度。
- 數學方法：S 為診斷文字所需的不同非空白 Unicode code points，C 為 cmap 有非零 glyph 的集合；覆蓋率 |S∩C|／|S|，S 空則不宣稱 100% 實際文字覆蓋。使用 1000 px em 的文字 shaping 寬度 W，再以 `pt × 25.4／72／1000` 換毫米，避免螢幕 DPI 變動。框宽 B、最小水平比例 m，必要比例 r=min(1,B/W)；只有完整字形、合法單行／shaping、r≥m 才是該單行寬度範圍可行。不改字級、不截字，亦不將此單框診斷冒充全模板／印刷合格。

## CORE-028：共用管理中心

GUI 全模式共用入口，列程式已核准本機資產、Qt 主機可用候選（無檔案身份／來源核實不冒稱 Windows 已安裝）、模板未登錄／未知／失聯引用。背景只讀檔案確認 hash／可解析家族與款式；SQLite／Qt資料庫與模板快照在 GUI 執行緒取得。不同記錄／path／hash 保留身份；健康、失聯、異動、未核准、不可解析等狀態與實際模板／欄位引用可查，草稿與發布均列，未知原稿字型不假稱已找回。

依家族／樣式／來源／狀態搜尋與篩選；現有本機匯入與同內容修復可從中心使用，模板不自動改字型、候選不自動核准、Windows 不自動安裝。單輪最多256資產、1000主機候選、256MiB資產驗證預算與2000未登錄引用；超額明示部分。字型資料只留本機，不隨 GitHub 或證據公開。

## CORE-029：所選字型診斷

只檢查使用者明列選取的條目與匿名診斷文字；空／非法點數、框宽、比例、過長文字與控制字元需分開處理。本機資產驗證同 bytes hash、可解析字面；Qt選字 shaping 若字形 run 的主要字型 tables 與已核准字面不符即阻擋，不能拿系統同名字型 fallback 算完成。TTC 目前只檢查 Qt 可讀字面，其他字面不冒稱通過。missing／modified 資產不因系統字型可用而通過。

诊斷顯示缺字清單、所選與實際解析家族／款式、mm 寬度及水平比例、已固定字級、結果及理由；原稿字型身份、嵌入／散布授權未知照實標示。診斷不寫模板、原稿或客戶資料，也不直接核准正式輸出；正式排版維持既有幾何／資料／字型 Gate。

## 驗收与未完成範圍

具名驗收涵蓋健康／失聯／篡改／未核准／坏格式、同家族系統字型不代替本機缺失、hash／path 引用與模板影響、未知引用、篩選与預算、Unicode含非BMP字形、真正 shaping／字型table不符阻擋、點數毫米線性與水平適配邊界、非法輸入、GUI背景與不改發布模板、修復刷新与實際截圖。

完整 Windows 安裝／來源證實、TTC多字面、不同檔同家族完整版本與字重共存、原生 Illustrator 字型／效果、視覺近似替代排序與 UI-033 批次替代、嵌入授權與真實硬體驗收仍未完成；UI-032 父題保留 PARTIAL。
