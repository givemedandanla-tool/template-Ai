# 當前精簡接手

- 核心：CONTEXT_AND_PERSISTENCE_RULES.md；零例行問答、GitHub持久化。先rg搜尋再分段讀；一般工具輸出≤1600tokens；新對話只帶倉庫／提交／本檔。大型媒體按頁／區域用檔案工具，不貼整串聊天或base64。
- 工作樹/workspace/template-Ai，分支dev/v0.1-first-version／PR2，未merge main。先執行`.venv/bin/python tools/resume_status.py`取精確HEAD／變更／收據。
- 最新目標為28個原父功能，契約FIXED70_NEXT_TWENTYEIGHT_CONTRACT.json；原20保留，新增UI013/014/015/018/028/029/030/037。先UI003/004/005/007/008/038/039/040/041/042，再UI001/002/006/010/011/012/033/034/035/036；本輪新結案0，不把子項或測試總數算完整父題。
- 原75：16 SELF_VERIFIED／56部分／3延後；固定70完成14／剩56；CORE87／GOV7另計。既有110驗證列已用本輪正式來源重驗恢復，沒有刪除歷史。
- 最新正式run：RUN-TWENTY-INTERIM-001；來源46d367bee0c642437d13de7202b8ac611f7ae08c；553/553 PASS、0跳過、capture0、來源未改。新增7個實際Qt畫面；模型14目標PASS。僅Linux合成資料SELF驗證，非真實AI全面或獨立覆核。
- 本批實作：可恢復自動候選管線／精確重試、來源作品總覽、畫布標記／區域拆分合併、風險分級確認、修正規則線索、語意／衍生SVG同步樹、模式保留未套用屬性、縮放／毫米微調／吸附、安全區原子歷史與發布Gate、版本差異／回退新草稿。
- 字串語意：phonenumbers9.0.16＋有界內容判讀；Tesseract5.5 eng/chi_tra僅OCR；另有可授權本機Character Naive Bayes訓練／留出／版本／獨立啟用。未替使用者真實資料訓練啟用；沒有GPT/Claude API。詳見SEMANTIC_MODEL_DESIGN.md、SEMANTIC_FIELD_CONTRACT.json；工程依據TWENTY_ENGINEERING_BASIS.json。
- 下一步：UI003近似檔案／作品重複／模板結構預檢仍UNKNOWN，需實作；再逐條對照20題完整原條款與具名測試／畫面。不能從目前553PASS直接結案。Windows／原生Illustrator全面／私人樣本／印刷／獨立覆核未驗證。
- 證據：24件文字metadata保存GitHub；86件新PNG/JPG/PDF依FULL70_PUBLICATION.json精確來源／檔名／bytes／hash留本機.checkpoints/formal-media/RUN-TWENTY-INTERIM-001，不重試媒體上傳；未宣稱全附件公開Gate。
- 環境：.venv可用；Qt離屏用QT_QPA_PLATFORM=offscreen、XDG_CACHE_HOME=/workspace/.cache；OCR預設local-data/tessdata。Git讀取／推送成功；runtime network_state曾回報unknown，不冒稱政策ready。雲端設定稿已存但未宣稱已發布。
- 保存每可恢復階段及每10分鐘checkpoint→push→fresh fetch逐檔讀回，收據下一提交保存。無多代理、不建EXE、不merge main、提交含[skip ci]；真資料不上傳、保留ignored與local-only。UI048最後，REV03／UI056D按既定延後。詳細歷史只按需讀WORK_LOG／HANDOFF。
