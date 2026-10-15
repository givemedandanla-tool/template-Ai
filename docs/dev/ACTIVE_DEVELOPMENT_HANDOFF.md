# 當前精簡接手

- 核心：CONTEXT_AND_PERSISTENCE_RULES.md；零例行問答、按需rg與段落讀取、一般工具總輸出≤1600tokens。換對話只帶倉庫／提交／本檔。每可恢復工作包及10分鐘checkpoint→push→fresh Git讀回；收據下一提交保存。
- /workspace/template-Ai，dev/v0.1-first-version／PR2。無多代理、不merge main、不建EXE、[skip ci]避免自動Actions。先resume_status取實際HEAD與變更。
- 最新目標28原父題，FIXED70_NEXT_TWENTYEIGHT_CONTRACT.json完整條款。原20加UI013/014/015/018/028/029/030/037。基準16完整／56部分／3延後；固定70完成14／剩56。本批尚未正式結案，不能從測試數推父題數。
- 上輪正式RUN-TWENTY-INTERIM-001來源46d367bee0c642437d13de7202b8ac611f7ae08c：553PASS、0跳過、7新Qt。現在原110完成列全暫IMPLEMENTED_PENDING_VERIFICATION，STATE.pending_revalidation_ids保留；previous_evidence_run保存原來源，latest_evidence_run=None待新正式run。
- 本批已保存：全部可讀PDF相容頁自動列入預檢／每頁獨立來源與作品（原生畫板未知）；三層只讀近似預檢（SHA256/dHash/作品裁切/結構Jaccard）、實際掃描進度／取消／持久job分頁；標記前後視覺對照、解除／恢復同步、倍率數值／滑桿；拒絕／隔離／恢復候選與真值阻擋；全庫作品狀態/來源/頁/尺寸分頁前篩選。
- 結果合格／不合格候選已實際分區；主模板畫布重用ObjectCanvas及propose，三向語意樹／屬性、縮放／微調／吸附；字距固定字級區間、語意分散逐欄核准；Qt shaping同渲染參數。新ink envelope修斜體AV/j/f overhang與截邊像素。
- 輸入卡片180ms即時欄位旁警告／頂部預估狀態／右側精確ID定位，不奪焦點或改未採用資料；公司欄位也量測。舊表格delegate可見警告。回呼關庫安全停止。
- 多尺寸新增OutputBatch逐檔更名／略過／明確覆寫（原檔保留恢復，移動後驗證、排他完整發布，非全交易原子replace）；真實進度、成功保護、精確失敗重試≤3、明確暫存清理。PREVIEW預設PNG，FINAL/PREVIEW分流。9新檔案故障／Qt測試及10既有PASS。
- 依賴新增kiwisolver1.4.9鎖requirements與lock。Cassowary只在無合格現成模板時，以核准基準及明定位移／擴框／間距求特製草稿；固定字級／歸屬／Logo、原拓撲不變；原TemplateVersions CAS交易存同family新版，發布獨立。6新測試及80字型／版本PASS。工程來源／hash見TWENTYEIGHT_ENGINEERING_BASIS.json（Qt/ImageHash/Python/Kiwi/Figma公開typings），不呼叫付費服務。
- 下一步：UI005已讀回核實SQL即時計模板影響數；28逐條acceptance/tests/Qt映射（尚未註冊），補必要缺口；擴充capture，凍結code到GitHub、正式run_evidence全回歸，才恢復110舊列及結案通過的父題。更新progress/roadmap/fixed70/契約/精簡接手並保存收據。所有新失敗attempt保留，沒有削弱斷言。
- 環境.venv Python3.12/Qt6.8.3/SQLite3.53.1，XDG_CACHE_HOME=/workspace/.cache QT_QPA_PLATFORM=offscreen；OCR local-data/tessdata。舊正式86媒體依FULL70_PUBLICATION精確metadata留本機，不重傳；新正式媒體同政策，code/tests/text全保存。真實私人AI全面／原生Illustrator／Windows／實體印刷／獨立覆核未驗證，UI048最後，REV03/UI056D按既定延後。
