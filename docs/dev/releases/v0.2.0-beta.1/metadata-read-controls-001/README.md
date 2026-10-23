# Windows CI metadata 讀取衝突

run39619925888／77e21544 正式執行：8個完整邏輯模組82個原案例全部PASS，包含整個19例輸入/預覽/拖動及原格式輸出模組。後續監看test_offline_support進度JSON時，Pythonopen遇到PermissionError(EACCES)，CI監看程序拋出；尚未產EXE，不能說176完整PASS。原始失敗及已完成模組見../windows-native-004-ci-read-failed。

只在Windows CI adapter包裝既有bounded metadata reader：Windows EACCES且winerror為None/5/32/33時最多8次、每次間隔20ms（總暫停上限140ms）。成功仍使用原32MiB大小限制與原內容；持續拒絕存取會重新拋出，不回傳空資料或PASS，其他錯誤立即拋出。產品、原工具、原案例、180秒程序watchdog及發布條件未變。此為NTFS短暫衝突的防護，不宣稱已證明哪個Windows程序鎖檔。

4個隔離控制實際PASS：先3次拒絕後讀回真實JSON；持續拒絕8次後仍拋出；非Windows拒絕1次立即拋出；原大小/結構類ValueError立即拋出。測試是模擬IO失敗示範，非原生Windows資格；新正式176/EXE仍待下一次實際結果。
