# 當前精簡接手

- 核心規則：CONTEXT_AND_PERSISTENCE_RULES.md；零例行問答、GitHub持久化、先搜尋再分段讀取、工具輸出一般≤1600 tokens。新對話只帶倉庫／提交／本交接，不帶整串聊天；大型媒體用檔案工具按頁／區域處理。
- 工作樹：/workspace/template-Ai；分支dev/v0.1-first-version／PR2，未合併main。精確HEAD先跑`.venv/bin/python tools/resume_status.py`。
- 使用者本輪目標：繼續20個原父功能，契約FIXED70_NEXT_TWENTY_CONTRACT。先UI003/004/005/007/008/038/039/040/041/042，再UI001/002/006/010/011/012/033/034/035/036；不能把子項或測試總數算父題完整。
- 基準：前輪16父題完整、56部分、3延後；固定70完成14／剩56，CORE87／GOV7另計。前輪來源3cd2c22，498PASS／87條新驗收PASS。本輪改碼後110既有驗證列暫待重驗，歷史未刪；本輪20題尚未新增結案。
- 已完成：20題BEGIN與四項核心規則已推送讀回。新增Inkscape來源→多作品／完整Logo候選、一鍵持久管線、逐作品隔離、已授權TRAIN幾何草稿、取消／續跑／精確重分析與Qt入口；14管線PASS（8.516s）、6標記後端PASS、7語意PASS、5實際Qt標記／視角模式／例外測試PASS（3.683s）；尚待全量來源回歸。本輪父題仍未結案。
- 新增使用者要求：SEMANTIC_FIELD_CONTRACT.json，辨別郵件／社群ID／市話／手機／地址／職稱；已補離線分類與未知拒答；CharacterModel已接持久化訓練／留出／獨立啟用及新來源管線（7目標測試含實際Qt／Inkscape PASS）；未替使用者真實資料訓練或啟用，不假稱模型已理解所有字串。能力界線見SEMANTIC_MODEL_DESIGN.md。
- 下一步：重用現有TrainingStore／批次匯入／規則審核，補作品例外檢視／精確重試、直接畫布標記／切分合併、事實修正與規則候選閉環，再GUI10題。逐條驗收、正式source-bound回歸及GitHub讀回後才結案。
- 驗證／未決：當前環境連線current/running、Git proxy讀取成功；runtime network state回報unknown，不宣稱政策已ready。沒有必要新增secret或付費API。Windows、真AI全面、實體印刷、硬體與獨立覆核未驗證。
- 保存：每可恢復階段及每10分鐘checkpoint→push→fresh fetch→逐檔讀回；收據下一提交保存。詳細歷史在HANDOFF／WORK_LOG，只按需查相關段落。
- 限制：無多代理、不建EXE、不merge main、[skip ci]保存；真資料不公開，新證明媒體依既定metadata-first留本機及hash。UI048最後，REV03／UI056D依既定順序延後。保留未提交／ignored／local-only資料，不reset。
