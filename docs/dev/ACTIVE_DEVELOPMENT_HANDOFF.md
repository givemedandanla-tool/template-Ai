# 當前精簡交接

## 當前任務與真實狀態

**最新c45dc236/run39630607193實際UTF8 A/B PASS（仍未發布）**：baseline實測utf8_mode0，原快取失效0單位exit1；fixed實測mode1，原14+7完整兩階段全PASS，含first-unit pause/explicit resume/unchanged replay/safe report/window close。source0c4完全不變。證據frozen-utf8-ab-001-passed。下一步補一個含369正式附件、原生176、AB全部資料的完整主要checkpoint，再正常無diag標記提交，strictGate後重跑原176、真EXE與下載發佈。原故障確定是frozen讀檔文字編碼差異，不是暫停控制錯誤；禁止修改原cacheGate或原_pause斷言。

使用者已將倉庫改公開，要求重試Windows EXE打包發佈及工作區文件用途/刪除評估。繼續直到實際Release，不再問例行確認；不合併main、不刪既有資料、不新增付費資源。開發在dev/v0.1-first-version。

**尚未發佈，無tag。** source03a7c692a365c64227807154a76bb3047077f0cd／run39623436705：原生176/176PASS、16健康模組、49個新Qt程序、0runtime、source unchanged。PyInstaller已產真EXE，真EXE通過11項（含合成訓練、產稿/預覽、滑鼠拖動、更正、預覽輸出、拒絕未資格正式稿、JSONpipe worker），在release_check._pause_worker保存邊界檢查失敗。原始證據releases/v0.2.0-beta.1/windows-native-005-frozen-pause-failed。不能把產生EXE說成可交付。

**當前c45dc23643044fa60c2088511575589146039479已推送並獨立讀回73537項，標記[frozen-probe-only] [utf8-ab]，不發布。** 下一步實際UTF8 A/B診斷（見frozen-utf8-controls-001）；d34e1310原診斷已FAIL，phase=COMPLETED_WITH_EXCEPTIONS、0 AUTO_UNIT，item.error來源或衍生快取失效，未到暫停。** 合成真快取UTF8 healthy=true/CP1252 cache_matches=false，僅控制示範。PyInstaller6.22.3官方釘定docs支持X utf8選項；新CI只調spec，不改產品/快取Gate。A/B要求原設定實測mode0+同錯誤；fixedmode1+原兩階段全PASS；不符合就FAIL，不發布。

歷史只做診斷候選d34e1310a17067763ce9acc60b3214ea5d67846a，[frozen-probe-only]，run39628676683已有RUNNING原生回執。此模式不跑/不聲稱新176，不建tag、不package、不發佈。docs/dev/releases/run_frozen_probe.py呼叫原真EXE驗收，在原authored fixture tearDown前只讀worker-observation.json，再照原方式清理；未換視窗/斷言/期限。Linux source smoke兩階段PASS、actual_frozen=false，見frozen-parent-probe-001。等實際phase/unit count/issues找根因，不先猜或放寬原_pause檢查。

## 來源資格與保存規則

產品、tools、原tests目前未再改；code manifest 0c4c11c8bd6a899cff6f10822f7af018a9998c5440ec05dc3b44d77075a14274。所有CI隔離/NTFS metadata讀取重試/父程序觀察都在.github及docs；讀取只Windows EACCES最多8次20ms，永久/其他錯誤仍拋出。診斷後正常提交不能帶任何diag標記，仍須完整176、真EXE兩階段、tag、發佈前後實際下載全部檔案SHA。只在RELEASE_PUBLISHED_DOWNLOAD_VERIFIED精確讀回後才聲稱發布。

Linux完整資格RUN-WINDOWS-BETA-FINAL-LINUX-001：1963唯一實際PASS與原27GUI。不是首次全綠批次：raw linux-regression-006為1961PASS/SourceWatch模組deadline FAIL；同bytes整個11例在原180秒獨占33.855秒PASS，linux-regression-006-requalified逐case來源/原失敗/inputhash均保留。原1958ID及原27腳本/命令/deadline不變。原5外部未知、私人作品/硬體/實印等資格不升級。改產品或工具/測試bytes須按原嚴格證據重新資格化，不能混用舊source。

**主要checkpoint必須保持docs/checkpoints/CP-20261021-WINDOWS-COMPLETE-EVIDENCE-001.receipt.json**：3fb5d882快照，396項REMOTE_VERIFIED，含369正式附件及CI修正，strict require-evidence/publication-scope實際PASS172/166/75/1963。小型CI/維護CP不能覆蓋它，否則缺完整正式附件Gate會正確拒絕（cee5f6df/run39622984200已有此FAIL）。輔助Git讀回用verify_git_readback.py不加--ack，最終若更新主要CP須含全部正式run附件。

## 工作區評估已完成

maintenance/STORAGE_ASSESSMENT_20261021.md及JSON、原226列CSV；只讀補查OLD_CHECKPOINT_INTEGRITY_20261021.json，55/55歷史實體ZIP SHA256與全CRC PASS，19.42GiB、182秒。2996b606已推送及獨立完整tree讀回。仍未完成逐包unique/full restore/remote blob復原，不是刪除核准；刪除數0。81舊ZIP失效連結的Git歷史可追溯，不冒稱已完整還原。保留程式/.git/正式證據/需求交接/私人資料/使用中工具及新checkpoint。盤點大小是as-of，非即時值。

## 執行環境與下一步

公開GitHub標準windows-latest可用，無新付費/API/試用/子代理。雲端api.github.com仍Forbidden，但公開HTML與原生Git可讀寫，不要求API key或重連。watcher .cache/release-public-retry/watch_receipt.py只觀察，不啟動build；20分鐘窗口結束可同source重開，不能把觀察期限誤作CI失敗。native結果在release-evidence/v0.2.0-beta.1原生Git取回。

本機空間偏低（/workspace最後約數百MiB，/tmp101MiB），不要亂刪。CI發佈流程本身會兩次實際下載；雲端可再核小manifest/checksum/公開URL，不為額外大ZIP下載清舊資料。最終交付後給完整ZIP連結、解壓後執行TemplateAI.exe、已驗證內容與本機回饋限制，再連工作區清單。所有舊失敗/細節見STATUS與各獨立資料夾；不展開整倉庫或完整日誌，每次輸出≤1600 tokens。
