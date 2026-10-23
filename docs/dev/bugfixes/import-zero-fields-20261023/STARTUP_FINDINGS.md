# 啟動慢與狀態不明：已核對的原因及後續量測

2026-10-23。使用者追加回報：雙擊後開啟慢且無法掌握是否正常運作，詢問是否因Python。這份是原因分析，不是已完成啟動效能修復或Windows量測。

## 已確認

- tools/windows_release.py74–81使用EXE(exclude_binaries=True)與COLLECT，為PyInstaller onedir；不是每次解壓的onefile。console=True、hide_console=hide-early會提早隱藏主控台。
- app.py64–78先匯入PySide6及gui，再建立QApplication、同步MainWindow、切工作模式，最後window.show；早期沒有可見啟動階段。
- 啟動例外保存本機安全記錄，但app.py89–92主要以stderr告知失敗；一般雙擊時主控台隱藏，不能依賴這個提示。
- gui.py251–315在show前建資料庫／schema、三區UI／屬性、分頁目錄、資源監督／備份／來源監看與安全報告控制器；QFontComboBox也是同步UI建構的一部分。這些是候選量測點，不是已證明的Windows瓶頸。
- 已存在lazy FontManager與48項目錄分頁；不能誤稱每次掃全部模型、作品或字型。
- OfflineJournal有APP_STARTED及elapsed_ms，但缺少對應首次顯示／可操作與分階段結束事件。既有EXE整套演練耗時不能替代啟動延遲。

## 建議的最小改善順序（尚未實作）

1. 在昂貴匯入及MainWindow建構前顯示輕量啟動狀態，分清載入、等待、完成、失敗。
2. 記錄模組／Qt／DB／UI／目錄／首次顯示及可操作階段秒數，資料只留本機並可手動匯出安全摘要。
3. 依實測延後非必要頁面與服務，不破壞字型、來源、資料與操作契約；不憑猜測改語言或重寫軟體。
4. 啟動失敗必須有白話可見訊息與安全報告取得方式，不能只寫隱藏stderr。

Python可能有匯入與執行成本，但成熟Python桌面軟體也能提供良好啟動回饋。目前證據支持先修啟動流程與可觀測性，尚不能將使用者延遲歸因於語言、防毒、Windows磁碟或特定模組，也沒有實機啟動秒數。不建議關閉防毒。沒有增加API、雲端或付費資源。
