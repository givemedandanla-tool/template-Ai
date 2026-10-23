# 原生 Windows 第一輪失敗與最小修正

原始結果在 windows-native-001-failed/：171預定、131完成、129PASS、2ERROR、40未完成，治理PASS；不是產品已通過或已建EXE。Inkscape/bin/python.exe確實遮住setup-python，workflow明確選3.11後依賴安裝已成功，原log保留選擇前後路徑。

1. 真實產品問題：training_pipeline.owner_alive與batch_import.recover用os.kill(pid,0)探測其他程序。在Windows這會TerminateProcess，不能用作唯讀探測。改用既有psutil.pid_exists，保留同程序token／session、SQLite接管與明確恢復規則。新案例真正啟動外部程序，確認探測與恢復不殺程序、不搶工作、不改原記錄。
2. 證據工具問題：Windows進度讀取暫時占用目的檔，replace可能WinError5/32/33。重用dev_common.write_json的既有fsync＋唯一暫存原子寫入，只對這些錯誤有限重試；永久拒絕或其他錯誤仍失敗。刪除progress的重複外層rename。新案例涵蓋暫時分享衝突、持續拒絕與其他權限錯誤。
3. 跨平台測試假設：桌面產物契約保存resolve後路徑，Windows短路徑與長路徑可不同；原案例比較同一resolve後的絕對路徑，仍檢查session、實際檔案與完整hash。Logo版本保護案例使用Qt實際可用字型建立合成模板，避免默認Linux Noto字型在Windows不存在；沒有放寬正式缺字型阻擋或版本唯讀斷言。
4. 未解釋的原input-integration模組deadline保留失敗，未提高期限。Windows缺少SIGUSR1，增加接近原owner截止時間的一次stack dump與有界失敗unittest/progress/stack紀錄；不做正常工作期間的週期性dump、不改通過條件。若再現，依原生stack找根因。

新增5個安全案例；既有1958個ID及原27個GUI腳本／斷言保留。Windows矩陣由15模組171項增加到16模組176項，不刪除舊案例。完整Linux同源回歸、原GUI截圖及真正Windows／EXE仍須重新驗證，不借用舊manifest的PASS。

本輪沒有新產品功能、私人作品／模型品質認證、資料／模板／字型規則變更或資料刪除。字型變更僅合成測試前置條件。尚未發布版本，因此維持0.2.0-beta.1，未建立或移動tag。
