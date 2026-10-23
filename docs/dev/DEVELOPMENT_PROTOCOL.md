# 零例行對話、checkpoint 與持久化流程

使用者明確指定的四條核心規則見[CONTEXT_AND_PERSISTENCE_RULES.md](CONTEXT_AND_PERSISTENCE_RULES.md)。按需搜尋與分段讀取、里程碑更新精簡交接、換對話只帶倉庫版本與接手資料、大型媒體以檔案工具按頁／區域取得資訊；一般工具輸出≤1600 tokens。新對話先執行`python tools/resume_status.py`。詳細決策與完整歷史分檔保存，不能靠整串聊天維持工作狀態。

較新使用者指令優先：開發先做本框架，再依要求清單完成核心功能；不以 EXE 為目標。產品內正常操作確認不是開發對話；未知產品決策仍記待決，不自行增加要求。

## 每次開工

讀 AGENTS → STATE → HANDOFF → REQUIREMENTS／FEATURES → 最新 WORK_LOG 與 checkpoint 收據。核對工作分支及 PR，不把 main 的歷史純文件狀態當目前代碼。執行 `python tools/dev_governance.py check`。例行是否繼續、是否保存、已決選型不重問；真正缺資料的依賴工作標 BLOCKED 並記原因／恢復條件，繼續其他已核准工作。

## Checkpoint

修改前、每個可恢復工作包、每 10 分鐘與可能中斷前 prepare。它保存原始碼／治理／公開合成證據的逐檔 SHA-256、Git blob SHA、下一步及本機 ZIP；排除本機資料庫、字型、原稿與密鑰。識別碼唯一，既有記錄不可覆寫。

以 Git 或 GitHub 連接器在工作分支保存快照程式、checkpoint 記錄、工作紀錄與狀態。取得該 commit 與 recursive tree 的原始 API JSON，執行 acknowledge：逐檔核對快照、checkpoint 本身與遠端 commit/tree。生成 REMOTE_VERIFIED 收據，下一次小提交把收據與 STATE 一起保存並讀回。收據指向先前已確認的快照 commit，避免把自身 commit SHA 塞進自己內容的循環。

本機快照可用 `restore-copy` 到**不存在的新目錄**；不覆蓋現在工作區。雲端工作區消失時從已確認遠端 commit 重新取得原碼，閱讀收據與下一步續行。若網路失敗，停在 PREPARED／PENDING_REMOTE 並保留本機 ZIP，不能宣稱已持久化或繼續累積多個未保存工作包。任何機制都不能保證最後尚未保存的操作絕不丟失；這個流程限制窗口並保留可核對恢復點。

## 證據與功能狀態

每輪修改前保存要求登錄基準，結束以 dev_progress 產生不可變進度快照與差異；dev_governance render 同時生成 CURRENT_PROGRESS.json／PROGRESS.md。分開父需求、CORE 功能及 GOV，依實作／驗證狀態分桶，新增／刪除／範圍修訂與完成差異均回報並持久化。每次最終回應告訴使用者已實作與尚待完成的明確數字，不以部分題或治理數冒充完整軟體功能。

REQUIREMENTS.json 是狀態來源；FEATURES.md 是自動生成的人類視圖。75 筆原需求／修訂完整保留，不將大量條件的 UI 主題誤算成單一已完成能力。CORE 子功能的 completed 只表示其明列的本地／合成驗收範圍；父 UI 仍保留 PARTIAL。未來、待決、最後權限與印刷需求帶明確 defer 條件，不能從清單消失。

`run_evidence.py` 在實際測試上收集個別結果、JUnit、環境、命令、測試 commit/tree 與逐檔來源 hash；另產生真實 GUI／數位檔附件。run ID 唯一，不覆寫。測試開始與結束來源不一致時無法完成驗收。跳過、失敗、預期失敗均不能滿足「必須 PASS」。GUI 截圖只補充實际畫面，不能證明語意正確或所有 AI 檔一致。

小型匿名附件和 JSON/XML/日誌永久保存 GitHub，不能只放有期限的 Actions artifact 或工作區路徑。大檔／真實資料只放經授權版本儲存位置與 hash；未取得可讀版本儲存時標 EVIDENCE_MISSING，不拿 hash 冒充可下載證據。不同執行器／真實樣本／獨立覆核是獨立狀態，本輪 SELF_VERIFIED 不能改成 INDEPENDENTLY_REVIEWED。

## GitHub 與優先順序

使用分支／PR，保存失敗與反覆嘗試次數；不得自動 merge。EXE 流程只手動 dispatch，沒有新交付指令不使用。功能與治理驗證可在本地或 CI 執行；CI 可用性不是本地功能完成的證據。框架 check 失败先修復治理，框架 READY checkpoint 已確認後再開產品工作包。詳細參考方案見 EVIDENCE_DESIGN.md。

## 本輪使用者核准的證明附件例外

2026-10-14使用者明確要求略過上傳證明附件並優先開發；精確9件見EVIDENCE_PUBLICATION_EXCEPTIONS.json與決策2026-10-14-EVIDENCE-UPLOAD-PRIORITY。只有這9件從新的可保存checkpoint view排除，全部code/tests/claims/結果與其餘公開附件仍核對；不覆寫舊full manifest，不以移除失敗測試或改程式標準結案。原full ZIP與本機附件保留。收據只對實際列入manifest的保存範圍REMOTE_VERIFIED，舊全附件require-evidence Gate仍未滿足並明示。新附件不自動套用此例外，也不把實際程式／測試缺漏當證明文件略過。

乾淨checkout缺少核准9件證明附件時，按 EVIDENCE_PUBLICATION_SCOPE_CHECK.md 逐項核對source／tests／claims及現存附件；僅容許精確例外，其他缺漏不略過。保留舊strict Gate未滿足，不重做證據上傳。
