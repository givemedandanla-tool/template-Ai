# 2026-10-13 持續開發授權與 v0.1.1 增量

## 使用者授權

使用者原文：「我授權你在24小時內的所有操作皆為合法，所有codex環境變更我都同意，在這24小時內，參照商用軟體、開源專案思路，持續推進軟體開發工作。」

授權於本對話 2026-10-13 收到，24 小時自該訊息起算；本文保存原始授權，不將文件提交時間冒稱訊息的精確時間。此輪可繼續程式開發、必要環境調整、驗證與 GitHub 持久化，不重問已授權的必要操作。仍保留分支／PR 及可追溯證據。授權不代表工作階段能在回覆結束後無人值守運行；尚未建立或宣稱 24 小時常駐開發服務。

## 參考與內化

- Adobe InDesign [Parent Pages](https://helpx.adobe.com/indesign/desktop/create-and-organize-pages/create-and-manage-parent-pages/about-parent-pages.html)：可重用固定元素與頁面可變內容分層。此輪內化為固定背景與動態資料欄位分開，不冒稱已完成 InDesign 等級功能。
- Scribus 官方倉庫 [Master Page Commands](https://github.com/scribusproject/scribus/blob/master/doc/en/scripterapi-masterpages.html)，讀取 blob `c1d865431a246c3886f6cc34e0e8ded892ad79d5`：建立、編輯及套用母版的工作上下文。參考思路，未複製實作代碼或文件全文。
- Inkscape [Using the Command Line](https://wiki.inkscape.org/wiki/Using_the_Command_Line)，以及本機 Inkscape 1.4 `--help`：本機實際支援 `--pages`、`--pdf-poppler`、文字轉曲與 SVG／PNG 匯出。以實際多頁 PDF 驗證參數，不沿用舊版 `--pdf-page` 假定。

## 本輪實作與界線

v0.1.1 加入人工核准乾淨固定背景、來源／實際呈現並排核對、向量／圖像選擇、背景內容雜湊與失聯阻擋、文字色彩、真實多頁選頁及早期像素預算保護。背景預設不從有舊資料的原稿自動提取；不得以白色覆蓋未知內容冒稱成功。背景去除可變資料仍需人工在設計工具整理，不宣稱自動分割或個資辨識完成。

Windows 失敗 job 的第二次重試仍在步驟前失敗，無可用 steps／logs；尚未取得確切原因，未產生 Windows EXE。此輪增加執行後的測試／字型診斷保存及封裝啟動逾時；這些是診斷改善，不是建置成功證據。

本地驗證、未完成範圍與下一工作以 [FIRST_VERSION_STATUS.md](../FIRST_VERSION_STATUS.md) 為準。原矩形產品、Inkscape 解套、指定硬體與印刷分析後移的定案不變。
