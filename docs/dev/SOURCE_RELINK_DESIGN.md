# CORE-024：受控來源重連

2026-10-13；UI-049 已核准需求的單件子包。商用、開源與演算法參考如下，採用流程與設計思路，自行實作，不複製第三方程式碼或導入其服務。

- Adobe InDesign [更新、恢復與替換連結](https://helpx.adobe.com/in/indesign/desktop/add-graphics-and-media/manage-links/update-restore-replace-links.html)：区分 missing、modified 與 replace。本版內容變更須另行匯入／審核，不把替換冒充重連。
- Blender [bpath.cc](https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/bpath.cc)：參考外部路徑遍歷及 missing files 管理；本版只檢查使用者選取來源，不搜尋整部電腦。GPL 程式碼不複製到專案。
- DVC data [hashfile/hash.py](https://github.com/treeverse/dvc-data/blob/main/src/dvc_data/hashfile/hash.py)：參考內容識別與分塊讀取，不把檔名當身份；不新增 DVC 依賴或照用其預設演算法。
- NIST [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)：使用 SHA-256。N bytes 的驗證時間 O(N)、讀取緩衝 O(1)，每塊 1 MiB；單檔上限 200 MB。雜湊不是來源授權、安全簽章或視覺一致證據，碰撞機率非零。

## 資料與操作

保留 sources.original_path 和 payload 原始登錄不變；新增 source_links 的目前位置及 revision、不可變 source_relinks 歷史。未重連舊資料以原路徑、r0 使用，無需重建來源。只更新當前位置，不改 source id、內容 hash、頁碼、作品／標記／模板及衍生資產。

候選在背景以唯讀串流驗證 SHA-256，核對讀取前後 stat；提交於 GUI SQLite 所屬執行緒，再次核對候選 stat 與來源 revision，避免長時間雜湊鎖住 GUI 或使用 SQLite 跨執行緒。這是本機正常檔案異動防護，stat 不是抵抗惡意檔案系統的證明。每次狀態檢查重新讀取內容，不承諾檔案提交後永不變更。

一筆交易保存路徑、歷史與事件，失敗全部回滾；舊 revision 不得覆寫另一工作階段的重連。相同已驗證路徑不另增版本。來源缺失、內容異動、不可讀分別呈現；衍生快取可用不等於原稿在場。

## 驗收與範圍

具名測試將驗證：同內容改名／搬移且原路徑缺失後重連與重開；同名不同內容拒絕；原登錄、作品、模板、快取不變；過期 revision、候選驗證後異動拒絕；事件失敗交易回滾；missing／changed／unreadable／ok 區別；GUI 使用背景驗證並保留已選作品。測試用匿名合成來源，不上傳本機資料庫或原稿。

批次資料夾掃描、變更內容的新來源版本工作流及 Windows 真機驗收不屬本包；UI-049 父題仍未全數完成。
