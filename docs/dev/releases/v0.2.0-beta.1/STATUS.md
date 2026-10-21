# v0.2.0-beta.1 實際進度

2026-10-21：**Linux 來源已驗證；公開倉庫的原生 Windows 建置重試中，尚未發布 EXE。** 此為內部實測版，不是私人作品、指定硬體或正式印刷品質認證。

## 已有可核對成果

- linux-regression-004：1958／1958 PASS、258健康模組、0 runtime錯誤，來源未變，原測試ID全部保留。
- stock-captures-004：原版27／27 PASS，原腳本、斷言及deadline未放寬，單獨執行。
- RUN-WINDOWS-BETA-LINUX-001：採錄同源真實結果及355附件；software_execution_status=PASS，原5外部未驗證條款保留整體FAIL。
- 來源CP-20261021-WINDOWS-BETA-SOURCE-002：快照956c89c8，獨立Git讀回11713項、隔離還原PASS；增量包依賴基底570ecebe。code manifest3cd6da4bbe162df29746c17e12e55992a4eabc09042f4492896a0b54b9c9c95f。
- 嚴格治理require-evidence/publication-scope PASS。172需求／75父題／166完成範圍及AI8包資格未更改。新一輪workflow接線調整另有7個既有發佈測試PASS；未改產品、tools、測試或依賴pin，未重跑無關整套測試。

## 原生 Windows 重試

公開倉庫已實際確認，標準windows-latest能啟動。舊run39587259422的公開annotation證明當時在工作啟動前被帳務／支出限制擋下；帳戶具體原因未獨立核實，未改帳務。

1. source5fc96ce4／run39591183044：真正啟動並安裝Inkscape，建置失敗，尚無初始錯誤檔。
2. sourceb0e1bc84／run39591928487：補上啟動失敗紀錄，取得Pinned dependency installation failed，第6行；來源171測試／EXE尚未執行。
3. source35d133cd／run39592388094：明確選用setup-python3.11，避免Inkscape/bin影響解譯器。原生RUNNING回執已讀回；PATH假說與完成結果仍待實際紀錄，不先宣稱成功。

實際狀態與有界報告保存在release-evidence/v0.2.0-beta.1，各來源目錄不可拿別次結果替代。此雲端api.github.com仍Forbidden，但公開HTML和原生Git讀寫可用；不再將API限制當成完全無法觀察或啟動工作。

## 發佈前仍須完成

Windows15模組171案例全PASS無skip、真正frozen EXE兩階段檢查、不可變tag、Pre-release、ZIP/manifest/SHA256上傳，以及草稿與公開後附件實際逐檔下載核對。任何一項未完成，就不能給出已發佈下載宣告。普通dev/main/PR不建置，不合併main，不覆寫tag。

成品預定TemplateAI-v0.2.0-beta.1-windows-x64.zip，完整解壓後開啟TemplateAI.exe。本機Inkscape、合法字型及可選OCR工具需另行就緒，私人資料與模型不隨包上傳；問題報告由使用者手動匯出。

## 空間與外部限制

唯讀空間評估見docs/dev/maintenance/STORAGE_ASSESSMENT_20261021.md及226列CSV；零刪除。55份舊實體ZIP共19.42GiB只是條件候選，尚需逐份hash／獨有資料／還原核對。最新來源包與本輪評估包2／2 hash/CRC/基底檢查PASS，不等於全部歷史備份皆可用。

真實作品學習品質、完整私人.ai還原、使用者Windows硬體／效能、實印、新手及完整網路隔離資格仍待本機回饋。教學／知識庫為未採用草案，網頁／手機延後。沒有新增付費API、外部模型、試用、付費runner、Codespaces、付款方式或子代理；不臆測整個帳戶帳單數字。


## 正式重試 da809 的實際結果與分組設定

run39612727807來源169PASS/7未完成，input模組到180秒watchdog，未產EXE。原失敗完整有界資料見windows-native-003-failed。新CI設定見grouped-qt-config-001：最多4原案例/程序，serial1，原180秒不變；5案例配置試跑及負例驗證通過。來源manifest0c4c11c8不變，嚴格證據Gate172/166/75/1963仍PASS。即將再跑全部176及實際EXE；未完成前不建成功標記。


## 77e21544原始CI讀取失敗

run39619925888完成前8模組82原案例PASS，後續進度JSON讀取EACCES使監看程序中止；未產EXE。Windows CI metadata讀取新增8次x20ms有界重試，4個控制示範PASS；原產品/案例/watchdog/Gate未變。詳見windows-native-004-ci-read-failed與metadata-read-controls-001。將重新跑全部176，不將部分82計作完整通過。
