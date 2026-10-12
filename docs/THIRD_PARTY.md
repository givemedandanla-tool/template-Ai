# 第一版第三方元件與研究選型

本輪採最小依賴：Python 3.11 標準庫＋PySide6 6.8.3。`requirements-lock.txt` 固定 PySide6／Addons／Essentials／shiboken6 同版。無 PyMuPDF／AGPL 依賴，沒有複製既有 business-card-text-bold 原始碼，也不宣稱其 peopleCapacity 或 Hungarian assignment 程式已可直接重用。

| 元件 | 用途 | 授權／限制及來源 |
| --- | --- | --- |
| Python | 主程式與標準庫 SQLite、雜湊、檔案／背景工作 | PSF License；https://docs.python.org/3/license.html |
| PySide6 / Qt 6.8.3 | 桌面 GUI、字型量測、SVG、PDF 讀取及向量 PDF 寫入 | Qt/PySide 提供 LGPLv3／GPL／商業等路線，具體模組及 wheel 的第三方授權需隨分發核對；https://doc.qt.io/qtforpython-6/licenses.html 及 https://doc.qt.io/qt-6/licensing.html |
| Inkscape | 外部只讀匯入／轉 SVG／渲染；環境實測 1.4 | GPL，第一版不隨成品重新散布，使用者安裝既有執行檔；https://inkscape.org/about/license/ |
| PyInstaller | Windows 打包工具，不是 runtime 功能 | GPL 帶 bootloader 特殊例外，產物仍須遵守 Qt 等被打包元件授權；https://pyinstaller.org/en/stable/license.html |

Windows 使用 onedir 而非把 Qt 藏在不可替換的靜態產物；保留動態庫與隨 wheel 授權資訊，說明相應來源及版本。這是研究交付的授權盤點，不取代發行時逐模組／字型授權核對。使用者字型不自動打包或提交 GitHub。

選型原因：Qt 為成熟跨平台桌面框架，QtPdf／QtSvg／QPdfWriter 能在同一毫米繪圖模型中支援預覽與數位輸出，避免原生 AI 私有結構成為共同依賴。真實樣本仍需視覺核對；有 SVG 來源的 Logo 由 Qt SVG 繪製向量，點陣來源保留點陣身份，不假稱向量化還原。
