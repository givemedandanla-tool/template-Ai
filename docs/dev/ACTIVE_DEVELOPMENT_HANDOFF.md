# 當前精簡交接

使用者已公開倉庫，授權重試Windows EXE發佈及工作區文件用途/清理評估。繼續直到實際Release，不問例行確認、不合併main、不刪既有資料、不新增付費資源。開發分支dev/v0.1-first-version。

## 當前正常發佈

**尚未發佈，無tag。04418ac0/run39632714813原176/176、16healthy、49Qtgroups、0runtime及真EXE14+7兩階段均PASS；最終包內容Gate攔下sklearn自帶tests/data，原始失敗保留windows-native-006-payload-failed。** 釘定官方hook全量collect_data_files根因已核對，docs建置配置在freeze與EXE驗證前移除三個已知第三方tests資料；原包Gate不變，7配置控制PASS。正在保存完整checkpoint後啟動新的正常完整原176+EXE+tag+兩次全下載流程。禁止僅複製044結果改來源，只有RELEASE_PUBLISHED_DOWNLOAD_VERIFIED精確讀回才算發佈。見PAYLOAD_POLICY_REPAIR.md。

原生Windows03a7c692/run39623436705已176/176PASS、16健康、49新Qt程序、0runtime、source unchanged；真EXE當時快取失效。d34e/run39628676683觀察到0AUTO_UNIT、COMPLETED_WITH_EXCEPTIONS、來源快取錯誤，未到暫停，不是暫停控制失效。

**c45dc236/run39630607193實際EXE UTF8 A/B PASS**：同一0c4產品、同主機，baseline實測utf8_mode0+同cacheFAIL+0單位exit1；fixed實測mode1，原14+7檢查兩階段全PASS，含first-unit pause/explicit resume/unchanged replay/safe report/window close；實際EXE/source match/unchanged均true。資料releases/v0.2.0-beta.1/frozen-utf8-ab-001-passed。這是診斷，不冒稱新跑176或已發佈。正常spec透過configure_frozen_utf8.py加釘定PyInstaller6.22.3官方Xutf8選項，runtimehook/父程序檢查實際mode1；原cacheGate/產品/視窗/斷言/期限不變。

## 來源資格與主要checkpoint

產品/tools/tests code manifest仍0c4c11c8bd6a899cff6f10822f7af018a9998c5440ec05dc3b44d77075a14274，只有.github/docs配置修改；Linux不無故重跑。RUN-WINDOWS-BETA-FINAL-LINUX-001是1963唯一實際PASS、原27GUI，原5外部UNKNOWN保留。不是首次全綠：raw006為1961PASS/SourceWatch deadlineFAIL，同bytes整個11例在原180秒獨占33.855sPASS，requalified逐case/inputhash/原失敗均保留。原1958ID/原27腳本命令deadline不變。

**當前主要checkpoint CP-20261021-WINDOWS-UTF8-READY-001.receipt.json**：a3fc928f快照，430項REMOTE_VERIFIED，含369正式附件、原生176、真EXE A/B及工作區55備份完整性報告。strict require-evidence/publication-scope實際PASS172/166/75/1963。不要用小型輔助CP覆蓋主要指標；補主要CP須含完整正式run附件。輔助Git讀回不加--ack。改產品/tools/tests bytes會改source，須重資格，不能混用舊結果。原私人作品/硬體/實印等外部資格不升級。

## 工作區評估完成

maintenance/STORAGE_ASSESSMENT_20261021.md/JSON、原226列CSV、OLD_CHECKPOINT_INTEGRITY_20261021.json。55/55舊實體ZIP SHA256與全CRC PASS、19.42GiB、182秒；2996b606已獨立Git讀回。仍未逐包unique/full restore/remote blob復原，不是刪除核准；刪除0。81舊ZIP失效連結可追溯Git歷史，不冒稱完整復原。保留程式/.git/正式證據/需求交接/私人資料/使用中工具及新checkpoint。盤點大小as-of非即時。

## 操作／最終交付

公開標準windows-latest可用；無新付費/API/試用/子代理。api.github.com仍Forbidden，但公開HTML/原生Git可讀寫，不要求API key/重連。watch_receipt.py只觀察；20分窗口到期可同source重啟，不當CI失敗。結果在release-evidence/v0.2.0-beta.1精確按source取回。

本機空間少（/workspace數百MiB、/tmp101MiB），不要亂刪。CI本身兩次實際下載全部ZIP驗證，雲端再核小manifest/checksum/公開URL即可，不為第三次大下載清資料。成功後給完整ZIP連結、解壓後TemplateAI.exe、實際驗證數量/真作品待本機回饋，以及工作區評估連結。細節按需讀STATUS與獨立資料夾，每批工具輸出≤1600tokens。
