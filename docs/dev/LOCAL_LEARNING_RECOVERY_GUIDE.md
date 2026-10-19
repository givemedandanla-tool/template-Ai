# 本地學習、來源還原與除錯

本輪依據：`docs/decisions/2026-10-19-LOCAL-ONLY-RECOVERY-AND-SYNTHETIC-ACCEPTANCE.md`。不需要把私人作品或字型提供給 Codex。原稿、字型、資料庫、模型、訓練與確認稿都留在本機；程式沒有把它們自動上傳 GitHub 或 AI 服務。依賴套件／OCR 語言檔安裝可能需要下載，不會因此上傳作品。

## Windows 準備

取得 `dev/v0.1-first-version` 分支的原始碼；`main` 尚未合併本輪變更。安裝 Python 3.11 與 Python Launcher，雙擊 `START_WINDOWS.bat` 建立本機 `.venv`、安裝鎖定依賴並啟動。既有私人資料先保留本地備份，不放入公開 Git 倉庫。

安裝 Inkscape；程式會檢查 PATH 及標準安裝路徑，非標準位置可設定 `TEMPLATE_AI_INKSCAPE` 為實際執行檔。要使用 OCR，另安裝本機 Tesseract 及 `eng.traineddata`／`chi_tra.traineddata`；沒有 OCR 時仍可走來源文字或人工核對路線。

以下是 PowerShell 設定例，路徑按實際安裝修改；設定僅適用同一個視窗啟動的程式。若希望往後雙擊啟動也生效，可將相同名稱加入 Windows 使用者環境變數。

```powershell
$env:TEMPLATE_AI_TESSERACT = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:TEMPLATE_AI_TESSDATA = "C:\Program Files\Tesseract-OCR\tessdata"
& $env:TEMPLATE_AI_TESSERACT --tessdata-dir $env:TEMPLATE_AI_TESSDATA --list-langs
.venv\Scripts\python.exe app.py
```

語言清單需包含選用的 `eng`／`chi_tra`。此處是本機準備指引；本輪雲端 Linux 測試未冒充 Windows 安裝驗收。先跑下方隔離合成驗收，再匯入私人作品。

## 本體入口

在「共用 AI 規則／當次稿件」的來源核對頁，開啟「本地來源還原／字型影像診斷」。有作品時先選擇作品與欄位；空資料庫也能直接開啟診斷、選擇第一份作品。即使完全無法匯入，仍可查看原因並匯出不含原稿資訊的診斷。

1. 匯入同時保存外觀與可編輯文字兩條路線。PDF 相容 AI 另外保留原始 PDF 字形／字級證據。Inkscape 失敗時，可讀的 PDF／SVG 由 Qt 重建，不沿用損壞快取。轉換後宣告不自動升格成原生字型真值。來源文字、欄位與 Logo 構件證據明列外觀／語意管道及各自 hash，不跨管道借用；查詢虛擬物件 ID 可重建且不修改原稿。
2. 對單一文字區裁切，使用原始／已核對文字，或本機 Tesseract 的繁中／英文 OCR。OCR 文字與字型身份分開處理。
3. 盤點 Windows 已登錄字型，或明確選擇本機 TTF／OTF／TTC。分批做實際字形比對，可取消；下一批會合併既有結果。未搜尋全部、無法讀取或候選相近均有提示，不把末批當全庫結果。
4. 選擇候選後帶回來源核對草稿；核對狀態預設不勾選，不自動授予印製／嵌入權利。沒有原生文字資訊時，可明確採用已核對的影像字型／幾何候選。推估作品字級標為 DERIVED，原生字級仍可為 UNKNOWN；未知詞距也不假造為零。
5. 依既有流程核對來源、作品／欄位、雜訊、用途與資料分組，再在共用學習頁指定 TRAIN／VALIDATION／HOLDOUT、建立共用模型。模型訓練與預覽在本地進行。正式數位輸出資格須依本地隔離驗證與來源／字型／政策取得；不需要上傳私人驗收資料。

多 run／多字型、分離標籤與向量欄位圖示的後台 API：`SourceTypographyReview.plan_composite`、`plan` 的 `source_text_flow.presentation`。字元分段需完整、不重疊；可核對字詞切分或固定前綴規則，未核對的字元區間只允許原文字回播。這些進階結構目前透過後台 API／合成案例建立，尚非完整圖形化標註精靈。公司 Logo 仍走既有 LogoStore；欄位圖示不能冒充公司身份。

參數、學習流程與數學方法見 [本地模型細節](LOCAL_LEARNING_MODEL_DETAILS.md)。

## 已實作的模型與規則

- 家族：TRAIN-only HDBSCAN、來源去重、低支持與離群保留；不逐作品產生全域模板。
- 字形／欄框：分字型與風格的聯合 Ridge；GMM 提議風格分組後，用群平衡 mixture-of-regressions BIC 比較，避免把連續尺寸直接切成互不相通風格，也保留有支持的不同風格。
- 結構：資料需求／容器能力雙視角、條件角色筆數、收合、相對關係、基線／錨點軟偏好、獨立物件等距。客戶調整相對位置，核心決定字級、字寬、欄框及分散，不恢復客戶細參數控制。
- 文字：同一 Qt 路徑量測與渲染，複合字面、換行、明確詞邊界或塑形字元群分散及自然／分散末行；沒有合法分隔邊界時保持自然字距。字元分散須有來源審查、`SHAPED_CLUSTER_BOUNDARIES_ONLY` 與實體最大額外間距，組合字／連字不拆開；RTL 視覺順序尚不支援。
- 容量：`LocalCapacityCalibration.review_case/from_evaluation` 將實際 VALIDATION 輸出、獨立適合風格標記與聯合字串需求校準成區域；來源群平衡，使用單側 Clopper–Pearson 成功率下界。HOLDOUT 不回填擬合。校準另存版本，不改寫訓練快照；最大已驗證欄位數不冒充全域理論上限，區域內仍重驗實際排版。
- 偏好：實際風格偏差等特徵、明確比較的 pairwise logistic、穩定決勝、NDCG／來源群 bootstrap。`RankerQualification` 支援本地正式資格與版本啟用，缺隔離證據仍拒絕，不靠自製樣本取得真實資格。

## 可在本地重跑的完整合成驗收

在專案根目錄，以已安裝依賴的 Python 執行；目錄必須是新的，避免污染既有客戶資料庫：

```powershell
$testDir = Join-Path $env:TEMP ("TemplateAI-selftest-" + [guid]::NewGuid().ToString("N"))
.venv\Scripts\python.exe tools\local_learning_selftest.py --directory $testDir
```

自動選擇本機常用 Regular 字型；也可用 `--font "本機字型檔路徑"` 指定。它建立隔離資料庫與 22 份匿名 SVG（12 TRAIN、6 VALIDATION、4 HOLDOUT），實際匯入、來源綁定、訓練、產生 2 共用家族、評估 10 個案例、校準適合區間及輸出預覽；檢查全域模板數為零、原稿未修改、模型權重未被評估改寫與同輸入版面穩定。結果在 `$testDir\result.json`；這是軟體合成驗收，不是真實作品美學資格。

`tools/run_source_file_scale.py --directory 新目錄 --count 1000`／`3000` 另外測試實際生成的 PDF 相容 `.ai`、Inkscape／Qt 匯入、原始字形、實際本機字面量測、持久工作前綴暫停／重開與共享 fit。它不是私有 Illustrator 格式、全 Windows 字庫影像搜尋、全功能多樣性或指定硬體資格；保存抽樣程序樹記憶體與耗時，不能拿描述子速度替代檔案處理速度。

## 回報問題

診斷頁會列出缺少的資訊、階段、影響與補救。先看「可分享診斷預覽」，再自行匯出 JSON 回到 Codex 討論。白名單排除原稿文字、客戶編號、檔名／路徑、字型名稱與檔案、原圖、原稿 hash 及原始日誌；保留固定錯誤代碼、數量與軟體版本。沒有自動傳送。

完全無法渲染、無可信文字、缺字型、尺寸未標定、旋轉／特殊書寫或候選歧義等情況，會保留未知或拒絕，不使用預設 10pt 假裝分析成功。可在本地另存 PDF 相容 AI／可信 SVG 或補充清晰預覽再重試。Windows 實機、私人作品與實體印前仍須在本地另行驗證；網站、手機與 EXE 仍延後。

## 參照與重用

實際重用 Inkscape CLI／Poppler、Qt QPdfDocument／QTextLayout／QRawFont／QSvgRenderer、fontTools、Tesseract、SciPy／scikit-learn／Kiwi。字型比對使用對稱距離變換與墨跡重疊，並聯合估計物理尺度；不靠字寬單一數字或 OCR 信心宣稱字型身份。商用影像找字型／Retype 類工作流程作為「辨識→候選→核對→轉成可編輯資料」的設計參考；本實作不調用商用服務或宣稱複製其私有模型。

工程參數、有限搜尋與信心界線須隨真實本地驗證調整；軟體測試 PASS 與真實模型資格分開報告。新對話讀 STATE、精簡交接及 checkpoint，不帶整串聊天。
