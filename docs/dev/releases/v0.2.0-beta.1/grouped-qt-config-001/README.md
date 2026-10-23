# Windows Qt 程序分組設定驗證

正式 run39612727807／da809cf5 在產生 EXE 前失敗：176 預定、169 實際 PASS，輸入整合模組 12/19 完成後達原 180 秒程序 watchdog。原始 FAIL 與 stack 保存在 ../windows-native-003-failed；沒有斷言失敗不等於完整通過。較早診斷176/176PASS不能代替本次正式結果。

改用 `.github/build_windows_ci.ps1` → `docs/dev/releases/run_windows_case_audit.py`，只調整 CI 程序生命週期：同一桌面一次一個程序，每程序至多4個原案例，180秒 watchdog不變，全部176 ID、斷言、案例內等待、正式資格與實際 EXE Gate不變。原 tools/build_windows.ps1、產品、原測試及工具內容未變。不能把這項設定說成已證明產品無洩漏；它減少單一程序累積的 Qt 狀態及累計耗時。跨步驟行為仍由原完整案例驗證。

本機 Linux 配置試跑：原5個 Windows release safety 案例透過同一新入口執行，2個真正獨立程序，5/5PASS、原ID順序完整、原來源不變。此為配置試跑，不是原生Windows或EXE。

隔離負例：5個示範案例跨2個程序，最後一個刻意失敗；實際4PASS、1FAIL，聚合結果拒絕通過。樣本只在.cache，不加入正式基準。negative-control.json 保留實際記錄。

目前 code-only manifest `0c4c11c8bd6a899cff6f10822f7af018a9998c5440ec05dc3b44d77075a14274`，與已資格化1963個實際來源結果及27張原GUI證據一致（逐檔完整 manifest 相等）。新組態下的原生176案例、實際EXE、公開下載均須另等正式結果；本文件不替代它們。
