# CORE-025：核准字型複本修復

2026-10-13；UI-032 子包。參考 [InDesign 缺字型處理](https://helpx.adobe.com/nz/indesign/desktop/troubleshoot/font-and-plugin-issues/missing-font-error.html) 的可見診斷與使用者選取流程，以及開源 [FontForge 驗證](https://fontforge.org/docs/ui/dialogs/validation.html) 的「可解析不代表完整字形驗證」。本版由 Qt 實際載入與家族核對，不宣稱執行 FontForge 全字形驗證，不複製其代碼。沿用 SOURCE_RELINK_DESIGN 的 DVC 串流內容識別參考與 SHA-256 演算法。

僅從已授權、相同 SHA-256 的檔案恢復既有本機資產；家族名稱、檔名或系統同名字型不足以核准。未核准或不同 hash 拒絕。只修復程式擁有的 assets/fonts/hash.ext，不寫 Windows Fonts，不改变已發布模板或 catalog 字型 pin。

同目錄暫存複本，串流核對 hash，fsync 後由 Qt 解析家族。損壞原複本先保存不可覆寫隔離備份與 hash；正常例外回滾回原內容，失聯情形回到失聯。參考 Python [os.replace](https://docs.python.org/3.11/library/os.html#os.replace)，以同檔案系統的名稱替換避免半檔案，不能宣稱檔案與 SQLite 跨儲存原子交易。

替換前先保存 SQLite PREPARED 修復意圖（同內容 hash、位置、隔離備份 hash）；成功記 COMPLETED／審核事件。若程序在兩種儲存操作間中斷，重開檢查：已恢復正確內容才補完成事件，否則維持字型阻擋並記 FAILED。不靠檔名／PREPARED 就宣稱完成。硬體断電與 Windows 鎖檔需真機驗收，本包只驗證 Linux 例外與模擬中斷恢復。

驗收：失聯／損壞複本修復後重開及重新排版輸出；已發布模板 payload 不變；不同內容、未核准、符號連結／非程式路徑拒絕；記錄失敗時複本回滾；Qt 無法載入不替換；成功才記完成；PREPARED 重開核對；GUI 選取既有資產，修復後候選過期重新排版。50 MB 支援上限，字型檔及隔離備份只留本機，GitHub 證據只有測試紀錄。

完整字重／版本／TTC 子字型指定、系統安裝、智慧字型匹配與嵌入授權管理仍未完成，UI-032 不標全部完成。
