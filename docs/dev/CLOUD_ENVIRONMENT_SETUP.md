# 雲端環境與跨對話接續

設定草稿已保存且由工具讀回確認，revision2；精確收據見CLOUD_CONFIG_DRAFT_RECEIPT.json。掛載路徑template-Ai、來源c1fe2ca、安裝及啟動接手指令均吻合。草稿仍需在環境設定儲存並發佈才啟用，尚未宣稱全新任務還原已驗證。

目前實際checkout為`/workspace/template-Ai`、`dev/v0.1-first-version`。開發來源、依賴鎖定、測試及checkpoints已逐段保存GitHub；main為較早文件基準，不應當成目前開發狀態。

可重建指令：`bash tools/cloud_setup.sh`。已在本環境真實執行，使用固定Python依賴、Inkscape、Qt、SQLite及本機Tesseract／官方固定繁中英文模型。pypdf5.9.0只校正PDF毫米頁面盒，不重繪內容。保留現有HTTPS proxy、TLS驗證與受限網域政策；沒有新增token或使用付費推論API。GitHub保存提交帶`[skip ci]`，未啟動Actions或EXE。

新對話開始：

1. 先確認實際Git根目錄、完整HEAD與`git status --short`，保留未提交／ignored檔及local-only提交。
2. 讀AGENTS、STATE、ACTIVE_DEVELOPMENT_HANDOFF、最新HANDOFF段、WORK_LOG及STATE所指契約；從GitHub工作分支的精確版本接續。倉庫是持久上下文來源，不需要讀取失聯的`chatgpt.com/local`對話。
3. 如環境掛載的是較早快照，先正常fetch開發分支。只有工作樹乾淨、無local-only分歧，且當前HEAD為遠端祖先時才fast-forward；不得reset、force checkout或覆蓋未提交資料。已存在改動先盤點並接續，不例行詢問是否繼續。
4. 執行治理check；依STATE.next_tasks做下一項已授權工作。來源／模型／資料版本不合或測試失敗先修；具體外部條件只阻塞相依驗證。
5. 每10分鐘及可恢復階段prepare→commit/push→fresh fetch→commit/tree/blob讀回；下一個提交保存收據。不合併main，不建EXE，不啟動多代理。

大型檔案只在工作區按頁／區域處理，對話讀取選定片段、精確hash與摘要；不把整個倉庫、完整歷史或base64附件回填到聊天。聊天訊息解碼大小上限與GitHub單檔限制是不同限制。上下文遺失時以checkpoint及測試重建狀態，不能假稱恢復了不可取得的完整對話。

環境設定工具只保存草稿，不會立即套用或發佈。首次更新環境設定後，需於環境設定儲存並發佈，才成為後續任務使用的配置；在此之前不能宣稱全新任務的自動還原已實測成功。一般對話切換亦不會讓未啟動的agent全天候背景開發。

UI051依賴更新：requirements與lock固定psutil7.2.2；需以`.venv/bin/python`驗證，不能只看global Python。此次精確安裝進專案venv，8個資源核心測試PASS；`cloud_setup.sh`沿用lock同步並新增psutil import smoke。完整新環境重建未因這個增量自動宣稱已重新驗證。
